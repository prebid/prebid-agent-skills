"""Wave 6 CI gate: doc-level count claims must match canonical sources.

Catches drift like the `12 enumerated behavioral fields` stale claim in
`cross-skill-integration.md` (canonical count is 15) — the kind of bug that
slipped past every reviewer until Wave 2 of the PR #1 hardening pass. Each
entry in `CLAIMS` below pairs a doc location with a regex capturing a
numeric claim and the canonical-source function that produces the truth.

Historical count claims that intentionally freeze a moment in time —
CHANGELOG release entries, dual-spec note paragraphs that record a past
inventory — are NOT gated. The gate watches LIVE claims that should track
canonical sources.

Run via:
    python3 -m unittest scripts.tests.test_doc_count_claims -v

The test runs as part of `make ci` via the unittest discover step.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Callable, NamedTuple

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY_YAML = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "behavior-taxonomy.yaml"
RULES_YAML = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "port-translation-rules.yaml"


def canonical_rule_count() -> int:
    """Count of port-translation rules in the YAML source-of-truth."""
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    total = 0
    for section in data.get("sections") or []:
        if section.get("kind") == "rules":
            total += len(section.get("rules") or [])
    return total


def canonical_enumeration_count() -> int:
    """Count of enumerated behavioral fields in the taxonomy YAML source-of-truth."""
    data = yaml.safe_load(TAXONOMY_YAML.read_text(encoding="utf-8"))
    return len(data.get("enumerations") or [])


class Claim(NamedTuple):
    relpath: str  # repo-relative
    regex: re.Pattern[str]
    source_fn: Callable[[], int]
    label: str


# Tracked claim sites. New occurrences should be added here when introduced.
# Removing a claim from a file is fine (the gate skips files where the regex
# doesn't match); ADDING a claim with an unmatched count requires a fix.
CLAIMS: tuple[Claim, ...] = (
    Claim(
        relpath="README.md",
        regex=re.compile(r"\b(\d+)\s+cross-language\s+port-translation\s+rules\b"),
        source_fn=canonical_rule_count,
        label="port-translation rules",
    ),
    Claim(
        relpath="prebid-server-go/read/skills/shared/cross-skill-integration.md",
        regex=re.compile(r"\b(\d+)\s+port-translation\s+rules\b"),
        source_fn=canonical_rule_count,
        label="port-translation rules",
    ),
    Claim(
        relpath="prebid-server-go/read/skills/shared/cross-skill-integration.md",
        regex=re.compile(r"\b(\d+)\s+enumerated\s+behavioral\s+fields\b"),
        source_fn=canonical_enumeration_count,
        label="enumerated behavioral fields",
    ),
    Claim(
        relpath="prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md",
        regex=re.compile(r"\b(\d+)\s+port-translation\s+rules\b"),
        source_fn=canonical_rule_count,
        label="port-translation rules",
    ),
    Claim(
        relpath="prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md",
        regex=re.compile(r"\b(\d+)\s+port-translation\s+rules\b"),
        source_fn=canonical_rule_count,
        label="port-translation rules",
    ),
)


class TestDocCountClaims(unittest.TestCase):
    def test_canonical_rule_count_loads(self):
        n = canonical_rule_count()
        self.assertGreater(n, 40, "should be at least 40 rules (corpus has been ≥46 since Phase 2.5)")
        self.assertLess(n, 200, "sanity: rule count should not be in the hundreds")

    def test_canonical_enumeration_count_loads(self):
        n = canonical_enumeration_count()
        self.assertGreater(n, 5, "should be at least 5 taxonomy enumerations")
        self.assertLess(n, 100, "sanity: enumeration count should not be in the hundreds")

    def test_doc_claims_match_canonical_sources(self):
        """Every tracked claim's number matches its canonical source.

        Iterates `CLAIMS`, finds every regex match in the file, and asserts
        each captured count equals the live source-of-truth count.
        """
        failures: list[str] = []
        sites_checked = 0
        for claim in CLAIMS:
            full = (REPO_ROOT / claim.relpath).read_text(encoding="utf-8")
            matches = list(claim.regex.finditer(full))
            if not matches:
                # The claim phrase isn't present — that's editorial latitude,
                # not a CI-blocking concern. Future Wave could tighten to
                # require presence on a per-claim basis.
                continue
            expected = claim.source_fn()
            for m in matches:
                sites_checked += 1
                claimed = int(m.group(1))
                if claimed != expected:
                    line_no = full.count("\n", 0, m.start()) + 1
                    failures.append(
                        f"{claim.relpath}:{line_no} claims {claim.label}={claimed}, "
                        f"but canonical count is {expected}"
                    )
        if failures:
            self.fail(
                "doc count claims drifted from canonical sources:\n  - "
                + "\n  - ".join(failures)
                + "\n\nUpdate the doc claims to match the live counts, or update CLAIMS in this test "
                "if a claim site is intentionally removed."
            )
        self.assertGreater(sites_checked, 0, "no claim sites matched — CLAIMS may be stale")


if __name__ == "__main__":
    unittest.main()
