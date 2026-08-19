"""Accepted-warning baseline gate for round-trip-ci.py and lint-port-rules.py.

Both harnesses exit 2 on warnings, and `make ci` plus the workflow both map
exit 2 to success. That is deliberate — the warnings are real, mostly
documented divergences, and blocking on them would stop all work. The
consequence was that the warning count could grow without anyone noticing:
nothing recorded which warnings were accepted, so warning number 60 arrived
looking exactly like the 59 before it.

This gate records them. `.github/accepted-warnings.txt` lists every warning
the repo currently accepts, and this module fails when the live set differs
in either direction:

- a warning appears that is not in the baseline — a regression, or a genuine
  new finding that needs a decision;
- a baseline entry produces no warning — it was fixed, and the baseline must
  shrink so the accepted list keeps meaning something.

## Key shape

    <source> | <rule> | <spec> | <topic>

`source` is `round-trip-ci` or `port-lint`; `rule` and `spec` come from each
tool's `--json` findings. Line numbers are NOT part of the key — an edit
above a finding must not invalidate the baseline. `topic` is the finding
detail, whitespace-collapsed, with content hashes replaced by `<hash>` and
bare integers by `<n>`, truncated to TOPIC_CHARS. That survives a fixture
refresh (which churns every `bidder_params_sha256`) while still changing when
the finding itself changes.

Truncation could in principle merge two findings that share a prefix, which
would let one hide behind the other, so `test_keys_are_unique` asserts it
does not happen. If it ever does, raise TOPIC_CHARS.

## Regenerating

After deciding that a change in warnings is correct:

    python3 scripts/tests/test_accepted_warnings.py --write-baseline

Then review the diff — that diff is the record of what was accepted.

## Known-broken pairs

`TestKnownBrokenPairs` covers the other standing downgrade in this repo:
`.github/known-broken-pairs.txt`, which turns a dual-spec `severity: fail`
into an informational finding for a named bidder. Same problem, so the same
treatment — every entry must carry a `# review-by:` directive, and the gate
fails once that date passes.
"""

from __future__ import annotations

import argparse
import datetime
import functools
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = REPO_ROOT / ".github" / "accepted-warnings.txt"
KNOWN_BROKEN_PAIRS = REPO_ROOT / ".github" / "known-broken-pairs.txt"

# Characters of normalized detail kept in a key. 60 is the smallest value
# that separates every current finding; 80 leaves margin without dragging
# whole prose paragraphs into the baseline file.
TOPIC_CHARS = 80

_HASH_RE = re.compile(r"\b[0-9a-f]{16,}\b")
_INT_RE = re.compile(r"\b\d+\b")


def read_known_broken_pairs() -> str:
    """The `--allow-known-broken-pairs` value CI passes, from the same file."""
    if not KNOWN_BROKEN_PAIRS.is_file():
        return ""
    names = [
        line.strip()
        for line in KNOWN_BROKEN_PAIRS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return ",".join(names)


def normalize_detail(detail: str) -> str:
    """Collapse a finding detail to a form stable under churn.

    Content hashes and bare integers are the two things that move without the
    finding changing: a fixture refresh rewrites every `bidder_params_sha256`,
    and counts/line numbers drift with unrelated edits.
    """
    s = " ".join(str(detail).split())
    s = _HASH_RE.sub("<hash>", s)
    s = _INT_RE.sub("<n>", s)
    return s[:TOPIC_CHARS]


def make_key(source: str, rule: str, spec: str, detail: str) -> str:
    return f"{source} | {rule} | {spec} | {normalize_detail(detail)}"


def _run_json(argv: list[str]) -> dict:
    """Run a harness with --json and parse stdout (memoized per argv)."""
    return _run_json_cached(tuple(argv))


@functools.lru_cache(maxsize=None)
def _run_json_cached(argv: tuple[str, ...]) -> dict:
    """Run a harness with --json and parse stdout.

    Exit codes 0/1/2 all carry a valid payload; anything else, or unparseable
    stdout, is an instrument failure and is raised rather than read as "no
    warnings". Memoized because both harnesses parse the whole golden corpus
    and several tests here need the same result.
    """
    proc = subprocess.run(
        [sys.executable, *argv],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1, 2):
        raise RuntimeError(
            f"{argv[0]} exited {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{argv[0]} --json produced unparseable stdout: {exc}\n"
            f"--- stdout ---\n{proc.stdout[:2000]}\n--- stderr ---\n{proc.stderr[:2000]}"
        ) from exc


def harnesses() -> list[tuple[str, list[str]]]:
    """(source, argv) for each harness, matching what `make ci` runs."""
    return [
        ("round-trip-ci", [
            "scripts/round-trip-ci.py", "--strict-r3",
            "--allow-known-broken-pairs", read_known_broken_pairs(), "--json",
        ]),
        ("port-lint", ["scripts/lib/lint-port-rules.py", "--json"]),
    ]


def collect_warnings() -> list[tuple[str, str, str, str]]:
    """Every warning from both harnesses as (source, rule, spec, detail)."""
    out: list[tuple[str, str, str, str]] = []
    for source, argv in harnesses():
        payload = _run_json(argv)
        findings = payload.get("findings")
        if not isinstance(findings, list):
            raise RuntimeError(f"{source} --json payload has no findings list")
        for f in findings:
            if f.get("severity") == "warn":
                out.append((source, str(f.get("rule")), str(f.get("spec")), str(f.get("detail"))))
    return out


def current_keys() -> list[str]:
    return [make_key(*w) for w in collect_warnings()]


def read_baseline() -> set[str]:
    if not BASELINE_PATH.is_file():
        return set()
    return {
        line.rstrip("\n")
        for line in BASELINE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


BASELINE_HEADER = """\
# Accepted warnings — round-trip-ci.py + lint-port-rules.py
#
# Both harnesses exit 2 on warnings and CI maps exit 2 to success. This file
# is the record of which warnings that covers. `scripts/tests/
# test_accepted_warnings.py` fails when the live warning set differs from
# this list in EITHER direction:
#
#   - an unlisted warning appears  -> a regression or a new finding to decide on
#   - a listed warning disappears  -> it was fixed; delete the line
#
# Key shape:  <source> | <rule> | <spec> | <topic>
#
# `topic` is the finding detail, whitespace-collapsed, with content hashes
# replaced by <hash> and bare integers by <n>, truncated. Line numbers are
# deliberately absent, so edits above a finding do not invalidate its entry,
# and a fixture refresh that rewrites every bidder_params_sha256 does not
# either.
#
# Regenerate after deciding a change is correct:
#
#     python3 scripts/tests/test_accepted_warnings.py --write-baseline
#
# Review the resulting diff — it is the record of what was accepted.
"""


def write_baseline() -> int:
    keys = sorted(set(current_keys()))
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        BASELINE_HEADER + f"#\n# Entries: {len(keys)}\n\n" + "\n".join(keys) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(keys)} accepted warnings to {BASELINE_PATH.relative_to(REPO_ROOT)}")
    return 0


class TestAcceptedWarnings(unittest.TestCase):
    def test_baseline_file_exists_and_is_populated(self):
        self.assertTrue(
            BASELINE_PATH.is_file(),
            f"missing {BASELINE_PATH.relative_to(REPO_ROOT)}; regenerate with "
            "`python3 scripts/tests/test_accepted_warnings.py --write-baseline`",
        )
        self.assertGreater(
            len(read_baseline()), 0,
            "accepted-warnings baseline is empty. Both harnesses currently emit "
            "warnings, so an empty baseline means the file was truncated, not "
            "that the warnings were fixed.",
        )

    def test_harnesses_produce_findings(self):
        """An empty finding set is an instrument failure, not a clean run.

        Both harnesses emit PASS findings for every rule they evaluate. Zero
        findings means the corpus did not load.
        """
        for source, argv in harnesses():
            with self.subTest(source=source):
                payload = _run_json(argv)
                self.assertGreater(
                    len(payload.get("findings") or []), 0,
                    f"{source} --json returned zero findings — the golden corpus "
                    f"did not load",
                )

    def test_keys_are_unique(self):
        """Truncation must not merge two distinct findings into one key."""
        keys = current_keys()
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        self.assertEqual(
            [], dupes,
            f"two findings normalize to the same key at TOPIC_CHARS="
            f"{TOPIC_CHARS}, so one could hide behind the other in the "
            f"baseline. Raise TOPIC_CHARS:\n  - " + "\n  - ".join(dupes),
        )

    def test_no_unbaselined_warnings(self):
        new = sorted(set(current_keys()) - read_baseline())
        self.assertEqual(
            [], new,
            f"{len(new)} warning(s) not in "
            f"{BASELINE_PATH.relative_to(REPO_ROOT)}:\n  - " + "\n  - ".join(new)
            + "\n\nFix the underlying finding, or — if the new warning is "
            "correct and accepted — regenerate the baseline with "
            "`python3 scripts/tests/test_accepted_warnings.py --write-baseline` "
            "and review the diff.",
        )

    def test_no_stale_baseline_entries(self):
        gone = sorted(read_baseline() - set(current_keys()))
        self.assertEqual(
            [], gone,
            f"{len(gone)} baseline entr(ies) no longer produce a warning:\n  - "
            + "\n  - ".join(gone)
            + "\n\nThese were fixed. Regenerate the baseline with "
            "`python3 scripts/tests/test_accepted_warnings.py --write-baseline` "
            "so the accepted list shrinks with the fix.",
        )


# --- known-broken-pairs expiry ---------------------------------------------

# `# review-by: YYYY-MM-DD <bidder> — <reason>`
REVIEW_BY_RE = re.compile(
    r"^#\s*review-by:\s*(\d{4})-(\d{2})-(\d{2})\s+(\S+)\s*(?:[—-]\s*(.*))?$"
)


def parse_known_broken_pairs() -> tuple[list[str], dict[str, datetime.date]]:
    """(listed bidders, {bidder: review-by date}) from known-broken-pairs.txt."""
    listed: list[str] = []
    directives: dict[str, datetime.date] = {}
    if not KNOWN_BROKEN_PAIRS.is_file():
        return listed, directives
    for raw in KNOWN_BROKEN_PAIRS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = REVIEW_BY_RE.match(line)
            if m:
                y, mo, d, bidder = m.group(1), m.group(2), m.group(3), m.group(4)
                directives[bidder] = datetime.date(int(y), int(mo), int(d))
            continue
        listed.append(line)
    return listed, directives


class TestKnownBrokenPairs(unittest.TestCase):
    """`.github/known-broken-pairs.txt` entries must carry a live expiry.

    An entry here downgrades a dual-spec `severity: fail` to informational
    for the whole round-trip run. Without an expiry the downgrade outlives
    the divergence that justified it and nothing says so.
    """

    def test_every_entry_has_a_review_by_directive(self):
        listed, directives = parse_known_broken_pairs()
        missing = sorted(set(listed) - set(directives))
        self.assertEqual(
            [], missing,
            "known-broken-pairs.txt entries with no `# review-by:` directive:\n  - "
            + "\n  - ".join(missing)
            + "\n\nAdd `# review-by: YYYY-MM-DD <bidder> — <what has to be true "
            "to remove it>` immediately above each bidder line.",
        )

    def test_no_orphan_review_by_directives(self):
        listed, directives = parse_known_broken_pairs()
        orphans = sorted(set(directives) - set(listed))
        self.assertEqual(
            [], orphans,
            "`# review-by:` directives naming bidders that are not listed "
            "(the entry was removed but its directive was left behind):\n  - "
            + "\n  - ".join(orphans),
        )

    def test_no_expired_entries(self):
        _, directives = parse_known_broken_pairs()
        today = datetime.date.today()
        expired = sorted(
            f"{bidder}: review-by {when.isoformat()} passed "
            f"({(today - when).days} day(s) ago)"
            for bidder, when in directives.items()
            if when < today
        )
        self.assertEqual(
            [], expired,
            "known-broken-pairs.txt entries are past their review date:\n  - "
            + "\n  - ".join(expired)
            + "\n\nRe-check whether the divergence still exists. If it is "
            "fixed, delete the entry and its directive. If it is not, push "
            "the date out and record what changed — the point of the date is "
            "that the downgrade gets looked at, not that it never expires.",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-baseline", action="store_true",
                        help="Rewrite .github/accepted-warnings.txt from the live warning set")
    args, remaining = parser.parse_known_args()
    if args.write_baseline:
        sys.exit(write_baseline())
    unittest.main(argv=[sys.argv[0], *remaining])
