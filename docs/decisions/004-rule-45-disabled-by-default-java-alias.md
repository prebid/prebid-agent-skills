# ADR-004: Rule 45 — Disabled-by-Default Java Alias

**Date**: 2026-05-02 (refined 2026-05-02 audit A1 — moved cross-language facts from per-language spec to dual-spec assertion format)
**Status**: Accepted (Phase 2 executed — Rule 45 lives at `port-translation-rules.yaml`/.md; rendered count 46)
**Context**: Round 3 inventory revealed 78 cross-language disabled-asymmetric bidders (Java disabled by default, Go enabled — or vice versa for ~6 cases). The pattern is systematic: Java's empire children typically ship `enabled: false`, requiring publishers to opt in. Go's aliases ship enabled by default. This asymmetry is real and common but no current rule names it.

## Decision

**Rule 45: Disabled-by-Default Java Alias.** Java alias children of empire parents typically ship with `enabled: false` in the parent's YAML `aliases:` block; publishers opt in by setting `enabled: true` in the deployment config. Go counterparts of the same alias typically ship enabled. This is **not** a port-fidelity violation — it's a Java-side default policy that operators expect.

**Statistical evidence** (Round 3 inventory):
- 78 cross-language pairs with mismatched `default_enabled` values
- 72 of them follow the pattern: Go-enabled, Java-disabled (the canonical Rule 45 case)
- 6 inverse cases: Go-disabled, Java-enabled (e.g., adagio, audienceNetwork, avocet, dianomi, epom, mgidX) — typically reflect Go-side default-off due to white-label/legal concerns; Java enables

**Spec field drivers** (refined 2026-05-02 audit A1 — cross-language facts live in dual-spec, not per-language spec):

- **Per-language spec**: `bidder_info.default_enabled` (existing) records the bidder's own state. No new per-language fields. A Go-side reader doesn't know the Java side's value at read time, so per-language `cross_language.default_enabled_asymmetric*` would always be null-on-write.

- **Per-language quirk** (NEW taxon): `quirks[].edge_case_taxon: disabled-by-default-empire-alias` — emitted on the side that ships disabled (typically Java alias children). Carries the local rationale (e.g., "publisher must opt in").

- **Dual-spec assertion file** (existing format): `bidder_info_default_enabled` block already accommodates this:
  ```yaml
  bidder_info_default_enabled:
    go: true
    java: false
    equivalent: false
    divergence_summary: "Java alias child ships enabled=false per Rule 45; publisher opt-in expected."
    severity: pass                              # Pass because divergence is expected per Rule 45.
    rule_45_match: go-enabled-java-disabled     # NEW field on dual-spec block.
  ```

**R5 dual-spec handling**: `default_enabled` is already in `R5_DIVERGENT_KEYS` (`round-trip-ci.py:678+`). Rule 45 documents WHY this is divergent (it's expected, not a bug). The new `rule_45_match` value on the dual-spec block carries the canonical direction; R5 emits `WARN` only if the assertion declares `severity: pass` while runtime values disagree about direction (e.g., assertion claims go-enabled-java-disabled but runtime shows the inverse — stale-assertion).

**Rationale for moving to dual-spec**: A Go-only or Java-only orchestrator can't populate cross-language assertions; the dual-spec file is the natural cross-language joiner. ADR-005 makes the same architectural move for Rule 46.

## Master samples

- **Canonical (`go-enabled-java-disabled`)**: optidigital (already covered in our golden — see `cross-language-pairs/optidigital.dual-spec-assertions.yaml` `bidder_info_default_enabled` block).
- **Mass evidence**: 72 alias-empire children — adport, adsinteractive, adport, etc. (all the Java empire aliases).
- **Inverse (`go-disabled-java-enabled`)**: adagio (Go: `disabled: true`, Java: `enabled: true`); audienceNetwork; avocet.

## Mechanizability

**Yes, partially mechanizable**. The lint can verify:
1. If `meta.is_alias=true` AND `cross_language.empire.flavor` is one of `white-label-saas` or `registration-only`, expect `default_enabled_asymmetric_direction: go-enabled-java-disabled`. Other flavors and non-aliases: no expectation.
2. Inverse cases (`go-disabled-java-enabled`) MUST carry a paired `quirks[]` entry with taxon `default-enabled-go-disabled-justified` documenting why (white-label, legal restriction, etc.).

## Consequences

- Phase 2 adds Rule 45 to `port-translation-rules.yaml`
- Phase 2 adds `rule_45_match: go-enabled-java-disabled | go-disabled-java-enabled | n/a` field to **dual-spec** assertion files (NOT to per-language spec)
- Phase 2 adds two new taxa: `disabled-by-default-empire-alias` (canonical case, paired on Java side) + `default-enabled-go-disabled-justified` (inverse case, paired on Go side)
- R5 logic stays as-is — Rule 45 documents the expected asymmetry; doesn't change CI behavior
- All 7 existing dual-spec assertion files get migrated to add `rule_45_match` field where applicable (mostly `n/a` for the 7 existing pairs since none cleanly hit the canonical case)

## References

- Round 3 inventory: 78 disabled-asymmetric pairs across 350+330 cross-language bidders
- Existing optidigital golden + `optidigital.dual-spec-assertions.yaml` (R5 `bidder_info_default_enabled` block already shows this pattern)
- Schema field `bidder_info.default_enabled` exists at `adapter-spec.md` (current schema)
- Related taxa: `enabled-false-default` (`prebid-server-java/references/new-bid-adapter-prs.md` Pattern Index) — already used for #4054 (optidigital)
