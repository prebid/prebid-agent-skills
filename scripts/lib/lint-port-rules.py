#!/usr/bin/env python3
"""scripts/lib/lint-port-rules.py — Phase 2.6 mechanizable port-translation rule lints.

Covers the 7 port-translation rules in `port-translation-rules.yaml` that are
marked mechanizable (full or partial). Each lint reads paired Go and Java
goldens (and optional dual-spec assertion files) and emits structured findings.

Rules covered:
  Rule 5  — Site/App mutation strategy pairing
            (`copy-then-mutate`/`in-place` Go ↔ `immutable-rebuild` Java)
  Rule 9  — Custom-typed request body coherence
            (Go `request_body.kind=custom` ↔ Java `parameterized_request_type` ≠ BidRequest)
  Rule 33 — Aliases inversion (FAIL-severity post-Wave-11b)
            (Go child's `aliasOf:` ↔ Java parent's `aliases[]` block)
  Rule 36 — Test fixture inventory parity
            (both languages have non-empty fixture inventories)
  Rule 44 — Java alias-empire parent-flavor coherence
            (alias's `meta.empire_parent_flavor` matches parent's `aliases[].relationship_flavor`)
  Rule 46 — Naming-convention normalization
            (`go_name.lower().replace('_','').replace('-','') == java_name`,
            with digit-leading-workaround / brand-acronym-preservation allow-listed)

Wave 11b B5 #8 deleted Rule 38 (bidder_params_sha256 byte-equality) from
this lint check — it was redundant with R5's dual-spec-aware byte-
divergence reporting in round-trip-ci.py. The Rule 38 PRINCIPLE remains
documented in port-translation-rules.md:45-77 ("Java MUST copy Go's
bidder_params bytes verbatim") as a load-bearing port-translation rule;
just no separate lint emission. R5 is the sole runtime gate.

Each finding is a tuple of (rule_id, severity, bidder, message).
Severities: `pass` | `warn` | `fail`.

Wave 11b B5 #8 promoted Rule 33 (alias inversion structural correctness)
from `warn` to `fail` severity. Round-2 audit confirmed 0 active Rule 33
warns across the 14-pair corpus; promotion is safe and turns alias-graph
inversions into hard CI gates instead of advisory noise.

Usage:
    python3 scripts/lib/lint-port-rules.py
    python3 scripts/lib/lint-port-rules.py --bidder kobler
    python3 scripts/lib/lint-port-rules.py --strict       # warns become exit 1
    python3 scripts/lib/lint-port-rules.py --quiet        # only print summary

Exit codes:
    0 — no warns, no fails
    1 — `--strict` mode AND any warns, OR any fails (currently no rule
        emits fail; pre-positioned for Wave 11b promotions)
    2 — warns only, treated as success by Makefile (matches round-trip-ci.py)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, NamedTuple, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDENS_GO = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
GOLDENS_JAVA = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
DUAL_SPEC_DIR = REPO_ROOT / "cross-language-pairs"
SHARED_DIR = REPO_ROOT / "prebid-server-go" / "read" / "skills" / "shared"
ADAPTER_SPEC_SCHEMA = SHARED_DIR / "adapter-spec.schema.json"
BEHAVIOR_TAXONOMY_YAML = SHARED_DIR / "behavior-taxonomy.yaml"

RULE_TITLES = {
    5: "Site/App mutation strategy pairing",
    9: "Custom-typed request body coherence",
    33: "Aliases inversion (Go child ↔ Java parent.aliases[])",
    36: "Test fixture inventory parity",
    # Rule 38 (bidder_params_sha256 byte-equality) deleted in Wave 11b B5 #8;
    # principle preserved in port-translation-rules.md:45-77, runtime gate
    # in round-trip-ci.py R5 (dual-spec-aware byte-divergence reporting).
    44: "Java alias-empire parent-flavor coherence",
    46: "Naming-convention normalization",
}


class Finding(NamedTuple):
    rule_id: int
    severity: str
    bidder: str
    message: str

    def format(self) -> str:
        return f"[Rule {self.rule_id:2d}] {self.severity.upper():<4} {self.bidder}: {self.message}"


def _path(d: Optional[dict], *keys) -> Any:
    """Safe nested-dict lookup; returns None on any missing intermediate."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _normalize_strategy(s: Any) -> Optional[str]:
    """Treat None and the literal string 'none' as equivalent (both mean 'not used')."""
    if s is None or s == "none":
        return None
    return s


# ---------------------------------------------------------------------------
# Rule 5 — entity_strategies pairing semantics
# ---------------------------------------------------------------------------
#
# The pre-fix implementation held three literal (go, java) tuples and
# normalized only None/'none'. Across the shipped corpus that produced 0
# passes and 4 warns — the pass arm had never executed, so the rule
# discriminated nothing. Both warns were model gaps, not divergences:
#
#   thetradedesk  Site/App  go=deep-copy-then-mutate  java=immutable-rebuild
#   vungle        Site      go=replace-with-app-synthesis  java=(same)
#   vungle        App       go=synthesize-app-replacement  java=(same)
#
# `deep-copy-then-mutate ↔ immutable-rebuild` is declared a valid pair by
# docs/methodology/port-skills-design.md ("Rule 5 mutation strategy pairing"),
# and the vungle Site/App pair is the ADR-007 F3 master sample, which the
# same document records as an R5 `pass` because the pattern is symmetric
# across languages.
#
# Enumerating tuples cannot express either case without growing
# combinatorially, so the model is now two orthogonal properties per
# strategy:
#
#   mutation_class — what the adapter does to the entity, language-neutral.
#                    Both sides must agree on this: if Go scrubs the entity
#                    and Java leaves it alone, that is a real divergence.
#   go_natural / java_natural — whether the strategy is idiomatic in that
#                    language. Go mutates through pointers; Java rebuilds
#                    through Lombok builders. A Java spec claiming `in-place`
#                    is a modelling error even though the class matches.
#
# A pair is valid iff the classes agree AND each side's strategy is natural
# for its own language. That admits every genuine pairing above and still
# rejects `copy-then-mutate ↔ in-place` (Java never mutates in place) and
# `copy-then-mutate ↔ none` (Go scrubs, Java does not).
#
# The vocabulary is NOT invented here: `test_lint_port_rules.py` asserts this
# table covers every value in the schema's `$defs.EntityStrategy` enums,
# every value in the taxonomy's entity_strategies table, and every value used
# by a shipped golden. A new strategy anywhere fails that test until it is
# modelled, so the table cannot silently drift from its sources.

class StrategySemantics(NamedTuple):
    mutation_class: str
    go_natural: bool
    java_natural: bool


_NO_MUTATION = "no-mutation"
_MUTATE_PRESERVE = "mutate-preserve"
_APPEND = "append"
_REPLACE_NULL = "replace-with-null"
_APP_SYNTHESIS = "app-synthesis"

STRATEGY_SEMANTICS: dict[str, StrategySemantics] = {
    # Entity untouched. Normalized to None before lookup; listed for coverage.
    "none": StrategySemantics(_NO_MUTATION, True, True),

    # Scrub/overwrite fields on the entity, preserving the rest. The language
    # idiom differs — this is the pairing Rule 5's title describes.
    "in-place": StrategySemantics(_MUTATE_PRESERVE, True, False),
    "copy-then-mutate": StrategySemantics(_MUTATE_PRESERVE, True, False),
    "deep-copy-then-mutate": StrategySemantics(_MUTATE_PRESERVE, True, False),
    "immutable-rebuild": StrategySemantics(_MUTATE_PRESERVE, False, True),

    # Add a value to a collection if absent (currency lists). Both languages
    # spell this the same way — kobler and beachfront do it on `Cur`.
    "append-if-missing": StrategySemantics(_APPEND, True, True),

    # Null the entity out to suppress passthrough. Java-side idiom
    # (`toBuilder().cur(null)`); rubicon is the shipped example.
    "replace-with-null": StrategySemantics(_REPLACE_NULL, False, True),

    # ADR-007 F3: destructive Site→App rewrite. Symmetric — both languages
    # carry the same token, so the pair is identity, not a translation.
    "replace-with-app-synthesis": StrategySemantics(_APP_SYNTHESIS, True, True),
    "synthesize-app-replacement": StrategySemantics(_APP_SYNTHESIS, True, True),
    "synthesize-from-site": StrategySemantics(_APP_SYNTHESIS, True, True),
}


def load_schema_entity_strategy_values() -> set[str]:
    """Strategy values admitted by `$defs.EntityStrategy` in the JSON Schema.

    Union across the per-entity (Site/App/User) enums. This is the canonical
    closed vocabulary; the schema position is not yet `$ref`-wired, so nothing
    else validates a golden's strategy values against it.
    """
    with open(ADAPTER_SPEC_SCHEMA, encoding="utf-8") as fp:
        schema = json.load(fp)
    node = (schema.get("$defs") or {}).get("EntityStrategy") or {}
    values: set[str] = set()
    for prop in (node.get("properties") or {}).values():
        for v in prop.get("enum") or []:
            if isinstance(v, str):
                values.add(v)
    return values


def load_taxonomy_entity_strategy_values() -> set[str]:
    """Strategy values listed in behavior-taxonomy.yaml's entity_strategies table."""
    with open(BEHAVIOR_TAXONOMY_YAML, encoding="utf-8") as fp:
        taxonomy = yaml.safe_load(fp)
    values: set[str] = set()
    for enum in taxonomy.get("enumerations") or []:
        for sub in enum.get("sub_sections") or []:
            title = str(sub.get("title") or "")
            if "entity_strategies" not in title:
                continue
            for row in sub.get("rows") or []:
                if not row:
                    continue
                cell = str(row[0]).strip().strip("`")
                if cell:
                    values.add(cell)
    return values


def _describe(strategy: Optional[str]) -> str:
    return "none/absent" if strategy is None else repr(strategy)


def rule_5_mutation_strategies(go: dict, java: dict) -> list[Finding]:
    """Verify Site/App entity_strategies pair correctly across languages.

    Scope is Site and App, matching Rule 5's declared `spec_field_driver`
    (`code.make_requests.mutation.entity_strategies.Site` / `.App`).
    """
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    findings: list[Finding] = []
    for entity in ("Site", "App"):
        go_strat = _normalize_strategy(_path(go, "code", "make_requests", "mutation", "entity_strategies", entity))
        java_strat = _normalize_strategy(_path(java, "code", "make_requests", "mutation", "entity_strategies", entity))
        if go_strat is None and java_strat is None:
            continue  # not applicable on either side; rule silent

        unknown = [s for s in (go_strat, java_strat) if s is not None and s not in STRATEGY_SEMANTICS]
        if unknown:
            findings.append(Finding(5, "warn", bidder,
                f"entity_strategies.{entity} uses unmodelled strategy value(s) {unknown!r}; "
                f"not in the canonical `$defs.EntityStrategy` vocabulary — either fix the "
                f"golden or add the value to the schema and STRATEGY_SEMANTICS"))
            continue

        go_sem = STRATEGY_SEMANTICS[go_strat] if go_strat else STRATEGY_SEMANTICS["none"]
        java_sem = STRATEGY_SEMANTICS[java_strat] if java_strat else STRATEGY_SEMANTICS["none"]

        if go_sem.mutation_class != java_sem.mutation_class:
            findings.append(Finding(5, "warn", bidder,
                f"entity_strategies.{entity} class divergence: go={_describe(go_strat)} "
                f"({go_sem.mutation_class}) vs java={_describe(java_strat)} "
                f"({java_sem.mutation_class}); per Rule 5 both sides must do the same thing "
                f"to the entity, differing only in language idiom"))
            continue

        unnatural = []
        if go_strat is not None and not go_sem.go_natural:
            unnatural.append(f"go={go_strat!r} is not a Go idiom")
        if java_strat is not None and not java_sem.java_natural:
            unnatural.append(f"java={java_strat!r} is not a Java idiom")
        if unnatural:
            findings.append(Finding(5, "warn", bidder,
                f"entity_strategies.{entity} idiom mismatch ({go_sem.mutation_class}): "
                + "; ".join(unnatural)
                + "; per Rule 5 Go mutates through pointers and Java rebuilds through builders"))
            continue

        findings.append(Finding(5, "pass", bidder,
            f"entity_strategies.{entity} pair OK ({go_sem.mutation_class}): "
            f"go={_describe(go_strat)} java={_describe(java_strat)}"))
    return findings


def rule_9_custom_request_body(go: dict, java: dict) -> list[Finding]:
    """Verify custom-body-type coherence across languages."""
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    go_kind = _path(go, "code", "make_requests", "request_body", "kind")
    java_param_type = _path(java, "bidder_class", "parameterized_request_type")

    # Aliases inherit from parent — skip
    if _path(go, "meta", "is_alias") or _path(java, "meta", "is_alias"):
        return []
    if go_kind is None and java_param_type is None:
        return []  # not enough data

    is_go_custom = (go_kind == "custom")
    is_java_custom = bool(java_param_type) and java_param_type != "BidRequest"

    if is_go_custom and is_java_custom:
        return [Finding(9, "pass", bidder,
                        f"custom-body coherent: go.kind=custom, java.parameterized_request_type={java_param_type!r}")]
    if not is_go_custom and not is_java_custom:
        return [Finding(9, "pass", bidder,
                        f"openrtb-passthrough/modified coherent: go.kind={go_kind!r} java.parameterized_request_type={java_param_type!r}")]
    return [Finding(9, "warn", bidder,
                    f"custom-body asymmetry: go.kind={go_kind!r} (custom={is_go_custom}) "
                    f"vs java.parameterized_request_type={java_param_type!r} (custom={is_java_custom}); "
                    f"per Rule 9, both sides must agree on custom vs passthrough")]


def rule_33_alias_inversion(go: dict, java: dict, java_parent_specs: dict) -> list[Finding]:
    """Verify Go child's aliasOf ↔ Java parent's aliases[] block."""
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    is_alias = _path(go, "meta", "is_alias") or _path(java, "meta", "is_alias")
    if not is_alias:
        return []  # rule applies only to aliases

    parent_name = _path(go, "meta", "alias_of") or _path(java, "meta", "alias_of")
    if not parent_name:
        # Wave 11b B5 #8: Rule 33 promoted warn → fail (alias-graph integrity).
        return [Finding(33, "fail", bidder, "is_alias=true but meta.alias_of is null/missing")]

    parent_spec = java_parent_specs.get(parent_name)
    if parent_spec is None:
        return [Finding(33, "pass", bidder,
                        f"alias of {parent_name!r}; Java parent spec not in scope (best-effort skip)")]

    parent_aliases = _path(parent_spec, "aliases") or []
    parent_alias_names = set()
    for a in parent_aliases:
        if isinstance(a, dict):
            n = a.get("name")
            if n:
                parent_alias_names.add(n)
        elif isinstance(a, str):
            parent_alias_names.add(a)

    if bidder in parent_alias_names:
        return [Finding(33, "pass", bidder,
                        f"alias graph coherent: {bidder!r} listed under Java parent {parent_name!r}.aliases[]")]
    # Wave 11b B5 #8: Rule 33 promoted warn → fail (alias-graph integrity).
    return [Finding(33, "fail", bidder,
                    f"Java parent {parent_name!r}.aliases[] does not list {bidder!r}; "
                    f"Go declares aliasOf={parent_name} but Java parent's aliases block omits this child "
                    f"(possible Rule 33 inversion divergence)")]


def rule_36_test_fixture_parity(go: dict, java: dict) -> list[Finding]:
    """Verify both languages have non-empty fixture inventories (loose parity check)."""
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    go_n = len(_path(go, "tests", "fixture_inventory", "exemplary") or [])
    java_n = len(_path(java, "tests", "fixture_inventory", "integration") or [])

    # For aliases, Go has zero exemplary by design (Rule 37) — skip Rule 36 noise on aliases
    if _path(go, "meta", "is_alias") or _path(java, "meta", "is_alias"):
        return [Finding(36, "pass", bidder, f"alias bidder; per Rule 37, Go has 0 exemplary by design (java.integration={java_n})")]

    if go_n == 0 and java_n == 0:
        return [Finding(36, "pass", bidder, "no fixtures on either side")]
    if go_n > 0 and java_n > 0:
        return [Finding(36, "pass", bidder, f"both sides have fixtures: go.exemplary={go_n} java.integration={java_n}")]
    side_has = "go" if go_n > 0 else "java"
    side_lacks = "java" if go_n > 0 else "go"
    return [Finding(36, "warn", bidder,
                    f"fixture-inventory asymmetry: {side_has} has {max(go_n, java_n)} fixtures, "
                    f"{side_lacks} has 0; per Rule 36 expect parallel coverage")]


# Wave 11b B5 #8: rule_38_bidder_params_byte_fidelity DELETED.
# Rule 38 the principle (Java MUST copy Go's bidder_params bytes verbatim)
# remains documented in port-translation-rules.md:45-77 as a load-bearing
# port-translation rule. The runtime gate is in round-trip-ci.py's R5
# bidder_params_sha256 check (dual-spec-aware byte-divergence reporting).
# This lint's prior implementation was redundant with R5 and noisy (13/14
# pairs warned with no actionable distinction between declared-divergence
# and undeclared-divergence). Cleanly removed; Rule 38 entry left out of
# RULE_TITLES so summary printout omits it without crashing.


def rule_44_alias_empire(go: dict, java: dict, java_parent_specs: dict) -> list[Finding]:
    """Verify alias-empire parent-flavor coherence (refines Rule 33 for empire cases)."""
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    is_alias = _path(go, "meta", "is_alias") or _path(java, "meta", "is_alias")
    if not is_alias:
        return []
    parent_name = _path(go, "meta", "alias_of") or _path(java, "meta", "alias_of")
    if not parent_name:
        return []  # already flagged by Rule 33

    java_flavor = _path(java, "meta", "empire_parent_flavor")
    if not java_flavor:
        return []  # not classified as an empire (yet)

    parent_spec = java_parent_specs.get(parent_name)
    if parent_spec is None:
        return [Finding(44, "pass", bidder,
                        f"empire alias of {parent_name!r} (flavor={java_flavor!r}); parent spec not in scope")]

    parent_aliases = _path(parent_spec, "aliases") or []
    matching = None
    for a in parent_aliases:
        if isinstance(a, dict) and a.get("name") == bidder:
            matching = a
            break
        if a == bidder:
            matching = {"name": a}
            break
    if matching is None:
        return [Finding(44, "warn", bidder,
                        f"empire-alias asymmetry: Java parent {parent_name!r}.aliases[] does not list {bidder!r}")]

    relationship_flavor = matching.get("relationship_flavor") if isinstance(matching, dict) else None
    if relationship_flavor and relationship_flavor != java_flavor:
        return [Finding(44, "warn", bidder,
                        f"empire-flavor mismatch: child meta.empire_parent_flavor={java_flavor!r} but "
                        f"parent.aliases[{bidder!r}].relationship_flavor={relationship_flavor!r}")]
    return [Finding(44, "pass", bidder,
                    f"empire alias coherent: {bidder!r} ↔ {parent_name!r} (flavor={java_flavor!r})")]


def rule_46_naming_normalization(go: dict, java: dict, dual_spec: Optional[dict] = None) -> list[Finding]:
    """Verify naming-convention normalization (mechanical formula or declared exception)."""
    go_name = _path(go, "meta", "bidder_name")
    java_name = _path(java, "meta", "bidder_name")
    bidder = go_name or java_name or "unknown"
    if not go_name or not java_name:
        return []
    if go_name == java_name:
        return [Finding(46, "pass", bidder, "names identical; rule trivially satisfied")]

    expected_java = go_name.lower().replace("_", "").replace("-", "")
    if java_name == expected_java:
        if "_" in go_name:
            transformation = "underscore-drop"
        elif "-" in go_name:
            transformation = "hyphen-drop"
        else:
            transformation = "lowercase"
        return [Finding(46, "pass", bidder,
                        f"Rule 46 mechanical formula matches ({transformation}): {go_name!r} → {java_name!r}")]

    # Allow-list: digit-leading bidders (e.g., 33across, 152media)
    if go_name and go_name[0].isdigit():
        return [Finding(46, "pass", bidder,
                        f"Rule 46 digit-leading-workaround accepted: {go_name!r} → {java_name!r}")]

    # Allow-list: brand-acronym-preservation declared in dual-spec
    if dual_spec:
        transformation = _path(dual_spec, "naming_asymmetry", "transformation")
        if transformation == "brand-acronym-preservation":
            return [Finding(46, "pass", bidder,
                            f"Rule 46 brand-acronym-preservation declared: {go_name!r} → {java_name!r}")]

    return [Finding(46, "warn", bidder,
                    f"Rule 46 violation: go={go_name!r} → expected java={expected_java!r}, got java={java_name!r}; "
                    f"declare exception in dual-spec naming_asymmetry block "
                    f"(transformation: digit-leading-workaround | brand-acronym-preservation)")]


def lint_pair(go_spec: dict, java_spec: dict, dual_spec: Optional[dict] = None,
              java_parent_specs: Optional[dict] = None) -> list[Finding]:
    """Run all 7 per-pair lints on one Go/Java spec pair."""
    java_parent_specs = java_parent_specs or {}
    findings: list[Finding] = []
    findings.extend(rule_5_mutation_strategies(go_spec, java_spec))
    findings.extend(rule_9_custom_request_body(go_spec, java_spec))
    findings.extend(rule_33_alias_inversion(go_spec, java_spec, java_parent_specs))
    findings.extend(rule_36_test_fixture_parity(go_spec, java_spec))
    # Rule 38 deleted in Wave 11b B5 #8; runtime gate is round-trip-ci.py R5.
    findings.extend(rule_44_alias_empire(go_spec, java_spec, java_parent_specs))
    findings.extend(rule_46_naming_normalization(go_spec, java_spec, dual_spec))
    return findings


def discover_pairs(
    go_dir: Path = GOLDENS_GO,
    java_dir: Path = GOLDENS_JAVA,
    dual_dir: Path = DUAL_SPEC_DIR,
) -> tuple[list[tuple[str, dict, dict, Optional[dict]]], list[Finding]]:
    """Find bidders with both Go and Java goldens; load each + optional dual-spec.

    Returns:
        (pairs, errors) where:
          - pairs: list of (bidder, go_spec, java_spec, dual_spec_or_None)
          - errors: list of Finding(rule_id=0, severity="fail", ...) for any
            per-file YAML/IO failures encountered. Pairs that fail to load
            are EXCLUDED from `pairs` (the lint can't run on a broken pair),
            but the failure is surfaced as a Finding so main() can report it.

    Raises:
        FileNotFoundError when either GOLDENS_GO or GOLDENS_JAVA directory
        is missing entirely. Wave 11b B4 C3 fix: prior code returned an
        empty list silently on missing dirs, masking environment misconfig
        as "no pairs to lint" (exit 0 success). Now refused at the source.
    """
    if not go_dir.is_dir():
        raise FileNotFoundError(f"Go fixtures directory not found: {go_dir}")
    if not java_dir.is_dir():
        raise FileNotFoundError(f"Java fixtures directory not found: {java_dir}")

    pairs: list[tuple[str, dict, dict, Optional[dict]]] = []
    errors: list[Finding] = []

    go_files = {f.stem.replace(".golden.spec", ""): f for f in go_dir.glob("*.golden.spec.yaml")}
    java_files = {f.stem.replace(".golden.spec", ""): f for f in java_dir.glob("*.golden.spec.yaml")}

    for bidder in sorted(set(go_files) & set(java_files)):
        try:
            with open(go_files[bidder]) as fp:
                go = yaml.safe_load(fp)
        except (OSError, yaml.YAMLError) as exc:
            errors.append(Finding(0, "fail", bidder,
                f"failed to load go golden {go_files[bidder].name}: {type(exc).__name__}: {exc}"))
            continue
        try:
            with open(java_files[bidder]) as fp:
                java = yaml.safe_load(fp)
        except (OSError, yaml.YAMLError) as exc:
            errors.append(Finding(0, "fail", bidder,
                f"failed to load java golden {java_files[bidder].name}: {type(exc).__name__}: {exc}"))
            continue
        dual_path = dual_dir / f"{bidder}.dual-spec-assertions.yaml"
        dual: Optional[dict] = None
        if dual_path.is_file():
            try:
                with open(dual_path) as fp:
                    dual = yaml.safe_load(fp)
            except (OSError, yaml.YAMLError) as exc:
                errors.append(Finding(0, "fail", bidder,
                    f"failed to load dual-spec {dual_path.name}: {type(exc).__name__}: {exc}"))
                # Don't `continue` — the pair lint can still run with dual=None;
                # only the dual-spec-aware rules will skip. The error finding
                # surfaces the load failure independently.
                dual = None
        pairs.append((bidder, go, java, dual))
    return pairs, errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--bidder", help="Lint a single bidder")
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (exit 1 instead of 2)")
    parser.add_argument("--quiet", action="store_true",
                        help="Print only the summary, not per-finding output")
    parser.add_argument("--json", action="store_true",
                        help="Emit machine-parseable JSON instead of human-readable text "
                             "(same shape as round-trip-ci.py --json: findings[] carry "
                             "rule/spec/severity/detail)")
    args = parser.parse_args(argv)

    try:
        pairs, load_errors = discover_pairs()
    except FileNotFoundError as exc:
        print(f"FATAL: {exc}", file=sys.stderr)
        return 1
    if args.bidder:
        pairs = [p for p in pairs if p[0] == args.bidder]
        load_errors = [e for e in load_errors if e.bidder == args.bidder]
        if not pairs:
            print(f"No pair found for bidder {args.bidder!r}", file=sys.stderr)
            return 1

    # Build map of Java parent specs (any non-alias Java spec is a candidate parent)
    java_parents: dict[str, dict] = {}
    for bidder, _, java, _ in pairs:
        if not _path(java, "meta", "is_alias"):
            java_parents[bidder] = java

    if not args.json:
        print("=== Port-rule lint (Phase 2.6) ===")
        print(f"Pairs scanned: {len(pairs)}")
        if pairs:
            print(f"  bidders: {', '.join(p[0] for p in pairs)}")
        if load_errors:
            print(f"Load errors: {len(load_errors)} (rule_id=0 fail entries)")
        print()

    # Seed findings with any per-file load errors from discover_pairs.
    all_findings: list[Finding] = list(load_errors)
    for bidder, go, java, dual in pairs:
        findings = lint_pair(go, java, dual, java_parents)
        all_findings.extend(findings)

    counts: dict[int, dict[str, int]] = {}
    for f in all_findings:
        counts.setdefault(f.rule_id, {"pass": 0, "warn": 0, "fail": 0})
        counts[f.rule_id][f.severity] += 1

    total_fail_json = sum(c["fail"] for c in counts.values())
    total_warn_json = sum(c["warn"] for c in counts.values())
    if args.json:
        exit_code = 1 if total_fail_json else (
            (1 if args.strict else 2) if total_warn_json else 0)
        print(json.dumps({
            "pairs_scanned": len(pairs),
            "bidders": [p[0] for p in pairs],
            "rules": {
                str(rule_id): counts.get(rule_id, {"pass": 0, "warn": 0, "fail": 0})
                for rule_id in sorted(RULE_TITLES)
            },
            # `rule` is stringified as "Rule N" so the key shape matches
            # round-trip-ci.py --json findings and one baseline checker can
            # consume both without special-casing.
            "findings": [
                {"rule": f"Rule {f.rule_id}", "spec": f.bidder,
                 "severity": f.severity, "detail": f.message}
                for f in all_findings
            ],
            "summary": {
                "pass": sum(c["pass"] for c in counts.values()),
                "warn": total_warn_json,
                "fail": total_fail_json,
                "exit_code": exit_code,
            },
        }, indent=2))
        return exit_code

    if not args.quiet:
        for f in all_findings:
            if f.severity != "pass":
                print(f.format())
        if any(f.severity != "pass" for f in all_findings):
            print()

    print("=== Summary by rule ===")
    for rule_id in sorted(RULE_TITLES):
        c = counts.get(rule_id, {"pass": 0, "warn": 0, "fail": 0})
        title = RULE_TITLES[rule_id]
        print(f"  Rule {rule_id:2d} {title:<55} pass={c['pass']:2d} warn={c['warn']:2d} fail={c['fail']:2d}")

    total_pass = sum(c["pass"] for c in counts.values())
    total_warn = sum(c["warn"] for c in counts.values())
    total_fail = sum(c["fail"] for c in counts.values())
    print(f"\nOVERALL: {total_pass} pass, {total_warn} warn, {total_fail} fail")

    if total_fail > 0:
        return 1
    if total_warn > 0:
        return 1 if args.strict else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
