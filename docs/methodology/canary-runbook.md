# Canary Runbook — Phase D port-skill methodology playbook

**Status:** Codified from D3.8 port-java2go canaries 1–8 (kobler v1, kobler v2, vungle, aax, adverxo, thetradedesk, adkernelAdn, teal). Future canaries (in either direction) follow this script. Direction-specific differences for D2.8 port-go2java are predicted in §8.

**Audience:** Operators running canary ports of prebid-server bid adapters between Java and Go. Phase F reflection-loop authors (downstream consumers of canary traces). SKILL maintainers (downstream of recurring findings).

**Authoritative inputs that fed this playbook:**

- 8 canary trace docs at `docs/runs/d3.8-{kobler-v1,kobler-v2,vungle,aax,adverxo,thetradedesk,adkernelAdn,teal}-canary-*.md`
- `docs/runs/d3.8-mvp-pairs-spike-2026-05-05.md` (pre-canary spike methodology)
- `docs/runs/d3.8-template-coverage-audit.md` (cross-language pairs corpus audit)
- `.tmp/teal-recon/plan.md` (canary 8 quality bar definition)
- `.tmp/teal-recon/iter5-{review-skills,beyond-review}-findings.md` (super-review reports)
- `.tmp/teal-recon/iter-final-{fidelity-audit,corpus-benchmark}.md` (Phase E verifications)
- `prebid-server-go/port-java2go/SKILL.md` v0.5.0 (current pipeline prose)
- `scripts/lib/port_engine.py` (current helper inventory)
- `prebid-server-go/port-java2go/templates/*.j2` (current template inventory)

---

## 1. The canary loop — formal definition

A **canary** is one full execution of the port pipeline against one source-language adapter, scored against the 8 acceptance gates (§3), instrumented to surface SKILL/template/helper gaps as `F-new-*` findings (§6), and concluding with a durable trace doc plus a reflection memo. A canary is the unit of work that converts "we have a port skill" into "we know exactly which adapter shapes our port skill handles cleanly today."

The canary loop has 4 phases. Each phase has a defined entry/exit and produces specific artifacts.

### Phase Pre — Pre-canary spike

**Purpose.** Predict what will fail BEFORE running the canary. Surface the predictable findings as Phase 2/3 prep work so the canary execution time is spent on the unpredictable findings only.

**Entry criteria.**

- Source adapter selected with rationale (typically: cleanest of the remaining batch for the next canary; gnarliest for the validation canary).
- Read skill (`read-bidder-orchestrator` Java side, or `read-adapter-orchestrator` Go side) v≥1.1.0 has emitted a schema-valid spec for the source adapter.
- Port skill version pinned (e.g., `port-java2go@v0.5.0`).

**Work performed.** Per §2 spike checklist.

**Exit criteria.**

- Adapter-source spec yaml file in `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml`, schema-valid against `adapter-spec.schema.json`.
- Predicted findings list (categorized as template-gap / helper-gap / fixture-shape-gap / convention-drift).
- Predicted gate scoreboard (per-gate status with reasoning).
- Risk register with top 5 risks and mitigations.
- Spike doc at `docs/runs/d3.8-{bidder-batch}-spike-{date}.md` (or per-bidder for solo canaries).

**Typical duration.** 30–90 minutes for a single bidder; 2–4 hours for a 5-bidder batch spike like `d3.8-mvp-pairs-spike-2026-05-05.md`.

### Phase C — Canary baseline (Iter 0)

**Purpose.** Run the port pipeline end-to-end with NO hand-fixes. Score the 8 D3.3 gates. Catalogue findings.

**Entry criteria.** Phase Pre exit criteria met. Sandbox worktree set up (typically `.tmp/full-loop/{run-id}/{target-lang}-sandbox/` as a git worktree off upstream HEAD).

**Work performed.**

- Author renderer script (`render_{bidder}.py`) inheriting from prior canary's renderer with bidder-specific ctx.
- Render Go (or Java) artifacts to `.tmp/full-loop/{run-id}/{target-lang}/`.
- Overlay artifacts onto sandbox worktree.
- Run all 8 gates (§3) and record per-gate status.
- Catalogue findings using the canonical F-new-N convention.

**Exit criteria.**

- Per-gate scoreboard recorded.
- Findings catalogued in §6 taxonomy (each with bucket / severity / status / evidence).
- Iteration trace recorded (round-by-round if retries needed).
- Pass criterion: ≥6/10 gates clean OR documented gaps with explicit hand-fix plan.

**Typical duration.** 1–4 hours depending on complexity.

### Phase D — Reflection-loop iterations (Iters 1–5)

**Purpose.** Polish the baseline emission to a "best in class" deliverable. Each iteration has a focused goal (§4).

**Entry criteria.** Iter 0 done. Pass criterion met OR explicit waiver from operator.

**Work performed.** Per-iteration entry/exit criteria in §4.

**Exit criteria.**

- All quality bar dimensions (§5) met.
- Iter 5 super-review (review skills + opus subagent) finds zero outstanding issues OR every outstanding issue is captured as a deferred follow-up.
- All 8 gates clean.

**Typical duration.** 4–12 hours total across all iters; canary 8 (teal) ran 5 iters in approximately one operator session.

NOTE: Phase D is OPTIONAL for canaries 1–7 (which were "smoke test" canaries: prove the pipeline works on representative pairs). Phase D is REQUIRED for any canary intended for real upstream submission (canary 8 teal was the first such case).

### Phase E — Final verification

**Purpose.** Independent validation before declaring the canary complete.

**Entry criteria.** Phase D Iter 5 done.

**Work performed.**

- Full 8-gate scoreboard re-run (no caching from prior iters).
- Opus subagent: Java line-by-line fidelity audit (or Go fidelity for Go→Java direction).
- Opus subagent: corpus quality benchmark vs 3 top-tier upstream adapters.
- Optional: pre-submission maintainer-review simulation (used in canary 8; see `.tmp/teal-recon/preflight-maintainer-review.md`).

**Exit criteria.**

- All 8 D3.3 gates clean.
- Fidelity audit passes (zero BLOCKING/HIGH findings; LOW notes acceptable).
- Corpus benchmark places adapter ≥top quartile on every measured dimension.

**Typical duration.** 1–3 hours.

### Phase F — Trace + reflection memo

**Purpose.** Durable documentation. Capture lessons learned for the next canary.

**Entry criteria.** Phase E done.

**Work performed.**

- Author canary trace doc at `docs/runs/{phase}-{bidder}-canary-{ts}-{hash}.md`.
- Author reflection memo at `docs/runs/{phase}-{bidder}-reflection.md` (canary 8 was first to do this; recommended for any canary surfacing ≥5 net-new findings).
- Update CHANGELOG / ROADMAP if SKILL was modified.
- File any upstream bugs (when the canary surfaces them).

**Exit criteria.**

- Trace doc and reflection memo committed.
- Findings cross-referenced into the canonical F-new-N catalogue (§6).

**Typical duration.** 1–2 hours.

---

## 2. Pre-canary spike checklist

A pre-canary spike MUST produce four deliverables before Phase C starts. These are checklist gates, not optional polish.

### 2.1 Adapter-source spec (yaml format, schema-valid)

- File path: `.tmp/full-loop/{run-id}/{source-lang}/{bidder}.yaml` OR `prebid-server-{lang}/read/test-fixtures/{bidder}.golden.spec.yaml` for persisted goldens.
- Schema: validates against `prebid-server-{lang}/read/skills/shared/adapter-spec.schema.json` via `jsonschema` library.
- Provenance: pinned `resolved_commit` matching the source-lang HEAD at canary time.
- R4-idempotent: re-reading the source produces a byte-identical spec modulo the 3 provenance fields (`resolved_commit`, `fetch_method`, `timestamp_utc`).

**Verification:** `python -c "import yaml, jsonschema; ..."` with the specified schema OR use the read skill's built-in validation (`read-bidder-orchestrator --validate-only`).

### 2.2 Predicted finding categories

For each predicted finding, the spike doc MUST record:

- **Bucket:** template-gap | helper-gap | fixture-shape-gap | convention-drift | docs-drift.
- **Confidence:** P-high (≥80% likely) / P-med (40–80%) / P-low (<40%) — these labels are reused for direction-flipped predictions in §8.
- **Predicted F-new-N reference:** if a similar finding exists in §6, cite its F-new-N. If it's net-new, label as `F-new-NEW-{slug}` and renumber after the canary.
- **Mitigation if predictable:** "Phase 2 template work needed" / "renderer hand-fill" / "spec-canonicalize" / "operator-fill at port time".

**Example (from canary 7 adkernelAdn spike, abridged):**

```markdown
| Predicted finding | Bucket | Confidence | F-new-N | Mitigation |
|---|---|---|---|---|
| template-macro endpoint TODO stub | template-gap | P-high | F-new-2 | TODO stub; operator hand-fills resolveEndpoint |
| per-key batching not in template | template-gap | P-high | F-new-7 EXT-A | renderer maps to single-batched (functional divergence) |
| imp-id-correlation bid-type | template-gap | P-high | F-new-7 EXT-B | renderer maps to by-bid-mtype + default-banner |
| Rule 46 lowercase asymmetry | renderer-config | P-high | F-new-34 | renderer reads from lowercase Java paths, emits to camelCase Go paths |
| 4-mutation pattern (imp.Ext=nil + Site/App publisher null + Banner.W/H from format) | template-gap | P-med | F-new-13/16/20/32/33 | passthrough body when template doesn't mutate; capture as functional divergence |
```

### 2.3 Predicted gate scoreboard

For each of the 8 gates, predict:

- **Status:** PASS clean | PASS-after-fixup | FAIL | PARTIAL.
- **Reasoning:** which finding(s) drive this prediction.
- **Coverage range** (gate 3 only): expected coverage % range with rationale (e.g., "55–65% with 3–5 supplementals").

The scoreboard is a discipline tool — comparing predictions to outcomes (each canary trace has a "Predictions vs outcomes" section) trains operator intuition for future spikes.

### 2.4 Risk register (top 5)

Format: `Risk | Probability × Impact | Mitigation`. Probability ∈ {high, med, low}; Impact ∈ {high, med, low}.

Risks should cover:

- Mutation fidelity drift (the emission doesn't match upstream semantics 1:1).
- Coverage gap (gate 3 80% threshold).
- Whitespace/Unicode handling cross-language semantic divergence.
- Mediatype/priority ordering disagreements.
- Builder-side validation differences (URL parsers, regex constraints).

See canary 8's plan.md §7 for the canonical 5-row example.

---

## 3. The 8-gate scoreboard (D3.3)

Each gate is binary (PASS/FAIL) with a documented PARTIAL state for gate 3 only. The scoreboard is the canonical "is this canary done" measurement.

### Gate 1 — `go build ./adapters/{bidder}/...`

**What it tests.** Emitted Go compiles cleanly.

**Failure modes:**

- Unused-import (e.g., `encoding/json` imported when `has_extra_info=False` — F1 in canary 1).
- Undefined struct reference (e.g., `ExtImpAdverxo` when upstream uses `ImpExtAdverxo` — F-new-28).
- Missing helper import (e.g., `text/template` when emitting endpoint substitution).

**Remedies:**

- Wrap conditional imports in `{% if ctx.X %}` Jinja blocks.
- Fix template's class-root prefix to use ctx-driven naming.
- Renderer-side post-process substitution (legacy ImpExt naming, etc.).

**Direction-flipped (Go→Java).** Replace with `mvn compile` or `mvn checkstyle:check` against the target package. Failure modes flip: Java needs explicit Lombok imports, Spring config classes may fail injection, etc.

### Gate 2 — `go test ./adapters/{bidder}/...`

**What it tests.** Adapter unit tests + JSON-driven adapterstest harness pass.

**Failure modes:**

- Fixture body mismatch: emitted MakeRequests output ≠ fixture's `expectedRequest.body` (F-new-13).
- Bid-shape mismatch: fixture's expected bid has framework enrichments not present in adapter output (F-new-11).
- URI mismatch: fixture's `expectedRequest.uri` doesn't match adapter's actual URL (F-new-10).
- impIDs assertion: fixture missing `impIDs` field (F-new-12).
- Currency mismatch: fixture missing `cur` in bid-response → empty Currency on bidderResponse (F-new-9).
- Nil-deref panic on User/Site/App access patterns (F-new-22).
- canonical-helpers no-response-body fixture path differs from kobler-style (F-new-23).

**Remedies:**

- `port_engine.exemplary_fixture_assemble_java_to_go` helper handles F-new-9/10/11/12/13 transparently.
- Per-bidder `inject_empty_user_if_missing=True` flag for User-deref bidders (F-new-22).
- Per-bidder `http_status_kind` ctx field gates supplemental no-response-body emission (F-new-23).

**Direction-flipped (Go→Java).** Replace with `mvn test` against the target package. Failure modes flip: Vert.x fixtures use 4-file split (auction-request, auction-response, downstream-request, downstream-response) instead of Go's flat shape; assertions use `assertJSONEq` (Hamcrest) not `adapterstest`. Predicted: F-new-go2java-9 (Java IT fixture body must NOT include framework enrichments — inverse of F-new-13's "Java IT IS post-framework").

### Gate 3 — Coverage ≥ 80%

**What it tests.** `go test -cover` exit > 80% per the upstream `./scripts/check_coverage.sh` convention.

**Failure modes:**

- Banner-only IT can't lift getBidType beyond 33.3% (3 mtype branches unreachable from happy-path).
- Currency-conversion no-op when IT has no bidfloor; `convertImpCurrency` stays at 28.6%.
- Builder extraInfo unmarshal branch unreachable when test setup uses default `ExtraAdapterInfo=""`.
- parseImpExt error branches unreachable on happy fixtures.

**Remedies:**

- Add 4–5 supplemental fixtures: status-204, status-400, status-404, malformed-body, no-response-body.
- For ADR-007 F4 master sample bidders: emit synthetic supplementals targeting macro-substitution branches.
- For multi-mediatype bidders: add per-mediatype exemplary fixtures (canary 8 had banner + video + native + audio).
- For currency-conversion bidders: add supplemental with non-USD bidfloor.

**Coverage trajectory across D3.8:** 51% (kobler v1) → 65% (kobler v2) → 76% (vungle) → 79% (aax) → 70% (adverxo) → 79% (thetradedesk) → **81%** (adkernelAdn — first to clear) → **95%** (teal canary 8 with full Phase D polish).

**Direction-flipped (Go→Java).** Java side uses JaCoCo coverage. Upstream asks for **90% on the changed code**, not 80% and not scoped to new bidders — `docs/developers/contributing.md:17` ("All pull requests must have 90% coverage in the changed code. Check the code coverage with your IDE or external tools."), echoed by the PR-template checkbox `.github/pull_request_template.md:34`. Nothing enforces it mechanically: JaCoCo runs `prepare-agent` + `report` only (`extra/pom.xml:325-344`), with no `check` goal and no coverage step in `pr-java-ci.yml`, so this gate is measured locally and read by a human. Predicted: structural-PARTIAL-by-default for the same reasons (1 IT scenario per bidder), supplementals come from JUnit `@ParameterizedTest` instead of JSON fixtures.

### Gate 4a — `gofmt -s -l`

**What it tests.** Emitted Go is canonical-formatted.

**Failure modes:**

- Excess whitespace from Jinja `{% for %}` / `{% if %}` blocks (F3).
- Tab-vs-space drift (rare; templates emit consistently).
- Comment-alignment in test files (canary 8 hit this in `TestIsBlank`).

**Remedies:**

- `port_engine.gofmt_post_process(file_paths)` runs `gofmt -s -w` post-emit unconditionally. This is BY DESIGN per F3 — templates may emit excess whitespace; gofmt canonicalizes.
- For test-file alignment: avoid raw fixture editing; emit through templates that gofmt-clean.

**Direction-flipped (Go→Java).** Replace with `mvn checkstyle:check` against the package. Java has no `gofmt -s` equivalent; use the project's checkstyle.xml. The `port_engine.mvn_checkstyle_dry_run` helper is the analogue of `gofmt_post_process`.

### Gate 4b — `go vet ./adapters/{bidder}/...`

**What it tests.** No Go static-analysis warnings.

**Failure modes:**

- Same root cause as gate 1 (unused imports). Often co-fails with gate 1.
- Shadow variable warnings (uncommon; templates don't introduce shadows).
- Format-string mismatches in `fmt.Errorf` (rare).

**Remedies:** Same as gate 1.

**Direction-flipped (Go→Java).** Replace with `mvn pmd:check` or the project's PMD configuration. Predicted: similar low-frequency failures, mostly co-failing with gate 1.

### Gate 5 — `TestBidderUniquenessGatekeeping`

**What it tests.** First-6-letter prefix of bidder name unique against existing `coreBidderNames`.

**Failure modes.**

- Two bidders share their first 6 letters (e.g., a hypothetical `koblerX` would collide with `kobler`).
- Registry insertion at non-alphabetical position (uncommon; helper-driven).

**Remedies.**

- `port_engine.prefix_uniqueness_check(target_lang, bidder_name, existing_names=...)` runs BEFORE emit; aborts on collision.
- `port_engine.alphabetical_insert(file_path, marker_pattern, insert_line)` for canonical insertion.

**Direction-flipped (Go→Java).** Java has no equivalent prefix-uniqueness gate (Spring's `@Component` naming is global, but bidders are namespace-scoped). Predicted: gate 5 has no analogue on Java side; replace with package-name-clash check against `org.prebid.server.bidder.{bidder}`.

### Gate 6a — `TestBidderInfoFiles`

**What it tests.** YAML at `static/bidder-info/{bidder}.yaml` validates against Go's `_schema.json`.

**Failure modes.**

- `gvlVendorID: 0` emitted when convention is omit-when-zero (F9).
- Missing required field (rare; templates have all required fields).
- Invalid `endpointCompression` casing (per literal SKILL but accepted at runtime — see iter5 review skills findings RV-INFO-09).
- `geoscope: global` lowercase vs uppercase canonical (RV-INFO-10).

**Remedies.**

- Wrap zero-valued optional fields in `{% if ctx.X is not none and ctx.X != 0 %}`.
- Use canonical uppercase for `endpointCompression: GZIP` and `geoscope: GLOBAL` even when runtime tolerates lowercase.

**Direction-flipped (Go→Java).** Java has no `static/bidder-info/{bidder}.yaml` directly; bidder config lives in `src/main/resources/bidder-config/{bidder}.yaml` with a different schema (Spring `@PropertySource` mapping). Replace gate 6a with: spring-boot context-load test for the bidder.

### Gate 6b — `TestValidParams` / `TestInvalidParams`

**What it tests.** `params_test.go` exercises the JSON schema with valid and invalid inputs.

**Failure modes.**

- Cross-language schema divergence: Java side has looser schema (no `minLength:1`); upstream Go's `params_test.go` invalid cases test empty strings that VALIDATE under Java schema (F-new-24).
- Wrong file path in tests (e.g., `static/bidder-params/` vs `../../static/bidder-params/`).

**Remedies.**

- `params_test_compute_invalid_cases(source_schema, upstream_go_invalid_cases) -> list[str]` filters out cases that validate under the (preserved) source schema. Currently a renderer-level adjustment; promotion to port_engine helper proposed.

**Direction-flipped (Go→Java).** Java side has `BidderParamsTest` per-bidder; the same cross-language divergence pattern flips: Go-side may have constraints Java doesn't. Predicted: F-new-go2java-24 mirrors F-new-24 with reversed asymmetry.

### Gate 7 — `port-report.json` schema

**What it tests.** Emitted port-report validates against `port-report.schema.json` v0.2.0.

**Failure modes.**

- Operator drift: 20 schema errors on first emit was canary 1's record (F2). Common drift fields:
  - `$schema` (not in schema; `additionalProperties: false`)
  - `emitted_files` (not in schema)
  - `pr_shape` (not in schema; use `recommended_pr_title` etc.)
  - `registry_inserts` (not in schema)
  - `bidder_params_sha256_match` (not in schema)
  - `note` inside rules_consumed entries (not in schema)
  - `rule_ref` inside human_todos entries (not in schema)
  - `rule_id` inside unresolved_translations entries (not in schema)

**Remedies.**

- SKILL Step 7 prose carries a canonical example (added in Stage A post canary 1).
- `port_engine.port_report_emit(report, path, schema_path=...)` validates before writing.

**Direction-flipped (Go→Java).** Same `port-report.schema.json` is shared cross-direction. Direction-specific fields are `port_run.{source_lang, target_lang}`. No predicted divergence.

### Gate 8 — `r5_check.state` matches expected

**What it tests.** R5-strict cross-language equivalence at port time produces the expected state for the pair.

**States:**

- `pass` — full equivalence on shared fields.
- `warn-byte-only-divergence` — Rule 38 fields differ in bytes only (whitespace, indent).
- `warn-target-strengthens-source` — destination has constraints absent in source (Connatix-style).
- `fail-source-omits-target-constraint` — source lacks a constraint destination enforces (aax-style).
- `fail-semantic-divergence` — true semantic mismatch.
- `error` — comparator failed to run.

**Failure modes.**

- bidder-params byte-equality mismatch (Rule 38 violation).
- Source spec has stale provenance (resolved_commit doesn't match HEAD).
- Cross-language SHA divergence undocumented (canary 4 aax F-new-24).

**Remedies.**

- Pin `resolved_commit` to source-lang HEAD at canary time.
- `port_engine.r5_check_at_port_time(source_spec, dest_spec)` produces the comparator output.
- Document expected state per pair in `docs/execution-plan-phase-d.md` §D3.3.

**Direction-flipped (Go→Java).** R5 check is symmetric; same comparator routes through `r5_check.compare_pair`. Direction-specific extensions: `warn-target-strengthens-source` flips to `fail-source-omits-target-constraint` (an aax-style asymmetry shows the former on Java→Go and the latter on Go→Java for the same pair).

---

## 4. Iteration model — entry/exit per iteration

The "best in class" iteration model derived from canary 8 (teal). Each iteration has a **goal**, **entry criteria**, **work performed**, and **exit criteria** + **quality bar dimensions met**.

### Iter 0 — Canary baseline

**Goal.** Run the port pipeline end-to-end with NO hand-fixes; score the 8 gates.

**Entry criteria.**

- Pre-canary spike (Phase Pre) complete.
- Source spec at `.tmp/full-loop/{run-id}/{source-lang}/{bidder}.yaml`, schema-valid.
- Sandbox worktree set up.
- Renderer script authored (typically copied from prior canary's renderer with bidder-specific ctx).

**Work performed.**

- Render artifacts to `.tmp/full-loop/{run-id}/{target-lang}/`.
- Overlay onto sandbox.
- Run all 8 gates in order, recording per-gate status.
- Capture iteration trace round-by-round if retries needed.
- Catalogue findings using F-new-N convention.

**Exit criteria.**

- Per-gate scoreboard recorded.
- Findings catalogued with bucket / severity / status / evidence.
- Pass criterion: ≥6/10 gates clean OR documented gaps with explicit hand-fix plan.

**Quality bar dimensions met.** Functional baseline only (gate-clean if achievable; otherwise findings-documented).

### Iter 1 — Source-language fidelity polish

**Goal.** Reproduce every source-language unit-test scenario in target-language tests; verify mutation 1:1 byte-equivalence where the harness allows.

**Entry criteria.** Iter 0 done, baseline rendered + gates scored.

**Work performed.**

- For Java→Go: enumerate every `@Test` method in `{Bidder}BidderTest.java`. For each, write a matching Go test (parity score = matched / total).
- Hand-emit any mutations the template can't yet emit (capture as F-new findings).
- Verify wire-format byte-equivalence via fixture diff against source-lang IT fixtures (modulo framework enrichments — see canary 1 F4 / canary 2 F-new-13).
- Update doc.go (Go side) or class-level Javadoc (Java side) to document any cross-language fidelity-surface differences.

**Exit criteria.**

- All N source-lang `@Test` scenarios reproduced (parity = 100%).
- Mutation diff against source-lang IT fixture is ≤ documented framework-enrichment delta.
- `gofmt`/`go vet` clean (or Java equivalents).
- Source-fidelity audit dispatched to opus subagent and returns PASS or PASS-WITH-NOTES (LOW notes only).

**Quality bar dimensions met.** Java fidelity (or Go-side fidelity for Go→Java direction) reaches the §5 target.

### Iter 2 — Test depth

**Goal.** Add fuzz, bench, property tests, race-clean. Drive coverage to the §5 quality bar.

**Entry criteria.** Iter 1 done.

**Work performed.**

- Add ≥1 fuzz harness on a non-trivial helper (Builder URL validator, params decoder, modifyImp, etc.).
- Add ≥2 benchmark harnesses (MakeRequests, MakeBids).
- Add ≥1 property/invariant test (testing/quick on Go side; junit-quickcheck on Java side).
- Run `-race` and verify zero data races.
- Add 4–5 supplemental fixtures targeting uncovered branches: status-204, status-400, status-404, malformed-body, no-response-body.

**Exit criteria.**

- Line coverage ≥ §5 target (≥95% for canary 8 quality bar; ≥80% for D3.3 minimum).
- Branch coverage ≥ §5 target.
- Fuzz runs ≥30s clean.
- Benchmarks compile + run.
- Race test passes.

**Quality bar dimensions met.** All §5 test-type minimums.

### Iter 3 — Idiomatic target-language polish

**Goal.** Adopt target-language idioms from top-tier upstream adapters; pass review skills.

**Entry criteria.** Iter 2 done.

**Work performed (Go side — Java→Go direction).**

- `errors.Join` instead of `[]error` accumulation where applicable.
- `slices.IndexFunc` / generic helpers from stdlib.
- Pre-allocate slices of known capacity (`make([]T, 0, n)` not `var s []T`).
- `url.Parse` validation with explicit error returns.
- `jsonutil.Marshal/Unmarshal` over `encoding/json` (per shared/framework-utilities.md).
- Sentinel errors with `errors.Is` test cases (≥3 per canary 8 quality bar).

**Work performed (Java side — Go→Java direction, predicted).**

- Records over POJOs where Lombok adds noise.
- `Optional<T>` over null-checks for nullable returns.
- Streams + collectors for collection mutations (instead of imperative loops).
- `@JsonAlias` for cross-language field-name asymmetry.
- Sentinel `PreBidException` subclasses with type assertions in tests.

**Exit criteria.**

- Review skills (e.g., `adapter-code-pr-review`, `bidder-info-pr-review`, `bidder-params-pr-review` on Go side; `pr-triage`, equivalent Java skills on Java side) pass with no FAIL findings, and CONCERN findings either fixed or documented.
- Manual diff vs 3 top-tier upstream adapters (e.g., openx/pubmatic/rubicon for Go) shows comparable or better idioms.

**Quality bar dimensions met.** Idiomatic target-language style; review-skill clean.

### Iter 4 — Documentation + edge cases

**Goal.** 100% doc coverage on every symbol; expand fixture set to cover edge cases.

**Entry criteria.** Iter 3 done.

**Work performed.**

- GoDoc on every exported AND unexported symbol (Go side).
- Javadoc on every public method + class (Java side).
- `doc.go` for package overview (Go side; canary 8 was first in corpus to do this).
- Edge case fixtures:
  - whitespace-only inputs (NBSP, U+2007, U+202F per canary 8 BR-02)
  - missing-all-mediatypes
  - mixed-imp first-account-wins (multi-imp partial behavior)
  - app-context where exemplary uses site (or vice versa)
  - existing-request-ext (M3 stamp into pre-populated ext)
- Total supplemental fixture count ≥10 per §5 target.

**Exit criteria.**

- 100% doc coverage on declarations (verified via grep audit).
- ≥10 supplemental fixtures.
- Edge-case coverage: every `mutation` in the spec has at least one fixture exercising the path.

**Quality bar dimensions met.** Documentation + fixture targets per §5.

### Iter 5 — Self-review + go beyond

**Goal.** Pass the project's review skills; surface what review skills don't catch.

**Entry criteria.** Iter 4 done.

**Work performed.**

- Run own review skills against the emission. Expected output: `iter5-review-skills-findings.md` (canary 8 example: 3 review skills × ~25–38 checks each = 74 total checks; pass ≥75% / concern <25% / fail <5%).
- Dispatch opus subagent with prompt "find what review skills miss." Expected output: `iter5-beyond-review-findings.md` (canary 8 surfaced 25 findings outside review-skill scope).
- Triage findings: MUST-FIX (blocking) / SHOULD-FIX (high impact) / DEFERRED (low priority, captured for future).
- Address all MUST-FIX and SHOULD-FIX findings.

**Exit criteria.**

- Zero outstanding MUST-FIX findings.
- All SHOULD-FIX findings either fixed OR explicitly deferred with rationale.
- Iter 5 trace doc records the disposition of every finding.

**Quality bar dimensions met.** Review-skill clean + corpus-novel quality dimensions (canary 8 is the only adapter in corpus with fuzz harnesses + benchmarks + doc.go).

---

## 5. Quality bar (numerical)

Distilled from canary 8's §4 plan.md. Each dimension has a **corpus median** (current state of upstream prebid-server-go corpus), a **target** (canary 8 "best in class" bar), and a **measurement** method.

| Dimension | Corpus median | Target | Measurement |
|---|---|---|---|
| Line coverage | ~85% | **≥95%** | `go test -cover` (Go) / `mvn jacoco:report` (Java) |
| Branch coverage | ~75% | **≥90%** | `go test -coverpkg=./... -coverprofile=...` (Go) / JaCoCo branch (Java) |
| GoDoc / Javadoc on exported symbols | ~50% | **100%** | grep audit on `// {Symbol}` or `/** ... */` |
| GoDoc / Javadoc on unexported helpers | ~10% | **100%** | grep audit |
| Fuzz functions | 0 | **≥1** | `go test -fuzz=...` (Go) / junit-quickcheck (Java) |
| Benchmarks | 0 | **≥2** | `go test -bench=...` (Go) / JMH (Java) |
| Property/invariant tests | 0 | **≥1** | `testing/quick` (Go) / junit-quickcheck (Java) |
| Sentinel error values | 0–1 | **≥3** | `errors.Is` test cases (Go) / `instanceof` assertions (Java) |
| Race-clean | varies | **PASS** | `go test -race ./...` (Go) / no Java equivalent |
| Pre-alloc on >0-cap slices | inconsistent | **100%** | code review pass; `make([]T, 0, n)` enforced |
| Supplemental fixtures | ~6 | **≥10** | file count under `{bidder}test/supplemental/` |
| Source-lang unit-test scenarios reproduced | N/A | **100%** (every `@Test` matched) | scenario mapping audit |

**Notes on measurement:**

- Branch coverage in Go requires post-processing the coverprofile (no native `-covermode=branch`). Approximation: use mutation-testing tool OR (line-coverage × 0.85) as a rough proxy.
- Property tests in Go corpus today: 0 across all 250+ adapters. Canary 8 added the first.
- Fuzz/bench/doc.go are corpus-unique to canary 8; future canaries should preserve this advantage.
- Source-lang fidelity is the load-bearing measurement: parity is 100% or it isn't.

---

## 6. Findings taxonomy

The full F-new-N catalogue across canaries 1–8. Structure: ID | Bucket | Severity | Status | Evidence (canary first surfaced + file:line if known).

### Buckets

- **template-gap:** Jinja template doesn't have a branch for the spec's value/pattern.
- **helper-gap:** port_engine helper missing or incomplete.
- **fidelity:** cross-language semantic divergence (NBSP, map-key ordering, Unicode whitespace).
- **test:** test-file gap or stale scaffolding.
- **convention:** target-language idiom / naming drift.
- **docs:** documentation gap or stale claim.
- **renderer:** renderer-level fix (alias mapping, hand-fill substitution).

### Severity (for v1.0.0 promotion)

- **BLOCKING:** v1.0.0 cannot ship without fixing.
- **HIGH:** v1.0.0 needs to fix; v0.6.0 may ship with workaround documented.
- **MEDIUM:** Quality-of-life; may defer to v0.7.0+.
- **LOW:** Documentation polish; defer indefinitely.

### Status

- **fixed-already:** Stage A/B/C/Phase 1/Phase 2 already addressed.
- **open-for-v0.6.0:** Confirmed 1+ time; landing recommended for v0.6.0.
- **open-for-v1.0.0:** Confirmed 1+ time; required for v1.0.0.
- **deferred:** Documented gap; not on near-term roadmap.

### Catalogue

#### Canary 1 (kobler v1) — F1–F13 baseline findings

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F1 | template-gap | BLOCKING | fixed-already | `bidder.go.j2` unconditionally imports `encoding/json`; fails compile when `has_extra_info=False` |
| F2 | docs | BLOCKING | fixed-already | `port-report.json` shape diverges from schema (8 non-schema fields drift) |
| F3 | template-gap | LOW | fixed-already (status-quo) | Templates emit excess whitespace; rely on post-emit `gofmt -s -w` |
| F4 | helper-gap | BLOCKING | fixed-already | Rule 36 inverse fixture transform doesn't translate `imp.ext` shape (Java per-bidder slot → Go bidder slot) |
| F5 | template-gap | HIGH | fixed-already | Currency-conversion logic missing from `bidder.go.j2` body |
| F6 | template-gap | MEDIUM | open-for-v1.0.0 | Dev-prod toggle endpoint resolution is a stub |
| F7 | template-gap | MEDIUM | open-for-v1.0.0 | Device/User sanitization not emitted |
| F8 | template-gap | MEDIUM | fixed-already | `bid_type_resolution: method-chain-fallback` falls through to constant-banner |
| F9 | template-gap | LOW | fixed-already | `bidder-info.yaml.j2` emits `gvlVendorID: 0` against Go convention |
| F10 | convention | LOW | fixed-already | `bidder-test.go.j2` emits `Test{ClassRoot}` instead of canonical `TestJsonSamples` |
| F11 | docs | MEDIUM | fixed-already | Read-orchestrator: `fetch_method` enum mismatch (`local` vs `local-checkout`) |
| F12 | docs | LOW | fixed-already | Read-orchestrator: `test-application.properties` path is wrong |
| F13 | docs | LOW | informational | Golden field drift (expected per R4 modulo-provenance) |

#### Audit + spike — F-new-1..F-new-8 catalogued during corpus audit

| ID | Bucket | Severity | Status | Summary | First confirmed |
|---|---|---|---|---|---|
| F-new-1 | template-gap | HIGH | fixed-already | `imp_ext_unmarshal=none` branch missing | canary 4 (aax) |
| F-new-2 | template-gap | HIGH | open-for-v1.0.0 | `endpoint_resolution=template-macro` not in template enum | canary 5 (adverxo) — confirmed 3× |
| F-new-3 | template-gap | MEDIUM | partial-fix | `by-bid-mtype` / `bid-mtype-switch` not in template (single-step path) | canary 5 (adverxo) |
| F-new-4 | template-gap | MEDIUM | deferred | Single-step `by-bid-ext-typed-field` not in template (audit pairs only) | not confirmed in MVP |
| F-new-5 | convention | LOW | fixed-already | `single-batched`/`per-batch` synonyms (canonicalize at renderer) | canary 4 (aax) |
| F-new-6 | convention | LOW | fixed-already | Header case asymmetry `X-OpenRTB-Version` vs `x-openrtb-version` | canary 7 (adkernelAdn) |
| F-new-7 | template-gap | HIGH | open-for-v1.0.0 | Multiple new bid_type values + per-key batching (umbrella; expanded into EXT-A and EXT-B) | canary 7 (adkernelAdn) |
| F-new-8 | template-gap | MEDIUM | deferred | `string-sniff-adm-substring` bid-type not in template (1/16 corpus) | not confirmed in MVP |

#### Canary 2 (kobler v2) — F-new-9..F-new-13 fixture-authoring helpers

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-9 | helper-gap | HIGH | fixed-already | bid-response.cur fallback (helper copies from auction-response) |
| F-new-10 | helper-gap | HIGH | fixed-already | `TEST_ENDPOINT` URI mismatch (renderer + template share constant) |
| F-new-11 | helper-gap | HIGH | fixed-already | expected_bids derived from bid-response (not auction-response — strips framework enrichments) |
| F-new-12 | template-gap | HIGH | fixed-already (template) | `expectedRequest.impIDs` emission in fixture |
| F-new-13 | helper-gap | HIGH | fixed-already | `expectedRequest.body` simulation (passthrough fallback for non-mutating adapters) |

#### Canary 3 (vungle) — F-new-15, F-new-22, F-new-23

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-15 | template-gap | HIGH (vungle) / MEDIUM (corpus) | open-for-v1.0.0 | Site→App synthesis & vungle-slot imp.ext rewrap |
| F-new-22 | helper-gap | HIGH (per-bidder) | fixed-already | Java IT auction-request lacks user object; Go nil-derefs (`inject_empty_user_if_missing` opt-in) |
| F-new-23 | template-gap | LOW | fixed-already | Supplemental no-response-body template kobler-only (gated on `http_status_kind`) |

#### Canary 4 (aax) — F-new-24, F-new-25, F-new-26

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-24 | renderer | LOW | open-for-v0.6.0 | Cross-language SHA divergence affects params_test invalid case set |
| F-new-25 | template-gap | MEDIUM | open-for-v1.0.0 | bid-type method-chain step with non-canonical bid.ext field path emits TODO |
| F-new-26 | template-gap | MEDIUM | open-for-v1.0.0 | endpoint_resolution=query-parameter-augmentation is a TODO stub |

#### Canary 5 (adverxo) — F-new-27..F-new-30

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-27 | template-gap | HIGH | open-for-v1.0.0 | multi-token-substitution endpoint TODO stub (= F-new-2; same root) |
| F-new-28 | renderer | MEDIUM | open-for-v0.6.0 | Cross-language ImpExt vs ExtImp legacy naming asymmetry |
| F-new-29 | template-gap | LOW (canary) / HIGH (ADR-007 F4) | open-for-v1.0.0 | Bid post-processing macros (`${AUCTION_PRICE}`) not template-emitted |
| F-new-30 | template-gap | LOW | deferred | Native ADM unwrap not template-emitted (1 corpus pair) |

#### Canary 6 (thetradedesk) — F-new-31, F-new-32, F-new-33

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-31 | template-gap | HIGH | open-for-v1.0.0 | Rule 35 inverse typed-extra-info struct emission (json-encoded vs raw-string variants) |
| F-new-32 | template-gap | LOW (canary) / MEDIUM (corpus) | open-for-v0.7.0 | Banner.W/H format[0] mutation not template-covered |
| F-new-33 | template-gap | LOW (canary) / LOW-MEDIUM (corpus) | open-for-v0.7.0 | Site/App publisher rewrite not template-covered |

#### Canary 7 (adkernelAdn) — F-new-7 EXT-A, F-new-7 EXT-B, F-new-34

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-7 EXT-A | template-gap | HIGH | open-for-v1.0.0 | per-key batching not template-covered |
| F-new-7 EXT-B | template-gap | HIGH | open-for-v1.0.0 | imp-id-correlation bid-type not template-covered |
| F-new-34 | renderer | HIGH (affected pairs) | open-for-v1.0.0 | Rule 46 multi-form naming master-sample (`naming_form_resolution` schema needed) |

#### Canary 8 (teal) — 11 net-new findings (BR-01..BR-25 in beyond-review report; partial mapping below)

| ID | Bucket | Severity | Status | Summary |
|---|---|---|---|---|
| F-new-37 (predicted) | template-gap | MEDIUM | open-for-v0.7.0 | per-imp `imp.ext.prebid.storedrequest.id` injection helper + template branch |
| F-new-38 (predicted) | template-gap | MEDIUM | open-for-v0.7.0 | `request.publisher_id_from_first_imp_ext` op kind for site+app publisher rewrite |
| F-new-39 (predicted) | template-gap | MEDIUM | open-for-v0.7.0 | `request_ext_property_stamp` op kind for FlexibleExtension property addition |
| BR-01 | test | HIGH | open (post-canary) | Stale fuzz-test recovery scaffolding references renamed test |
| BR-02 | fidelity | HIGH | documented | Cross-language `isBlank` / NBSP / Unicode whitespace divergence |
| BR-03 | fidelity | MEDIUM | documented | JSON map-key ordering: Go alphabetical vs Java insertion order |
| BR-04 | test | HIGH | open (post-canary) | `fmtRecover` is dead code in test file |
| BR-05 | docs | MEDIUM | documented | doc.go performance numbers stale |
| BR-06 | docs | MEDIUM | documented | doc.go "Two cross-language differences" undercount |
| BR-07 | template-gap | MEDIUM | deferred | modifyImp 7-marshal allocation pattern (sjson would help) |
| BR-19 | docs | MEDIUM | documented | audio-imp.json fixture exercises unreachable-in-prod path (Java fidelity) |
| BR-21 | docs | LOW | documented | getBidType priority `banner > video > audio > native` inverted from corpus default |

**Cumulative count.** ~33 distinct F-new-* findings across canaries 1–7; ~11 net-new from canary 8 (teal) including 22 BR-* "beyond review" items partially overlapping. Total: ~44 distinct findings.

---

## 7. Subagent dispatch playbook

Distilled from the 9+ subagent dispatches across canary 8 (teal), plus prior canary subagent uses.

### When to dispatch

A subagent dispatch is the right move when:

- **Recon work** is mechanical-but-tedious (read 9+ Java files, extract spec). Inline reading is fine for <5 files; subagent for ≥5.
- **Independent verification** is needed (Java-fidelity audit, corpus benchmark). The parent agent's context already biases toward "make this work"; a fresh subagent with the source as input gives an unbiased read.
- **Wide-search work** crosses many files (e.g., "find idiomatic Go patterns in 3 top-tier upstream adapters"). Subagent's parallel reading is faster than serial inline reading.
- **"Find what review skills miss"** — this is the killer use case. The parent agent ran review skills and got their canonical output; a subagent's job is to think outside that frame and surface what those skills don't check.
- **Trace authoring** is heavy synthesis work. The trace doc summarizes 4–8 hours of work into 200–500 lines of markdown; a subagent specializing in synthesis produces tighter prose than the parent doing it inline.

### Subagent inputs (per dispatch type)

**Recon dispatch.**

- Inputs: source-lang HEAD SHA + target adapter directory path + the read-skill's output spec.
- Output format: a markdown spec doc + a list of files read with line counts.
- Typical duration: 15–45 minutes (opus, max thinking).

**Fidelity audit dispatch.**

- Inputs: source-lang adapter file path + emitted target-lang adapter file path + source-lang test file paths.
- Output format: behavior-by-behavior comparison table + findings table (BLOCKING / HIGH / MEDIUM / LOW / NOTE).
- Typical duration: 30–90 minutes (opus, max thinking).

**Corpus benchmark dispatch.**

- Inputs: emitted adapter dir + 3 hand-picked top-tier upstream adapter dirs (e.g., openx/pubmatic/rubicon for Go).
- Output format: per-dimension comparison table (color-coded), strengths, gaps, recommendations.
- Typical duration: 30–60 minutes.

**"Find what review skills miss" dispatch.**

- Inputs: emitted adapter dir + the review skills' SKILL.md files (so the subagent knows what's already checked).
- Output format: 15–30 findings outside the skills' scope, each with severity / category / observation / evidence / recommendation / "reachable by review skills?" annotation.
- Typical duration: 60–120 minutes (opus, max thinking).

**Trace authoring dispatch.**

- Inputs: per-iteration notes + per-finding notes + per-gate scoreboard data.
- Output format: full trace doc following the template structure (`docs/runs/d3.8-{bidder}-canary-*.md`).
- Typical duration: 30–60 minutes.

### Output format conventions

Across all dispatches, use these section conventions:

- **Executive verdict** at top (PASS / PASS-WITH-NOTES / REQUEST-CHANGES / FAIL).
- **Findings table** with stable IDs (BR-NN, RV-NN, F-new-NN, M-NN per dispatch type).
- **Per-finding detail** with severity / category / observation / evidence / recommendation / "reachable by review skills" annotation.
- **Cross-cutting concerns** section for findings that span multiple skill boundaries.
- **Methodology notes** at bottom for any decisions about scope/severity.

### Model choice + thinking effort

User mandate: **always use opus subagents with max thinking** for all canary subagent dispatches. Per memory note `feedback_subagent_model.md`. Lower-effort sonnet calls produce inferior fidelity-audit output (fewer findings, weaker rationale).

---

## 8. Direction-specific notes

### 8.1 Java→Go (port-java2go) — what we learned

**Helper inventory** (the 12 port_engine helpers needed for Java→Go canaries):

1. `byte_copy(source_path, dest_path)` — Rule 38 byte-fidelity.
2. `normalize_bidder_name(go_name, target_lang='java')` — Rule 46 forward.
3. `alias_graph_invert(parent_spec, alias_specs, direction)` — Rule 33 inverse.
4. `iab_table_translate(direction, source_artifact)` — Rule 42 inverse.
5. `r5_check_at_port_time(source_spec, dest_spec)` — gate 8.
6. `port_report_emit(report_dict, path)` — gate 7.
7. `alphabetical_insert(file_path, marker_pattern, insert_line, language)` — registry insertion.
8. `prefix_uniqueness_check(target_lang, bidder_name)` — gate 5 pre-check.
9. `gofmt_post_process(file_paths)` — gate 4a remediation.
10. `imp_ext_shape_transform_java_to_go(fixture_dict, java_bidder_name)` — F4 fix; Java per-bidder slot → Go bidder slot.
11. `exemplary_fixture_assemble_java_to_go(*, java_auction_request, java_auction_response, java_bid_request, java_bid_response, java_bidder_name, expected_request_body_simulator=None, default_bid_type='banner', test_endpoint=TEST_ENDPOINT, inject_empty_user_if_missing=False)` — F-new-9/10/11/12/13/22 fix.
12. `simulate_makerequests_mutations(bid_request, mutations)` — F-new-15/16/20/32/33 fixture body simulator.

**Template emission patterns:**

- 7 templates at `prebid-server-go/port-java2go/templates/*.j2`: `bidder.go.j2`, `bidder-test.go.j2`, `imp-ext-pojo.go.j2`, `bidder-info.yaml.j2`, `params-test.go.j2`, `exemplary-fixture.json.j2`, `supplemental-fixture.json.j2`.
- Excessive whitespace in templates is BY DESIGN (F3); `gofmt_post_process` canonicalizes.
- `imp-ext-pojo.go.j2` emit is conditional on `imp_ext_unmarshal_kind != "none"` (F-new-1).
- `bidder.go.j2` has multiple Phase 2 hooks: `_emit_parse_imp_ext`, `_has_per_imp_work`, `_legacy_raw_go_with_handlers`.
- `supplemental-fixture.json.j2` has `http_status_kind` gating for canonical-helpers vs legacy-raw vs kobler-style nil-body short-circuit.

**Fixture-assembly patterns:**

- Java IT 4-file split (auction-{request,response} + bid-{request,response}) → Go flat exemplary file.
- Java's `imp.ext.{bidder_name}` rewrites to Go's `imp.ext.bidder` (Rule 36 inverse + helper 10).
- bid-response.cur fallback from auction-response (helper 11's `_apply_cur_fallback`).
- expected_bids derived from bid-response (NOT auction-response — auction-response has framework enrichments).
- expectedRequest.uri uses `TEST_ENDPOINT` constant (`https://test.example.com/bid`) shared between renderer + bidder-test.go.j2.
- expectedRequest.impIDs from `mockBidRequest.imp[].id` (template-emitted).
- expectedRequest.body simulation: passthrough for non-mutating adapters; `simulate_makerequests_mutations` for mutating adapters.

**Common workaround patterns** (canary-tested, applicable for Java→Go):

1. TODO-stub for unsupported endpoint kinds (template-macro / multi-token-substitution): renderer passes `multi-token-substitution`, template emits TODO body returning `a.endpoint`, gate 2 passes when `TEST_ENDPOINT` has no token. Validated 3× (adverxo, thetradedesk, adkernelAdn).
2. Spec-value alias mapping at renderer ctx assembly. Validated for `bid-mtype-switch → by-bid-mtype` (thetradedesk), `imp-id-correlation → by-bid-mtype + default-banner` (adkernelAdn), `per-key → single-batched` (adkernelAdn).
3. `has_extra_info=False` bypass (workaround for empty-extraInfo-struct TODO when typed Spring config or no-extra-info). Validated 3× (thetradedesk, adverxo+, adkernelAdn).
4. Passthrough body when template doesn't mutate. Validated 4× (thetradedesk, adverxo, adkernelAdn, +partial vungle).
5. `inject_empty_user_if_missing=False` per-bidder verification.
6. Custom header canonicalization (Java-canonical mixed-case `X-OpenRTB-Version`).
7. Rule 46 multi-form naming (renderer reads from Java's lowercase paths, emits to Go's camelCase paths).

### 8.2 Go→Java (port-go2java) — what to expect

**No Go→Java canary has run yet (D2.8 is upcoming).** Predictions below carry confidence labels:

- **P-high:** Direction-flipped version of an established Java→Go finding; expect mirror.
- **P-med:** Direction-flipped finding likely but with Go-side specifics that may flip frequency.
- **P-low:** Speculation based on Java-side ecosystem differences; expect surprises.

#### Inverse mapping table (predictions)

| Java→Go finding | Go→Java predicted equivalent | Confidence |
|---|---|---|
| F1 (unused encoding/json) | Java emits unused Lombok import or unused Spring annotation when `has_extra_info=False` | P-high |
| F4 (imp.ext shape transform: Java per-bidder slot → Go bidder slot) | Inverse transform: Go's `imp.ext.bidder` → Java's `imp.ext.{bidder_name}` per-bidder slot | P-high |
| F-new-9 (bid-response.cur fallback) | Inverse: Java IT bid-response inherits cur from auction-response in framework — likely no Go→Java equivalent (Java framework auto-defaults to USD; Go side passes through) | P-med — likely NOT a finding |
| F-new-10 (TEST_ENDPOINT URI mismatch) | Java IT uses framework-resolved endpoint (no TEST_ENDPOINT analog needed); Java→Java (within-framework) tests don't have this concern | P-low — possibly not a finding |
| F-new-11 (expected_bids from bid-response) | Inverse: Java IT bid-response should have framework-enriched bids; Go→Java would need to RE-ENRICH bare Go bids to match Java IT shape | P-high |
| F-new-12 (impIDs) | Java side has no `impIDs` field convention; predicted analog: `expectedHttpRequestImps` field | P-low — Java framework doesn't expose this |
| F-new-13 (expectedRequest.body simulation) | Inverse: Java IT bid-request includes framework enrichments (`secure`, `tid`, `at`, `tmax`, `cur:[USD]`, `ext.prebid.{server,channel}`, `source.tid`, `regs.gdpr`, etc.) — Go→Java port needs to ADD these to mockBidRequest before comparing | P-high |
| F-new-14 (legacy-raw-go status handlers) | Inverse: Java side uses framework-default status handling (`framework-default` vs `framework-default-plus-empty-seatbid-shortcircuit`); Go's per-status branching collapses to a Java helper call | P-med |
| F-new-22 (inject_empty_user) | Inverse: Java's null-safe `User::getBuyeruid` would handle Go's `request.User=nil` via `Optional` chain — likely NOT a finding | P-med — likely NOT a finding |
| F-new-23 (canonical-helpers no-response-body) | Inverse: Java's framework body-handling fixtures use different shape; predicted analog for malformed-body Java fixtures | P-low — likely a Java-side test convention |
| F-new-24 (cross-language SHA divergence) | Inverse: Go-side has `minLength:1`; Java side params_test invalid cases include `{cid:"", crid:""}` and they MIGHT validate under preserved-from-Go schema. Same pattern, mirror direction | P-high |
| F-new-25 (non-canonical bid.ext field path) | Inverse: Java side template typed wrapper structs are easier to express (Lombok-generated) so this finding may be lower-frequency on Java side | P-med |
| F-new-26 (query-parameter-augmentation) | Inverse: Java's `HttpUtil.appendQueryParameter` collapses to a one-liner; predicted: Java side has THIS as a built-in helper, no template gap | P-med — likely fixed-on-emission |
| F-new-27 / F-new-2 (template-macro endpoint) | Inverse: Java's `String.format` or Spring's `${env}` templating — different mechanism but same conceptual gap | P-high |
| F-new-28 (ImpExt vs ExtImp legacy naming) | Inverse: Java side has fewer naming asymmetries (always uses `ExtImp{Bidder}` per Spring convention) — likely NOT a finding on Go→Java | P-med |
| F-new-29 (bid post-processing macros) | Inverse: Java's `MacroProcessor` is a framework class; predicted analog has different shape | P-med |
| F-new-31 (Rule 35 typed-extra-info) | Inverse: Java's typed `BidderConfigurationProperties` subclass NEEDS to be authored from Go's flat string `ExtraAdapterInfo` — this is the WHOLE POINT of Rule 35 inverse forward direction. Expect inverse to SURFACE this as the dominant Go→Java finding | P-high |
| F-new-34 (Rule 46 multi-form naming) | Inverse: Java reads from Go's camelCase paths, emits to Java's lowercase paths. Same `naming_form_resolution` schema works in both directions | P-high |
| F-new-7 EXT-A (per-key batching) | Inverse: Java's `Map.entrySet()` batching idiom may differ from Go's `map` literal pattern, but the schema field is direction-agnostic | P-med |
| F-new-7 EXT-B (imp-id-correlation) | Inverse: Java's stream-walking `imp-id-correlation` is idiomatic via `Optional<Imp>` chains — likely cleaner Java template than Go template | P-med |

#### Predicted Go→Java helper inventory

The 12 Java→Go helpers should have inverses:

1. `byte_copy` — symmetric, no change.
2. `normalize_bidder_name(java_name, target_lang='go')` — used.
3. `alias_graph_invert(parent_spec, alias_specs, direction='go-to-java')` — direction parameter handles both.
4. `iab_table_translate(direction='go-to-java', source_artifact)` — inverse: Go data-table → Java YAML-inlined.
5. `r5_check_at_port_time` — symmetric.
6. `port_report_emit` — symmetric.
7. `alphabetical_insert(language='java')` — Java equivalent: maven plugin loader configs, Spring component scans.
8. `prefix_uniqueness_check(target_lang='java')` — Java has no prefix-uniqueness gate (P-low this is needed).
9. `mvn_checkstyle_dry_run(target_clone)` — direct analogue of `gofmt_post_process`; ALREADY EXISTS in port_engine.
10. `imp_ext_shape_transform_go_to_java(fixture_dict, go_bidder_name)` — INVERSE; emits Java per-bidder slot from Go bidder slot.
11. `exemplary_fixture_assemble_go_to_java(...)` — INVERSE; needs to RE-ENRICH bare Go bids with framework enrichments to match Java IT shape. **Predicted dominant new helper for D2.8.**
12. `simulate_makerequests_mutations` — symmetric IF the mutation ops are direction-agnostic.

#### Predicted Go→Java template emission patterns

Templates needed (predicted):

- `BidderJava.java.j2` — analog of `bidder.go.j2`; emits Builder + makeHttpRequests + makeBids per Java canonical pattern.
- `BidderTestJava.java.j2` — analog of `bidder-test.go.j2`; emits JUnit test class + `assertJSONEq` invocations.
- `ExtImpBidderJava.java.j2` — analog of `imp-ext-pojo.go.j2`; emits Lombok-annotated POJO with Jackson `@JsonProperty` tags.
- `bidder-yaml.yaml.j2` — analog of `bidder-info.yaml.j2`; emits Spring `@PropertySource` config YAML at `src/main/resources/bidder-config/{bidder}.yaml`.
- `params-test-java.java.j2` — analog of `params-test.go.j2`; emits `BidderParamsTest` per-bidder.
- `it-fixture-{auction,bid}-{request,response}.json.j2` — 4 templates (Java IT 4-file split) replacing Go's flat exemplary fixture template.
- `supplemental-fixture-java.json.j2` — analog of `supplemental-fixture.json.j2`.

Key direction-flipped concerns:

- Templates must EMIT Java-side framework enrichments to mockBidRequest fixtures (the inverse of Go's "strip enrichments to passthrough body").
- Templates must EMIT 4-file IT fixture split (the inverse of Go's flat shape).
- Templates must EMIT Lombok annotations (`@Builder`, `@Value`, `@Getter`) on POJOs.
- Templates must EMIT Spring `@Configuration` class for bidder + `@Bean`-method registration.

---

## 9. Multi-adapter sprint playbook

What changes when running 3–5 canaries in parallel vs sequentially.

### Subagent dispatch fan-out

**Sequential (canaries 1–7):** Each canary's subagent dispatches block on the prior canary's findings being captured. Total subagent dispatches = N (canaries) × ~3 (recon, fidelity, benchmark per canary).

**Parallel (D2.8+ multi-adapter sprint, planned):** Dispatch fan-out per phase:

- Phase Pre (spike) — N parallel subagents, one per bidder, max-thinking opus, 30–60 min each.
- Phase C (canary baseline) — INLINE work per-canary; subagents only used for ad-hoc subspecialty (e.g., "this bidder uses Vert.x in a non-standard way; recon").
- Phase D (iterations) — N parallel "find-what-review-skills-miss" subagents, one per bidder, max-thinking opus, 60–120 min each.
- Phase E (verification) — N parallel fidelity-audit subagents + N parallel corpus-benchmark subagents.

**Concurrency bound.** Limit to ~5 concurrent subagents per phase (more, and tracking outputs becomes hard for the parent agent). For larger sprints, batch in waves of 5.

### Findings dedup across parallel canaries

When 3–5 canaries surface findings concurrently, expect ~30–60% overlap (e.g., template-macro endpoint surfaced 3× across canaries 5/6/7). Dedup strategy:

1. Each canary trace catalogues findings independently using F-new-N convention.
2. After all canaries' Iter 0 baselines complete, parent agent runs a dedup pass: cluster F-new findings by symptom + root cause; merge cross-references.
3. Findings shared across ≥2 canaries get an "umbrella F-new-N" with EXT-A/B/C sub-findings (canary 7 model: F-new-7 EXT-A + EXT-B).
4. SKILL/template/helper fix prioritization weighted by canary-frequency: 3+ canaries surfacing → P0; 2 canaries → P1; 1 canary → P2.

### Cross-canary lessons capture cadence

After every batch of canaries:

- Update §6 catalogue with new F-new-N entries.
- Update §3 gate failure modes / remedies with newly-discovered patterns.
- Update §8 direction-specific notes if the batch surfaces direction-flipped findings.
- File any post-canary follow-up PRs against this repo (per `docs/methodology/reflection-loop.md` §5).

### When to pause for SKILL improvements

Pause-conditions (run a SKILL improvement PR before the next batch):

- A SAME finding surfaces in ≥3 consecutive canaries (signals high-frequency gap; fix it before the next batch wastes time rediscovering).
- A canary takes >2× the typical duration due to a template/helper gap (signals diminishing returns from the current SKILL state).
- Operator hand-fill consistently exceeds 30 lines per pair (signals low automation; pause to extend templates).
- A net-new finding has severity HIGH and confidence ≥P-med for ≥3 future bidders (signals proactive fix opportunity).

Per D3.8: Stage A/B was a pause-batch after canary 1 (13 findings → fixes); Phase 1 helpers was a pause-batch after canary 2; Phase 2 templates was a pause-batch after canary 3; canaries 4–7 ran without pauses because findings were lower-frequency.

---

## 10. Anti-patterns observed

What NOT to do, learned from canary 1's chaos before canaries 5–7's clean runs.

### Skipping the spike

**Symptom.** Canary 1 (kobler v1) ran without a pre-canary spike; surfaced 13 findings. Canary 2 ran with the same approach; surfaced 5 more. By contrast, canaries 4–7 ran AFTER a 5-pair spike (`d3.8-mvp-pairs-spike-2026-05-05.md`) and surfaced ~3 findings each, all predicted.

**Fix.** Always run Phase Pre (§2 spike checklist) before Phase C. The spike's predictions are not always correct (canary 7 had 6 predicted findings, all confirmed; canary 4 had aax cross-language SHA divergence as not-predicted) — but the act of forcing predictions trains operator intuition and surfaces the mitigatable predictable findings as Phase 2/3 prep work.

### Treating "passes 8 gates" as "done"

**Symptom.** Canary 5 (adverxo) was the first 10/10 canary. The temptation was to declare it done. But a SUPER-review (review skills + opus subagent) would have surfaced corpus-novel quality dimensions canary 5 didn't have (fuzz, bench, doc.go, 100% doc coverage). Canary 8 (teal) raised the bar to "best in class" — passing 8 gates is the FLOOR, not the ceiling.

**Fix.** For canaries intended for upstream submission, run all 5 iterations (§4). For canaries that are smoke tests of the SKILL, 8-gate-clean is acceptable. Don't conflate "smoke test passed" with "ready to ship."

### Hand-emitting mutations without capturing as F-new-* findings

**Symptom.** Canary 1's render script applied F4 (imp.ext shape transform) inline in the renderer without capturing it as F-new-4 in port-report. Result: canaries 2–7 had to re-discover the workaround pattern.

**Fix.** Every hand-fill or renderer-side workaround must be captured as an F-new-N finding in port-report's `unresolved_translations[]` or `human_todos[]`. The next canary's renderer either inherits the workaround from the prior canary's renderer, or the workaround gets promoted to a port_engine helper (if the pattern recurs).

### Not deepcopying inputs in helpers (reviewer F-1 in PR #5)

**Symptom.** `port_engine.exemplary_fixture_assemble_java_to_go` mutated input dicts in place — caller's `mock_bid_request` was modified. PR #5 reviewer flagged this.

**Fix.** All port_engine helpers MUST `copy.deepcopy(input)` before mutation. The helper's input contract is: "I will not modify your input; I return a fresh object." This is a non-negotiable safety contract for shared helpers; assume callers chain helper calls and rely on input immutability.

### Not running the super-review

**Symptom.** Canaries 5/6 had 10/10 gates clean. Canary 7 had 10/10 gates clean AND cleared 80% coverage. None of these canaries ran review skills or opus "find-what-review-skills-miss" subagents — because they weren't intended for upstream submission. Canary 8 (teal) was the first to do this and surfaced 25 findings outside review-skill scope (canary 8 BR-01..BR-25).

**Fix.** Any canary intended for upstream submission MUST run Iter 5 (§4). The opus "find-what-review-skills-miss" subagent is the differentiator dispatch — review skills are necessary but not sufficient.

### Mutating iter-state without capturing iter trace

**Symptom.** Canary 3 (vungle) had 3 retry rounds in gate 2 before passing. The trace doc captures each round's failure + fix. Without that, future operators would not know the per-mutation order-of-operations dependency.

**Fix.** Every iteration retry round gets logged in the canary trace's "Iteration trace" section. Even when you know the answer, write it down — it's the historical record for the next operator who hits a similar issue.

### Treating "Java→Go" findings as "everywhere findings"

**Symptom.** Canary 1's F11 (read-orchestrator `fetch_method` enum) was a Java-side read-skill finding. Easy to fix once; easy to forget the Go-side has the SAME structurally-different organization issue (per F11 follow-up note in canary 2).

**Fix.** Direction-specific findings must explicitly note "this is direction-X-specific" with an inverse-direction sibling task captured. Update §8 notes when a direction-asymmetric finding surfaces.

### Letting the renderer drift from the SKILL prose

**Symptom.** Renderer-level patches (e.g., F-new-22 inject_empty_user opt-in flag) accumulate in `render_*.py` scripts but don't always promote to port_engine helpers. Each subsequent canary's renderer copy-pastes the prior renderer; over 7 canaries, renderer diverges 200+ lines from the canonical SKILL emission.

**Fix.** When the same renderer-level workaround is applied in 2+ canaries, promote it to a port_engine helper before the third canary. This is the "rule of three" for helper promotion. If you can't promote, document the workaround in `references/porting-guide.md` so future operators don't re-derive it.

---

## Closing note

This runbook is a living document. Future canaries that surface new patterns SHOULD update the relevant section and increment the relevant version. The expected next updates:

- After D2.8 first Go→Java canary: §8.2 confidence labels resolve to "confirmed" / "disconfirmed"; §8.2 helper inventory and template list firm up.
- After multi-adapter sprint completes: §9 concrete findings dedup pattern + cadence numbers.
- After v1.0.0 promotion: §6 catalogue closes "open-for-v1.0.0" entries.
- After the next 20 canaries: §3 gate failure modes get more nuanced; §6 catalogue likely doubles in size before stabilizing.

The ratio of "canary spent on novel work" vs "canary spent on rediscovery" should trend upward over time. If a canary surfaces ≥2 findings already in this catalogue without progress on closing them, that's a signal to pause for SKILL improvements (per §9).
