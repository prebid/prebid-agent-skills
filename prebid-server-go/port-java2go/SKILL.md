---
name: port-java2go
description: Translates a Java-source Adapter Spec (prebid-server-java/read/specs/{bidder}/latest.yaml or .tmp/full-loop/{run-id}/java/{bidder}.yaml) into Go artifacts under prebid-server-go/adapters/{bidder}/ plus paired YAML, bidder-params, exemplary fixtures, and registry entries. USE WHEN porting a new (or existing) Java bid adapter to the Go codebase. Walks the 46 port-translation rules, applies the 7-step pipeline, emits port-report.json. SKELETON — Phase D3 fills the body; not yet operational.
version: 0.1.0
---

# port-java2go (Java → Go)

> **Status: SKELETON.** Phase D1.1 scaffold. Phase D3 (per `docs/execution-plan-phase-d.md`) will populate the pipeline body, ship the auto-PR shape automation, and validate the skill against the same 6 MVP pairs as D2 reversed (`kobler`, `aax`, `adkernelAdn`, `adverxo`, `vungle`, `thetradedesk`). Until D3 lands, invoking this skill returns a "not implemented" notice; the design contract below is what D3 implements.
>
> **D3 ships production-grade**, not exploratory. The empirical Go→Java dominance in merged PRs (12+ vs 0 in 18 months) reflects current tooling limits, not user need or maintainer disinterest. Phase D removes that asymmetry as a first-class deliverable.

## What this skill does

Takes a structured Java-source Adapter Spec (read by `prebid-server-java/read/skills/read-bidder-orchestrator`) and emits the Go artifacts that satisfy R5-strict cross-language equivalence at port time. Applies the 46 port-translation rules from `../read/skills/shared/port-translation-rules.yaml` in **inverse direction** (Java → Go). Emits a `port-report.json` documenting what was applied, what was novel, and what needs human review.

**Source** (this skill consumes): `prebid-server-java/read/specs/{bidder}/latest.yaml`, or transient at `.tmp/full-loop/{run-id}/java/{bidder}.yaml` when running under the Teal flow.

**Target** (this skill emits): Go artifacts at the canonical paths per `references/go-artifact-shapes.md` (D1.3 deliverable):

- `adapters/{bidder}/{bidder}.go` (Builder + MakeRequests + MakeBids)
- `adapters/{bidder}/{bidder}_test.go` (thin `RunJSONBidderTest` wrapper)
- `adapters/{bidder}/{bidder}test/exemplary/*.json` (re-authored from Java IT 4-file fixtures into Go's flat shape)
- `adapters/{bidder}/{bidder}test/supplemental/*.json` (error-path fixtures; preserve those reachable in Go)
- `adapters/{bidder}/params_test.go` (validates schema)
- `openrtb_ext/imp_{bidder}.go` (struct emitted from Java's `ExtImp{Bidder}.java` + Lombok annotations stripped)
- `openrtb_ext/bidders.go` constant addition + `coreBidderNames` slice entry (alphabetical, lower-first)
- `exchange/adapter_builders.go` import + map entry (alphabetical)
- `static/bidder-info/{bidder}.yaml` (camelCase keys; converted from Java's kebab-case)
- `static/bidder-params/{bidder}.json` (byte-copy from Java per Rule 38)

**Out of scope** (handled elsewhere or future): writing a Go adapter from scratch (`write/`, future); reviewing post-merge (`review/`, future composition); analytics modules / RTD modules / general modules / delta-ports (deferred per execution-plan-phase-d.md "Out of scope").

## Invocation

```bash
# One-shot Teal flow (read → port → review):
$ orchestrator port \
    --source-lang=java \
    --target-lang=go \
    --bidder={bidder} \
    --source-spec=prebid-server-java/read/specs/{bidder}/latest.yaml \
    --target-branch=feat/{bidder}-go-port \
    --run-id=2026-05-04T1430Z-a3f9

# Direct invocation (when the source spec is persisted):
$ /port-java2go --bidder={bidder} --target-branch=feat/{bidder}-go-port

# Spec-only port (no Go code emitted; useful for design review):
$ /port-java2go --bidder={bidder} --dry-run
```

Pre- and post-conditions per `../../docs/methodology/port-skills-design.md` §2.

## Pipeline (7 steps)

Per design doc `../../docs/methodology/port-skills-design.md` §3. Phase D3 fills each step's body; the skeleton below names the contract.

### Step 1 — Load + validate source spec

**TODO (D3)**: Load the Java-source spec YAML. Validate against `../read/skills/shared/adapter-spec.schema.json`. Confirm `source_language: java`. Reject (exit 1) if malformed or directionally wrong.

### Step 2 — Discover the bidder family

**TODO (D3)**: Read `meta.is_alias`, `meta.parent_aliases`, `aliases[]`, `meta.empire_parent_flavor`. Determine whether the bidder is primary, alias child, alias-empire parent (Java declares the empire on the parent's YAML), or alias-empire child. Family shape drives Rule 33 inverse (Java parent → Go child YAMLs decomposition) and Rule 44 inverse (alias-empire flavor coherence).

### Step 3 — Apply rules (Java → Go inverse direction)

**TODO (D3)**: Walk `../read/skills/shared/port-translation-rules.yaml` rule-by-rule in inverse direction. For each rule, check `spec_field_driver` against the source spec; emit `verdict: applied | skipped-not-applicable | skipped-source-side-only | applied-with-warning`.

D3's mechanical-ready rules (priority order; same 10 as D2 in inverse direction):

1. Rule 38 — bidder-params byte-fidelity (`byte_copy` Java → Go)
2. Rule 46 inverse — name-normalization reversal (Java lowercase `adkerneladn` → Go camelCase `adkernelAdn`); requires the dual-spec assertion lookup since not fully mechanical in this direction
3. Rule 33 inverse — Java parent → child YAML decomposes into Go child → parent YAMLs
4. Rule 44 inverse — alias-empire flavor coherence (parent flavor inferred from Java aliases block, projected into Go child-yamls + alias entries)
5. Rule 36 inverse — Java IT 4-file split + JUnit class collapses to Go's flat `{bidder}test/exemplary/*.json` + `{bidder}_test.go` thin runner (semantic-coverage parity, not 1:1)
6. Rule 42 inverse — Java YAML-inlined IAB cats convert to Go data-table `iab_categories.go` with static-init `delivery_mechanism`
7. Rule 35 inverse (lossy-direction) — Java typed `BidderConfigurationProperties` subclass demotes to Go's `ExtraAdapterInfo` opaque JSON string (per Round-Trip Safety section pre-declaration). Emit `quirks[]: hardcoded-config-as-anti-pattern` if the Java subclass has fields the Go side won't structurally enforce.
8. Rule 39 — derived-view (no-op on porter)
9. Rule 19 inverse — Java `HttpUtil.headers()` collapse expands to explicit Go `http.Header` `Add()` calls
10. Rule 30 inverse — Java framework-default HTTP status handling expands to explicit Go `adapters.IsResponseStatusCodeNoContent` + `adapters.CheckResponseStatusCodeForErrors` helper calls

The remaining 36 rules are handled prose-driven (the SKILL walks the rule's prose body and applies the inverse translation in-line). Conflict resolution per design doc §5: lower-id rule wins on artifact placement; record `unresolved_translations[]` with reason `conflicting-rules` for the reflection loop.

**Lossy-direction safety**: Rule 35 inverse, Rule 19 inverse, Rule 30 inverse, Rule 8 (Java helper collapses → Go explicit expansions) are pre-declared lossy in `port-translation-rules.yaml` Round-Trip Safety section. The SKILL preserves source-side semantic information by emitting explicit `quirks[]` entries on the Go destination spec capturing what was lossy, so a future Go→Java re-port retains traceability.

### Step 4 — Author the destination spec

**TODO (D3)**: Construct the Go-side destination spec. Carry over R5-strict-shared fields verbatim. Apply Go-specific transformations on `code.adapter_struct`, `code.builder`, `code.make_requests`, `code.make_bids`. Re-compute `bidder_params_sha256` (matches source per Rule 38). Set `provenance.source.resolved_commit` to the same commit as the source spec.

### Step 5 — Emit Go artifacts

**TODO (D3)**: Walk the destination spec; emit files at the canonical paths listed under "Target" above. Use Jinja templates from `templates/` (D3 fills): `bidder.go.j2`, `bidder-test.go.j2`, `imp-ext-pojo.go.j2`, `bidder-info.yaml.j2`, etc.

Emission rules:

- **`gofmt -s -w` post-process**: every emitted `.go` file passes `gofmt -s -w` post-emit (via `scripts/lib/port_engine.gofmt_post_process`). Otherwise upstream Go CI fails on style.
- **`go vet` clean by construction**: templates include explicit error returns + named-result-parameter style only when needed. `go vet` should exit 0.
- **`coreBidderNames` alphabetical insert**: `port_engine.alphabetical_insert` does case-insensitive lower-first insertion into `openrtb_ext/bidders.go` and `exchange/adapter_builders.go`. This matches upstream `TestBidderUniquenessGatekeeping` enforcement.
- **Prefix uniqueness pre-check**: `port_engine.prefix_uniqueness_check(target_lang="go", bidder_name=...)` runs BEFORE emit. If the first 6 letters of the bidder name collide with an existing `coreBidderNames` entry, abort with operator notification — `TestBidderUniquenessGatekeeping` would fail otherwise.
- **PR-shape automation**: emit `recommended_pr_title: "New Adapter: {Bidder}"` (capital A per real-PR audit) and `target_pr_label_recommendations: []` (Go has no upstream PR template; no mandatory labels).
- **Companion docs PR**: emit `companion_docs_pr_draft` with target_repo `prebid/prebid.github.io`, file_path `dev-docs/bidders/{bidder}.md`, body_markdown populated from the source spec. Less maintainer-pressure than Java side, but expected for parity.
- **Pre-submit rebase**: rebase the target branch onto upstream `prebid/prebid-server` `master` HEAD; abort with operator notification on framework conflict; record outcome in `pre_submit_rebase`.

### Step 6 — R5-strict check at port time

**TODO (D3)**: Re-read the destination spec via `prebid-server-go/read/skills/read-adapter-orchestrator`. Call `scripts/lib/r5_check.compare_pair(go_spec, java_spec)` (no dual-spec assertions for new ports). Map the four-state harness output plus port-time direction-aware analysis to one of the six `r5_check.state` enum values; populate `byte_equal_fields[]`, `warn_fields[]`, `fail_fields[]`, `summary`.

### Step 7 — Emit port-report.json

**TODO (D3)**: Build the port-report dict per `../read/skills/shared/port-report.schema.json` (v0.2.0); write to `.tmp/full-loop/{run-id}/port-report.json`. Schema-validate before writing (use `scripts/lib/port_engine.port_report_emit`).

## Rule application order

Per design doc §4. Rules applied in declaration order from `port-translation-rules.yaml`. Two port runs of the same source spec at the same `port_translation_rules_version` produce byte-identical destination artifacts (R4 round-trip determinism). When two rules conflict, lower-id wins; conflict recorded in `unresolved_translations[]`.

## R5-strict check at port time

Per design doc §7. The skill consumes `scripts/lib/r5_check.compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result`. The four harness states map to the schema's six-state enum; the two extended states (`warn-target-strengthens-source`, `fail-source-omits-target-constraint`) are emitted when the port skill detects direction-specific source-vs-target asymmetries beyond what the harness compares.

A port-time R5 fail is a `human_todos[]` entry, not a CI failure. The port still ships; humans decide whether to merge.

## Quality bar (D3 acceptance gates)

D3 considers the skill production-ready only when, for each MVP pair:

1. Emitted Go compiles cleanly via `go build ./adapters/{bidder}/...`.
2. Emitted tests pass via `go test ./adapters/{bidder}/...`.
3. Adapter-coverage report (per upstream `./scripts/check_coverage.sh`) ≥ 80% (real-world median; well above the 30% CI minimum).
4. `gofmt -s -l` exits with no diff; `go vet ./adapters/{bidder}/...` exits clean.
5. `TestBidderUniquenessGatekeeping` passes (first-6-letter prefix unique against current `coreBidderNames`).
6. Emitted YAML validates against Go's `static/bidder-info/_schema.json`; emitted JSON validates against the bidder-params schema convention.
7. `port-report.json` schema-validates against `port-report.schema.json` v0.2.0.
8. `r5_check.state` matches the per-pair expectation in `docs/execution-plan-phase-d.md` §D3.3.

## References

- **Design doc**: [`../../docs/methodology/port-skills-design.md`](../../docs/methodology/port-skills-design.md) — 7-step pipeline + conflict resolution + novel-pattern handling.
- **Execution plan**: [`../../docs/execution-plan-phase-d.md`](../../docs/execution-plan-phase-d.md) — D3 acceptance criteria + per-pair expectations.
- **Rules corpus**: [`../read/skills/shared/port-translation-rules.yaml`](../read/skills/shared/port-translation-rules.yaml) — 46 rules at v0.2.0; the SKILL pins to this version. Round-Trip Safety section pre-declares lossy-direction asymmetries.
- **Output schema**: [`../read/skills/shared/port-report.schema.json`](../read/skills/shared/port-report.schema.json) — port-report contract (v0.2.0).
- **Source-spec schema**: [`../read/skills/shared/adapter-spec.schema.json`](../read/skills/shared/adapter-spec.schema.json) — what the source spec must satisfy.
- **R5 lib**: [`../../scripts/lib/r5_check.py`](../../scripts/lib/r5_check.py) — R5 comparator (Phase D0.1).
- **Port engine**: `../../scripts/lib/port_engine.py` — 9 mechanical helpers (D1.2 deliverable).
- **Inverse porting guide**: `references/porting-guide.md` — D1.3 authors this; analogue of upstream Java's `bid-adapter-porting-guide.md` (Go has no upstream equivalent).
- **Reflection loop**: [`../../docs/methodology/reflection-loop.md`](../../docs/methodology/reflection-loop.md) — Phase F consumes `port-report.json::human_todos[]` and `unresolved_translations[]`.

### Per-skill subdirectories

- [`references/`](references/) — Go-target emission references (D1.3 fills): `go-artifact-shapes.md`, `pr-shape.md`, `registration-rules.md`, `porting-guide.md` (internally authored — Go has no upstream equivalent).
- [`templates/`](templates/) — Jinja templates for Go artifact emission (D3 fills): `bidder.go.j2`, `bidder-test.go.j2`, `imp-ext-pojo.go.j2`, `bidder-info.yaml.j2`, etc.
