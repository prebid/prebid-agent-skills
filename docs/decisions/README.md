# Architecture Decision Records (ADRs)

This directory captures non-obvious decisions made during PR review and planning so they survive between planning sessions and execution. Each ADR documents one decision; together they form a chronological log of the project's design rationale.

## Format

```markdown
# ADR-NNN: <decision title>

**Date**: YYYY-MM-DD
**Status**: Proposed | Accepted | Rejected | Superseded by ADR-XXX
**Context**: <what problem>
**Options considered**: <list>
**Decision**: <choice>
**Consequences**: <implications>
**References**: <PR refs, related ADRs, evidence>
```

## When to write an ADR

- A schema field is added, removed, or renamed
- A port-translation rule is added, modified, or sub-categorized
- A worked example or master sample changes its canonical interpretation
- An earlier decision is reversed (mark old ADR `Superseded`, write new ADR)
- A non-trivial naming/structural choice is made (e.g., directory layout, file format)

## Index

| # | Title | Status |
|---|---|---|
| [ADR-001](001-phase-2-schema-field-additions.md) | Phase 2 schema field additions: code_naming, injection rename, shared-genesis, schain_movement, lifecycle.rename sub-fields, 22-phantom-path resolutions, SemVer version format | Accepted |
| [ADR-002](002-bidder-constant-and-bean-dependencies.md) | bidder_constant_referenced semantics & kobler bean_dependencies — reversing Round-2 verdicts | Accepted |
| [ADR-003](003-rule-44-alias-empire-consolidation.md) | Rule 44: Java alias-empire consolidation pattern | Accepted |
| [ADR-004](004-rule-45-disabled-by-default-java-alias.md) | Rule 45: Disabled-by-default Java alias pattern | Accepted |
| [ADR-005](005-rule-46-naming-convention-normalization.md) | Rule 46: Naming-convention normalization (Java lowercases Go camelCase/snake_case) | Accepted |
| [ADR-006](006-rule-43-sub-categorization.md) | Rule 43 sub-categorization: bilateral / java-leads / go-leads / mirror-topology / inverted-parent lifecycle renames (5 subtypes; refined 2026-05-03 from 3 — `synchronized` renamed to `bilateral` in audit A5; `mirror-topology` and `inverted-parent` added per Phase 5 empirical evidence) | Accepted |
| [ADR-007](007-novel-pattern-schema-additions.md) | Five new schema fields for novel patterns observed in diversity sample | Accepted |
| [ADR-008](008-phase-5-pair-fixtures.md) | Phase 5 expanded pair fixtures: 7 new pairs (smarthub, teqblaze, adverxo, limelightDigital, vungle [refined 2026-05-03 from vungle/liftoff cross-name], emxdigital/cadent_aperture_mx, adkernelAdn/adkerneladn) — 9.5 days P1-P3 | Accepted |
| [ADR-009](009-lean-conformance-doctrine.md) | Lean-conformance doctrine for adapter ports: emit only the canonical corpus; fuzz/bench/doc.go are dev-time aids, not PR artifacts; target-conformance beats source-fidelity; ADR every reversal. Reverses the prior "above-and-beyond" emit mandate after the Teal #4765 review. | Accepted (execution in progress) |
| [ADR-010](010-rules-47-49-effective-value-emission.md) | Rules 47/48/49 from the rtbstack Go→Java port: grouped-by-key batching, param-derived endpoint macros, and opposite-framework-default config keys. Effective-value emission for adapter-default-backed `bidder_info` fields; Rule 48's first cut taught the pattern upstream review rejected. | Accepted |

ADRs 001–008 are `Accepted` as of 2026-05-03; corresponding execution is complete (Phase 1 corrections, Phase 2 schema migration, Phase 5 fixture authoring, Wave 3 ADR-007 schema additions, Wave 7 status flips). Per-ADR bodies record individual execution evidence and any post-execution refinements (ADR-005, ADR-006, ADR-007 carry refinement annotations from Phase 5 + 2026-05-03 audit). See CHANGELOG.md for the version-bump history.

ADR-009 (2026-06-03) is the first **doctrine-level** decision (vs the schema/rule-level ADRs 001–008). It reverses the prior "above-and-beyond" emit strategy documented in `ROADMAP.md`, `docs/methodology/canary-runbook.md`, and `docs/runs/d3.8-teal-reflection.md`; its execution is the multi-phase port-skills hardening program (Phase 0 = this ADR; Phases 1–2 pending). None of ADRs 001–008 are superseded.

ADR-010 (2026-08-19) is the first ADR minted from an upstream-submitted port rather than from a corpus audit. It records the measured finding that 14 of 20 Java goldens hold `false` for a `modifying-vast-xml-allowed` key absent upstream, where the Java framework's absent-key semantics make it effective `true` — so the reader-side decision it defers has a known cost, not a hypothetical one. It supersedes nothing.

## Pre-execution audit corrections (2026-05-02)

All 8 ADRs were audited for technical misassumptions before execution kickoff. The corrections are inline in each ADR. Summary of changes:

- **ADR-001**: Added D6 (22 phantom-path resolutions), D7 (SemVer string format), JSON Schema terminology note
- **ADR-003**: Replaced `cross_language.empire` block with `meta.empire_*` + `aliases[].relationship_flavor` (eliminates redundancy with existing fields)
- **ADR-004**: Moved Rule 45 cross-language facts to dual-spec assertion format (per-language reader can't know other side)
- **ADR-005**: Same architectural move for Rule 46 — `naming_asymmetry` lives in dual-spec, not per-language spec
- **ADR-006**: Renamed `synchronized` sub-type to `bilateral` (Adoppler→ElementalTV is 52 days apart, not lockstep)
- **ADR-007**: Added array ordering policy for R4 round-trip determinism
- **ADR-008**: Effort revised down (P1-P3: 11.5 → 9.5 days) — empire parents use flat `parent_aliases` lists, not per-alias-child specs

The execution plan (`../execution-plan.md`) carries the full audit summary with B/C-tier corrections (Phase 3 effort up to 5 days; Makefile + templates added to Phase 4; CHANGELOG to Phase 2.7; etc.).
