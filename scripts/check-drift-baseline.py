#!/usr/bin/env python3
"""Compare a drift report against the accepted-drift baseline.

WHY THIS EXISTS
    `sync-from-upstream.py` compares each pinned golden against current upstream
    master, so its resting state is NOT empty: upstream moves, and every move
    shows up here until someone re-reads the golden at a newer commit. The
    scheduled workflow files a tracking issue and enforces the exit code, which
    means a permanently non-empty finding set is a permanently red job and a
    permanently open issue -- the state that teaches people to stop reading it.

    This turns the scan into a control. Findings listed in the baseline are
    EXPECTED and do not fail; anything else does. A baseline entry that produces
    no finding also fails, so the file cannot silently accumulate permissions for
    drift that has since been resolved.

    Same shape as `.github/accepted-warnings.txt` and the gate over it
    (`scripts/tests/test_accepted_warnings.py`), which does this for
    round-trip-ci and lint-port-rules.

ONE DELIBERATE DIFFERENCE FROM THAT GATE
    It normalizes content hashes to `<hash>` so a fixture refresh does not
    invalidate every key. Here the opposite is required: the observed upstream
    value IS what identifies the accepted divergence. If `test-x-bid-request.json`
    changes again, that is a NEW divergence which nobody has looked at, and it
    must not match the entry accepted for the previous one. So keys carry the
    observed upstream value verbatim.

KEY SHAPE
    sync-upstream | <type> | <bidder>/<language> | <observation>

    `<observation>` is per-type, from the detail the detector already emits --
    the upstream value for a field drift, `<path> -> <upstream sha>` for a
    fixture, the successor name for a rename. A type this script does not know
    how to observe is reported as unobservable rather than defaulted, because a
    key that silently drops its observation would accept any future change of
    that type.

USAGE
    python3 scripts/check-drift-baseline.py                       # after a scan
    python3 scripts/check-drift-baseline.py --report path.json
    python3 scripts/check-drift-baseline.py --write-baseline      # regenerate

Exit: 0 every finding is accepted and every entry was used; 1 undeclared drift or
a stale entry; 2 setup error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _rel(path: Path) -> str:
    """Repo-relative when it can be, absolute otherwise. `relative_to` raises on
    a path outside the repo, and a diagnostic that raises replaces the error it
    was describing."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)
DEFAULT_REPORT = REPO_ROOT / "scripts" / "output" / "drift-report.json"
BASELINE_PATH = REPO_ROOT / ".github" / "accepted-drift.txt"
SOURCE = "sync-upstream"

# What "the same divergence" means, per finding type. A type absent here has no
# defined observation and is reported rather than accepted.
OBSERVERS: dict[str, tuple[str, ...]] = {
    "endpoint_drift":                  ("upstream",),
    "endpoint_compression_drift":      ("upstream",),
    "gvl_vendor_id_drift":             ("upstream",),
    "ortb_version_drift":              ("upstream",),
    "modifying_vast_xml_allowed_drift": ("upstream",),
    "default_enabled_drift":           ("upstream",),
    "alias_of_drift":                  ("upstream",),
    "fixture_content_drift":           ("path", "upstream_sha"),
    "bidder_params_sha_drift":         ("path", "upstream_sha"),
    "bidder_params_renamed_upstream":  ("path", "candidate"),
    "artifact_renamed_upstream":       ("path", "candidate"),
    "bidder_renamed_upstream":         ("successor",),
    # `successor` is None here, so the vanished-path count is what pins this
    # particular removal. Accepting one should be rare: a golden for an adapter
    # that no longer exists upstream wants retiring, not a baseline entry.
    "bidder_removed_upstream":         ("vanished_count",),
    "new_yaml_field":                  ("new_keys",),
}


def observe(finding: dict) -> str | None:
    """The observation string for a finding, or None when its type has none."""
    keys = OBSERVERS.get(str(finding.get("type")))
    if keys is None:
        return None
    detail = finding.get("detail") or {}
    parts = []
    for k in keys:
        v = detail.get(k)
        parts.append(",".join(map(str, v)) if isinstance(v, list) else str(v))
    return " -> ".join(parts)


def make_key(finding: dict) -> str | None:
    obs = observe(finding)
    if obs is None:
        return None
    return (f"{SOURCE} | {finding.get('type')} | "
            f"{finding.get('bidder')}/{finding.get('language')} | {obs}")


def load_report(path: Path) -> list[dict]:
    if not path.is_file():
        sys.stderr.write(f"ERROR: no drift report at {path}. Run sync-from-upstream.py first.\n")
        raise SystemExit(2)
    payload = json.loads(path.read_text(encoding="utf-8"))
    findings = payload.get("findings")
    if not isinstance(findings, list):
        sys.stderr.write(f"ERROR: {path} has no findings list\n")
        raise SystemExit(2)
    if not payload.get("scan_set") and not findings:
        # A zero-input scan produces zero findings, which would read as a clean
        # baseline match. It is an instrument failure.
        sys.stderr.write("ERROR: the report records no scan set -- a zero-input scan is not a clean result\n")
        raise SystemExit(2)
    return findings


def read_baseline() -> list[str]:
    if not BASELINE_PATH.is_file():
        return []
    return [line.strip()
            for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


BASELINE_HEADER = """\
# Accepted upstream drift — scripts/sync-from-upstream.py
#
# The scan compares each pinned golden against current upstream master, so its
# resting state is not empty: every upstream change shows up here until the
# golden is re-read at a newer commit. This file records which of those are
# known, so the scheduled job can be green when nothing NEW has moved.
#
# `scripts/check-drift-baseline.py` fails when the live finding set differs from
# this list in either direction:
#
#   - a finding that is not listed — upstream moved again, and nobody has looked;
#   - a listed entry that produces no finding — the drift was resolved, and the
#     entry must go so the list keeps meaning something.
#
# Keys carry the OBSERVED UPSTREAM VALUE verbatim. That is the difference from
# .github/accepted-warnings.txt, which normalizes hashes so a fixture refresh
# does not invalidate every key. Here a second change to the same file is a new
# divergence nobody has reviewed, and it must not inherit the acceptance granted
# to the first.
#
# A golden is NOT wrong because it appears here. Each is a point-in-time read and
# is true at its own `provenance.source.resolved_commit`; resolving an entry means
# re-reading that golden at a newer commit, per
# prebid-server-go/read/test-fixtures/README.md, not editing the drifted field.
#
# Regenerate after deciding a change is expected:
#
#     python3 scripts/sync-from-upstream.py --source-mode=local \\
#         --go-checkout=... --java-checkout=... --scan-tier=full
#     python3 scripts/check-drift-baseline.py --write-baseline
#
# Then review the diff and write the cause above each new entry. That diff is the
# record of what was accepted.
"""


def write_baseline(findings: list[dict]) -> int:
    keys, unobservable = [], []
    for f in findings:
        k = make_key(f)
        (keys if k else unobservable).append(k or f"{f.get('type')} ({f.get('bidder')})")
    if unobservable:
        sys.stderr.write("ERROR: no observation defined for: " + ", ".join(sorted(set(unobservable)))
                         + "\nAdd the type to OBSERVERS before baselining it.\n")
        return 2
    existing = BASELINE_PATH.read_text(encoding="utf-8") if BASELINE_PATH.is_file() else ""
    comments = {}
    current = []
    for line in existing.splitlines():
        if line.lstrip().startswith("#") and not line.startswith("# "):
            continue
        if line.lstrip().startswith("#"):
            current.append(line)
        elif line.strip():
            comments[line.strip()] = current
            current = []
        else:
            current = []
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = []
    for k in sorted(set(keys)):
        body.extend(comments.get(k, []))
        body.append(k)
    BASELINE_PATH.write_text(BASELINE_HEADER + f"#\n# Entries: {len(set(keys))}\n\n"
                             + "\n".join(body) + "\n", encoding="utf-8")
    print(f"wrote {len(set(keys))} accepted-drift entries to {_rel(BASELINE_PATH)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--write-baseline", action="store_true")
    args = ap.parse_args(argv)

    findings = load_report(args.report)
    if args.write_baseline:
        return write_baseline(findings)

    baseline = read_baseline()
    if not baseline:
        sys.stderr.write(f"ERROR: {_rel(BASELINE_PATH)} is missing or empty. "
                         f"Regenerate with --write-baseline.\n")
        return 2

    live: dict[str, dict] = {}
    unobservable = []
    for f in findings:
        k = make_key(f)
        if k is None:
            unobservable.append(f)
        else:
            live[k] = f

    undeclared = sorted(set(live) - set(baseline))
    stale = sorted(set(baseline) - set(live))

    for f in unobservable:
        print(f"[UNOBSERVABLE] {f.get('type')} on {f.get('bidder')}/{f.get('language')}: "
              f"no observation defined, so it cannot be accepted. Add the type to OBSERVERS.")
    for k in undeclared:
        f = live[k]
        print(f"[UNDECLARED {str(f.get('severity')).upper()}] {k}")
    for k in stale:
        print(f"[STALE ENTRY] {k}")

    print(f"\ndrift baseline: {len(findings)} findings, {len(baseline)} accepted   "
          f"undeclared={len(undeclared)} stale={len(stale)} unobservable={len(unobservable)}")
    if undeclared:
        print("Upstream moved somewhere nobody has looked. Either re-read the golden at a newer "
              "commit, or accept the change and record its cause in the baseline.")
    if stale:
        print("An accepted entry no longer fires. Remove it — an accepted list that outlives its "
              "findings stops meaning anything.")
    return 1 if (undeclared or stale or unobservable) else 0


if __name__ == "__main__":
    sys.exit(main())
