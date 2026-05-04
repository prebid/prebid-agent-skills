# Execution Plan: Hardening the Read-Skill Suite for Phase D

**Status**: Draft (planning complete; ready for execution)
**Date**: 2026-05-02
**Scope**: Phases 0-5 covering restoration → schema spine → conciseness → methodology → pair fixtures, in preparation for Phase D (porting skills) per `ROADMAP.md`.

This plan integrates findings from the 3-round PR review, the cross-language adapter inventory (358 Go + 350 Java bidders), the empire/lifecycle/diversity deep-dives, and the 8 ADRs in `docs/decisions/`. It supersedes the original mid-conversation plan with data-grounded prioritization.

## Five guiding principles

1. **Replace, don't append.** Edit wrong content in place; no corrective footnotes.
2. **Single source of truth.** Every fact has exactly one home; everything else `$ref`s.
3. **Data over prose.** Closed enums, taxa, rules become JSON Schema / YAML; prose generates.
4. **CI catches drift.** Every fact has a gate.
5. **Evolution is automated.** Drift detection, PR ingestion, gap reports run on schedule.

## Phases at a glance

| Phase | Effort | Net LOC | Outcome |
|---|---|---|---|
| 0 — Frontmatter standardization | 0.5 day | +20 | All SKILLs versioned `1.0.0` SemVer |
| 1 — Restoration | 2 days | -50 / +30 | All H/M bugs fixed; CI gating restored |
| 1.5 — Golden audit | 1.5 days | TBD per audit | All 40 goldens pass upstream-faithfulness check |
| 2 — Schema spine | 4 days | -1,500 / +1,000 | JSON Schema authoritative; new fields per ADR-001/007; Rules 44-46 land |
| 3 — Conciseness | 5 days | -2,500 / +800 | SKILLs ≤250 lines; 10 mechanical scripts in `scripts/lib/` (revised up from 3 days per audit B5) |
| 4 — Methodology | 3 days | +1,500 | Drift detection, PR audit, coverage report, CI gates, `Makefile`, `templates/empty-adapter-spec.yaml` |
| 5 — Pair fixtures | 9.5 days (P1-P3) | +1,800 | 7 new pairs cover Rules 43-46; empire coverage 5→8 of 32 (revised down from 11.5 days per audit B1) |

**Total**: ~28 working days (revised from 25.5 after audit). Net delta: ~+780 LOC (loss in prose, gain in machine-checked artifacts).

## Pre-execution audit corrections applied (2026-05-02)

Before kickoff, the plan was audited for technical misassumptions. Five critical, six important, and ten nice-to-flag items were identified and resolved. Key corrections incorporated:

- **A1, A2** — Cross-language asymmetry facts (Rule 45 `default_enabled`, Rule 46 `naming_asymmetry`) live in **dual-spec assertion file format**, NOT per-language spec. A Go-only orchestrator can't know the Java side's value at read time. Updated ADR-004, ADR-005.
- **A3** — JSON Schema 2020-12 has no `discriminator` keyword (that's OpenAPI). Java-only blocks use `if/then/else` keyed on `source_language` `const`-value. Updated ADR-001.
- **A4** — Phantom-path resolutions extended to cover all 36 of the truly-undocumented paths from Round 3, not just the 14 in D1/D4/D5. Updated ADR-001 with new D6.
- **A5** — Rule 43's "synchronized" sub-type renamed to `bilateral` (Adoppler→ElementalTV is 52 days apart between Go and Java — bilateral cooperation, not lockstep). Updated ADR-006.
- **B1** — Phase 5 effort revised down from 11.5 to 9.5 days (P1+P2+P3). Empire-parent goldens use flat `parent_aliases` lists, not per-alias-child specs. Updated ADR-008.
- **B5** — Phase 3 effort revised up from 3 to 5 days (10 scripts × 0.25-1 day each + consolidation = ~5 days). Updated execution plan above.
- **B6** — `cross_language.empire` block replaced with `meta.empire_canonical_master`/`meta.empire_parent_flavor` + `aliases[].relationship_flavor`. Eliminates redundancy with existing `meta.alias_of` and `aliases[]` structures. Updated ADR-003.
- **C7** — Array ordering policy (logical, not lexicographic) added for new array fields (`endpoints[]`, `language_stamped_headers[]`, `bid_post_processing.macros[]`). Updated ADR-007.
- **C8** — Phase 5 fixtures MUST verify cited PR refs via `gh pr view` before commit (some round-3 agent claims were unverified — e.g., freewheelssp Go #2392 / Java #2251). Updated ADR-008.
- **C2, C3, C9** — `CHANGELOG.md` (Phase 2.7), `Makefile` (Phase 4 start), `templates/empty-adapter-spec.yaml` (Phase 4) added to plan.

## Phase 0 — Frontmatter standardization (precursor, 0.5 day)

Standardize `version: "1.0.0"` (SemVer string) on all 8 read-skill `SKILL.md` files. Document version-bump policy in `CONTRIBUTING.md` (additive → minor; user-visible change → minor; schema-affecting → major). One commit.

Per ADR-001 D7, all `*_version` fields across the project (SKILL frontmatter, golden specs' `adapter_spec_version`, `taxonomy_version`, `port_translation_rules_version`) use the SemVer string format `"X.Y.Z"`.

## Phase 1 — Restoration (2 days, 11 commits)

Surgical fixes from Round 3 verification. Each commit is independently revertible. Tests stay green.

| # | Commit | Files | Scope |
|---|---|---|---|
| 1.1 | Rule-count drift fix | `cross-skill-integration.md:327`, `review-pattern-transfer-policy.md:97,178` | "37" → "43" (3 sites). NOTE: Phase 2.5 will subsequently bump to 46 when Rules 44-46 land. Sequencing per audit B2: fix to current state (43) first; bump to 46 in Phase 2 commit. |
| 1.2 | H5 R7 PascalCase rule | `provenance-warnings.md:35-37` | Replace prose with bidders.go ground-truth lookup |
| 1.3 | R9 broken test fix | `test_round_trip_ci.py:398` | `hasattr(rtci, "r_legacy_encoding_check")` → `True`; assertion fires |
| 1.4 | Kobler bean_dependencies reference fix (per ADR-002) | `spring-config-patterns.md:30-37`, `:250-256` | Both quoted Java code blocks → upstream order |
| 1.5 | bidder_constant_referenced reference fix (per ADR-002) | `schema-interpretation.md:365` | "TestValidParams primary" → "last-observed wins" |
| 1.6 | Orchestrator file count claim removal | `read-adapter-orchestrator/SKILL.md:193` | Remove "(5+, 3, 4)"; cite per-bidder goldens |
| 1.7 | README count fixes | Both test-fixtures READMEs; `cross-language-pairs/README.md` | "10"→"12" Go; "four of sixteen" → "thirteen of sixteen" |
| 1.8 | `hardcoded-toggle` enum addition | `read-bidder-config/SKILL.md:87` | Add 9th enum value |
| 1.9 | Taxonomy false Rule 5 citation fix | `behavior-taxonomy.md:174` | Delete fabricated citation; replace with two-distinct-enums note |
| 1.10 | R6 alias suppression | `scripts/round-trip-ci.py r6_check` + new test | Suppress R6 warn when `meta.is_alias=true` |
| 1.11 | CI workflow restoration | `.github/workflows/round-trip-ci.yml`, `.github/known-broken-pairs.txt` | Run unittest + round-trip-ci `--strict-r3 --allow-known-broken-pairs <list>` + schema-contract. Per audit C5: `--allow-known-broken-pairs` reads `.github/known-broken-pairs.txt` (one bidder per line). Initial entry: `aax`. |

**End state**: every Round-3-verified bug is closed. CI gates restored. Tests still green.

## Phase 1.5 — Golden audit (1.5 days, 1-3 commits)

Author `scripts/audit-golden.py <bidder>` — a **deterministic-subset** of the orchestrator's mechanical checks (per audit B3). The script does NOT run the full Claude SKILL; it encodes the byte-fact checks:

- Re-fetches `static/bidder-info/<bidder>.yaml` at the pinned commit; SHA-256 compare against golden's recorded SHA
- Re-fetches `static/bidder-params/<bidder>.json`; verify `bidder_params_sha256` matches
- Lists files in `adapters/<bidder>/`; cross-checks against `code.file_layout.files[]`
- Re-checks fixture inventory by directory listing
- Reports diffs as `docs/audits/golden-audit-<date>.md`

Run on all 40 goldens; fix any inaccuracies discovered before schema migration locks them in. Round 2 spot-checked 4 bidders manually; Phase 1.5 covers the remaining 36 mechanically.

For LLM-required work (novelty classification, new-pattern surfacing), Phase 4.2's `audit-pr.py` is a separate workflow that calls the Claude API.

## Phase 2 — Schema spine (4 days, 1 large PR with staged commits)

The structural transformation. Per ADRs 001, 003-007.

### 2.0 — Prove on kobler

Author `adapter-spec.schema.json` covering kobler's spec shape only. Validate kobler-Go and kobler-Java goldens. Iterate until clean.

### 2.1 — Full JSON Schema

Encode the full schema using `$defs` for `Helper`, `FixtureFile`, `Quirk`, etc. Per audit A3: use JSON Schema 2020-12 `if/then/else` keyed on `source_language` `const`-value for Java-only blocks (`spring_config`, `bidder_class`, `code_naming`, `lifecycle`). Avoid OpenAPI's `discriminator` keyword (not part of JSON Schema). Per audit C6: use `{"type": ["string", "null"]}` for nullable fields, NOT `nullable: true`.

Apply ADR-001 field decisions:
- D1 — `code_naming` top-level
- D2 — rename `iab_category_storage.injection` → `delivery_mechanism`
- D3 — add `shared-genesis` to `port_lineage.source_language` enum
- D4 — add `mutation.schain_movement` block
- D5 — add `lifecycle.rename` sub-fields (package_moves, fixture_dir_moves, subtype, merged_at, release)

Apply ADR-007 schema additions:
- F1 — `endpoint_resolution.endpoints[]` (multi-endpoint)
- F2 — `headers_constructed.language_stamped` (+ `language_stamped_headers`)
- F3 — `mutation.entity_strategies.{Site,App}: synthesize-replacement` enum value
- F4 — `make_bids.bid_post_processing.macros[]`
- F5 — `imp_ext_unmarshal.strip_post_extraction`

Apply ADR-003 (refined per audit B6): add `meta.empire_canonical_master`, `meta.empire_parent_flavor`, `aliases[].relationship_flavor`. NOT a new top-level block — uses existing `meta` and `aliases[]` structures.

### 2.2 — Reduce `adapter-spec.md` to ~300 lines

Cut: 700 lines of YAML pseudo-code (encoded in JSON Schema now) + 400 lines of duplicated worked example. Keep: schema fork policy, validation rules R1-R10, single short worked example, link to schema.

### 2.3 — Goldens validate against schema

Add `validate_goldens_against_schema()` to `scripts/tests/test_schema_contract.py`. Run on all 40 goldens. Decide each of the 36 truly-undocumented paths per ADR-001 D1/D4/D5.

### 2.4 — Behavior taxonomy as data

Convert `behavior-taxonomy.md` (464 lines) → `behavior-taxonomy.yaml`. Generate `*.md` via `scripts/render-taxonomy.py`. Add new taxa from ADR-007: `multi-endpoint-by-mediatype`, `language-stamped-header-divergence`, `mediatype-context-rewrite-site-to-app`, `bid-post-processing-macro`, `imp-ext-strip-post-extraction`. Add `default-enabled-go-disabled-justified` per ADR-004.

### 2.5 — Port-translation rules as data

Convert `port-translation-rules.md` (1460 lines) → `port-translation-rules.yaml` keyed by rule ID. Each rule carries `master_samples_go[]`, `master_samples_java[]`, `dual_spec_coverage[]`, `mechanizable: bool`. Generate `*.md` via `scripts/render-rules.py`.

Add Rule 44 (ADR-003), Rule 45 (ADR-004), Rule 46 (ADR-005). Update Rule 43 with sub-types (`bilateral | java-leads | go-leads`, ADR-006). Bump rule count from 43 → 46 (per audit B2 sequencing).

**Audit C1 — Review-skill suite coordination check**: BEFORE Phase 2.5 commits, grep all `prebid-server-go/review/skills/` files for references to `behavior-taxonomy.md`, `port-translation-rules.md`, anchor names, and rule numbers. AFTER migration, verify all links/anchors still resolve. If review-skill prose references the old "37 rules" count, fix concurrently.

### 2.6 — Mechanizable rule lints

Implement `scripts/lib/lint-port-rules.py` for the 5 mechanizable rules: 5, 9, 33, 36, 38, plus the new 44 (alias-empire structural assertion) and 46 (naming-normalization mechanical check).

### 2.7 — Migrate goldens + CHANGELOG

Apply schema migrations to all 40 goldens:
- `iab_category_storage.injection` → `delivery_mechanism` (bulk rename)
- huaweiads-Java `code.naming.*` → `code_naming.*` (move block)
- huaweiads-Java `registry.test_application_properties.*` → `tests.test_application_properties.*` (rename per ADR-001 D6)
- huaweiads-Java `tests.unit_test_breakdown.*` validates against new OPEN_MAP declaration (no migration needed if format already open-map-compatible)
- appnexus-Go: `mutation.schain_movement.*` block now schema-validated
- elementaltv-Java: add `lifecycle.rename.subtype: bilateral` (per ADR-006 audit A5)
- rubicon-Java: `cross_language.port_lineage.source_language: shared-genesis` now valid
- All goldens: add `adapter_spec_version: "1.0.0"` and `taxonomy_version: "1.0.0"` (SemVer strings per ADR-001 D7)

**Audit C4 — Round-trip determinism on migrations**: After each golden migration commit, run `r4_check` against the migrated golden. If YAML reordering breaks byte-stability, adjust anchor/sort-keys settings. Document any changes in CHANGELOG.

**Audit C2 — CHANGELOG.md**: Phase 2.7 includes a `CHANGELOG.md` entry summarizing all schema changes (rename `injection→delivery_mechanism`, new fields F1-F5, Rules 44-46, Rule 43 sub-types).

**End state**: schema is machine-readable single source of truth. 40 goldens auto-validate. The 36 phantom paths are decided. Rules 44-46 land with master samples (Phase 5 fills in the goldens that pressure-test them). CHANGELOG documents the migration for future maintainers.

## Phase 3 — Conciseness (3 days, 5-7 commits)

Per the original Round 1 structural-agent recommendations. Now grounded in Phase 2's schema spine.

### 3.1 — Extract 10 mechanical scripts to `scripts/lib/`

Per the original plan: `compute-bidder-params-sha.py`, `extract-bidder-info-yaml.py`, `classify-endpoint.py`, `count-fixture-inventory.py`, `detect-multi-file-layout.py`, `extract-go-imports.py`, `extract-java-spring-config.py`, `compute-port-pair-sha-diff.py`, `generate-cross-language-path-stubs.py`, `detect-endpoint-macros.py`. Each ships with tests in `scripts/lib/tests/`.

### 3.2 — Consolidate duplicated tables

Move Java edge-case-#18-#34 catalog to `worked-examples/java-edge-cases.md`; delete from 3 SKILL files (~75 lines saved). Move Go edge-case mapping to canonical home.

Delete `read-adapter-orchestrator/references/output-format.md` (298 lines, 60% markdown skeleton). Replace with one-line "see test-fixtures/*.golden.spec.yaml".

### 3.3 — Each SKILL ≤250 lines

Cut "Sources" boilerplate, "Cross-language note" duplicates, "Edge cases" tables (already in references/), "Determinism" shell-block recipes (now in `scripts/lib/`).

**End state**: ~3,000 prose lines deleted. `read-bidder-params/SKILL.md` 378→200; `read-bidder-class/SKILL.md` 388→220.

## Phase 4 — Methodology infrastructure (3 days, 5-6 commits)

The durable layer that automates future evolution. Per ADRs and Round 1 structural recommendations.

### 4.0 — Make + templates (audit C3, C9)

Author `Makefile` with targets: `make ci` (run all checks), `make test` (unittest discover), `make audit-goldens` (Phase 1.5 script bulk-run), `make sync` (drift detection), `make coverage` (gap report). Author `templates/empty-adapter-spec.yaml` for new-bidder authoring (carries all required fields nulled with inline comments). One commit at start of Phase 4.

### 4.1 — Drift detection

`scripts/sync-from-upstream.py`: weekly job that fetches HEAD, diffs each pinned bidder against new commit, classifies (data-only / structural / breaking), generates PRs. `.github/workflows/upstream-sync.yml` runs Mondays.

Per audit B3, this is a **deterministic-subset** of the orchestrator's mechanical checks. The script does NOT run the full Claude SKILL — it encodes the byte-fact comparisons (file SHA, file lists, line counts) and reports diffs as `drift-report.json`/`drift-report.md`.

### 4.2 — PR learning ingestion

`scripts/audit-pr.py <PR-URL>`: classifies novelty against taxonomy, proposes new-taxon PR if pattern is novel. Documented workflow in `docs/methodology/pr-ingestion.md`.

Per audit C10: `audit-pr.py` requires Claude API access for novelty classification (LLM task). Optional manual invocation; not CI-blocking. CI offers PR audit only when `CLAUDE_API_KEY` env var is set. Manual invocation is the primary use mode.

### 4.3 — Coverage report

`scripts/coverage-report.py`: per-rule, per-empire, per-pair-coherency matrix. Output as Markdown table. Lists 27 uncovered Java empire parents, 8 uncovered lifecycle pairs, 1 uncovered Rule 46 master sample (closes during Phase 5).

### 4.4 — Schema versioning

ADR-equivalent in `docs/methodology/schema-versioning.md`: SemVer (additive minor, breaking major). Migration scripts at `scripts/migrate/`.

### 4.5 — Repo-rules tracking

`docs/methodology/repo-rules.md`: snapshot of upstream policies (white-label, GVL, naming) with provenance + update cadence policy.

### 4.6 — Rollback policy

`docs/methodology/rollback.md`: each Phase 2 commit individually revertible; CI smoke job validates revert paths.

### 4.7 — CI gates suite

`.github/workflows/round-trip-ci.yml` (PR-time): unit tests + round-trip-ci + schema-contract + goldens-against-schema + render-drift checks. Description-length lint (informational).

## Phase 5 — Pair fixtures (11.5 days P1-P3, optional 14.5 with stretch)

Per ADR-008. P1 (5 days) lands first to pressure-test Rules 44-46 with master samples. P2 + P3 (6.5 days) cover Rule 43 sub-types + naming-normalization master.

| Priority | Pair | Effort | Days cumulative |
|---|---|---|---|
| **P1** | smarthub/Attekmi | 2 | 2 |
| **P1** | teqblaze | 2 | 4 |
| **P1** | adverxo | 1 | 5 |
| P2 | limelightDigital | 2.5 | 7.5 |
| P2 | liftoff/vungle (cross-name) | 1.5 | 9 |
| P2 | cadent_aperture_mx/emxdigital (cross-name) | 1.5 | 10.5 |
| P3 | adkernelAdn/adkerneladn | 1 | 11.5 |
| Stretch | freewheelssp (F2 master) | 1.5 | 13 |
| Stretch | thetradedesk (F4 master) | 1.5 | 14.5 |

**End state**: Phase D unblocked. Coverage report shows 8/32 empire parents covered (vs 5 today), 4/12 lifecycle pairs covered (vs 1), Rules 44-46 with functional master samples.

## Sequencing

```
Phase 0 (frontmatter) ─┐
                       ├─→ Phase 1 (restoration) ─┐
                       │                          │
                       │                          ├─→ Phase 1.5 (golden audit) ─┐
                       │                          │                              │
                       │                          │                              ├─→ Phase 2 (schema spine) ─┐
                       │                          │                              │                          │
                       │                          │                              │                          ├─→ Phase 3 (conciseness)
                       │                          │                              │                          │
                       │                          │                              │                          ├─→ Phase 4 (methodology)
                       │                          │                              │                          │
                       │                          │                              │                          └─→ Phase 5 (pair fixtures)
```

Phase 0 + Phase 1 are independent and can interleave. Phase 1.5 depends on Phase 1's CI workflow (so the audit script can integrate). Phase 2 depends on Phase 1.5 (so we audit on clean goldens). Phase 3, 4, 5 can run in parallel post-Phase-2.

## Risks

Captured in the Round 3 risk register (see meta-review). Top three:
- Phase 2 schema migration introduces regression in review-skill suite → mitigation: explicit pre-migration grep + post-migration smoke
- `scripts/sync-from-upstream.py` floods with auto-PRs → mitigation: weekly cadence; require human approval to merge
- Phase 5 effort overruns budget → mitigation: P1 (5 days) is the minimum acceptable Phase 5; P2/P3/stretch are scope-down candidates

## Reference: ADR index

| ADR | Topic | Status |
|---|---|---|
| ADR-001 | Phase 2 schema field additions (5 fields) | Proposed |
| ADR-002 | bidder_constant_referenced + kobler bean_dependencies — Round-2 reversals | Proposed |
| ADR-003 | Rule 44 — alias-empire consolidation | Proposed |
| ADR-004 | Rule 45 — disabled-by-default Java alias | Proposed |
| ADR-005 | Rule 46 — naming-convention normalization | Proposed |
| ADR-006 | Rule 43 sub-categorization | Proposed |
| ADR-007 | Five novel-pattern schema additions | Proposed |
| ADR-008 | Phase 5 expanded pair fixtures (7+2) | Proposed |
