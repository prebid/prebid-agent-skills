---
name: port-go2java
description: Translates a Go-source Adapter Spec (prebid-server-go/read/specs/{bidder}/latest.yaml or .tmp/full-loop/{run-id}/go/{bidder}.yaml) into Java artifacts under prebid-server-java/src/main/java/org/prebid/server/bidder/{bidder}/ plus paired YAML, bidder-params, IT fixtures, and Spring config. USE WHEN porting a new (or existing) Go bid adapter to the Java codebase. Walks the 46 port-translation rules, applies the 7-step pipeline, emits port-report.json. SKELETON — Phase D2 fills the body; not yet operational.
version: 0.1.0
---

# port-go2java (Go → Java)

> **Status: SKELETON.** Phase D1.1 scaffold. Phase D2 (per `docs/execution-plan-phase-d.md`) will populate the pipeline body, ship the auto-PR shape automation, and validate the skill against the 6 MVP pairs (`kobler`, `aax`, `adkernelAdn`, `adverxo`, `vungle`, `thetradedesk`). Until D2 lands, invoking this skill returns a "not implemented" notice; the design contract below is what D2 implements.

## What this skill does

Takes a structured Go-source Adapter Spec (read by `prebid-server-go/read/skills/read-adapter-orchestrator`) and emits the Java artifacts that satisfy R5-strict cross-language equivalence at port time. Applies the 46 port-translation rules from `../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`. Emits a `port-report.json` documenting what was applied, what was novel, and what needs human review.

**Source** (this skill consumes): `prebid-server-go/read/specs/{bidder}/latest.yaml`, or transient at `.tmp/full-loop/{run-id}/go/{bidder}.yaml` when running under the Teal flow.

**Target** (this skill emits): Java artifacts at the canonical paths per `references/java-artifact-shapes.md` (D1.3 deliverable):

- `src/main/java/org/prebid/server/bidder/{bidder}/{Bidder}Bidder.java`
- `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}Configuration.java`
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java`
- `src/main/resources/bidder-config/{bidder}.yaml`
- `src/main/resources/static/bidder-params/{bidder}.json` (byte-copy from Go per Rule 38)
- `src/test/java/org/prebid/server/bidder/{bidder}/{Bidder}BidderTest.java`
- `src/test/java/org/prebid/server/it/{Bidder}Test.java`
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-auction-{bidder}-{request,response}.json`
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-{bidder}-bid-{request,response}.json`
- `src/test/resources/org/prebid/server/it/test-application.properties` (append two lines)

**Out of scope** (handled elsewhere or future): writing a Java adapter from scratch (`write/`, future); reviewing post-merge (`review/`, future composition); analytics modules / RTD modules / general modules / delta-ports (deferred per execution-plan-phase-d.md "Out of scope").

## Invocation

```bash
# One-shot Teal flow (read → port → review):
$ orchestrator port \
    --source-lang=go \
    --target-lang=java \
    --bidder={bidder} \
    --source-spec=prebid-server-go/read/specs/{bidder}/latest.yaml \
    --target-branch=feat/{bidder}-java-port \
    --run-id=2026-05-04T1430Z-a3f9

# Direct invocation (when the source spec is persisted):
$ /port-go2java --bidder={bidder} --target-branch=feat/{bidder}-java-port

# Spec-only port (no Java code emitted; useful for design review):
$ /port-go2java --bidder={bidder} --dry-run
```

Pre- and post-conditions per `../../docs/methodology/port-skills-design.md` §2.

## Pipeline (7 steps)

Per design doc `../../docs/methodology/port-skills-design.md` §3. Phase D2 fills each step's body; the skeleton below names the contract.

### Step 1 — Load + validate source spec

**TODO (D2)**: Load the Go-source spec YAML. Validate against `../../prebid-server-go/read/skills/shared/adapter-spec.schema.json`. Confirm `source_language: go`. Reject (exit 1) if malformed or directionally wrong.

### Step 2 — Discover the bidder family

**TODO (D2)**: Read `meta.is_alias`, `meta.parent_aliases`, `aliases[]`. Determine whether the bidder is primary, alias child, alias-empire parent, or alias-empire child. Family shape drives Rule 33 (alias inversion) and Rule 44 (alias-empire consolidation).

### Step 3 — Apply rules (Go → Java direction)

**TODO (D2)**: Walk `../../prebid-server-go/read/skills/shared/port-translation-rules.yaml` rule-by-rule. For each rule, check `spec_field_driver` against the source spec; emit `verdict: applied | skipped-not-applicable | skipped-source-side-only | applied-with-warning`.

D2's mechanical-ready rules (priority order, all consumed via `scripts/lib/port_engine.py` helpers):

1. Rule 38 — bidder-params byte-fidelity (`byte_copy` + SHA verify)
2. Rule 46 — naming-convention normalization (`normalize_bidder_name`)
3. Rule 33 — alias-graph invert (`alias_graph_invert`)
4. Rule 44 — alias-empire flavor coherence
5. Rule 36 — fixture-inventory parity → semantic-coverage parity (re-author Java IT 4-file split from Go's flat fixtures)
6. Rule 42 — IAB-cat storage translation (`iab_table_translate`)
7. Rule 35 — config-properties subclass scaffolding
8. Rule 39 — derived-view (no-op on porter)
9. Rule 19 — standard headers (`HttpUtil.headers()` collapse)
10. Rule 30 — canonical Go status helpers ↔ Java framework default

The remaining 36 rules are handled prose-driven (the SKILL walks the rule's prose body and applies the translation in-line). Conflict resolution per design doc §5: lower-id rule wins on artifact placement; record `unresolved_translations[]` with reason `conflicting-rules` for the reflection loop.

### Step 4 — Author the destination spec

**TODO (D2)**: Construct the Java-side destination spec. Carry over R5-strict-shared fields verbatim. Apply Java-specific transformations on `spring_config.*`, `bidder_class.*`, `code_naming.*`. Re-compute `bidder_params_sha256` (matches source per Rule 38). Set `provenance.source.resolved_commit` to the same commit as the source spec.

### Step 5 — Emit Java artifacts

**TODO (D2)**: Walk the destination spec; emit files at the canonical paths listed under "Target" above. Use Jinja templates from `templates/` (D1.3 deliverable: `configuration-properties.java.j2`, `bidder.java.j2`, `bidder-test.java.j2`, `it-test.java.j2`, `bidder-config.yaml.j2`, etc.).

Emission rules:

- **Checkstyle-compliant by construction**: ImportOrder strict 3-group with blank-line separation; LineLength≤120; EmptyLineSeparator. Templates author the imports in the canonical order.
- **Spring-config wiring**: `bidder-config/{bidder}.yaml` declares the BidderDeps; `{Bidder}Configuration.java` provides the `BidderInfoCreator`-driven beans. Emission is idempotent on re-port.
- **Test-application.properties append**: two-line append (the test-fixture toggle + the bidder enabled flag). NOT a full rewrite of the file; that would clobber other ports' entries.
- **PR-shape automation**: emit `recommended_pr_title: "Port {Bidder}: New Adapter"` (or `"Port {alias}: New alias for {parent}"`) and `target_pr_label_recommendations: ["do not port"]` per upstream porting guide.
- **Companion docs PR**: emit `companion_docs_pr_draft` with target_repo `prebid/prebid.github.io`, file_path `dev-docs/bidders/{bidder}.md`, body_markdown populated from the source spec's `bidder_info`, `params`, and `meta` fields. Maintainer-mandatory per BeOp #4660 review pattern.
- **Pre-submit rebase**: rebase the target branch onto upstream `prebid/prebid-server-java` `master` HEAD; abort with operator notification on framework conflict; record outcome in `pre_submit_rebase`.

### Step 6 — R5-strict check at port time

**TODO (D2)**: Re-read the destination spec via `prebid-server-java/read/skills/read-bidder-orchestrator`. Call `scripts/lib/r5_check.compare_pair(go_spec, java_spec)` (no dual-spec assertions — the pair file may not exist for new ports). Map the four-state harness output plus port-time direction-aware analysis to one of the six `r5_check.state` enum values; populate `byte_equal_fields[]`, `warn_fields[]`, `fail_fields[]`, `summary`.

### Step 7 — Emit port-report.json

**TODO (D2)**: Build the port-report dict per `../../prebid-server-go/read/skills/shared/port-report.schema.json` (v0.2.0); write to `.tmp/full-loop/{run-id}/port-report.json`. Schema-validate before writing (use `scripts/lib/port_engine.port_report_emit`).

## Rule application order

Per design doc §4. Rules applied in declaration order from `port-translation-rules.yaml`. Two port runs of the same source spec at the same `port_translation_rules_version` produce byte-identical destination artifacts (R4 round-trip determinism). When two rules conflict, lower-id wins; conflict recorded in `unresolved_translations[]`.

## R5-strict check at port time

Per design doc §7. The skill consumes `scripts/lib/r5_check.compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result`. The four harness states map to the schema's six-state enum; the two extended states (`warn-target-strengthens-source`, `fail-source-omits-target-constraint`) are emitted when the port skill detects direction-specific source-vs-target asymmetries beyond what the harness compares.

A port-time R5 fail is a `human_todos[]` entry, not a CI failure. The port still ships; humans decide whether to merge.

## Quality bar (D2 acceptance gates)

D2 considers the skill production-ready only when, for each MVP pair:

1. Emitted Java compiles cleanly via `mvn -B compile --file extra/pom.xml`.
2. Emitted unit tests pass via `mvn -B test -Dtest={Bidder}BidderTest`.
3. Jacoco line-coverage on the new `{Bidder}Bidder.java` ≥ 90%.
4. `mvn -B checkstyle:check` exits 0.
5. Emitted YAML validates against Java's `bidder-info-schema.json`; emitted JSON validates against `static/bidder-params/_schema.json`.
6. `port-report.json` schema-validates against `port-report.schema.json` v0.2.0.
7. `r5_check.state` matches the per-pair expectation in `docs/execution-plan-phase-d.md` §D2.3.

## References

- **Design doc**: [`../../docs/methodology/port-skills-design.md`](../../docs/methodology/port-skills-design.md) — 7-step pipeline + conflict resolution + novel-pattern handling.
- **Execution plan**: [`../../docs/execution-plan-phase-d.md`](../../docs/execution-plan-phase-d.md) — D2 acceptance criteria + per-pair expectations.
- **Rules corpus**: [`../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) — 46 rules at v0.2.0; the SKILL pins to this version.
- **Output schema**: [`../../prebid-server-go/read/skills/shared/port-report.schema.json`](../../prebid-server-go/read/skills/shared/port-report.schema.json) — port-report contract (v0.2.0).
- **Source-spec schema**: [`../../prebid-server-go/read/skills/shared/adapter-spec.schema.json`](../../prebid-server-go/read/skills/shared/adapter-spec.schema.json) — what the source spec must satisfy.
- **R5 lib**: [`../../scripts/lib/r5_check.py`](../../scripts/lib/r5_check.py) — R5 comparator (Phase D0.1).
- **Port engine**: `../../scripts/lib/port_engine.py` — 9 mechanical helpers (D1.2 deliverable).
- **Upstream porting guide**: `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` — maintainer-authored spec the SKILL version-pins to.
- **Reflection loop**: [`../../docs/methodology/reflection-loop.md`](../../docs/methodology/reflection-loop.md) — Phase F consumes `port-report.json::human_todos[]` and `unresolved_translations[]`.

### Per-skill subdirectories

- [`references/`](references/) — Java-target emission references (D1.3 fills): `java-artifact-shapes.md`, `pr-template-mapping.md`, `registration-rules.md`, `porting-guide.md` (pinned to upstream SHA).
- [`templates/`](templates/) — Jinja templates for Java artifact emission (D2 fills): `configuration-properties.java.j2`, `bidder.java.j2`, `bidder-test.java.j2`, etc.
