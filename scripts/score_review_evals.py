#!/usr/bin/env python3
"""Score a review-skill run against the maintainer-finding corpus in review-evals/.

This is the only gate in this repository that can detect a CALIBRATION error --
a check that is present, runs, and reaches the wrong verdict. Every other gate
detects absence or staleness.

Hermetic: this script never touches the network. Fixtures are snapshots captured
by `review-evals/capture_fixture.py`; the operator supplies an actual-findings
file produced by running the review skills against that snapshot.

Inputs
------
Fixture (`review-evals/fixtures/<id>/`):
    meta.yaml      provenance: repo, PR, review SHA, capture date, outcome
    files.json     the changed-file list with patches, at the review SHA
    expected.yaml  maintainer findings (`expected`) + named non-findings
                   (`forbidden`) -- verdicts a correct review must NOT reach

Actual (`--actual DIR` or `--actual FILE`):
    fixture:        <fixture id>
    files_scanned:  int  REQUIRED -- the scan set. 0 is an ERROR, never a pass.
    findings:       list REQUIRED -- may be empty, but the key must be present

Metrics
-------
    recall              matched expected findings / total expected
    forbidden_hits      actual findings matching a named non-finding (hard FP)
    unexpected          actual findings matching neither (soft FP)
    severity_agreement  exact severity matches / matched, plus under/over split

Exit codes
----------
    0  PASS   every committed floor met
    1  FAIL   recall below floor, or false positives above ceiling
    2  ERROR  the instrument did not run: missing/unparseable/empty scan set,
              unknown fixture, or a fixture whose expected anchors do not occur
              in its own captured patches
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

try:
    import yaml
except ImportError:  # pragma: no cover - environment problem, not a verdict
    sys.stderr.write("score_review_evals: PyYAML is required (pip install -r requirements.txt)\n")
    sys.exit(2)

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "review-evals" / "fixtures"
BASELINE_PATH = REPO_ROOT / "review-evals" / "baseline.yaml"

EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2

SEVERITIES = ["INFO", "WARN", "FAIL"]
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITIES)}

# Sentinel anchor for a finding about a file's existence rather than a line in
# it (a non-canonical artifact, a redundant fixture, a bidder name). File-level
# entries match on (path, family) because there is no line to quote.
FILE_ANCHOR = "<file>"

# Shortest anchor overlap accepted, in normalized characters. Below this a
# containment test degenerates into matching punctuation.
MIN_ANCHOR_CHARS = 8


# --------------------------------------------------------------------------
# normalization -- the single definition; capture_fixture.py imports these
# --------------------------------------------------------------------------

def normalize_anchor(text: str) -> str:
    """Collapse whitespace runs. Case- and punctuation-preserving: code is
    case-sensitive, and an anchor is a quoted line, not prose."""
    return " ".join((text or "").split())


def normalize_patch(patch: str) -> str:
    """Render a unified diff as a whitespace-collapsed line of source text.

    Strips the leading diff marker from each body line, drops `@@` hunk headers
    and `\\ No newline` markers. Marker-stripping is applied ONLY here, never to
    a hand-written anchor: a YAML list item (`- banner`) would otherwise lose
    its dash and stop matching the patch line `+      - banner`.
    """
    out = []
    for line in (patch or "").splitlines():
        if line.startswith("@@") or line.startswith("\\ No newline"):
            continue
        if line[:1] in ("+", "-", " "):
            line = line[1:]
        out.append(line)
    return " ".join(" ".join(out).split())


def anchors_overlap(a: str, b: str) -> bool:
    """Bidirectional containment, so a reviewer quoting a longer span still
    matches a short symbol anchor and vice versa. Guarded by MIN_ANCHOR_CHARS
    so a two-character anchor cannot match everything.

    Line-number independent by construction: no line number is consulted.
    """
    na, nb = normalize_anchor(a), normalize_anchor(b)
    if not na or not nb:
        return False
    shorter = na if len(na) <= len(nb) else nb
    if len(shorter) < MIN_ANCHOR_CHARS:
        return na == nb
    return na in nb or nb in na


def normalize_path(path: str | None) -> str:
    """None-tolerant on purpose: a fixture or a recorded run may omit `path`,
    and an absent path must compare unequal rather than raise."""
    p = (path or "").strip().replace("\\", "/")
    for prefix in ("./", "a/", "b/"):
        if p.startswith(prefix):
            p = p[len(prefix):]
    return p


# --------------------------------------------------------------------------
# errors
# --------------------------------------------------------------------------

class HarnessError(Exception):
    """The instrument did not run. Distinct from a failing verdict."""


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------

def load_fixture(fixture_id: str, fixtures_dir: pathlib.Path) -> dict:
    d = fixtures_dir / fixture_id
    if not d.is_dir():
        raise HarnessError(f"unknown fixture {fixture_id!r} (looked in {fixtures_dir})")
    try:
        meta = yaml.safe_load((d / "meta.yaml").read_text())
        files = json.loads((d / "files.json").read_text())
        expected = yaml.safe_load((d / "expected.yaml").read_text()) or {}
    except FileNotFoundError as exc:
        raise HarnessError(f"fixture {fixture_id} incomplete: {exc}") from exc
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise HarnessError(f"fixture {fixture_id} unparseable: {exc}") from exc

    return {
        "id": fixture_id,
        "meta": meta,
        "files": files,
        "expected": expected.get("expected") or [],
        "forbidden": expected.get("forbidden") or [],
        "patches": {normalize_path(f["filename"]): normalize_patch(f.get("patch"))
                    for f in files},
    }


def validate_fixture(fx: dict) -> list[str]:
    """A fixture whose expected anchor does not occur in its own captured patches
    is broken -- no reviewer could reach that finding from this snapshot."""
    problems = []
    for key in ("expected", "forbidden"):
        for entry in fx[key]:
            for required in ("id", "path", "anchor", "family", "source"):
                if not entry.get(required):
                    problems.append(f"{fx['id']}/{key}/{entry.get('id', '?')}: missing {required}")
            path = normalize_path(entry.get("path", ""))
            if path not in fx["patches"]:
                problems.append(
                    f"{fx['id']}/{key}/{entry.get('id', '?')}: path {path!r} not in files.json")
                continue
            anchor = entry.get("anchor", "")
            if anchor == FILE_ANCHOR:
                continue
            if normalize_anchor(anchor) not in fx["patches"][path]:
                problems.append(
                    f"{fx['id']}/{key}/{entry.get('id', '?')}: anchor not present in the "
                    f"captured patch for {path}: {anchor!r}")
    if key_dupes := _dupes([e["id"] for e in fx["expected"] + fx["forbidden"] if e.get("id")]):
        problems.append(f"{fx['id']}: duplicate finding ids {sorted(key_dupes)}")
    return problems


def _dupes(items: list[str]) -> set[str]:
    seen, dupes = set(), set()
    for i in items:
        (dupes if i in seen else seen).add(i)
    return dupes


def load_actual(path: pathlib.Path, fixture_id: str) -> dict:
    """Load one actual-findings file.

    An empty scan set is an ERROR, not a clean pass: `findings: []` only means
    "clean" when the run declares it examined a non-zero number of files.
    """
    if not path.exists():
        raise HarnessError(
            f"{fixture_id}: no actual-findings file at {path}. A missing scan is not a "
            f"clean verdict -- run the review skills against this fixture first.")
    raw = path.read_text()
    if not raw.strip():
        raise HarnessError(
            f"{fixture_id}: actual-findings file {path} is empty. An empty scan set is a "
            f"finding about the harness, not a verdict about the PR.")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise HarnessError(f"{fixture_id}: actual-findings file {path} unparseable: {exc}") from exc
    if not isinstance(data, dict):
        raise HarnessError(
            f"{fixture_id}: actual-findings file {path} must be a mapping with "
            f"`files_scanned` and `findings` keys, got {type(data).__name__}")
    if "findings" not in data:
        raise HarnessError(
            f"{fixture_id}: actual-findings file {path} has no `findings` key. Absent is not "
            f"the same as empty -- write `findings: []` to assert the run found nothing.")
    if "files_scanned" not in data:
        raise HarnessError(
            f"{fixture_id}: actual-findings file {path} has no `files_scanned` key. A detector's "
            f"scan set is part of its claim.")
    scanned = data["files_scanned"]
    if not isinstance(scanned, int) or scanned <= 0:
        raise HarnessError(
            f"{fixture_id}: files_scanned={scanned!r}. Zero inputs is an error, not a clean "
            f"verdict -- the review skills examined nothing.")
    findings = data["findings"] or []
    if not isinstance(findings, list):
        raise HarnessError(f"{fixture_id}: `findings` must be a list, got {type(findings).__name__}")
    for i, f in enumerate(findings):
        if not isinstance(f, dict) or not f.get("path"):
            raise HarnessError(f"{fixture_id}: findings[{i}] needs at least a `path`")
    return {"fixture": fixture_id, "files_scanned": scanned, "findings": findings,
            "source_path": str(path)}


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------

def _candidate_score(entry: dict, actual: dict) -> int | None:
    """How well `actual` satisfies `entry`; None when it does not.

    Higher is a more specific match, so the greedy assignment below prefers a
    line-anchored match over a symbol-only one.
    """
    if normalize_path(entry.get("path")) != normalize_path(actual.get("path")):
        return None

    if entry.get("anchor") == FILE_ANCHOR:
        # No line to quote: require the family to agree so that any finding
        # anywhere in the file cannot satisfy a file-level entry.
        a_fam = (actual.get("family") or "").strip().lower()
        e_fam = (entry.get("family") or "").strip().lower()
        if a_fam and e_fam and a_fam == e_fam:
            return 10
        return None

    a_anchor = actual.get("anchor") or actual.get("evidence") or ""
    if a_anchor and anchors_overlap(entry["anchor"], a_anchor):
        return 30 + min(len(normalize_anchor(a_anchor)), 200)

    e_sym, a_sym = (entry.get("symbol") or "").strip(), (actual.get("symbol") or "").strip()
    if e_sym and a_sym and e_sym == a_sym:
        return 20
    # A skill may quote the symbol inside its anchor rather than in a field.
    if e_sym and a_anchor and e_sym in normalize_anchor(a_anchor):
        return 15
    return None


def assign(entries: list[dict], actuals: list[dict]) -> tuple[dict[str, int], set[int]]:
    """One-to-one greedy assignment: each actual finding satisfies at most one
    entry, and each entry is satisfied by at most one actual finding.

    Two expected findings anchored on the same line therefore need two actual
    findings; they do not collapse into one.
    """
    pairs = []
    for ei, entry in enumerate(entries):
        for ai, actual in enumerate(actuals):
            score = _candidate_score(entry, actual)
            if score is not None:
                pairs.append((score, ei, ai))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))

    matched: dict[str, int] = {}
    used_entries: set[int] = set()
    used_actuals: set[int] = set()
    for _, ei, ai in pairs:
        if ei in used_entries or ai in used_actuals:
            continue
        used_entries.add(ei)
        used_actuals.add(ai)
        matched[entries[ei]["id"]] = ai
    return matched, used_actuals


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------

def score_fixture(fx: dict, actual: dict) -> dict:
    exp_matched, exp_used = assign(fx["expected"], actual["findings"])
    remaining = [f for i, f in enumerate(actual["findings"]) if i not in exp_used]
    forb_matched, forb_used = assign(fx["forbidden"], remaining)
    unexpected = [f for i, f in enumerate(remaining) if i not in forb_used]

    total_expected = len(fx["expected"])
    recall = (len(exp_matched) / total_expected) if total_expected else None

    sev_exact = sev_under = sev_over = 0
    for entry in fx["expected"]:
        ai = exp_matched.get(entry["id"])
        if ai is None:
            continue
        want = (entry.get("severity") or "").strip().upper()
        got = (actual["findings"][ai].get("severity") or "").strip().upper()
        if want not in SEVERITY_RANK or got not in SEVERITY_RANK:
            continue
        if want == got:
            sev_exact += 1
        elif SEVERITY_RANK[got] < SEVERITY_RANK[want]:
            sev_under += 1
        else:
            sev_over += 1
    sev_judged = sev_exact + sev_under + sev_over
    sev_agreement = (sev_exact / sev_judged) if sev_judged else None

    families: dict[str, dict] = {}
    for entry in fx["expected"]:
        fam = entry.get("family", "unclassified")
        slot = families.setdefault(fam, {"expected": 0, "matched": 0, "missed": []})
        slot["expected"] += 1
        if entry["id"] in exp_matched:
            slot["matched"] += 1
        else:
            slot["missed"].append(entry["id"])

    file_count = len(fx["files"])
    scan_note = None
    if actual["files_scanned"] > file_count:
        raise HarnessError(
            f"{fx['id']}: files_scanned={actual['files_scanned']} exceeds the fixture's "
            f"{file_count} changed files. The run did not scan this snapshot.")
    if actual["files_scanned"] < file_count:
        scan_note = (f"partial scan set: {actual['files_scanned']}/{file_count} changed files "
                     f"declared; findings in unscanned files cannot be reached")

    return {
        "fixture": fx["id"],
        "repo": fx["meta"].get("repo"),
        "pr": fx["meta"].get("pr_number"),
        "review_sha": fx["meta"].get("review_sha"),
        "outcome": fx["meta"].get("outcome"),
        "language": fx["meta"].get("language"),
        "files_in_fixture": file_count,
        "files_scanned": actual["files_scanned"],
        "scan_note": scan_note,
        "actual_findings": len(actual["findings"]),
        "expected_total": total_expected,
        "expected_matched": len(exp_matched),
        "expected_missed": [e["id"] for e in fx["expected"] if e["id"] not in exp_matched],
        "recall": recall,
        "forbidden_total": len(fx["forbidden"]),
        "forbidden_hits": sorted(forb_matched),
        "unexpected": len(unexpected),
        "unexpected_detail": [
            {"path": f.get("path"), "anchor": (f.get("anchor") or "")[:120],
             "severity": f.get("severity"), "family": f.get("family")}
            for f in unexpected],
        "severity_exact": sev_exact,
        "severity_under_rated": sev_under,
        "severity_over_rated": sev_over,
        "severity_agreement": sev_agreement,
        "families": families,
    }


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------

def load_baseline(path: pathlib.Path) -> dict:
    if not path.exists():
        raise HarnessError(f"no baseline at {path}")
    data = yaml.safe_load(path.read_text()) or {}
    if "global" not in data:
        raise HarnessError(f"{path}: missing `global` floors block")
    return data


def floors_for(baseline: dict, fixture_id: str) -> dict:
    merged = dict(baseline.get("global") or {})
    merged.update((baseline.get("fixtures") or {}).get(fixture_id) or {})
    return merged


def apply_floors(result: dict, floors: dict) -> list[str]:
    breaches = []
    fid = result["fixture"]

    min_recall = floors.get("min_recall")
    if min_recall is not None and result["recall"] is not None:
        if result["recall"] + 1e-9 < float(min_recall):
            breaches.append(
                f"{fid}: recall {result['recall']:.3f} < floor {float(min_recall):.3f} "
                f"(missed: {', '.join(result['expected_missed']) or 'none'})")

    max_forbidden = floors.get("max_forbidden_hits")
    if max_forbidden is not None and len(result["forbidden_hits"]) > int(max_forbidden):
        breaches.append(
            f"{fid}: {len(result['forbidden_hits'])} forbidden finding(s) "
            f"> ceiling {max_forbidden}: {', '.join(result['forbidden_hits'])}")

    max_unexpected = floors.get("max_unexpected")
    if max_unexpected is not None and result["unexpected"] > int(max_unexpected):
        breaches.append(
            f"{fid}: {result['unexpected']} unexpected finding(s) > ceiling {max_unexpected}")

    min_sev = floors.get("min_severity_agreement")
    if min_sev is not None and result["severity_agreement"] is not None:
        if result["severity_agreement"] + 1e-9 < float(min_sev):
            breaches.append(
                f"{fid}: severity agreement {result['severity_agreement']:.3f} < floor "
                f"{float(min_sev):.3f} ({result['severity_under_rated']} under-rated)")
    return breaches


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _pct(value) -> str:
    return "  n/a" if value is None else f"{value * 100:5.1f}%"


def render_table(results: list[dict], baseline: dict, breaches: list[str]) -> str:
    lines = []
    lines.append("review-eval scores")
    lines.append("=" * 96)
    header = (f"{'fixture':<26} {'out':<9} {'exp':>4} {'hit':>4} {'recall':>7} "
              f"{'forb':>5} {'unexp':>6} {'sev':>7} {'scan':>9}")
    lines.append(header)
    lines.append("-" * 96)
    for r in results:
        lines.append(
            f"{r['fixture']:<26} {(r['outcome'] or '?'):<9} {r['expected_total']:>4} "
            f"{r['expected_matched']:>4} {_pct(r['recall']):>7} "
            f"{len(r['forbidden_hits']):>5} {r['unexpected']:>6} "
            f"{_pct(r['severity_agreement']):>7} "
            f"{r['files_scanned']}/{r['files_in_fixture']:<7}")
    lines.append("-" * 96)

    tot_exp = sum(r["expected_total"] for r in results)
    tot_hit = sum(r["expected_matched"] for r in results)
    tot_forb = sum(len(r["forbidden_hits"]) for r in results)
    tot_unexp = sum(r["unexpected"] for r in results)
    corpus_recall = (tot_hit / tot_exp) if tot_exp else None
    lines.append(f"{'CORPUS':<26} {'':<9} {tot_exp:>4} {tot_hit:>4} {_pct(corpus_recall):>7} "
                 f"{tot_forb:>5} {tot_unexp:>6}")
    lines.append("")

    fam: dict[str, dict] = {}
    for r in results:
        for name, slot in r["families"].items():
            agg = fam.setdefault(name, {"expected": 0, "matched": 0, "missed": []})
            agg["expected"] += slot["expected"]
            agg["matched"] += slot["matched"]
            agg["missed"].extend(slot["missed"])
    lines.append("per check family")
    lines.append("-" * 96)
    for name in sorted(fam):
        slot = fam[name]
        rate = slot["matched"] / slot["expected"] if slot["expected"] else None
        missed = ", ".join(slot["missed"][:4]) + ("  ..." if len(slot["missed"]) > 4 else "")
        lines.append(f"  {name:<26} {slot['matched']:>3}/{slot['expected']:<3} {_pct(rate):>7}"
                     + (f"   missed: {missed}" if missed else ""))
    lines.append("")

    for r in results:
        if r["scan_note"]:
            lines.append(f"NOTE {r['fixture']}: {r['scan_note']}")
        for hit in r["forbidden_hits"]:
            entry = hit
            lines.append(f"FORBIDDEN {r['fixture']}: emitted a verdict maintainers ruled out "
                         f"-- {entry}")
        for u in r["unexpected_detail"]:
            lines.append(f"UNEXPECTED {r['fixture']}: {u['severity'] or '?'} {u['path']} "
                         f"{u['anchor']}")
    if any(r["scan_note"] or r["forbidden_hits"] or r["unexpected_detail"] for r in results):
        lines.append("")

    unmeasured = [k for k, v in (baseline.get("fixtures") or {}).items()
                  if v.get("status") == "unmeasured"]
    if baseline.get("global", {}).get("status") == "unmeasured" or unmeasured:
        lines.append("!! RECALL FLOORS ARE UNMEASURED. A green run here is not a certification;")
        lines.append("!! it only means nothing recorded has regressed. Record a floor with")
        lines.append("!! `--record-baseline` once a real skill run has been scored.")
        lines.append("")

    if breaches:
        lines.append("FAIL")
        for b in breaches:
            lines.append(f"  - {b}")
    else:
        lines.append("PASS (against the committed regression floors)")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------

def discover_fixtures(fixtures_dir: pathlib.Path) -> list[str]:
    return sorted(d.name for d in fixtures_dir.iterdir()
                  if d.is_dir() and (d / "meta.yaml").exists())


def actual_path_for(actual_root: pathlib.Path, fixture_id: str) -> pathlib.Path:
    if actual_root.is_file():
        return actual_root
    for name in (f"{fixture_id}.yaml", f"{fixture_id}.yml", f"{fixture_id}.json"):
        p = actual_root / name
        if p.exists():
            return p
    return actual_root / f"{fixture_id}.yaml"


def record_baseline(results: list[dict], baseline: dict, path: pathlib.Path,
                    margin: float) -> None:
    fixtures = baseline.setdefault("fixtures", {})
    for r in results:
        slot = fixtures.setdefault(r["fixture"], {})
        slot.pop("status", None)
        if r["recall"] is not None:
            slot["min_recall"] = round(max(0.0, r["recall"] - margin), 3)
        if r["severity_agreement"] is not None:
            slot["min_severity_agreement"] = round(max(0.0, r["severity_agreement"] - margin), 3)
        slot["max_forbidden_hits"] = 0
        slot["max_unexpected"] = max(int(slot.get("max_unexpected", 0)), r["unexpected"])
        slot["recorded_from_review_sha"] = r["review_sha"]
    baseline.setdefault("global", {}).pop("status", None)
    header = path.read_text().split("\n")
    preserved = [ln for ln in header if ln.startswith("#")]
    path.write_text("\n".join(preserved) + "\n"
                    + yaml.safe_dump(baseline, sort_keys=False, default_flow_style=False))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--actual", type=pathlib.Path,
                    help="directory of <fixture-id>.yaml actual-findings files, or one file "
                         "(with --fixture)")
    ap.add_argument("--fixture", action="append", dest="fixtures",
                    help="score only this fixture (repeatable); default: all")
    ap.add_argument("--fixtures-dir", type=pathlib.Path, default=FIXTURES_DIR)
    ap.add_argument("--baseline", type=pathlib.Path, default=BASELINE_PATH)
    ap.add_argument("--json", type=pathlib.Path, help="write the machine-readable summary here")
    ap.add_argument("--validate-only", action="store_true",
                    help="check fixture integrity (anchors resolve inside the captured "
                         "patches) and exit; needs no actual-findings file")
    ap.add_argument("--record-baseline", action="store_true",
                    help="rewrite baseline.yaml floors from this run (minus --margin)")
    ap.add_argument("--margin", type=float, default=0.05,
                    help="slack subtracted when recording a floor (default 0.05)")
    args = ap.parse_args(argv)

    try:
        fixture_ids = args.fixtures or discover_fixtures(args.fixtures_dir)
        if not fixture_ids:
            raise HarnessError(
                f"no fixtures under {args.fixtures_dir}. An empty corpus is an error, not a "
                f"clean run.")
        fixtures = [load_fixture(f, args.fixtures_dir) for f in fixture_ids]

        problems = [p for fx in fixtures for p in validate_fixture(fx)]
        if problems:
            for p in problems:
                sys.stderr.write(f"FIXTURE ERROR {p}\n")
            raise HarnessError(f"{len(problems)} broken fixture entr(ies); corpus is not scorable")

        if args.validate_only:
            n_exp = sum(len(fx["expected"]) for fx in fixtures)
            n_forb = sum(len(fx["forbidden"]) for fx in fixtures)
            print(f"fixtures OK: {len(fixtures)} fixture(s), {n_exp} expected finding(s), "
                  f"{n_forb} forbidden finding(s); every anchor resolves inside its "
                  f"captured patch")
            return EXIT_PASS

        if not args.actual:
            raise HarnessError("--actual is required unless --validate-only is given")
        if args.actual.is_file() and len(fixture_ids) > 1:
            raise HarnessError("--actual FILE needs exactly one --fixture")

        baseline = load_baseline(args.baseline)
        results = []
        for fx in fixtures:
            actual = load_actual(actual_path_for(args.actual, fx["id"]), fx["id"])
            results.append(score_fixture(fx, actual))

        breaches = []
        for r in results:
            breaches.extend(apply_floors(r, floors_for(baseline, r["fixture"])))

        tot_exp = sum(r["expected_total"] for r in results)
        tot_hit = sum(r["expected_matched"] for r in results)
        summary = {
            "corpus": {
                "fixtures": len(results),
                "expected_total": tot_exp,
                "expected_matched": tot_hit,
                "recall": (tot_hit / tot_exp) if tot_exp else None,
                "forbidden_hits": sum(len(r["forbidden_hits"]) for r in results),
                "unexpected": sum(r["unexpected"] for r in results),
                "severity_under_rated": sum(r["severity_under_rated"] for r in results),
                "severity_over_rated": sum(r["severity_over_rated"] for r in results),
            },
            "baseline_status": baseline.get("global", {}).get("status", "measured"),
            "breaches": breaches,
            "fixtures": results,
        }
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(summary, indent=2) + "\n")

        if args.record_baseline:
            record_baseline(results, baseline, args.baseline, args.margin)
            print(f"recorded floors into {args.baseline} (margin {args.margin})")

        print(render_table(results, baseline, breaches))
        return EXIT_FAIL if breaches else EXIT_PASS

    except HarnessError as exc:
        sys.stderr.write(f"HARNESS ERROR: {exc}\n")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
