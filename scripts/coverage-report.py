#!/usr/bin/env python3
"""scripts/coverage-report.py — Phase 4.3 corpus coverage report.

Produces a markdown matrix at docs/coverage-report.md that shows:

1. Golden inventory — Go + Java + paired counts.
2. Dual-spec coherency — for each `cross-language-pairs/<bidder>.dual-spec-assertions.yaml`,
   whether both halves are present and the assertion file is structurally valid.
3. Phase 5 readiness — per ADR-008, the 9 prioritized pair fixtures and what's
   currently covered.
4. Rule 46 naming pairs — 12 from ADR-005; which are in the corpus.
5. Rule 43 lifecycle sub-types — bilateral / java-leads / go-leads coverage.
6. Java empire parents — 5 deep-dived in ADR-003 + the 32-parent total target;
   which have Java goldens, which have child goldens.
7. Per-rule master-sample mentions — for each of the 46 rules in
   port-translation-rules.yaml, regex-scan the body for bidder names and
   report which of those mentions are covered by goldens.

The report is regenerable via `make coverage` (Phase 4.3) and is intended
to drive Phase 5 prioritization.

Usage:
    python3 scripts/coverage-report.py            # write fresh docs/coverage-report.md
    python3 scripts/coverage-report.py --check    # exit 1 if drift vs on-disk report
    python3 scripts/coverage-report.py --stdout   # print to stdout instead of writing
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDENS_GO = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
GOLDENS_JAVA = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
DUAL_SPEC_DIR = REPO_ROOT / "cross-language-pairs"
RULES_PATH = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared" / "port-translation-rules.yaml"
OUT_PATH = REPO_ROOT / "docs" / "coverage-report.md"


# ─── Reference data from ADRs (stable; refreshed when ADRs change) ────────

# Phase 5 priority pairs (ADR-008 P1 + P2 + P3 + Stretch).
PHASE_5_PAIRS = [
    ("smarthub", "P1", "ADR-003 Rule 44 canonical (white-label-saas, 9 aliases, parent-rebrand)"),
    ("teqblaze", "P1", "ADR-003 Rule 44 (white-label-saas, 9 aliases)"),
    ("adverxo", "P1", "ADR-003 Rule 44 (registration-only, 3 aliases — smallest clean canonical)"),
    ("limelightDigital", "P2", "ADR-003 Rule 44 (endpoint-macro-substitution, 15 aliases)"),
    ("vungle", "P2", "ADR-006 Rule 43 bilateral phantom-rename (liftoff/vungle — refined 2026-05-03 from go-leads)"),
    ("emxdigital", "P2", "ADR-006 Rule 43 java-leads with Go dual-core registration (cadent_aperture_mx/emxdigital cross-name)"),
    ("adkernelAdn", "P3", "ADR-005 Rule 46 naming-normalization master (adkernelAdn → adkerneladn)"),
    ("freewheelssp", "Stretch", "ADR-007 F2 master (language-stamped-header-divergence — refined 2026-05-03 from multi-endpoint-by-mediatype label-collision)"),
    ("thetradedesk", "Stretch", "ADR-007 F4 master (bid-post-processing-macro)"),
]

# Rule 46 naming-convention pairs (ADR-005, 11 verified pairs — refined 2026-05-03
# from 12 after Phase 5 empirical verification removed freewheel-ssp/freewheelssp;
# see ADR-005 "Excluded cases" section).
RULE_46_PAIRS = [
    ("adkernelAdn", "adkerneladn", "lowercase"),
    ("audienceNetwork", "audiencenetwork", "lowercase"),
    ("boldwin_rapid", "boldwinrapid", "underscore-drop"),
    ("emx_digital", "emxdigital", "underscore-drop"),
    ("e_volution", "evolution", "underscore-drop"),
    ("lm_kiviads", "lmkiviads", "underscore-drop"),
    ("mgidX", "mgidx", "lowercase"),
    ("sa_lunamedia", "salunamedia", "underscore-drop"),
    ("sspBC", "sspbc", "lowercase"),
    ("stroeerCore", "stroeercore", "lowercase"),
    ("triplelift_native", "tripleliftnative", "underscore-drop"),
]

# Rule 43 lifecycle-rename pairs (ADR-006). Refined 2026-05-03 — 5 of 7 pairs
# reclassified per Phase 5 empirical verification (commit `f11b2ba` and
# follow-up). Distribution: 2 bilateral + 1 java-leads + 0 go-leads + 2
# mirror-topology + 2 inverted-parent. See ADR-006 for verbatim evidence and
# subtype definitions.
LIFECYCLE_PAIRS = [
    ("elementaltv", "elementaltv", "bilateral", "Adoppler→ElementalTV (PR java#4326 + go#4639)"),
    ("vungle", "vungle", "bilateral", "Liftoff acquired Vungle 2021 — phantom-rename (refined 2026-05-03 from go-leads); both sides canonical at vungle"),
    ("cadent_aperture_mx", "emxdigital", "java-leads", "Cadent acquired EMX (Go has dual-core registration of both cadent_aperture_mx + emx_digital)"),
    ("conversant", "epsilon", "inverted-parent", "Publicis Epsilon acquired Conversant — Go parent=conversant, Java parent=epsilon (refined 2026-05-03 from java-leads)"),
    ("magnite", "rubicon", "mirror-topology", "Magnite/Rubicon merger — both sides parent=rubicon, alias=magnite (refined 2026-05-03 from java-leads)"),
    ("intenze", "gothamads", "inverted-parent", "Acquisition — Go parent=intenze with gothamads in removed-warn map; Java parent=gothamads (refined 2026-05-03 from java-leads)"),
    ("equativ", "smartadserver", "mirror-topology", "Smart AdServer rebrand 2022 — both sides parent=smartadserver, alias=equativ (refined 2026-05-03 from go-leads)"),
]

# Java empire parents deep-dived in ADR-003 (5 of 32 total).
EMPIRE_PARENTS_DEEP_DIVED = [
    ("smarthub", "white-label-saas", 9, "SmartHub→Attekmi rebrand co-occurs"),
    ("teqblaze", "white-label-saas", 9, "TeqBlaze established Java#4161"),
    ("limelightDigital", "endpoint-macro-substitution", 15, "complexity-high reference"),
    ("nexx360", "registration-only", 4, "Nexx360 established Java#4053"),
    ("adverxo", "registration-only", 3, "smallest clean canonical"),
]

# Reconnaissance totals from ADR-003 / Round 3 inventory.
INVENTORY_TOTALS = {
    "go_bidders": 358,
    "java_bidders": 350,
    "java_empire_parents": 32,
    "java_empire_aliases": 95,
    "disabled_asymmetric_pairs": 78,
    "naming_normalization_pairs": 11,
    "lifecycle_rename_pairs": 8,
}


# ─── Discovery helpers ────────────────────────────────────────────────────

def discover_goldens() -> dict[str, set[str]]:
    """Return {'go': {bidder, ...}, 'java': {...}, 'paired': {...}}."""
    go = {f.stem.replace(".golden.spec", "") for f in GOLDENS_GO.glob("*.golden.spec.yaml")}
    java = {f.stem.replace(".golden.spec", "") for f in GOLDENS_JAVA.glob("*.golden.spec.yaml")}
    return {"go": go, "java": java, "paired": go & java}


def discover_dual_specs() -> dict[str, dict]:
    """Return {bidder: parsed_yaml} for each dual-spec assertion file."""
    out = {}
    if not DUAL_SPEC_DIR.is_dir():
        return out
    for f in sorted(DUAL_SPEC_DIR.glob("*.dual-spec-assertions.yaml")):
        bidder = f.stem.replace(".dual-spec-assertions", "")
        try:
            with open(f) as fp:
                out[bidder] = yaml.safe_load(fp) or {}
        except Exception as e:
            out[bidder] = {"_parse_error": str(e)}
    return out


def load_rules() -> list[dict]:
    """Return the rules list from port-translation-rules.yaml."""
    with open(RULES_PATH) as fp:
        data = yaml.safe_load(fp)
    rules = []
    for sec in data.get("sections", []):
        if sec.get("kind") == "rules":
            rules.extend(sec.get("rules", []))
    return rules


# Bidders mentioned in rule bodies that we want to cross-reference against
# goldens. Conservative: words that look like bidder identifiers (lowercase
# or camelCase, alphanumeric + underscore + hyphen, length 4-30).
_BIDDER_NAME_RE = re.compile(r"\b([a-z][A-Za-z0-9_\-]{3,29})\b")
# Words that look like bidder names but aren't (workflow words, helper
# verbs, etc.). Add as needed.
_BIDDER_NAME_DENYLIST = {
    "alias", "aliases", "bidder", "bidders", "builder", "config", "default",
    "domain", "endpoint", "extra", "false", "field", "fields", "format",
    "framework", "function", "future", "header", "helper", "imports",
    "include", "infrastructure", "input", "java", "language", "lifecycle",
    "lookup", "method", "module", "notes", "object", "parent", "prebid",
    "request", "required", "response", "result", "review", "schema",
    "skill", "static", "string", "subset", "syntax", "system", "target",
    "translation", "true", "type", "value", "verbose", "verify", "wrapper",
    "actually", "adapter", "always", "another", "applies", "assertion",
    "assigns", "becomes", "before", "between", "called", "cannot",
    "captures", "carries", "change", "channel", "chosen", "claims",
    "collapses", "complex", "component", "concrete", "consume", "consumer",
    "context", "contract", "coverage", "covered", "create", "current",
    "decision", "declared", "delete", "denote", "details", "different",
    "directly", "discovers", "divergence", "during", "dynamic", "edge",
    "effective", "emerges", "either", "emits", "enabled", "enough",
    "ensure", "equivalent", "exactly", "example", "exist", "extends",
    "external", "factory", "feature", "fixture", "follows", "general",
    "generated", "given", "global", "ground", "happens", "having",
    "implies", "include", "includes", "infer", "inline", "inside",
    "instead", "interaction", "invoke", "knows", "language", "latest",
    "layout", "leads", "least", "legacy", "lookup", "manual", "master",
    "matching", "means", "merges", "minimum", "model", "moves", "needed",
    "normal", "older", "operator", "optional", "outputs", "owner",
    "package", "passes", "passing", "patterns", "phase", "policy",
    "popular", "possibly", "present", "primary", "pristine", "process",
    "programs", "promoted", "proper", "proposed", "provides", "publish",
    "purpose", "quirk", "really", "receive", "records", "register",
    "reject", "release", "remain", "removed", "rename", "render",
    "report", "request", "requires", "result", "return", "review",
    "round", "rules", "running", "runtime", "second", "section", "select",
    "separate", "service", "shared", "should", "since", "sister", "small",
    "source", "specifically", "starts", "still", "stops", "structural",
    "submitted", "sub-flavor", "subtype", "successor", "sufficient",
    "summary", "supplies", "support", "surface", "surfaces", "syntax",
    "table", "taken", "taxonomy", "third", "though", "through",
    "throughout", "today", "together", "translation", "treats", "trick",
    "truth", "uniform", "unique", "unless", "update", "usage", "usually",
    "values", "verify", "version", "violates", "warning", "warnings",
    "watch", "where", "which", "while", "whose", "without", "writing",
    "yaml", "yields", "above", "below", "after",
}


def extract_mentioned_bidders(text: str) -> set[str]:
    """Pull out bidder-name-like tokens from a rule body."""
    out = set()
    for m in _BIDDER_NAME_RE.finditer(text or ""):
        token = m.group(1)
        if token.lower() in _BIDDER_NAME_DENYLIST:
            continue
        # Reject snake_case framework imports like `errortypes_BadInput`.
        if "errortypes" in token or "openrtb_ext" in token:
            continue
        out.add(token)
    return out


# ─── Per-section computations ─────────────────────────────────────────────

def _build_cross_name_lookup() -> dict[str, tuple[str, str]]:
    """Cross-name pairs from LIFECYCLE_PAIRS and RULE_46_PAIRS where Go ≠ Java.
    Both names map to the same (go_name, java_name) tuple so Phase 5 entries
    keyed by either side resolve correctly. LIFECYCLE entries take precedence
    when a name appears in both (e.g., `emxdigital` is in LIFECYCLE_PAIRS as
    java side of cadent pair AND in RULE_46_PAIRS as java side of emx_digital
    pair — LIFECYCLE wins because lifecycle pairs include rename/parent-child
    relationships, while Rule 46 pairs are pure naming normalizations)."""
    lookup = {}
    for entry in LIFECYCLE_PAIRS:
        go, java = entry[0], entry[1]
        if go != java:
            lookup[go] = (go, java)
            lookup[java] = (go, java)
    for entry in RULE_46_PAIRS:
        go, java = entry[0], entry[1]
        if go != java:
            lookup.setdefault(go, (go, java))
            lookup.setdefault(java, (go, java))
    return lookup


def compute_phase_5_readiness(goldens: dict[str, set[str]],
                              duals: dict[str, dict] | None = None) -> list[dict]:
    """Map each Phase 5 pair to {bidder, priority, gap}.

    Resolution order for Go/Java filenames:
      1. Dual-spec's go_spec/java_spec paths (most authoritative — handles
         empirical ADR-005/ADR-006 corrections like freewheelssp same-name
         canonical or vungle bilateral phantom-rename).
      2. LIFECYCLE_PAIRS / RULE_46_PAIRS cross-name lookup.
      3. Bidder name verbatim on both sides (default).
    """
    cross_name = _build_cross_name_lookup()
    out = []
    for bidder, priority, summary in PHASE_5_PAIRS:
        bidder_lc = bidder.lower()
        go_name, java_name = bidder, bidder
        if duals and bidder in duals:
            go_name, java_name = _resolve_dual_spec_filenames(bidder, duals[bidder] or {})
            has_go = go_name in goldens["go"]
            has_java = java_name in goldens["java"]
        elif bidder in cross_name:
            go_name, java_name = cross_name[bidder]
            has_go = go_name in goldens["go"] or go_name.lower() in goldens["go"]
            has_java = java_name in goldens["java"] or java_name.lower() in goldens["java"]
        else:
            has_go = bidder in goldens["go"] or bidder_lc in goldens["go"]
            has_java = bidder in goldens["java"] or bidder_lc in goldens["java"]
        out.append({
            "bidder": bidder,
            "priority": priority,
            "summary": summary,
            "has_go": has_go,
            "has_java": has_java,
            "covered": has_go and has_java,
        })
    return out


def compute_rule_46_coverage(goldens: dict[str, set[str]]) -> list[dict]:
    out = []
    for go, java, transformation in RULE_46_PAIRS:
        out.append({
            "go": go,
            "java": java,
            "transformation": transformation,
            "has_go": go in goldens["go"],
            "has_java": java in goldens["java"],
        })
    return out


def compute_lifecycle_coverage(goldens: dict[str, set[str]]) -> list[dict]:
    out = []
    for go, java, subtype, summary in LIFECYCLE_PAIRS:
        out.append({
            "go": go,
            "java": java,
            "subtype": subtype,
            "summary": summary,
            "has_go": go in goldens["go"],
            "has_java": java in goldens["java"],
        })
    return out


def compute_empire_coverage(goldens: dict[str, set[str]]) -> list[dict]:
    out = []
    for parent, flavor, n_aliases, note in EMPIRE_PARENTS_DEEP_DIVED:
        out.append({
            "parent": parent,
            "flavor": flavor,
            "n_aliases": n_aliases,
            "note": note,
            "has_java_parent_golden": parent in goldens["java"],
            "has_go_parent_golden": parent in goldens["go"],
        })
    return out


def _resolve_dual_spec_filenames(bidder: str, d: dict) -> tuple[str, str]:
    """Extract go/java golden filenames from a dual-spec.

    Prefers explicit `go_spec`/`java_spec` paths in the dual-spec content
    (load-bearing for cross-name pairs and ADR-corrected lifecycle entries);
    falls back to LIFECYCLE_PAIRS cross-name lookup if paths are absent;
    falls back to bidder name if neither.
    """
    go_match = java_match = None
    if isinstance(d, dict):
        go_match = re.search(r"/([^/]+)\.golden\.spec\.yaml$", d.get("go_spec") or "")
        java_match = re.search(r"/([^/]+)\.golden\.spec\.yaml$", d.get("java_spec") or "")
    if go_match and java_match:
        return go_match.group(1), java_match.group(1)
    cross_name = _build_cross_name_lookup()
    if bidder in cross_name:
        return cross_name[bidder]
    return bidder, bidder


def compute_dual_spec_coherency(goldens: dict[str, set[str]],
                                  duals: dict[str, dict]) -> list[dict]:
    out = []
    for bidder in sorted(duals):
        d = duals[bidder]
        if isinstance(d, dict) and "_parse_error" in d:
            out.append({
                "bidder": bidder,
                "error": d["_parse_error"],
                "has_go": False,
                "has_java": False,
            })
            continue
        go_name, java_name = _resolve_dual_spec_filenames(bidder, d or {})
        out.append({
            "bidder": bidder,
            "has_go": go_name in goldens["go"],
            "has_java": java_name in goldens["java"],
            "has_naming_asymmetry": "naming_asymmetry" in (d or {}),
            "has_bidder_info_default_enabled": "bidder_info_default_enabled" in (d or {}),
            "has_bidder_params_sha256": "bidder_params_sha256" in (d or {}),
            "block_count": len(d or {}),
            "is_cross_name": go_name != java_name,
        })
    return out


def compute_per_rule_mentions(rules: list[dict],
                              goldens: dict[str, set[str]]) -> list[dict]:
    """For each rule, extract bidder names from body and check golden coverage."""
    all_goldens = goldens["go"] | goldens["java"]
    out = []
    for rule in rules:
        body = rule.get("body") or ""
        pattern = rule.get("pattern") or ""
        mentioned = extract_mentioned_bidders(body + " " + pattern)
        # Only count ones that look plausibly like bidder names (case-insensitive
        # match against any golden, OR a known PHASE_5/Rule46/lifecycle entry).
        known_set = (
            all_goldens
            | {p[0] for p in PHASE_5_PAIRS}
            | {p[0] for p in RULE_46_PAIRS}
            | {p[1] for p in RULE_46_PAIRS}
            | {p[0] for p in LIFECYCLE_PAIRS}
            | {p[1] for p in LIFECYCLE_PAIRS}
            | {p[0] for p in EMPIRE_PARENTS_DEEP_DIVED}
        )
        relevant = mentioned & known_set
        covered = {m for m in relevant if m in all_goldens}
        out.append({
            "id": rule["id"],
            "title": rule["title"],
            "mentioned": sorted(relevant),
            "covered": sorted(covered),
            "uncovered": sorted(relevant - covered),
        })
    return out


# ─── Markdown rendering ───────────────────────────────────────────────────

def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def yn(b: bool) -> str:
    return "✓" if b else "—"


def render(goldens, duals, rules) -> str:
    phase5 = compute_phase_5_readiness(goldens, duals)
    r46 = compute_rule_46_coverage(goldens)
    life = compute_lifecycle_coverage(goldens)
    empire = compute_empire_coverage(goldens)
    dual_coh = compute_dual_spec_coherency(goldens, duals)
    per_rule = compute_per_rule_mentions(rules, goldens)

    out = []
    out.append("# Coverage Report")
    out.append("")
    out.append("<!-- AUTO-GENERATED by scripts/coverage-report.py. DO NOT EDIT. -->")
    out.append(f"<!-- Regenerate via: make coverage. Last run: {date.today().isoformat()}. -->")
    out.append("")
    out.append("Tracks per-rule, per-empire, per-pair coverage of the goldens corpus against ADR-stated targets. Drives Phase 5 prioritization.")
    out.append("")
    out.append("---")
    out.append("")

    # Section 1: Inventory
    out.append("## 1. Golden inventory")
    out.append("")
    out.append(f"- **Go goldens**: {len(goldens['go'])} ({', '.join(sorted(goldens['go'])) or '—'})")
    out.append(f"- **Java goldens**: {len(goldens['java'])} ({', '.join(sorted(goldens['java'])) or '—'})")
    out.append(f"- **Paired goldens** (both languages): {len(goldens['paired'])} ({', '.join(sorted(goldens['paired'])) or '—'})")
    out.append(f"- **Dual-spec assertion files**: {len(duals)}")
    out.append("")
    out.append("Reconnaissance totals (Round 3 inventory, ADR-003):")
    out.append("")
    for k, v in INVENTORY_TOTALS.items():
        out.append(f"- `{k}`: **{v}**")
    out.append("")
    out.append("---")
    out.append("")

    # Section 2: Phase 5 readiness
    out.append("## 2. Phase 5 readiness (per ADR-008)")
    out.append("")
    rows = []
    p5_covered = sum(1 for p in phase5 if p["covered"])
    for p in phase5:
        status = "✓ covered" if p["covered"] else (
            "Go only" if p["has_go"] else ("Java only" if p["has_java"] else "missing"))
        rows.append([f"`{p['bidder']}`", p["priority"], yn(p["has_go"]), yn(p["has_java"]), status, p["summary"]])
    out.append(md_table(["Bidder", "Priority", "Go", "Java", "Status", "Why"], rows))
    out.append("")
    out.append(f"**Phase 5 status**: {p5_covered} of {len(phase5)} pairs covered. {len(phase5) - p5_covered} remaining (matches ADR-008's 9-pair plan).")
    out.append("")
    out.append("---")
    out.append("")

    # Section 3: Rule 46 naming pairs
    out.append("## 3. Rule 46 naming-convention pairs (per ADR-005)")
    out.append("")
    rows = []
    r46_covered = 0
    for p in r46:
        c = p["has_go"] and p["has_java"]
        if c:
            r46_covered += 1
        rows.append([f"`{p['go']}`", f"`{p['java']}`", f"`{p['transformation']}`", yn(p["has_go"]), yn(p["has_java"])])
    out.append(md_table(["Go", "Java", "Transformation", "Go golden", "Java golden"], rows))
    out.append("")
    out.append(f"**Rule 46 coverage**: {r46_covered} of {len(r46)} pairs fully covered. ADR-005 lists {INVENTORY_TOTALS['naming_normalization_pairs']} verified pairs.")
    out.append("")
    out.append("---")
    out.append("")

    # Section 4: Lifecycle (Rule 43)
    out.append("## 4. Rule 43 lifecycle-rename pairs (per ADR-006)")
    out.append("")
    rows = []
    life_covered = 0
    for p in life:
        c = p["has_go"] and p["has_java"]
        if c:
            life_covered += 1
        rows.append([f"`{p['go']}`", f"`{p['java']}`", f"`{p['subtype']}`", yn(p["has_go"]), yn(p["has_java"]), p["summary"]])
    out.append(md_table(["Go", "Java", "Sub-type", "Go golden", "Java golden", "Why"], rows))
    out.append("")
    out.append(f"**Rule 43 coverage**: {life_covered} of {len(life)} pairs fully covered (`elementaltv` is the only `bilateral` master in the corpus today).")
    out.append("")
    out.append("---")
    out.append("")

    # Section 5: Empires
    out.append("## 5. Java alias-empire parents (deep-dived in ADR-003)")
    out.append("")
    rows = []
    empire_covered = 0
    for p in empire:
        c = p["has_java_parent_golden"]
        if c:
            empire_covered += 1
        rows.append([f"`{p['parent']}`", f"`{p['flavor']}`", str(p["n_aliases"]), yn(p["has_java_parent_golden"]), yn(p["has_go_parent_golden"]), p["note"]])
    out.append(md_table(["Parent", "Flavor", "Aliases", "Java golden", "Go golden", "Note"], rows))
    out.append("")
    out.append(f"**Empire coverage**: {empire_covered} of {len(empire)} deep-dived parents covered. Total Java empire parents in upstream corpus: {INVENTORY_TOTALS['java_empire_parents']} (95 children).")
    out.append("")
    out.append("---")
    out.append("")

    # Section 6: Dual-spec coherency
    out.append("## 6. Dual-spec assertion coherency")
    out.append("")
    rows = []
    for d in dual_coh:
        if "error" in d:
            rows.append([f"`{d['bidder']}`", yn(False), yn(False), "—", "—", "—", f"⚠ parse error: {d['error']}"])
            continue
        rows.append([
            f"`{d['bidder']}`",
            yn(d["has_go"]),
            yn(d["has_java"]),
            yn(d["has_bidder_params_sha256"]),
            yn(d["has_bidder_info_default_enabled"]),
            yn(d["has_naming_asymmetry"]),
            str(d["block_count"]),
        ])
    out.append(md_table(["Bidder", "Go", "Java", "sha256 block", "default_enabled block", "naming_asymmetry block", "Total blocks"], rows))
    out.append("")
    out.append("`naming_asymmetry` is a Phase 2.7 dual-spec block (ADR-005). Existing assertions don't have it because none of the 7 covered pairs hit Rule 46. Phase 5's `adkernelAdn`/`adkerneladn` pair will populate it for the first time.")
    out.append("")
    out.append("---")
    out.append("")

    # Section 7: Per-rule mentions
    out.append("## 7. Per-rule master-sample coverage")
    out.append("")
    out.append("For each of the 46 rules, scan the rule body for bidder names and check whether the corpus has a golden for them. Rules with no specific bidder mentions (general patterns) show empty.")
    out.append("")
    rows = []
    rules_with_uncovered = 0
    for r in per_rule:
        if r["mentioned"]:
            mentioned_str = ", ".join(f"`{m}`" + ("" if m in goldens["go"] | goldens["java"] else "*") for m in r["mentioned"])
        else:
            mentioned_str = "(generic)"
        if r["uncovered"]:
            rules_with_uncovered += 1
        rows.append([f"Rule {r['id']:2d}", r["title"], mentioned_str, len(r["covered"]), len(r["uncovered"])])
    out.append(md_table(["#", "Title", "Mentioned bidders", "Covered", "Uncovered"], rows))
    out.append("")
    out.append(f"`*` after a name = bidder is named in rule body but NOT in the goldens corpus. {rules_with_uncovered} of {len(per_rule)} rules mention at least one uncovered bidder.")
    out.append("")
    out.append("---")
    out.append("")

    # Section 8: Top gaps
    out.append("## 8. Top gaps to close (sorted by impact)")
    out.append("")
    gaps = []
    for p in phase5:
        if not p["covered"]:
            gaps.append((1 if p["priority"] == "P1" else (2 if p["priority"] == "P2" else 3),
                         f"Phase 5 {p['priority']}: pair `{p['bidder']}` — {p['summary']}"))
    for p in life:
        if not (p["has_go"] and p["has_java"]):
            gaps.append((4, f"Rule 43 sub-type `{p['subtype']}`: pair `{p['go']}/{p['java']}` ({p['summary']})"))
    for p in empire:
        if not p["has_java_parent_golden"]:
            gaps.append((5, f"Empire parent `{p['parent']}` ({p['flavor']}, {p['n_aliases']} aliases) — {p['note']}"))
    gaps.sort(key=lambda g: g[0])
    if gaps:
        for _, g in gaps[:25]:
            out.append(f"- {g}")
    else:
        out.append("- (no gaps detected)")
    out.append("")
    out.append("---")
    out.append("")
    out.append("## Sources")
    out.append("")
    out.append(f"- Goldens: `prebid-server-{{go,java}}/read/test-fixtures/*.golden.spec.yaml` ({len(goldens['go']) + len(goldens['java'])} files).")
    out.append(f"- Dual-spec assertions: `cross-language-pairs/*.dual-spec-assertions.yaml` ({len(duals)} files).")
    out.append("- Port-translation rules (46 rules): `prebid-server-go/read/skills/shared/port-translation-rules.yaml`.")
    out.append("- ADRs driving the inventory: ADR-003 (empire), ADR-005 (Rule 46 pairs), ADR-006 (lifecycle sub-types), ADR-008 (Phase 5 plan).")
    out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Verify on-disk report matches re-generated; exit 1 on drift.")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of writing to file.")
    args = parser.parse_args(argv)

    goldens = discover_goldens()
    duals = discover_dual_specs()
    rules = load_rules()
    rendered = render(goldens, duals, rules)

    if args.stdout:
        sys.stdout.write(rendered)
        return 0
    if args.check:
        if not OUT_PATH.is_file():
            sys.stderr.write(f"ERROR: missing {OUT_PATH}; run `make coverage` to generate.\n")
            return 1
        on_disk = OUT_PATH.read_text()
        if on_disk != rendered:
            sys.stderr.write(f"DRIFT: {OUT_PATH.name} differs from re-generated output. Run `make coverage` and commit.\n")
            return 1
        print(f"OK: {OUT_PATH.name} matches the re-generated output.")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rendered)
    print(f"Wrote {OUT_PATH} ({len(rendered.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
