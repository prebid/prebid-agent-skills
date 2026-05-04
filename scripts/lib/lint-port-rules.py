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
  Rule 33 — Aliases inversion
            (Go child's `aliasOf:` ↔ Java parent's `aliases[]` block)
  Rule 36 — Test fixture inventory parity
            (both languages have non-empty fixture inventories)
  Rule 38 — bidder_params_sha256 byte-equality
            (re-reports R2/R5 with explicit Rule 38 framing)
  Rule 44 — Java alias-empire parent-flavor coherence
            (alias's `meta.empire_parent_flavor` matches parent's `aliases[].relationship_flavor`)
  Rule 46 — Naming-convention normalization
            (`go_name.lower().replace('_','').replace('-','') == java_name`,
            with digit-leading-workaround / brand-acronym-preservation allow-listed)

Each finding is a tuple of (rule_id, severity, bidder, message).
Severities: `pass` | `warn` | `fail`.

NOTE on severity (Wave 11b will tighten): no rule currently emits the
`fail` severity in default mode — every violation is a `warn`. The exit-1
"always blocking" branch below activates only when `--strict` is passed
or if a future rule is promoted to fail-severity. CI does NOT pass
`--strict` by default. Wave 11b plan B5 finding-8 promotes Rule 38
(sha-equality, contractual) and Rule 33 (alias inversion structural
correctness) to fail-severity.

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
import sys
from pathlib import Path
from typing import Any, NamedTuple, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDENS_GO = REPO_ROOT / "prebid-server-go" / "read" / "test-fixtures"
GOLDENS_JAVA = REPO_ROOT / "prebid-server-java" / "read" / "test-fixtures"
DUAL_SPEC_DIR = REPO_ROOT / "cross-language-pairs"

RULE_TITLES = {
    5: "Site/App mutation strategy pairing",
    9: "Custom-typed request body coherence",
    33: "Aliases inversion (Go child ↔ Java parent.aliases[])",
    36: "Test fixture inventory parity",
    38: "bidder_params_sha256 byte-equality",
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


# Rule 5: valid (go, java) entity_strategy pairings for Site/App scrubbing
_RULE_5_VALID_PAIRS = {
    ("copy-then-mutate", "immutable-rebuild"),
    ("in-place", "immutable-rebuild"),
    (None, None),
}


def rule_5_mutation_strategies(go: dict, java: dict) -> list[Finding]:
    """Verify Site/App entity_strategies pair correctly across languages."""
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    findings: list[Finding] = []
    for entity in ("Site", "App"):
        go_strat = _normalize_strategy(_path(go, "code", "make_requests", "mutation", "entity_strategies", entity))
        java_strat = _normalize_strategy(_path(java, "code", "make_requests", "mutation", "entity_strategies", entity))
        if go_strat is None and java_strat is None:
            continue  # not applicable on either side; rule silent
        if (go_strat, java_strat) in _RULE_5_VALID_PAIRS:
            findings.append(Finding(5, "pass", bidder,
                                    f"entity_strategies.{entity} pair OK: go={go_strat!r} java={java_strat!r}"))
        else:
            findings.append(Finding(5, "warn", bidder,
                                    f"entity_strategies.{entity} pair unexpected: go={go_strat!r} java={java_strat!r}; "
                                    f"per Rule 5, expect copy-then-mutate↔immutable-rebuild (or in-place↔immutable-rebuild)"))
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
        return [Finding(33, "warn", bidder, "is_alias=true but meta.alias_of is null/missing")]

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
    return [Finding(33, "warn", bidder,
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


def rule_38_bidder_params_byte_fidelity(go: dict, java: dict) -> list[Finding]:
    """Verify bidder_params_sha256 matches across languages."""
    bidder = _path(go, "meta", "bidder_name") or _path(java, "meta", "bidder_name") or "unknown"
    go_sha = go.get("bidder_params_sha256")
    java_sha = java.get("bidder_params_sha256")

    if not go_sha and not java_sha:
        return []  # both absent — no bidder params on either side
    if go_sha and java_sha:
        if go_sha == java_sha:
            return [Finding(38, "pass", bidder, f"bidder_params_sha256 byte-equal: {go_sha[:16]}…")]
        return [Finding(38, "warn", bidder,
                        f"bidder_params_sha256 byte divergence: go={go_sha[:16]}… java={java_sha[:16]}…; "
                        f"per Rule 38 the bytes MUST match (R2/R5 also enforce this)")]
    side_has = "go" if go_sha else "java"
    side_lacks = "java" if go_sha else "go"
    return [Finding(38, "warn", bidder,
                    f"one-sided bidder_params_sha256: {side_has} has it, {side_lacks} does not; "
                    f"per Rule 38 both sides must declare and bytes must match")]


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
    findings.extend(rule_38_bidder_params_byte_fidelity(go_spec, java_spec))
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
    for bidder, _go, java, _dual in pairs:
        if not _path(java, "meta", "is_alias"):
            java_parents[bidder] = java

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
