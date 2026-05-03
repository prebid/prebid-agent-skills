"""Wave 6 + Wave 9b CI gate: doc-level count claims must match canonical sources.

The gate catches stale numeric claims like "12 enumerated behavioral fields"
(canonical was 15; surfaced in Wave 2 of the PR #1 hardening pass) BEFORE
they reach main.

Wave 9b generalized the gate from a 5-entry hardcoded `CLAIMS` tuple to a
discovery-based design over the 4 currently-tracked claim phrases:

1. `CANONICAL_SOURCES` maps the 4 tracked phrases (port-translation rules,
   enumerated behavioral fields, registered taxa, dual-spec files/pairs) to
   source-of-truth functions.
2. `DISCOVERY_REGEX` is a multi-alternation pattern matching those 4 phrases.
3. The gate walks every `*.md` under `INCLUDED_DIRS` (excluding
   `EXCLUDED_PATHS`), runs the regex, and asserts each numeric capture
   matches the canonical source for that phrase.

To add a new tracked claim phrase: add it to `DISCOVERY_REGEX` AND
`CANONICAL_SOURCES` (with a backing counter function). New claim SITES are
auto-discovered — no manifest update needed.

## Known untracked phrases (Wave 11b plan B5 finding-5 will add)

The discovery regex does NOT track:
- "N goldens" (canonical: `canonical_goldens_count` — already exists in
  this file but not wired to the regex)
- "N reference PRs" (canonical: count from
  `prebid-server-{go,java}/references/new-bid-adapter-prs.md`; the Java
  reference doesn't separately track tagged-vs-total — needs disambiguation)
- "N empire parents" (canonical: `INVENTORY_TOTALS["java_empire_parents"]`
  in `coverage-report.py`, currently a hardcoded 32)
- "N fixtures" (canonical: `canonical_goldens_count`, equivalent)

Wave 11b will extend the regex with these alternations and wire each to a
canonical-source function. Until then, drift on these phrases (e.g., README
saying "20 reference PRs" when canonical is 92) ships silently.

Files NOT gated (intentional):
- `CHANGELOG.md` — version-history snapshots; counts there are frozen.
- `docs/audits/` — audit snapshots; intentionally past-tense.
- `docs/decisions/*.md` — ADR bodies often cite historical counts that were
  true at ADR-write time (e.g., "22 goldens" in ADR-001 lines 140-144 with
  refresh annotations on more current lines).
- `docs/execution-plan.md` — historical execution log.
- `docs/methodology/rollback.md` — describes specific historical Phase 2
  commits whose count claims describe the state AT that commit.
- `prebid-server-{go,java}/references/new-bid-adapter-prs.md` — the
  canonical source-of-truth (the gate consumes it; gating it would be
  circular).

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
GO_FIXTURES_DIR = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
JAVA_FIXTURES_DIR = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
DUAL_SPECS_DIR = REPO_ROOT / "cross-language-pairs"
GO_SKILLS_DIR = REPO_ROOT / "prebid-server-go" / "read" / "skills"
JAVA_SKILLS_DIR = REPO_ROOT / "prebid-server-java" / "read" / "skills"


# === Canonical source-of-truth functions ===

def canonical_rule_count() -> int:
    """Count of port-translation rules in the YAML source-of-truth."""
    data = yaml.safe_load(RULES_YAML.read_text(encoding="utf-8"))
    total = 0
    for section in data.get("sections") or []:
        if section.get("kind") == "rules":
            total += len(section.get("rules") or [])
    return total


def canonical_enumeration_count() -> int:
    """Count of enumerated behavioral fields in the taxonomy YAML."""
    data = yaml.safe_load(TAXONOMY_YAML.read_text(encoding="utf-8"))
    return len(data.get("enumerations") or [])


def canonical_goldens_count() -> int:
    """Total golden fixtures across both languages (Go + Java)."""
    return (
        len(list(GO_FIXTURES_DIR.glob("*.golden.spec.yaml")))
        + len(list(JAVA_FIXTURES_DIR.glob("*.golden.spec.yaml")))
    )


def canonical_dual_specs_count() -> int:
    """Cross-language dual-spec assertion files."""
    return len(list(DUAL_SPECS_DIR.glob("*.dual-spec-assertions.yaml")))


def canonical_quirk_taxa_count() -> int:
    """Registered taxa in behavior-taxonomy.yaml `quirks_taxa[]`."""
    data = yaml.safe_load(TAXONOMY_YAML.read_text(encoding="utf-8"))
    return len(data.get("quirks_taxa") or [])


# === Discovery regex + canonical-source mapping ===

# A single multi-alternation regex catching every tracked claim phrase.
# `(\d+)` captures the count; group 2 captures the phrase. Phrase text is
# normalized (lowercased, whitespace-collapsed) before lookup in
# CANONICAL_SOURCES.
#
# Adding a new tracked phrase:
# 1. Add the phrase variant to the regex below.
# 2. Add an entry in CANONICAL_SOURCES mapping the normalized phrase to its
#    source-of-truth function.
DISCOVERY_REGEX = re.compile(
    r"\b(\d+)\s+("
    r"(?:cross-language\s+)?port-translation\s+rules"
    r"|enumerated\s+behavioral\s+fields"
    r"|registered\s+taxa"
    r"|dual-spec\s+(?:assertion\s+)?(?:files|pairs)"
    r")\b",
    re.IGNORECASE,
)


def _normalize_phrase(s: str) -> str:
    """Collapse whitespace and lowercase, plus strip the optional 'cross-language' prefix."""
    out = " ".join(s.lower().split())
    if out.startswith("cross-language "):
        out = out[len("cross-language "):]
    if out.startswith("dual-spec assertion "):
        out = "dual-spec " + out[len("dual-spec assertion "):]
    return out


CANONICAL_SOURCES: dict[str, Callable[[], int]] = {
    "port-translation rules": canonical_rule_count,
    "enumerated behavioral fields": canonical_enumeration_count,
    "registered taxa": canonical_quirk_taxa_count,
    "dual-spec files": canonical_dual_specs_count,
    "dual-spec pairs": canonical_dual_specs_count,
}


# === Path inclusion/exclusion ===

# Directories whose `*.md` files are walked.
INCLUDED_DIRS = (
    REPO_ROOT,                                   # README.md, ROADMAP.md only (not recursive)
    REPO_ROOT / "docs" / "methodology",          # methodology docs
    GO_SKILLS_DIR,                               # SKILL.md + references/*.md (recursive)
    JAVA_SKILLS_DIR,
    GO_FIXTURES_DIR,                             # test-fixtures/README.md
    JAVA_FIXTURES_DIR,
    DUAL_SPECS_DIR,                              # cross-language-pairs/README.md
)

# Files excluded from gating. Two flavors: paths and path-suffixes.
EXCLUDED_PATHS = frozenset({
    REPO_ROOT / "CHANGELOG.md",
    REPO_ROOT / "docs" / "execution-plan.md",
    REPO_ROOT / "docs" / "methodology" / "rollback.md",
})
EXCLUDED_DIRS = (
    REPO_ROOT / "docs" / "audits",
    REPO_ROOT / "docs" / "decisions",
    REPO_ROOT / "prebid-server-go" / "references",
    REPO_ROOT / "prebid-server-java" / "references",
)


def _eligible_docs() -> list[Path]:
    """Discover all `*.md` files eligible for count-claim gating."""
    candidates: list[Path] = []
    # Top-level only for REPO_ROOT (README.md, ROADMAP.md).
    candidates.append(REPO_ROOT / "README.md")
    candidates.append(REPO_ROOT / "ROADMAP.md")
    for d in INCLUDED_DIRS[1:]:
        if not d.is_dir():
            continue
        candidates.extend(d.rglob("*.md"))
    out: list[Path] = []
    for p in candidates:
        if not p.is_file():
            continue
        if p in EXCLUDED_PATHS:
            continue
        if any(_is_under(p, d) for d in EXCLUDED_DIRS):
            continue
        out.append(p)
    return sorted(set(out))


def _is_under(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


class Mismatch(NamedTuple):
    relpath: str
    line_no: int
    phrase: str
    claimed: int
    canonical: int

    def format(self) -> str:
        return (
            f"{self.relpath}:{self.line_no} claims `{self.phrase}` = {self.claimed}, "
            f"but canonical count is {self.canonical}"
        )


class TestDocCountClaims(unittest.TestCase):
    def test_canonical_sources_load(self):
        """Sanity-check: every source-of-truth function returns a plausible count."""
        self.assertGreater(canonical_rule_count(), 40, "≥40 port-translation rules expected")
        self.assertGreater(canonical_enumeration_count(), 5, "≥5 enumerations expected")
        self.assertGreater(canonical_quirk_taxa_count(), 30, "≥30 quirk taxa expected")
        self.assertGreater(canonical_goldens_count(), 30, "≥30 goldens expected")
        self.assertGreater(canonical_dual_specs_count(), 10, "≥10 dual-spec files expected")

    def test_phrase_lookup_complete(self):
        """Every alternation in DISCOVERY_REGEX has a CANONICAL_SOURCES entry."""
        # A test text that triggers every regex alternation. If the regex
        # gains a new alternation, this string must be extended.
        sample = (
            "1 port-translation rules. "
            "1 cross-language port-translation rules. "
            "1 enumerated behavioral fields. "
            "1 registered taxa. "
            "1 dual-spec files. "
            "1 dual-spec pairs. "
            "1 dual-spec assertion files. "
            "1 dual-spec assertion pairs."
        )
        for m in DISCOVERY_REGEX.finditer(sample):
            phrase = _normalize_phrase(m.group(2))
            self.assertIn(
                phrase, CANONICAL_SOURCES,
                f"DISCOVERY_REGEX alternation `{m.group(2)}` (normalized `{phrase}`) "
                f"has no entry in CANONICAL_SOURCES",
            )

    def test_doc_claims_match_canonical_sources(self):
        """Every tracked claim's number matches its canonical source.

        Walks every `*.md` under INCLUDED_DIRS (minus EXCLUDED_PATHS /
        EXCLUDED_DIRS), runs DISCOVERY_REGEX, and asserts each captured
        count equals the live source-of-truth count.
        """
        mismatches: list[Mismatch] = []
        sites_checked = 0
        files_walked = 0
        for path in _eligible_docs():
            files_walked += 1
            text = path.read_text(encoding="utf-8")
            for m in DISCOVERY_REGEX.finditer(text):
                claimed = int(m.group(1))
                phrase = _normalize_phrase(m.group(2))
                source_fn = CANONICAL_SOURCES.get(phrase)
                if source_fn is None:  # pragma: no cover — covered by test_phrase_lookup_complete
                    continue
                canonical = source_fn()
                sites_checked += 1
                if claimed != canonical:
                    line_no = text.count("\n", 0, m.start()) + 1
                    mismatches.append(Mismatch(
                        relpath=str(path.relative_to(REPO_ROOT)),
                        line_no=line_no,
                        phrase=phrase,
                        claimed=claimed,
                        canonical=canonical,
                    ))
        if mismatches:
            self.fail(
                f"doc count claims drifted from canonical sources "
                f"({len(mismatches)} mismatch(es) across {files_walked} files, "
                f"{sites_checked} total sites checked):\n  - "
                + "\n  - ".join(mm.format() for mm in mismatches)
                + "\n\nUpdate the doc claims to match the live counts, OR "
                "update CANONICAL_SOURCES if the canonical source changed, OR "
                "add the file to EXCLUDED_PATHS if the claim is intentionally "
                "frozen historical."
            )
        # Sanity: at least SOME sites must be discovered, otherwise the
        # discovery regex or path filter has regressed.
        self.assertGreater(sites_checked, 0, "no claim sites discovered — discovery regex or path filter may be broken")


if __name__ == "__main__":
    unittest.main()
