# Roadmap

This repo's work is organized into project-level phases A–F. Phases A–C (read-skill foundation) are complete; Phase D (porting skills) is in progress (D0 + D1 scaffolding landed; D2 + D3 implement the bidirectional MVPs); Phase E (review-skill expansion) and Phase F (reflection loop) have design landed with implementation deferred.

## Phase A — Acceptance-gate goldens (complete)

The first Adapter Specification fixtures, hand-authored as the canonical shape contract:

- `optidigital` (clean baseline, Go)
- `kobler` (cross-language port pair, Go + Java)

Living at `prebid-server-{go,java}/read/test-fixtures/` (now 21 Go + 19 Java fixtures post-Phase 5).

## Phase B — Go read-skill suite (complete)

Four skills under `prebid-server-go/read/skills/`:

- `read-adapter-orchestrator` — discovery, fetch, dispatch, assembly
- `read-adapter-code` — parses `adapters/{bidder}/*.go`
- `read-bidder-info` — parses `static/bidder-info/{bidder}.yaml`
- `read-bidder-params` — parses `static/bidder-params/{bidder}.json` + `openrtb_ext/imp_{bidder}.go` + `params_test.go`

## Phase C — Java read-skill suite (complete)

Four parallel skills under `prebid-server-java/read/skills/`:

- `read-bidder-orchestrator`
- `read-bidder-class` — parses `src/main/java/org/prebid/server/bidder/{xyz}/*.java` + JUnit tests
- `read-bidder-config` — parses `src/main/resources/bidder-config/{xyz}.yaml` + Spring `@Configuration`
- `read-bidder-params-java` — parses `src/main/resources/static/bidder-params/{xyz}.json` + `ExtImp{Xyz}.java`

The Java suite shares the canonical schema, taxonomy, and port-translation rules with Go via `prebid-server-go/read/skills/shared/`. A future Java-specific schema would land at `prebid-server-java/read/skills/shared/adapter-spec-java.md` if divergence demands it.

## Phase D — Porting skills (engineering complete; operator validation pending)

Bidirectional Go ↔ Java translation. Both directions ship production-grade — the empirical Go→Java dominance in merged PRs (12+ vs 0 in 18 months) reflects current tooling limits, not user need or maintainer disinterest. Phase D removes that asymmetry as a first-class deliverable.

- [`prebid-server-java/port-go2java/`](prebid-server-java/port-go2java/) — Go-source spec → Java artifacts. SKILL.md pipeline + 11 Jinja templates shipped (D2.1-D2.7; frontmatter v0.3.0).
- [`prebid-server-go/port-java2go/`](prebid-server-go/port-java2go/) — Java-source spec → Go artifacts. SKILL.md pipeline + 7 Jinja templates shipped (D3.1-D3.2 + D3.8 supplemental-fixture). **Frontmatter v1.0.0 (production-promoted 2026-05-12)** via F2 sprint which retired the 4 template-coverage v1.0.0 blockers (F-new-2, F-new-7 EXT-A, F-new-7 EXT-B, F-new-34) — see § "Phase D — Operator validation status" below.

Both consume the cross-language translation rules at `prebid-server-go/read/skills/shared/port-translation-rules.md`. Cross-language pair fixtures at `cross-language-pairs/` are the round-trip safety net (16 pairs at the pinned commits). Design at [`docs/methodology/port-skills-design.md`](docs/methodology/port-skills-design.md); execution plan + per-phase acceptance gates at [`docs/execution-plan-phase-d.md`](docs/execution-plan-phase-d.md); output schema at [`prebid-server-go/read/skills/shared/port-report.schema.json`](prebid-server-go/read/skills/shared/port-report.schema.json) (v0.2.0).

**Phase D engineering layer complete:**

- D0 — R5 comparator lifted to [`scripts/lib/r5_check.py`](scripts/lib/r5_check.py); upstream snapshot re-verified.
- D1 — port skill scaffolds; [`scripts/lib/port_engine.py`](scripts/lib/port_engine.py) with 10 mechanical helpers; port-report schema 0.2.0 (additive PR-shape automation, source provenance, fidelity tracking); 11 emission references; CONTRIBUTING.md.
- D2 — port-go2java pipeline prose + 11 Jinja templates (Java code + IT fixtures); 110+ render tests.
- D3 — port-java2go pipeline prose + 6 Go-target Jinja templates (Go code + flat fixtures); 25 render tests.
- D4 — round-trip-ci.py R11 port-side round-trip determinism gate; coverage-report.py per-rule applied-count from port-report.json archives; `mvn_checkstyle_dry_run` port-engine helper for pre-submit Java style validation.

- D4.4 — beachfront fixture (ADR-007 F1 multi-endpoint-by-mediatype master sample) — Go + Java goldens + dual-spec assertions; also master sample for Rule 35 typed-config-subclass and Rule 9 parameterized-request-type. Corpus expanded 40 → 42 goldens, 16 → 17 dual-specs.

**Operator-side validation status**:

- **D3.8 — port-java2go: COMPLETE (2026-05-05; SKILL further promoted to v1.0.0 on 2026-05-12 via F2 sprint).** All 6 MVP pairs (kobler, aax, adkernelAdn, adverxo, vungle, thetradedesk) demonstrably portable Java → Go end-to-end via 7 canary runs. Trajectory `5 clean / 2 after-fix / 2 FAIL` (canary 1) → 3 consecutive `10 clean / 0 / 0` (canaries 5-7); final canary cleared D3.3 gate 3's 80% coverage threshold (81.4%). port-java2go SKILL bumped 0.3.0 → 0.5.0 at D3.8; subsequently 0.5.0 → 1.0.0 (production-promoted) on 2026-05-12 via the F2 sprint which retired all 4 template-coverage v1.0.0 blockers (see next bullet). Traces under `docs/runs/d3.8-*-canary-*.md`; corpus audit at `docs/runs/d3.8-template-coverage-audit.md`.
- **D3.8 — canary 8 (teal green-field, "best-in-class" mandate): COMPLETE (2026-05-05).** Eighth canary of the D3.8 series — first GREEN-FIELD port (no upstream Go reference; Teal flow's namesake). 5 polish iterations beyond the SKILL baseline; final state is TOP QUARTILE on every quality dimension vs 3 top-tier upstream Go adapters (openx, pubmatic, rubicon). All 8 D3.3 gates clean (coverage 95.0%, race-clean, 280k+ fuzz execs clean). Only adapter in the entire 267-adapter prebid-server-go corpus with fuzz tests, benchmarks, AND `doc.go`. 11 NEW findings catalogued (F-new-37 through F-new-47), including a real fuzz-discovered nil-map panic in mutation helpers (now fixed). Trace: `docs/runs/d3.8-teal-canary-2026-05-05T-canary8-teal.md`. SKILL improvements memo: `docs/runs/d3.8-teal-reflection.md`.
- **port-java2go v1.0.0 promotion: COMPLETE (2026-05-12).** All 4 template-coverage blockers retired via the F2 sprint (`feat/f2-port-java2go-v1.0.0`): F-new-2/27 multi-token endpoint resolution (commit `964d088`), F-new-7 EXT-A per-key batching (commit `058ca15`), F-new-7 EXT-B imp-id-correlation (commit `de9256a`), F-new-34 naming_form_resolution (commit `5cc1471`). Criterion 5 (non-MVP validation canary) was previously RETIRED by canary 8 (teal). All 5 ledger items now LANDED / RETIRED. SKILL frontmatter `0.5.0 → 1.0.0` (production-promoted) — symmetric to D3.8's validation work. New `ctx.endpoint_macros` + `ctx.batching_per_key` + `ctx.bid_type_fallback_value` + `ctx.naming_form_resolution` schema fields; new `port_engine.lookup_forms` helper; `bidder-constant-table.yaml` extended with per-bidder `forms:` sub-map (6 non-mechanical pairs populated). +55 tests across F2 sprint + v1.0.0 review-fix commit (493 → 548); 0 regressions. Full enumeration of D3.8's ~44 findings (~33 from canaries 1-7 + F-new-37..47 from canary 8) in canary 7 + canary 8 traces.
- **D2.8 — port-go2java: COMPLETE (2026-05-11).** All 6 MVP pairs (kobler, aax, adkernelAdn, adverxo, vungle, thetradedesk) demonstrably portable Go → Java end-to-end via a 6-canary batch run (`feat/d2.8-port-go2java-validation`). All 6 canaries PASS **4 of 7** D2.3 acceptance gates: Gate 1 (mvn compile), Gate 4 (mvn checkstyle), Gate 6 (port-report schema v0.2.0), Gate 7 (r5_check.state). Gates 2 + 3 (mvn test + Jacoco) are operator-fillable scaffolds (templates emit `Assertions.fail` placeholders the operator wires from `tests.fixture_inventory.exemplary[]`). Gate 5 has a documentation gap (F-new-62; referenced schemas don't exist in upstream Java; runtime validation via `BidderParamValidator.java` instead). port-go2java SKILL bumped 0.3.0 → 0.5.0. F2 fix milestone retired all gate-blocking defects in 4 commits (universal checkstyle/javac fixes via Tier 0+1 → 6/6 PASS Gate 1+4; entity-mutation + endpoint-resolution + F3/F4/imp.ext scaffolds via Tier 3 steps 1-3; new `port_engine.extract_entity_strategies` helper; ~25 F-new findings catalogued across 6 subagent traces). Per-canary traces: `docs/runs/d2.8-{bidder}-canary-2026-05-11.md`. Cross-canary findings: `docs/runs/d2.8-cross-canary-summary.md`.
- **port-go2java v1.0.0 promotion criteria** (out of D2.8 scope; tracked for follow-up): Gates 2 + 3 routinely cleared by operator-completed test scaffolds; green-field validation canary (D3.8-canary-8 analog) demonstrably portable Go → Java without leaning on MVP-pair fixtures; SKILL prose audit for the new `ctx.entity_strategies` + `ctx.has_bid_post_processing_macros` + `ctx.config_class_name` + Rule 30 framework-default mappings landed in 0.5.0; Tier 4 cosmetic fixes (F-new-62 doc gap, F-new-69-adverxo family-shape classifier `meta.empire_*` consultation, etc.).

## Phase E — Review-skill expansion + cross-skill integration (partially shipped)

**Shipped in this PR**:

- `pr-triage` SKILL `prior_source_spec` slot — for cross-language port-fidelity comparisons (Go-PR-vs-Java-source). Documented at the SKILL's "Optional: Prior-Spec Comparison" section.
- `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` convention — transient run-scoped specs for the Teal flow orchestration.

**Shipped post-D2.8**:

- `--- PRIOR SOURCE SPEC COMPARISON ---` downstream consumption — all 3 Go review skills (`adapter-code-pr-review`, `bidder-info-pr-review`, `bidder-params-pr-review`) gained Step 1g substeps consuming pr-triage's cross-language port-fidelity manifest block with the `info`/`warn`/`fail` severity policy + skill-specific worked examples (template-macro endpoint resolution in adapter-code; R5-strict geoscope/capabilities/gvl_vendor_id in bidder-info; Rule 38 byte-fidelity + aax dual-spec `severity: fail` in bidder-params). Port-fidelity findings now flow end-to-end from pr-triage → downstream Go review skills.

**Still future**:

- Java review-skill suite (`prebid-server-java/review/skills/`) — currently absent.
- Implement `--- PRIOR SPEC COMPARISON ---` (same-language regression) and `--- PRIOR AGENT FINDINGS ---` (CodeRabbit/ChatGPT prior-PR feedback) consumption in the downstream Go review skills — pr-triage authors both manifest blocks but no downstream skill reads them yet (separate from the cross-language `--- PRIOR SOURCE SPEC COMPARISON ---` consumption shipped post-D2.8).
- Java mirror of the cross-language port-fidelity hooks (post Java review-skill suite landing).
- `write/` skills — generate adapters from a spec.
- `diff-spec` skills — compare two specs across commits.

## Phase F — Reflection loop (design landed in this PR)

Phase F closes the Teal flow by reading port reports + post-merge upstream signal and proposing amendments to SKILLs / rules / taxonomy / ADRs:

- Triage matrix mapping issue type → fix location (9 rows; e.g., novel pattern → taxonomy MINOR, R5 semantic divergence → upstream PR).
- ADR amendment protocol with refinement annotations.
- Cross-version replay (replay an old port report against a newer rules version).
- Output: PRs against this repository (`prebid-agent-skills`), NOT against `prebid/prebid-server-{go,java}`.

Design at [`docs/methodology/reflection-loop.md`](docs/methodology/reflection-loop.md). Phase D produces the port reports Phase F consumes.

The "Teal flow" is the cross-phase orchestration that wires read → port (D) → review (E) → reflect (F) into a single end-to-end pass. Design at [`docs/methodology/end-to-end-flow.md`](docs/methodology/end-to-end-flow.md). Teal flow is NOT a phase letter — it's the integration concept.

## Phase numbering map

The repo uses several numbering schemes for different domains. The canonical mapping:

| Scheme | Domain | Lives in |
|---|---|---|
| **A–F** | Project-level phases (this doc) | `ROADMAP.md`, `README.md`, `docs/methodology/README.md`, `docs/methodology/end-to-end-flow.md` |
| **2.X** | Schema-evolution sub-phases — versioned-artifact lifecycle for `adapter-spec.schema.json` (e.g., 2.0 = first schema; 2.5 = +Rules 44/45/46; 2.7 = goldens migrated to `"1.0.0"`; 2.8 = future `$ref`-wiring of ADR-007 F1/F3/F4/F5 `$defs`) | `docs/methodology/schema-versioning.md`, ADR bodies, `CHANGELOG.md` versioned releases |
| **4.X** | Methodology hardening sub-phases — predates the A–F framing; identifies WHICH methodology doc / CI gate landed in WHICH commit (4.1 = `sync-from-upstream.py`, 4.2 = `audit-pr.py`, 4.3 = coverage report, 4.4 = schema-versioning policy, 4.5 = repo-rules, 4.6 = rollback policy, 4.7 = round-trip-ci hardening) | `docs/methodology/{pr-ingestion,repo-rules,schema-versioning,rollback}.md`, `docs/methodology/README.md` |
| **Wave-N** | This PR's commit history (Waves 1–9 are the hardening + polish waves landed atop Phases A–C) | Commit messages, `CHANGELOG.md` Unreleased section |

The 2.X and 4.X numberings predate the A–F framing and survive because they identify specific sub-phase artifacts. A–F is the project-level taxonomy. Wave-N is commit-history shorthand and does not appear in design docs.

The original "Phase 2" reconnaissance pass (master-plan, 17+17 edge cases) was renamed informally; the artifacts derived from that pass live under "Phase 2.X" schema-evolution numbering.

## Out of scope

- `prebid-js/`, `prebid-dcos/` — directories existed as exploratory stubs before PR #1; deleted in PR #1. Future suites for these surfaces are not currently planned.
