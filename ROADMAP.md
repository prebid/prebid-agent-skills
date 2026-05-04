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
- [`prebid-server-go/port-java2go/`](prebid-server-go/port-java2go/) — Java-source spec → Go artifacts. SKILL.md pipeline + 6 Jinja templates shipped (D3.1-D3.2; frontmatter v0.3.0).

Both consume the cross-language translation rules at `prebid-server-go/read/skills/shared/port-translation-rules.md`. Cross-language pair fixtures at `cross-language-pairs/` are the round-trip safety net (16 pairs at the pinned commits). Design at [`docs/methodology/port-skills-design.md`](docs/methodology/port-skills-design.md); execution plan + per-phase acceptance gates at [`docs/execution-plan-phase-d.md`](docs/execution-plan-phase-d.md); output schema at [`prebid-server-go/read/skills/shared/port-report.schema.json`](prebid-server-go/read/skills/shared/port-report.schema.json) (v0.2.0).

**Phase D engineering layer complete:**

- D0 — R5 comparator lifted to [`scripts/lib/r5_check.py`](scripts/lib/r5_check.py); upstream snapshot re-verified.
- D1 — port skill scaffolds; [`scripts/lib/port_engine.py`](scripts/lib/port_engine.py) with 10 mechanical helpers; port-report schema 0.2.0 (additive PR-shape automation, source provenance, fidelity tracking); 11 emission references; CONTRIBUTING.md.
- D2 — port-go2java pipeline prose + 11 Jinja templates (Java code + IT fixtures); 110+ render tests.
- D3 — port-java2go pipeline prose + 6 Go-target Jinja templates (Go code + flat fixtures); 25 render tests.
- D4 — round-trip-ci.py R11 port-side round-trip determinism gate; coverage-report.py per-rule applied-count from port-report.json archives; `mvn_checkstyle_dry_run` port-engine helper for pre-submit Java style validation.

- D4.4 — beachfront fixture (ADR-007 F1 multi-endpoint-by-mediatype master sample) — Go + Java goldens + dual-spec assertions; also master sample for Rule 35 typed-config-subclass and Rule 9 parameterized-request-type. Corpus expanded 40 → 42 goldens, 16 → 17 dual-specs.

**Pending operator-side work** (out-of-session against local upstream clones; review team can run on a real prebid-server-{go,java} checkout):

- D2.8 — port-go2java validation against the 6 MVP pairs (kobler, aax, adkernelAdn, adverxo, vungle, thetradedesk): `mvn -B compile`, `mvn -B checkstyle:check`, Jacoco line-coverage ≥ 90%, R5 state matches expectation per [execution plan §D2.3](docs/execution-plan-phase-d.md).
- D3.8 — port-java2go validation against the same 6 pairs reversed: `go build`, `go vet`, `gofmt -s -l`, `./scripts/check_coverage.sh ≥ 80%`, `TestBidderUniquenessGatekeeping`, R5 state per [§D3.3](docs/execution-plan-phase-d.md).

## Phase E — Review-skill expansion + cross-skill integration (partially shipped)

**Shipped in this PR**:

- `pr-triage` SKILL `prior_source_spec` slot — for cross-language port-fidelity comparisons (Go-PR-vs-Java-source). Documented at the SKILL's "Optional: Prior-Spec Comparison" section.
- `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` convention — transient run-scoped specs for the Teal flow orchestration.

**Still future**:

- Java review-skill suite (`prebid-server-java/review/skills/`) — currently absent.
- Implement `--- PRIOR SPEC COMPARISON ---` and `--- PRIOR SOURCE SPEC COMPARISON ---` consumption in the downstream Go review skills (the hooks are authored in `pr-triage` but no downstream skill reads them yet).
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
