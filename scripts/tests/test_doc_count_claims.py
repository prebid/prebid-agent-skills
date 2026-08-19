"""Wave 6 + Wave 9b + Wave 11b CI gate: doc-level count claims must match
canonical sources.

The gate catches stale numeric claims like "12 enumerated behavioral fields"
(canonical was 15; surfaced in Wave 2 of the PR #1 hardening pass) BEFORE
they reach main.

Wave 9b generalized the gate from a 5-entry hardcoded `CLAIMS` tuple to a
discovery-based design. Wave 11b B5 #5 adds Java empire parents to the
tracked phrase set:

1. `CANONICAL_SOURCES` maps tracked phrases (port-translation rules,
   enumerated behavioral fields, registered taxa, dual-spec files/pairs,
   Java empire parents) to source-of-truth functions.
2. `DISCOVERY_REGEX` is a multi-alternation pattern matching those phrases.
3. The gate walks every `*.md` under `INCLUDED_DIRS` (excluding
   `EXCLUDED_PATHS`), runs the regex, and asserts each numeric capture
   matches the canonical source for that phrase.

To add a new tracked claim phrase: add it to `DISCOVERY_REGEX` AND
`CANONICAL_SOURCES` (with a backing counter function). New claim SITES are
auto-discovered — no manifest update needed.

## Phrases NOT tracked (Wave 11b deliberately deferred)

- "N reference PRs" — the corpus uses this phrase ambiguously: "92 reference
  PRs" means Go-side totals; "49 reference PRs" means Java-side totals; "44
  currently tagged" / "39 currently tagged" are subset-only counts on each
  side. Tracking via single canonical needs disambiguation (Go vs Java vs
  total vs tagged-subset). Deferred to a future wave that picks a
  disambiguation policy.
- "N fixtures" — the test-fixtures/README cites phase-specific fixture
  counts ("21 fixtures" for Phase A, "12 fixtures" for Phase 5 batch 1, "9
  fixtures" for batch 2). These are HISTORICAL state counts that do not
  match any single canonical. Adding "N fixtures" generically would force
  test-fixtures/README to either be excluded or rewritten. Deferred.
- Bare "N goldens" — still deferred, for the original reason: used as both a
  per-language subset count and the cross-language total, and SemVer
  fragments ("1.0.0 goldens") are false positives.

  The SPLIT form "N goldens (X Go + Y Java)" IS now tracked
  (`GOLDENS_SPLIT_REGEX`), because it is unambiguous and because leaving it
  untracked cost exactly what this gate exists to prevent: the schema's own
  description and a "make ci covers N" instruction both read "40 goldens
  (21 Go + 19 Java)" while the corpus held 22 + 20. All three numbers are
  checked.

## Gated surfaces

All four skill surfaces are walked: `prebid-server-{go,java}/read/skills/`,
`prebid-server-{go,java}/review/skills/`, `prebid-server-go/port-java2go/`
and `prebid-server-java/port-go2java/`. The read suites were the original
scope; the review suites and the port skills are the surfaces that run
against real upstream PRs. The two port SKILLs each cite the live
port-translation rule count twice — four claim sites that would go stale
on the next rules bump if the gate stopped at the read trees.

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
GO_REVIEW_SKILLS_DIR = REPO_ROOT / "prebid-server-go" / "review" / "skills"
JAVA_REVIEW_SKILLS_DIR = REPO_ROOT / "prebid-server-java" / "review" / "skills"
GO_PORT_SKILL_DIR = REPO_ROOT / "prebid-server-go" / "port-java2go"
JAVA_PORT_SKILL_DIR = REPO_ROOT / "prebid-server-java" / "port-go2java"


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


def canonical_java_empire_parents_count() -> int:
    """Wave 11b B5 #5: Java alias-empire parent count from coverage-report.py's
    INVENTORY_TOTALS dict. The canonical 32 is a Round-3 reconnaissance
    snapshot per ADR-003; this function reads coverage-report.py's
    constant so any future re-count cascades to all docs that cite it."""
    import importlib.util
    cr_path = REPO_ROOT / "scripts" / "coverage-report.py"
    spec = importlib.util.spec_from_file_location("_cr_for_count", cr_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {cr_path}")
    cr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cr)
    return int(cr.INVENTORY_TOTALS["java_empire_parents"])


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
    # Wave 11b post-review (3c): port-translation-rules.yaml intro uses
    # the phrasing "explicit translation rules" (no "port-" prefix).
    # Without this alternation, the YAML intro count drifts undetected.
    r"|explicit\s+translation\s+rules"
    r"|enumerated\s+behavioral\s+fields"
    r"|registered\s+taxa"
    r"|dual-spec\s+(?:assertion\s+)?(?:files|pairs)"
    # Wave 11b B5 #5: Java empire parents (alias-empire reconnaissance).
    r"|(?:java\s+)?(?:alias-)?empire\s+parents"
    r")\b",
    re.IGNORECASE,
)
# Bare "N goldens" stays untracked, for the reason first recorded here: the
# corpus uses it both as a per-language subset count in the per-language READMEs
# and as the cross-language total, and SemVer fragments ("1.0.0 goldens") are
# false positives.
#
# The SPLIT form is not ambiguous, and it is the one that rotted: the schema's own
# description and an instruction about what `make ci` covers both said "40 goldens
# (21 Go + 19 Java)" against a real 22 + 20. GOLDENS_SPLIT_REGEX below tracks it
# and checks all three numbers, so a new fixture cannot land without the claims
# moving. Historical corpus-size notes inside cross-language-pairs/*.yaml ("32
# goldens (16 Go + 16 Java)") record the corpus as it was when each pair was
# authored; they are YAML, outside this gate's *.md walk, and stay as history.
GOLDENS_SPLIT_REGEX = re.compile(
    r"\b(\d+)\s+goldens\s*\(\s*(\d+)\s+Go\s*\+\s*(\d+)\s+Java",
    re.IGNORECASE,
)


def canonical_goldens_split() -> tuple[int, int, int]:
    """(total, go, java) counted on disk."""
    go = len(list(GO_FIXTURES_DIR.glob("*.golden.spec.yaml")))
    java = len(list(JAVA_FIXTURES_DIR.glob("*.golden.spec.yaml")))
    return go + java, go, java


def _normalize_phrase(s: str) -> str:
    """Collapse whitespace and lowercase; strip optional prefixes that don't
    affect the canonical lookup ('cross-language' on rules, 'java' / 'alias-'
    on empire parents). Map "explicit translation rules" to the canonical
    "port-translation rules" key (Wave 11b post-review 3c)."""
    out = " ".join(s.lower().split())
    if out.startswith("cross-language "):
        out = out[len("cross-language "):]
    if out.startswith("dual-spec assertion "):
        out = "dual-spec " + out[len("dual-spec assertion "):]
    if out.startswith("java "):
        out = out[len("java "):]
    if out == "explicit translation rules":
        out = "port-translation rules"
    if out.startswith("alias-"):
        out = out[len("alias-"):]
    return out


CANONICAL_SOURCES: dict[str, Callable[[], int]] = {
    "port-translation rules": canonical_rule_count,
    "enumerated behavioral fields": canonical_enumeration_count,
    "registered taxa": canonical_quirk_taxa_count,
    "dual-spec files": canonical_dual_specs_count,
    "dual-spec pairs": canonical_dual_specs_count,
    # Wave 11b B5 #5 addition
    "empire parents": canonical_java_empire_parents_count,
}


# === Path inclusion/exclusion ===

# Directories whose `*.md` files are walked.
INCLUDED_DIRS = (
    REPO_ROOT,                                   # README.md, ROADMAP.md only (not recursive)
    REPO_ROOT / "docs" / "methodology",          # methodology docs
    GO_SKILLS_DIR,                               # SKILL.md + references/*.md (recursive)
    JAVA_SKILLS_DIR,
    # The review suites and the two port skills are the surfaces that run
    # against real upstream PRs. The port SKILLs each cite the live
    # port-translation rule count twice, so a rules bump that skips them
    # ships four stale claims into the skills a reviewer actually loads.
    GO_REVIEW_SKILLS_DIR,
    JAVA_REVIEW_SKILLS_DIR,
    GO_PORT_SKILL_DIR,
    JAVA_PORT_SKILL_DIR,
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


def _scan_goldens_split(text: str) -> list[tuple[int, tuple[int, int, int]]]:
    """(line_no, (total, go, java)) for each split-form claim in `text`."""
    out = []
    for m in GOLDENS_SPLIT_REGEX.finditer(text):
        out.append((text[:m.start()].count("\n") + 1,
                    (int(m.group(1)), int(m.group(2)), int(m.group(3)))))
    return out


class TestGoldensSplitClaims(unittest.TestCase):
    """The split form has to agree with the directory listing, in all three
    numbers. A total that happens to match while the per-language split is wrong
    is still a wrong claim, and the stale site had that shape -- off by one on
    each side."""

    def test_every_split_claim_matches_the_corpus(self):
        want = canonical_goldens_split()
        bad = []
        for doc in _eligible_docs():
            text = doc.read_text(encoding="utf-8", errors="replace")
            for line_no, got in _scan_goldens_split(text):
                if got != want:
                    rel = doc.relative_to(REPO_ROOT).as_posix()
                    bad.append(f"{rel}:{line_no} claims {got[0]} goldens "
                               f"({got[1]} Go + {got[2]} Java), corpus has "
                               f"{want[0]} ({want[1]} Go + {want[2]} Java)")
        self.assertEqual([], bad, "\n  ".join(bad))

    def test_the_schema_description_agrees_too(self):
        """The schema is not markdown, so the *.md walk cannot see it -- and it
        is where the stale count actually lived."""
        import json
        want = canonical_goldens_split()
        schema = json.loads(
            (REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared"
             / "adapter-spec.schema.json").read_text(encoding="utf-8"))
        claims = _scan_goldens_split(schema.get("description", ""))
        self.assertTrue(claims, "adapter-spec.schema.json description no longer states its "
                                "golden coverage in the tracked form")
        for line_no, got in claims:
            self.assertEqual(want, got,
                             f"schema description claims {got}, corpus has {want}")

    def test_the_regex_matches_the_form_the_corpus_uses(self):
        self.assertEqual([(1, (42, 22, 20))],
                         _scan_goldens_split("all 42 goldens (22 Go + 20 Java) validate"))
        self.assertEqual([], _scan_goldens_split("10 goldens in this README"),
                         "bare form must stay untracked")
        self.assertEqual([], _scan_goldens_split("1.0.0 goldens"),
                         "SemVer fragment must not match")


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
            "1 explicit translation rules. "  # Wave 11b post-review 3c
            "1 enumerated behavioral fields. "
            "1 registered taxa. "
            "1 dual-spec files. "
            "1 dual-spec pairs. "
            "1 dual-spec assertion files. "
            "1 dual-spec assertion pairs. "
            "1 empire parents. "
            "1 Java empire parents. "
            "1 alias-empire parents. "
            "1 Java alias-empire parents."
        )
        for m in DISCOVERY_REGEX.finditer(sample):
            phrase = _normalize_phrase(m.group(2))
            self.assertIn(
                phrase, CANONICAL_SOURCES,
                f"DISCOVERY_REGEX alternation `{m.group(2)}` (normalized `{phrase}`) "
                f"has no entry in CANONICAL_SOURCES",
            )

    def test_included_dirs_all_contribute_docs(self):
        """Every INCLUDED_DIR yields at least one eligible `*.md`.

        An empty tree is a finding, not a pass: renaming or moving a skill
        surface would otherwise drop it from the gate while the run still
        reported OK.
        """
        eligible = _eligible_docs()
        for d in INCLUDED_DIRS[1:]:  # REPO_ROOT is handled non-recursively
            with self.subTest(directory=str(d.relative_to(REPO_ROOT))):
                self.assertTrue(d.is_dir(), f"included dir missing: {d}")
                self.assertTrue(
                    any(_is_under(p, d) for p in eligible),
                    f"included dir contributed zero gated docs: {d}",
                )

    def test_port_skills_rule_count_claims_are_gated(self):
        """The port SKILLs' live rule-count citations are inside the gate.

        Both port SKILL.md files cite the port-translation rule count. This
        asserts the citations are discovered, so a future path-filter change
        that drops the port trees fails here instead of silently letting the
        four claims drift on the next rules bump.
        """
        eligible = set(_eligible_docs())
        port_skills = [GO_PORT_SKILL_DIR / "SKILL.md", JAVA_PORT_SKILL_DIR / "SKILL.md"]
        sites = 0
        for p in port_skills:
            self.assertIn(p, eligible, f"port SKILL not gated: {p}")
            for m in DISCOVERY_REGEX.finditer(p.read_text(encoding="utf-8")):
                if _normalize_phrase(m.group(2)) == "port-translation rules":
                    sites += 1
        self.assertGreaterEqual(
            sites, 2,
            "expected each port SKILL to cite the port-translation rule count",
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
