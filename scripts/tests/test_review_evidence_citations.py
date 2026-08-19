"""Every evidence citation in a review skill must resolve to something that exists.

WHY
    The cross-language port-fidelity hooks in the Go review skills carry a table
    of worked examples, each with an evidence column. Those citations are the
    reason a reviewer trusts the row: they say "this pattern is real, here is
    where it was observed." A citation that no longer resolves still looks
    precise, and it sends the reviewer to the wrong assertion.

    The branch these hooks came from cited in-repo files by LINE NUMBER --
    `optidigital.dual-spec-assertions.yaml:60` for the `default_enabled`
    divergence, which by then sat at lines 49-55, with line 60 holding an
    unrelated `severity: warn`. Every edit to a pair file renumbers every
    citation into it, so line numbers are the one form of citation that cannot
    survive ordinary maintenance.

WHAT THIS FIXES IT TO
    Two stable forms, both checked here:

      `<bidder>.dual-spec-assertions.yaml` -> `<key>`     the key must exist
      `<canary-trace>.md` -> `<finding-id>`               a heading must exist

    A key path survives reordering. A finding id survives everything short of
    renaming the finding, which is the kind of change that should invalidate the
    citation.

WHAT IT DOES NOT CHECK
    That the cited assertion SAYS what the row claims. A key that exists but
    records something else passes here. The reviewer still reads the assertion;
    this gate only guarantees they can reach it.

Run: python3 -m unittest scripts.tests.test_review_evidence_citations -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOTS = (
    REPO_ROOT / "prebid-server-go" / "review" / "skills",
    REPO_ROOT / "prebid-server-java" / "review" / "skills",
)
PAIRS_DIR = REPO_ROOT / "cross-language-pairs"
RUNS_DIR = REPO_ROOT / "docs" / "runs"

# `aax.dual-spec-assertions.yaml` -> `bidder_params_sha256`
DUAL_CITE = re.compile(r"`([\w.-]+)\.dual-spec-assertions\.yaml`\s*(?:→|->)\s*`([\w.-]+)`")
# `d3.8-teal-canary-....md` -> F-new-43   |   same trace -> F-new-44
RUN_CITE = re.compile(r"`([\w.\-]+\.md)`\s*(?:→|->)\s*(F(?:-new-)?\d+)")

MIN_CITATIONS = 12


def _markdown_sources() -> list[Path]:
    out: list[Path] = []
    for root in SKILL_ROOTS:
        if root.is_dir():
            out.extend(sorted(root.rglob("*.md")))
    return out


def _all_keys(node, acc: set[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            acc.add(str(k))
            _all_keys(v, acc)
    elif isinstance(node, list):
        for v in node:
            _all_keys(v, acc)


class TestReviewEvidenceCitations(unittest.TestCase):
    def setUp(self):
        self.dual: list[tuple[str, int, str, str]] = []
        self.runs: list[tuple[str, int, str, str]] = []
        for path in _markdown_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = str(path.relative_to(REPO_ROOT))
            for m in DUAL_CITE.finditer(text):
                self.dual.append((rel, text[:m.start()].count("\n") + 1, m.group(1), m.group(2)))
            for m in RUN_CITE.finditer(text):
                self.runs.append((rel, text[:m.start()].count("\n") + 1, m.group(1), m.group(2)))

    def test_scan_finds_citations(self):
        """An empty scan is a setup error. If the hooks are reworded so the
        patterns stop matching, this arm says so instead of reporting a pass."""
        total = len(self.dual) + len(self.runs)
        self.assertGreaterEqual(
            total, MIN_CITATIONS,
            f"only {total} evidence citations matched (expected at least "
            f"{MIN_CITATIONS}). Either the review hooks lost their evidence "
            f"columns or the citation form changed.")

    def test_dual_spec_key_citations_resolve(self):
        cache: dict[str, set[str]] = {}
        broken = []
        for rel, line, bidder, key in self.dual:
            pair = PAIRS_DIR / f"{bidder}.dual-spec-assertions.yaml"
            if not pair.is_file():
                broken.append(f"{rel}:{line} cites {pair.name}, which does not exist")
                continue
            if bidder not in cache:
                acc: set[str] = set()
                _all_keys(yaml.safe_load(pair.read_text(encoding="utf-8")), acc)
                cache[bidder] = acc
            if key not in cache[bidder]:
                broken.append(f"{rel}:{line} cites {pair.name} key {key!r}, which is absent")
        self.assertEqual([], broken, "unresolvable dual-spec citations:\n  " + "\n  ".join(broken))

    def test_canary_finding_citations_resolve(self):
        broken = []
        for rel, line, doc, finding in self.runs:
            trace = RUNS_DIR / doc
            if not trace.is_file():
                broken.append(f"{rel}:{line} cites {doc}, which does not exist under docs/runs/")
                continue
            text = trace.read_text(encoding="utf-8", errors="replace")
            if not re.search(rf"^#+\s+`?{re.escape(finding)}`?\b", text, re.M):
                broken.append(f"{rel}:{line} cites {doc} finding {finding}, "
                              f"which has no heading in that trace")
        self.assertEqual([], broken, "unresolvable canary citations:\n  " + "\n  ".join(broken))

    def test_no_line_number_citations_into_pair_files(self):
        """The form this gate exists to retire. A pair file's line numbers change
        on every edit, so a line-anchored citation is stale by construction."""
        offenders = []
        rx = re.compile(r"`?[\w.-]+\.dual-spec-assertions\.yaml:\d+")
        for path in _markdown_sources():
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in rx.finditer(text):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:"
                                 f"{text[:m.start()].count(chr(10)) + 1} -> {m.group(0)}")
        self.assertEqual([], offenders,
                         "line-anchored dual-spec citations (cite the key path instead):\n  "
                         + "\n  ".join(offenders))


if __name__ == "__main__":
    unittest.main()
