#!/usr/bin/env python3
"""Is a drift finding a read error or upstream movement?

THE QUESTION THIS ANSWERS
    `sync-from-upstream.py` compares each golden against current upstream master,
    so a finding means only "the golden and master disagree." Two very different
    things produce that:

      read error       the golden was never true, not even at its own
                       `provenance.source.resolved_commit`. Fix the field; the pin
                       does not move.
      upstream drift   the golden is true at its pin and upstream moved past it.
                       The field cannot be edited -- editing it makes the spec
                       assert a value at a commit nobody read. Resolving it means
                       re-reading the golden at a newer commit, per
                       prebid-server-go/read/test-fixtures/README.md.

    Guessing wrong in either direction is expensive. Recording a read error as
    accepted upstream drift preserves a wrong value behind an explanation; treating
    drift as a read error edits a field out of agreement with its own pin.

HOW IT DECIDES
    It re-runs the detector's own comparison against each golden's pin. A finding
    that also fires there was never true; one that fires only at master is drift.
    The detector is the same instrument in both runs, so the two results differ
    only in the commit they read.

    This found three findings that were neither -- elementaltv, msft and
    optidigital reported `ortb_version_drift` at their own pins because the
    comparison read one of two documented golden locations. A finding that fires at
    the pin is a claim about the golden OR about the comparison, and the
    distinction is worth making by hand before editing anything.

USAGE
    python3 scripts/classify-drift.py --go-checkout ... --java-checkout ...

Exit: 0 classification completed; 2 setup error. It reports; it does not judge.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = REPO_ROOT / "scripts" / "output" / "drift-report.json"

_spec = importlib.util.spec_from_file_location("sfu", REPO_ROOT / "scripts" / "sync-from-upstream.py")
if _spec is None or _spec.loader is None:  # pragma: no cover
    sys.stderr.write("ERROR: cannot load sync-from-upstream.py\n")
    raise SystemExit(2)
sfu = importlib.util.module_from_spec(_spec)
sys.modules["sfu"] = sfu
_spec.loader.exec_module(sfu)


def source_at(root: Path, commit: str) -> "sfu.UpstreamSource":
    """A source that reads one commit out of a local checkout."""
    def fetch(path: str):
        proc = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"],
                              capture_output=True)
        return proc.stdout if proc.returncode == 0 else None

    def listing():
        proc = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "--name-only", commit],
                              capture_output=True, text=True)
        return set(proc.stdout.split())

    return sfu.UpstreamSource(f"{root.name}@{commit[:9]}", fetch, listing)


def classify(report_path: Path, checkouts: dict[str, Path]) -> dict[str, list[dict]]:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    findings = payload.get("findings") or []
    out: dict[str, list[dict]] = {"read_error": [], "drift": [], "unclassified": []}
    pairs = sorted({(f["bidder"], f["language"]) for f in findings})
    for bidder, language in pairs:
        root = checkouts.get(language)
        golden_path = (REPO_ROOT / f"prebid-server-{language}" / "read" / "test-fixtures"
                       / f"{bidder}.golden.spec.yaml")
        mine = [f for f in findings if (f["bidder"], f["language"]) == (bidder, language)]
        if root is None or not golden_path.is_file():
            out["unclassified"].extend(mine)
            continue
        golden = sfu._load_golden(golden_path)
        pin = ((golden.get("provenance") or {}).get("source") or {}).get("resolved_commit")
        if not pin:
            out["unclassified"].extend(mine)
            continue
        compare = sfu.compare_bidder_go if language == "go" else sfu.compare_bidder_java
        at_pin = {f.type for f in compare(bidder, golden_path, source_at(root, pin),
                                          tier=sfu.TIER_FULL)}
        for f in mine:
            out["read_error" if f["type"] in at_pin else "drift"].append(f)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    ap.add_argument("--go-checkout", type=Path)
    ap.add_argument("--java-checkout", type=Path)
    args = ap.parse_args(argv)

    if not args.report.is_file():
        sys.stderr.write(f"ERROR: no drift report at {args.report}. Run sync-from-upstream.py first.\n")
        return 2
    checkouts = {}
    for lang, path in (("go", args.go_checkout), ("java", args.java_checkout)):
        if path is not None:
            if not (path / ".git").exists():
                sys.stderr.write(f"ERROR: not a git checkout: {path}\n")
                return 2
            checkouts[lang] = path
    if not checkouts:
        sys.stderr.write("ERROR: pass --go-checkout and/or --java-checkout. Classification needs "
                         "each golden's own pin, which needs history.\n")
        return 2

    buckets = classify(args.report, checkouts)
    labels = {
        "read_error": ("READ ERROR — fires at the golden's own pin too, so the golden was never "
                       "true there. Fix the field, or the comparison if the golden records the "
                       "value somewhere the comparison does not look. The pin does not move."),
        "drift": ("UPSTREAM DRIFT — fires only against master, so the golden is true at its pin. "
                  "Do not edit the field; either re-read the golden at a newer commit or record "
                  "the drift in .github/accepted-drift.txt with its cause."),
        "unclassified": ("UNCLASSIFIED — no checkout for that language, or the golden has no "
                         "resolved_commit. Not a verdict either way."),
    }
    for bucket in ("read_error", "drift", "unclassified"):
        items = buckets[bucket]
        print(f"\n=== {bucket.replace('_', ' ').upper()} ({len(items)}) ===")
        print(f"    {labels[bucket]}")
        for f in items:
            print(f"    {f['severity']:5} {f['type']:32} {f['bidder']}/{f['language']}")
    total = sum(len(v) for v in buckets.values())
    print(f"\n{total} findings: {len(buckets['read_error'])} read error, "
          f"{len(buckets['drift'])} drift, {len(buckets['unclassified'])} unclassified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
