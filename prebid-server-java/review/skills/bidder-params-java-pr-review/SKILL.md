---
name: bidder-params-java-pr-review
description: Reviews changes to Java bidder parameter schemas — JSON Schema (src/main/resources/static/bidder-params/{x}.json), Lombok @Builder @Value POJO (src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/ExtImp{X}.java), and IT test fixtures (src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json). USE WHEN a PR touches any of these files. Do NOT use for bidder-config/{x}.yaml, {X}Bidder.java, or Configuration files — those are owned by sibling skills.
version: 1.0.0
---

# Bidder Params PR Review (Java)

Review pull requests that touch the Java bidder-params triplet: the draft-04 JSON Schema, the Lombok-annotated imp-ext POJO (`ExtImp{X}.java` plus helper protos co-located in the same package), and the 4-file IT fixture set (Rule 36) that exercises the schema end-to-end through the WireMock integration-test harness.

This skill is the Java-tree analog of `prebid-server-go/review/skills/bidder-params-pr-review`. The Go-side covers `static/bidder-params/{x}.json` + `openrtb_ext/imp_{x}.go` + `adapters/{x}/params_test.go`. The Java side covers the same JSON schema (byte-fidelity to Go per Rule 38), the Lombok POJO (a different shape than Go structs — Java has `@Value @Builder` + Jackson annotations), and IT fixtures (Java's per-bidder Rule 36 4-file split has no Go analog; Go uses `exemplary/` + `supplemental/` directories under `{bidder}test/`).

## Core Principle: Review Only What Changed

**You are a PR reviewer, not a full-file auditor.** The PR diff (received from pr-triage-java) is your single source of truth. Only create verification tasks for items that actually changed.

- **NEVER** review unchanged schema properties / POJO fields / fixture lines just because they exist in a file
- **NEVER** verify items in unchanged files mentioned only in cross-skill context (those exist for read-only verification, not as review targets)
- **DO** verify every item that the diff marks as added (`+`) or modified
- The number of verification tasks should correspond 1:1 with changed items, not with total items in the file

## Activation

This skill activates when `pr-triage-java`'s routing manifest routes ≥1 file in any of the following patterns to `bidder-params-java-pr-review`:

- `src/main/resources/static/bidder-params/{x}.json` — the draft-04 JSON Schema
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java` — Lombok `@Value @Builder` POJO `ExtImp{X}.java` plus helper protos co-located in the same package (e.g., `ExtImp{X}BidExt.java`, `ExtImp{X}Param.java`, `ExtImp{X}Banner.java`, `ExtImp{X}Deserializer.java`)
- `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` — IT fixture set (the 4-file Rule 36 split per scenario: `test-auction-{x}-request.json` + `test-auction-{x}-response.json` + `test-{x}-bid-request.json` + `test-{x}-bid-response.json`; multi-scenario bidders ship N × 4 files with the scenario name embedded — see references/params-type-index.md §C.1 for the canonical pattern verified at SHA `e3ffd57`)

It does NOT activate on its own — `pr-triage-java` runs first and routes files here. The activation cases:

- **Schema-only PR**: only `bidder-params/{x}.json` changed (rare; usually `minLength`/`pattern`/`enum` tweaks or an added optional property). The Lombok POJO and IT fixtures are READ-ONLY context (cross-skill).
- **Ext-only PR**: only `ExtImp{X}.java` (or a helper proto) changed (rare; usually Jackson annotation refactors, e.g., adding `@JsonAlias` for a legacy field name). The schema is READ-ONLY context.
- **Paired PR** (new-adapter / property-add): schema + POJO + IT fixtures all change. The most common activation pattern.
- **IT-fixture-only PR**: only fixtures changed (rare; usually new scenario added to an existing bidder for a new code path).

Do NOT activate for `bidder-config/{x}.yaml`, `{X}Configuration.java`, `{X}BidderConfigurationProperties.java` (owned by `bidder-config-pr-review`), or `{X}Bidder.java`, `{X}BidderTest.java`, `{X}Test.java` (owned by `bidder-class-pr-review`).

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model, which can paraphrase source code and lose raw JSON / annotation structure. `curl` returns exact, deterministic content. Parse the raw JSON output directly.

### Step 1: Receive Triage Data

This skill receives pre-fetched PR data from the `pr-triage-java` skill. Do NOT re-fetch PR files or run drift checks — they were already performed centrally.

**1a. Accept the routing manifest.**

The pr-triage-java skill provides:
- File list filtered to files owned by this skill (`bidder-params/{x}.json`, `proto/openrtb/ext/request/{x}/*.java`, `it/openrtb2/{x}/*.json`)
- Each file's `filename`, `status`, and `patch` (diff hunks)
- Drift check results — none drive this skill directly (the Java JSON-schema validation mechanism lives in `BidderParamValidator.java` per F-new-62; see Step 4 verification)
- CI status summary
- PR type classification (`new-adapter`, `adapter-modification`, `infrastructure`, etc.)
- PR description analysis (docs PR link, template completeness, feature rationale)
- Commit history
- PR comments (reviewer feedback, CI bot reports, author responses)
- Duplicate PR search results
- Bidder metadata (parent / aliases / capabilities if extractable from the PR)
- `--- PRIOR AGENT FINDINGS ---` (when `agent review` label is set) — dedup against your findings
- `--- PRIOR SPEC COMPARISON ---` (when `prior_spec` resolves) — Java same-language regressions
- `--- PRIOR SOURCE SPEC COMPARISON ---` (when `prior_source_spec` resolves) — Go-source ↔ Java-port port-fidelity findings (Step 1g consumes this)

**1b. Handle drift warnings.**

The pr-triage manifest may report:
- `bidder-config: DRIFT: ...` — does NOT affect this skill (config-owned)
- `framework-spring-di: DRIFT: ...` — typically does NOT affect this skill unless `BidderParamValidator.java` was changed (rare; framework-level)
- `checkstyle.xml: DRIFT: ...` — does NOT affect this skill directly (the imp-ext POJO is a Java file subject to checkstyle, but Lombok-annotated POJOs rarely trigger checkstyle finds; pre-flags come through pr-triage's `PRE-CHECKSTYLE` cross-skill concerns)

Include any reported drift in your review output for context but do NOT re-fetch.

**1c. Handle CI status.**

If CI status is `blocked`, acknowledge in the summary and note that review findings are preliminary until CI passes. Java's `BidderParamValidator` is exercised at runtime during IT tests (`mvn test`); a CI failure in the test phase MAY indicate a schema/POJO/fixture mismatch this skill should re-examine.

**1d. Incorporate reviewer feedback.**

Cross-reference the PR comments from the triage manifest against your review findings:
- If a reviewer has already flagged an issue you also find, note: `Previously flagged by {reviewer}` and reference their comment
- If a CI bot report indicates a failure relevant to your scope (schema parse error, POJO unmarshal error, IT test failure on a fixture), use it as additional evidence for your verification steps
- If the author has responded to reviewer feedback with fixes, check whether the current diff reflects those fixes

**1e. Dedup against prior agent findings.**

If the manifest contains `--- PRIOR AGENT FINDINGS ---`, cross-reference each of your findings:
- Exact duplicate (same file, same rule, same severity) → emit as `Previously flagged by prior agent` instead of a fresh finding
- Net-new findings emit normally

**1f. Dedup against prior_spec regressions.**

If the manifest contains `--- PRIOR SPEC COMPARISON ---`, the orchestrator has already detected regressions against the previously-read Java spec at `prebid-server-java/read/specs/{bidder}/latest.yaml`. Examples this skill cares about:
- `PRIOR-SPEC: Custom Jackson deserializer added. Verify ext.accepts_shapes captures the new flexibility.` → this skill's deserializer verification (Step 4) addresses; emit a finding only if the new deserializer's `accepts_shapes` differs from what the new POJO surface implies.
- `PRIOR-SPEC: bidder_params_sha256 changed from {old} to {new}.` → confirm the schema change is intentional and the Go side's Rule 38 byte-fidelity assertion is being honored (see Step 1g for cross-language).

Cross-reference these against your findings and dedup as `Previously captured in prior_spec — confirm with reviewer if intentional.`

**1g. Cross-language port-fidelity check (consumes `--- PRIOR SOURCE SPEC COMPARISON ---`).**

When the manifest contains a `--- PRIOR SOURCE SPEC COMPARISON ---` block, the orchestrator has loaded the Go-source spec for the same bidder. Apply these port-fidelity checks for bidder-params-specific concerns:

1. **Rule 38 byte-fidelity on bidder-params JSON.** The Go and Java repos ship byte-identical `static/bidder-params/{x}.json` for paired bidders (port-translation Rule 38). Cross-check the manifest's `prior_source_spec.bidder_params_sha256` (the Go-side SHA) against the Java side (either the new SHA in the PR if the file is `status=modified`, or the existing SHA if untouched):
   - Source spec's `bidder_params_sha256` MATCHES the Java side → no fidelity issue. Suppress any `info` entries about JSON schema bytes — Rule 38 holds.
   - Source spec's `bidder_params_sha256` MISMATCHES → flag as `warn`. Identify the diverging property by diffing the schemas. Common divergence categories:
     - Missing `minLength: 1` on a string field that the Go side enforces (the **canonical aax case** below)
     - `required[]` set differs (one side has it, the other does not)
     - `additionalProperties` declared on one side but not the other
     - `pattern` or `maximum` constraints differ
   - Emit:
     ```
     PRIOR-SOURCE-SPEC: bidder_params.json bytes diverge from Go (file: src/main/resources/static/bidder-params/{x}.json)
       Go SHA: {go_sha}
       Java SHA: {java_sha}
       Diverging property: {property} — {category} (e.g., minLength: 1 absent in Java)
       Severity: warn — Rule 38 byte-fidelity violated. PR description should explain why.
     ```

2. **Dual-spec assertion `severity: fail` elevation.** If `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` exists AND declares the diverging field with `severity: fail`, ELEVATE the finding from `warn` to `urgent`. The canonical example is **aax**: the dual-spec at `cross-language-pairs/aax.dual-spec-assertions.yaml` declares the missing `minLength: 1` on `cid` and `crid` as `severity: fail` (semantic divergence — an empty-string `cid`/`crid` is REJECTED by Go but ACCEPTED by Java). If the current PR touches `aax.json` AND the `minLength` is still missing OR the PR introduces a similar omission, emit:
   ```
   PRIOR-SOURCE-SPEC: cross-language-pairs/{bidder}.dual-spec-assertions.yaml declares this divergence as severity:fail
     Field: {property}
     Java behavior: {what Java accepts that Go rejects, or vice versa}
     Upstream recommendation: {from the dual-spec's upstream_action_recommended block, when present}
     Severity: urgent — port-fidelity bug confirmed by canonical dual-spec assertion.
   ```

3. **Flexible-type cross-language symmetry.** If `prior_source_spec.params.schema_interpretation.flexible_types` is non-empty (Go uses `["integer","string"]` type arrays driving `jsonutil.StringInt` per port-translation Rule 9), verify the Java side uses an appropriate flexible-type mechanism:
   - Java field type `Long` + `@JsonAlias({...})` is the typical Java idiom (mismatch with Go's `jsonutil.StringInt` is documented, R9-tolerated; emit `info` only)
   - Java field type `Integer` or `String` with NO `@JsonAlias` on a Go-flexible field is a **port-fidelity miss** — Java will reject the form Go accepts. Emit:
     ```
     PRIOR-SOURCE-SPEC: Go's {field} accepts both integer and string via jsonutil.StringInt (flexible_types=true). Java's ExtImp{X}.{field} is {Java type} without @JsonAlias or @JsonDeserialize, so the form Go accepts will fail Java's Jackson parse.
       Severity: warn — Rule 38 schema bytes match but R9 semantic equivalence broken.
     ```
   - Java field type `JsonNode` (raw passthrough) with bidder-class shape-branching → emit `info` only (R9-tolerated; see read-side companion's `runtime-isobject-isarray-branching` taxonomy)

4. **`info` default for legitimate asymmetries.** When the divergence is structural (e.g., Java POJO has `@Builder` and Go has no analog; Java helper proto split vs Go single struct) and does NOT touch behavior, emit `info` and continue. Port asymmetries are often legitimate per Rules 5/9/11/35/38.

If `--- PRIOR SOURCE SPEC COMPARISON ---` is absent (the orchestrator did not resolve a Go-source spec), skip Step 1g — the cross-language check is opt-in.

**1h. Fetch full file content when needed.**

For files with status `modified`, the patch contains only changed regions. When verification requires full file context (e.g., checking all properties in a schema, verifying every POJO field against every schema property), fetch the full file at the PR's `head_sha`:

```bash
# Full file for modified schemas / POJOs / fixtures
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/{head_sha}/{filename}"
# Check the bidder's parent (for alias awareness) when YAML access is needed
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/{head_sha}/src/main/resources/bidder-config/{x}.yaml"
```

- For `added` files: full content is already in the patch (all `+` lines) — do NOT re-fetch
- For `modified` files: only fetch if verification requires context beyond the diff hunks
- Cache fetched content — do not re-fetch the same file multiple times

### Step 2: Extract Changes From the Diff

Group changed files by bidder name (extracted from filename patterns per the routing rules in `pr-triage-java/SKILL.md` Step 3). For each bidder, identify which of the 3 file types changed:

- `src/main/resources/static/bidder-params/{bidder}.json` — schema changes
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/*.java` — POJO changes (may include helper protos)
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/*.json` — IT fixture changes

For each changed file, parse the diff to identify exactly what changed:

- **Added file** (entire file is new) — every property / field / fixture line is new and needs review
- **Modified file** (some lines changed) — **ONLY** review the specific lines that changed. Unchanged items are out of scope.
- **Removed file** (entire file deleted) — create a single task to validate the removal is intentional

**Comment-only / whitespace-only changes:** If all changed lines are comments or whitespace with no actual property / field / fixture changes, the file has **zero changed items**. Skip to Step 5 and recommend fast-track approval. (Note: trailing-whitespace-before-`]` in IT fixtures is F-new-49 — Lombok-template emit defect; flag in the IT-fixture workflow but it does NOT count as a behavioral change.)

### Step 3: Build Verification Task List

There are two categories of tasks:

**1. PR-level task (at most one):** A single task covering PR-wide checks that don't map to a specific property / field / fixture line:
- **Alias check**: If the bidder is an alias (its parent's `bidder-config/{parent}.yaml` declares `aliases: { {bidder}: ... }`), it MUST NOT have its own `bidder-params/{bidder}.json` or `ExtImp{Bidder}.java` — these inherit from the parent. The Java `BidderParamValidator.createSchemaNode` falls back to the parent's schema when an alias has no own file. Flag if present.
- **Cross-file consistency**: If multiple file types changed for the same bidder, verify they are in sync (see [Cross-File Consistency](#workflow-cross-file-consistency) workflow).
- **F-new-49 IT-fixture trailing-whitespace check (companion check)**: When the PR includes IT fixture files (`it/openrtb2/{x}/*.json`), this skill unconditionally records an **INFO** flagging that trailing whitespace before `]` is a known Lombok-template emit defect; checkstyle does not enforce JSON formatting but reviewers prefer clean diffs. The bidder-class skill's IT-class review (sibling) has the actual `@Test`-method scrutiny; this skill verifies fixture-file structural correctness only.

**2. Item-level tasks (one per changed item):** For each changed schema property, POJO field, helper-proto class, or fixture line, look up the matching Verification Workflow:

For **schema changes** (`bidder-params/{bidder}.json`):
1. Changed / added `properties` entries — use [Schema Property Changed](#workflow-schema-property-changed)
2. Changed `required` array — use [Required Fields Changed](#workflow-required-fields-changed)
3. Changed conditional validation (`oneOf` / `anyOf` / `allOf` / `not`) — use [Conditional Validation Changed](#workflow-conditional-validation-changed)
4. Schema-level changes (`$schema`, `title`, `description`, top-level `type`) — use [Schema Metadata Changed](#workflow-schema-metadata-changed)
5. Flexible-type fields (`"type": ["integer","string"]`) — use [Flexible Type Schema Field](#workflow-flexible-type-schema-field)

For **POJO changes** (`proto/openrtb/ext/request/{bidder}/*.java`):
6. Changed / added Lombok class annotations (`@Value`, `@Builder`, `@Data`, `@Jacksonized`, `@JsonDeserialize`) — use [Lombok Class Annotation Changed](#workflow-lombok-class-annotation-changed)
7. Changed / added fields with Jackson annotations (`@JsonProperty`, `@JsonAlias`, `@JsonInclude`, `@JsonDeserialize`) — use [POJO Field Changed](#workflow-pojo-field-changed)
8. Changed package / class name — use [POJO Declaration Changed](#workflow-pojo-declaration-changed)
9. Added helper proto class in the same package (e.g., `ExtImp{X}BidExt.java`) — use [Helper Proto Added](#workflow-helper-proto-added)

For **IT fixture changes** (`it/openrtb2/{bidder}/*.json`):
10. Added / modified fixture file (one of the 4-file Rule 36 set) — use [IT Fixture Changed](#workflow-it-fixture-changed)

**Do NOT create separate "new params file" or "new POJO file" tasks.** For new files, the relevant per-item checks (every property → Schema Property Changed; every field → POJO Field Changed; etc.) cover the file.

**Sanity check**: The number of item-level tasks must equal the number of changed items across all files. If you have more tasks than changed items, you are reviewing out-of-scope content — remove the excess tasks. The PR-level task does not count toward this check.

### Step 4: Execute Verification Tasks

Work through tasks, parallelizing where possible. For each task:

1. Mark the task `in_progress`
2. Execute every verification step from the matching workflow
3. Record each step's result as PASS, FAIL, or WARN with evidence (file:line + the offending bytes)
4. Mark the task `completed` with findings

**Java JSON-schema validation note (F-new-62).** Earlier execution-plan drafts (§183) referenced literal Java schema files that don't exist as separate artifacts — the validation runs at **runtime** inside `BidderParamValidator.java` (`src/main/java/org/prebid/server/validation/BidderParamValidator.java`). The validator instantiates a `JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V4)` and validates `imp.ext.bidder` against the schema loaded from classpath (`static/bidder-params/{x}.json`). When you suspect a schema-parse or property-resolution issue, the diagnostic is: load the JSON file, feed it to a draft-04 validator (the `com.networknt.schema` library Java uses), and confirm it parses cleanly. CI exercises this path during the IT tests (Gate 2 of D2.3); a schema bug surfaces as `IllegalArgumentException: Couldn't parse {bidder} bidder schema` at server startup or `Set<ValidationMessage>` returned to the auction pipeline.

### Step 5: Summary

After all tasks are complete, produce a review summary:

- Files changed (with category: schema / POJO / fixture; status: added / modified / removed)
- Items changed per file
- Verification steps executed
- Issues found (urgent / fail / warn / info)
- Cross-skill concerns surfaced (with the target sibling skill name)
- Recommendation (approve, request changes, or comment)

Findings format (one per line, severity-first):

```
[severity] file:line — finding
  Evidence: {1-line excerpt}
  Recommendation: {1-2 sentence fix}
```

Severities map to:
- `urgent` — port-fidelity `severity: fail` from a dual-spec assertion (Step 1g rule 2), or a behavior-breaking schema regression
- `fail` — required-field break, malformed schema, POJO/schema name mismatch
- `warn` — style/convention, minor port-fidelity divergence, missing `minLength` etc.
- `info` — Java-side legitimate asymmetry, cross-skill nudge, F-new-49 fixture whitespace

---

## Verification Workflows

### Workflow: Schema Property Changed

**Triggers when:** A property is added or modified inside `properties:` in `bidder-params/{bidder}.json`.

1. **Valid JSON Schema draft-04**: Property definition must use only draft-04 constructs (no `if` / `then` / `else`, no `const`, no `contentEncoding`). Draft-04 is enforced at runtime by `JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V4)` in `BidderParamValidator.java`. Severity: **FAIL**.
2. **Type correctness**: Property `type` must be a valid JSON Schema type (`string`, `integer`, `number`, `boolean`, `object`, `array`) or an array of types (e.g., `["integer", "string"]` for flexible types). Severity: **FAIL** on invalid types.
3. **Description present**: New properties **MUST** have a `"description"` string explaining what the property is and how it's used. Severity: **FAIL** for new properties without description. For existing properties being modified, missing description is tolerated (do not churn).
4. **Naming convention**: New property names should be lowercase camelCase (Adverxo uses `adUnitId`; Ix uses `siteid` / `siteId` / `siteID`; legacy snake_case like Appnexus's `placement_id` is tolerated but not encouraged for new adapters). Cross-reference: if the property name doesn't match the Java POJO field's `@JsonProperty` (or default field name), surface to [POJO Field Changed](#workflow-pojo-field-changed).
5. **Constraints appropriate**:
   - `minLength: 1` on string fields that the adapter cannot accept as empty is HIGHLY recommended — its absence on required string fields is the canonical port-fidelity bug (the aax case: missing on `cid`/`crid`). Severity: **WARN** when missing on a string field listed in `required[]`.
   - `minimum: 1` on integer fields that must be positive (e.g., Adverxo's `adUnitId`).
   - `pattern` on fields with format constraints — verify the regex compiles in the `com.networknt.schema` library (draft-04 uses ECMA 262 regex per the JSON Schema spec; Java's `Pattern` is mostly compatible but `\\Q ... \\E` literal quoting is non-portable).
   - `enum` on fields with a closed value set — verify each enum value is consistent with what the adapter code (`{X}Bidder.java`) expects. Cross-skill: surface to `bidder-class-pr-review` if the enum set differs from what the adapter switches on.
6. **Reserved OpenRTB field check**: Property must not duplicate standard OpenRTB 2.x fields (e.g., a bidder param named `bidfloor` shadowing the OpenRTB Imp.bidfloor). For **new** properties, flag as **FAIL**. For **existing** properties being modified, flag as **WARN** (the field is already established).
7. **POJO alignment**: If the corresponding `ExtImp{Bidder}.java` exists, verify this property has a matching Java field with correct `@JsonProperty` (or default Lombok-generated field name). If only the schema property was added but the POJO field is absent, flag as **FAIL** under [Cross-File Consistency](#workflow-cross-file-consistency); the adapter code (`{X}Bidder.java`) cannot read a schema property that has no POJO field.
8. **Breaking change detection**: If a **required** property is renamed (old name removed, new name added) or removed entirely, flag as **FAIL** — this breaks existing publisher integrations. Backward-compatibility options:
   - Add the new property AND keep the old one with `description: "Deprecated, use {new} instead."` (the Appnexus / Ix pattern — Java schema lists both)
   - Use the Java `@JsonAlias({"oldName"})` annotation on the POJO field, paired with `oneOf` in the schema to accept either spelling — this is the Java-side answer to Go's flexible-type idiom (port-translation Rule 9)
   - Relaxing a type constraint (e.g., adding `"integer"` to a `"string"` field) is non-breaking and acceptable

### Workflow: Required Fields Changed

**Triggers when:** The top-level `required[]` array is added or modified.

1. **Fields exist**: Every field in the `required` array must be defined in `properties`. Severity: **FAIL** (otherwise the schema is malformed and `JsonSchemaFactory.getSchema(...)` will reject it).
2. **Genuinely required**: Required fields should be ones the adapter cannot function without (e.g., placement ID, account ID, auth token). Flag as **WARN** if a field is marked required but the adapter code (`{X}Bidder.java`) has fallback logic — surface to `bidder-class-pr-review` for cross-skill verification.
3. **POJO alignment** (Java-specific):
   - Required schema fields should map to **non-pointer-typed** value fields in the Lombok POJO when possible. But beware: Lombok `@Value` generates a constructor that accepts any object reference (including `null`), and Jackson will inject `null` for a missing JSON key. Java does NOT have Go's `omitempty` vs non-omitempty distinction at the struct level — instead, the `BidderParamValidator` (runtime, JSON-schema-driven) enforces presence, and a non-null Java type does not, by itself, enforce non-null at deserialization.
   - For optional fields with `minLength: 1` in the schema, the POJO field type must NOT be `String` directly (without `@JsonInclude(NON_EMPTY)` or similar guard) because the adapter code may then accept empty strings the schema technically forbids. This is **F-new-38** territory — pre-flag when an optional schema field has `minLength: 1` and the POJO declares it as a plain `String`; Jackson will deserialize an empty-string JSON value into the field, but the runtime validator rejects it AFTER deserialization. The reviewer should confirm the adapter code (`{X}Bidder.java`) does not rely on the schema's enforcement (since the validator runs separately).
4. **Test coverage**: IT fixtures (the `test-{bidder}-bid-request.json` 4-file set) MUST exercise the required fields with valid values. If the PR adds a required field without updating the IT fixtures, flag as **WARN**. (The unit-test coverage for required-field-missing is owned by `bidder-class-pr-review`'s `{X}BidderTest.java` review.)

### Workflow: Conditional Validation Changed

**Triggers when:** `oneOf`, `anyOf`, `allOf`, or `not` constructs are added or modified.

1. **Draft-04 compatible**: The construct must be valid in JSON Schema draft-04. `oneOf` / `anyOf` / `allOf` / `not` ARE supported in draft-04. `if` / `then` / `else` are NOT (those are draft-07). Severity: **FAIL** if any draft-07 construct is used.
2. **Logical correctness**: The conditions should make semantic sense for the adapter:
   - `anyOf` — at least one group of fields is needed (OR logic). Java Ix uses `oneOf: [{required: [siteid]}, {required: [siteId]}, {required: [siteID]}]` to require exactly one of three spellings.
   - `oneOf` — exactly one group of fields is needed (XOR logic).
   - `allOf` — all groups must be satisfied (AND; used for inheritance-like composition).
   - `not` — prevents invalid combinations (rare in bidder schemas).
3. **No contradictions**: Combined constraints should not make it impossible to produce valid input. The `com.networknt.schema` validator does not detect logical contradiction at compile time; a logically-impossible schema accepts no input at runtime — the adapter becomes unreachable. Severity: **WARN** when the reviewer can spot an obvious contradiction.
4. **POJO alignment**: When the schema uses `oneOf: [{required: [a]}, {required: [b]}]`, the POJO field for `a` and `b` should both be optional (Java type plain `String`/`Integer`, not validated by Jackson). The runtime validator handles the OR-logic. `@JsonAlias` on the POJO is the Java-side answer for accepting alternate spellings of the SAME logical field (Ix `siteid` / `siteId` / `siteID` → one POJO field with `@JsonAlias({"siteid","siteID"})` + `@JsonProperty("siteId")`).
5. **IT-fixture coverage**: Each branch of the conditional should be exercised by at least one IT fixture scenario. If the PR adds an `anyOf`/`oneOf` branch without an accompanying fixture, flag as **WARN**.

### Workflow: Schema Metadata Changed

**Triggers when:** `$schema`, `title`, `description` (top-level), or top-level `type` is changed.

1. **$schema must be draft-04**: Value must be `"http://json-schema.org/draft-04/schema#"`. `BidderParamValidator` instantiates `JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V4)` (V4 == draft-04 in `com.networknt.schema` enum); any other `$schema` value will be silently ignored by the factory, so reviewers should enforce this at PR time. Severity: **FAIL** on mismatch.
2. **Top-level `type` must be `object`**: `"type": "object"` is required at the top level. Severity: **FAIL**.
3. **`properties` must exist**: Even adapters with no params declared today must have `"properties": {}` (an empty object). Without `properties`, the validator treats arbitrary input as valid — an unsafe default. Severity: **FAIL** if absent.
4. **Title format**: Should follow `"{Bidder} Adapter Params"` convention (e.g., `"Aax Adapter Params"`, `"Kobler Adapter Params"`). Severity: **WARN** on stylistic deviation; not enforced at runtime.
5. **Description present**: Top-level `description` should be a one-line sentence (e.g., `"A schema which validates params accepted by the Aax adapter"`). Severity: **WARN** if absent.

### Workflow: Flexible Type Schema Field

**Triggers when:** A schema property uses `"type": ["integer", "string"]` (or similar polymorphic type array) — typically used for placement IDs that can be either form.

This is port-translation Rule 9 territory: Go uses `jsonutil.StringInt` (a custom Go type that unmarshals both forms cleanly). Java's idiomatic answer is asymmetric — Java has multiple mechanisms:

1. **Java field type `Long` + `@JsonAlias({...})`** — the most common pattern when the Java side wants both spellings of a SINGLE logical key. Severity: **INFO** — `notes` should record the Go-vs-Java mismatch under port-translation Rule 9.
2. **Java field type `JsonNode`** — raw passthrough; the adapter code (`{X}Bidder.java`) does runtime shape-branching (`isObject() / isArray() / isTextual()`). Common in Appnexus `keywords` field. Pair this with `ext_pojo_construction.custom_unmarshal.kind: runtime-isobject-isarray-branching` per the read-side companion. Severity: **INFO**.
3. **Custom `@JsonDeserialize(using = {X}Deserializer.class)`** — when the field needs more shape-flexibility than `@JsonAlias` provides. Verify a corresponding `{X}Deserializer.java` exists in the same package. Severity: **INFO** (legitimate pattern); **WARN** if the deserializer is missing.
4. **Plain `Integer` / `String` without alias or deserializer** — REGRESSION RISK. Jackson will reject the form the schema accepts. Severity: **FAIL** (Java will fail at deserialization on JSON the schema would accept; an integration-test fixture with the alternate form will fail at `mvn test`).

Cross-language symmetry verification (when `--- PRIOR SOURCE SPEC COMPARISON ---` is present): see Step 1g rule 3 — flag asymmetries where Java cannot accept what Go accepts.

See [`../../../read/skills/shared/framework-utilities-java.md`](../../../read/skills/shared/framework-utilities-java.md) for the Jackson-annotation-vs-flexible-type idiom matrix.

### Workflow: Lombok Class Annotation Changed

**Triggers when:** A POJO class's Lombok / Jackson annotations change at the class level: `@Value`, `@Builder`, `@Data`, `@Jacksonized`, `@JsonDeserialize`, `@AllArgsConstructor`, `@NoArgsConstructor`, etc.

1. **`@Value @Builder` is the canonical pattern for `ExtImp{X}.java`.** Lombok `@Value` generates an immutable POJO with `final` fields and a constructor accepting all fields in declared order; `@Builder` adds the fluent builder API. This is the dominant Java pattern (~80% of ExtImp classes). Severity: **INFO** if a new ExtImp uses a non-canonical form; **FAIL** if the class declares `@Data` instead (mutable; breaks immutability contract; ExtImp objects should not be mutated post-construction).
2. **`@Value(staticConstructor = "of")` is the alternate canonical form.** Used by Kobler, Adverxo, Ix — generates a static factory `ExtImpKobler.of(true)` instead of (in addition to) the default constructor. Severity: **PASS** — accepted variant.
3. **`@Jacksonized` for `@Builder` + Jackson interop**. When a Lombok-built POJO needs Jackson deserialization to use the builder, `@Jacksonized` is required (otherwise Jackson uses the all-args constructor by default). Severity: **WARN** when `@Builder` is present without `@Jacksonized` AND the field set includes optional fields (Jackson cannot skip optional builder calls without it).
4. **`@JsonDeserialize(using = {X}Deserializer.class)` declares custom deserialization at the class level.** Verify a corresponding `{X}Deserializer.java` (or named class) exists in the same package and `extends StdDeserializer<{ExtImp{X}}>` or implements `JsonDeserializer<{ExtImp{X}}>`. Severity: **FAIL** if the referenced class is missing.
5. **Anti-patterns:**
   - `@Data` on an `ExtImp{X}` class — mutable POJO; ExtImp should be immutable. Severity: **FAIL**.
   - `@AllArgsConstructor` without `@Value` / `@Builder` — raw POJO; non-idiomatic for ExtImp. Severity: **WARN**.
   - `@NoArgsConstructor` on a Lombok-`@Value` class — Lombok forbids mutating `final` fields; this combination indicates the class is being used as a Spring bean (anti-pattern for ExtImp). Severity: **FAIL**.

### Workflow: POJO Field Changed

**Triggers when:** A field is added or modified in `ExtImp{X}.java` or a helper proto in the same package.

1. **Field naming**: Java field name MUST be camelCase per Java convention (Lombok / Jackson serialize verbatim, so the JSON tag defaults to the field name if no `@JsonProperty` is present). Mismatched casing in `@JsonProperty` against the schema's `properties` key is the **#1 misalignment trap**.
2. **`@JsonProperty` alignment with schema**: When the schema property name differs from the Java field name (e.g., schema `placement_id` ↔ Java `placementId`), the POJO MUST declare `@JsonProperty("placement_id")` on the field. Cross-check every PR-added schema property has a matching Java field with `@JsonProperty` (or matching default field name). Severity: **FAIL** on mismatch (Jackson cannot resolve the JSON key → field, deserialization yields a `null`-injected field, schema rejects, adapter pipeline breaks).
3. **`@JsonAlias({...})` for accepting alternate spellings**: When the schema property exists with multiple legacy spellings (Appnexus `placementId` / `placement_id`; Ix `siteid` / `siteId` / `siteID`), the Java field uses `@JsonAlias({...})` to accept multiple JSON keys on the SAME logical field. Verify the alias list matches the schema's deprecated-name entries. Severity: **WARN** on a missing alias (legacy spellings will not deserialize).
4. **Optional vs required type semantics**:
   - For schema-required fields, the Java type can be primitive (`int`, `boolean`) or boxed (`Integer`, `Boolean`); Jackson will reject the JSON before construction if the key is missing AND the schema validator enforces presence at runtime.
   - For schema-optional fields, the Java type should be boxed (`Integer`, not `int`) so Jackson can inject `null` cleanly. Primitive types on optional fields force a 0/false default that conflates "absent" with "set to zero" — a known bug pattern.
   - **F-new-38**: when an optional schema field has `minLength: 1`, the Java field SHOULD NOT be raw `String` without guard; Jackson will deserialize an empty-string JSON value into the field, the runtime validator rejects it after deserialization, and the adapter sees a partially-constructed object only if the adapter pipeline tolerates the schema-rejection-fallthrough. Pre-flag this Java-side regression risk; the cleanest fix is to make the schema field `required` if it cannot be empty, OR add a non-empty guard inside `{X}Bidder.java`. Severity: **WARN**.
5. **`@JsonInclude(JsonInclude.Include.NON_NULL)`** — when the POJO is also used for serialization (e.g., when re-emitting `imp.ext.bidder` upstream), this annotation suppresses null fields in output JSON. Generally not required for ExtImp{X} (read-only direction) but if the POJO is round-tripped, the annotation is expected.
6. **Java field type alignment with schema type**:

   | Schema type | Recommended Java type | Notes |
   |---|---|---|
   | `"string"` | `String` | Plain string |
   | `"integer"` | `Integer` (boxed) or `Long` | `Long` for wide IDs (Adverxo `adUnitId` uses Integer; Appnexus `placementId` uses Integer + `@JsonAlias`) |
   | `"number"` | `BigDecimal` | Required for precision; never `double` or `float` |
   | `"boolean"` | `Boolean` (boxed) | Avoid primitive `boolean` for optional fields |
   | `"array"` | `List<T>` | `T` matches `items.type` |
   | `"object"` | typed POJO OR `JsonNode` / `ObjectNode` | Typed POJO when fields are known; `JsonNode` for raw passthrough |
   | `["integer","string"]` | See [Flexible Type Schema Field](#workflow-flexible-type-schema-field) | Multiple Java idioms |

7. **`@Singular` on `List<>` builder fields**: when the class uses `@Builder` and a field is a `List<T>`, `@Singular` enables `builder.tag("x").tag("y")` for one-at-a-time addition. Severity: **INFO** if absent on a list field; **PASS** when present.
8. **Cross-skill nudge**: When the POJO adds a field that has no matching schema property, the adapter code (`{X}Bidder.java`) may read a non-existent property — surface to `bidder-class-pr-review` as: `CROSS-SKILL: ExtImp{X}.{field} declared but no matching schema property. The adapter may use a stale name or be reading a removed param.`

### Workflow: POJO Declaration Changed

**Triggers when:** A new class is added to the package, OR an existing class name, package declaration, or import block changes.

1. **Naming convention**: **Canonical type name is `ExtImp{X}`** (e.g., `ExtImpAax`, `ExtImpKobler`, `ExtImpAdverxo`). Helper protos in the same package follow `ExtImp{X}{Suffix}` (e.g., `ExtImpAppnexusKeywords`, `ExtImpGumGumBanner`, `ExtImpAdverxoExt`). Severity: **WARN** when a new class deviates.
2. **Package is `org.prebid.server.proto.openrtb.ext.request.{x}`**: must match the bidder's lowercase name. Severity: **FAIL** on package mismatch.
3. **`OuterTypeFilename` checkstyle rule**: the public class declared MUST match the filename root (`ExtImpAax.java` declares `public class ExtImpAax`). Pre-flag any deviation; checkstyle will fail CI (`PRE-CHECKSTYLE: ExtImp{X}.java declares public class {ClassName}; does not match filename root.`). Severity: **FAIL**.
4. **No breaking rename**: If the type name changed, the adapter code (`{X}Bidder.java`) AND any tests must also be updated. Cross-skill: surface to `bidder-class-pr-review` to verify the adapter and tests reference the new name.
5. **Imports check**: Java imports must follow checkstyle `ImportOrder` 3-group convention (`*`, blank, `java|jakarta`). Pre-flag any added imports that violate the order — checkstyle will fail CI. Severity: **FAIL** (CI-blocking).

### Workflow: Helper Proto Added

**Triggers when:** A new helper proto class is added to `proto/openrtb/ext/request/{x}/` alongside `ExtImp{X}.java`.

Helper protos typically support:
- Custom request/response payloads (e.g., `ExtImp{X}Request.java`, `ExtImp{X}Response.java`)
- Sub-objects of the main ExtImp (e.g., `ExtImp{X}Param.java`, `ExtImp{X}Banner.java`, `ExtImp{X}BidExt.java`)
- Custom Jackson deserializers (e.g., `ExtImp{X}Deserializer.java` `extends StdDeserializer<T>`)

1. **Lombok pattern matches the main ExtImp**: helper sub-objects typically use `@Value @Builder` like the parent. Deserializer classes use plain Java (no Lombok) since they `extends StdDeserializer<T>`. Severity: **WARN** when a helper sub-object uses `@Data` instead.
2. **Justification**: helper protos that don't directly map to schema properties (e.g., `ExtImp{X}BidExt` for bid-response parsing, not request) should be USED by the adapter code (`{X}Bidder.java`). If the helper is unused (orphan class), flag as **INFO** with: `Helper proto {ClassName} appears unused — verify it's read by {X}Bidder.java.` Cross-skill: surface to `bidder-class-pr-review`.
3. **Deserializer correctness** (when the helper is a `JsonDeserializer<T>`):
   - Class `extends StdDeserializer<{ExtImp{X}}>` OR implements `JsonDeserializer<{ExtImp{X}}>`. Severity: **FAIL** on mismatch.
   - The `deserialize(JsonParser p, DeserializationContext ctxt)` method has explicit shape-branching (`isArray() / isObject() / isTextual() / isNumber()`); each accepted shape is recorded for the read-side companion's `accepts_shapes` taxonomy. Severity: **WARN** when shapes are accepted silently (no explicit branch).
   - Reference: `@JsonDeserialize(using = {X}Deserializer.class)` on the field or class that delegates to this deserializer.
4. **Package check**: helper protos live in the SAME package as `ExtImp{X}.java`. A helper in `proto/openrtb/ext/request/` (the parent package, no `{x}` subdir) is an anti-pattern — it should be bidder-scoped. Severity: **FAIL**.

### Workflow: IT Fixture Changed

**Triggers when:** A file under `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/` is added or modified.

The 4-file Rule 36 fixture set per scenario (filenames are STRICT — the IT class' `@Test` methods reference them by exact path). Verified at SHA `e3ffd57` against `src/test/resources/org/prebid/server/it/openrtb2/kobler/` and `.../adprime/`:

| File | Role |
|---|---|
| `test-{x}-bid-request.json` | The mock bidder's expected incoming request (what the adapter would send to the bidder's endpoint). Drives WireMock's `stubFor(post(...).withRequestBody(equalToJson(...)))`. |
| `test-{x}-bid-response.json` | The mock bidder's response (what the bidder would return). Drives WireMock's `willReturn(aResponse().withBody(...))`. |
| `test-auction-{x}-request.json` | The publisher's OpenRTB auction request entering prebid-server (what the test client posts to `/openrtb2/auction`). |
| `test-auction-{x}-response.json` | The expected OpenRTB auction response from prebid-server (what the test verifies against). |

Multi-scenario bidders (e.g., Appnexus video) ship N × 4 files with scenario name embedded (`test-{scenario}-{x}-bid-request.json` + `test-auction-{scenario}-{x}-request.json` style — verified pattern in upstream `it/openrtb2/`).

1. **Filename pattern**: must match the canonical Rule 36 pattern exactly — `test-auction-{x}-request.json` + `test-auction-{x}-response.json` (publisher auction request/response) + `test-{x}-bid-request.json` + `test-{x}-bid-response.json` (adapter↔bidder bid request/response). The IT class `{X}Test.java` (owned by `bidder-class-pr-review`) loads these by filename — a typo breaks the IT silently. Severity: **FAIL** on filename mismatch.
2. **Bidder-id consistency**: the request's `imp[].ext.{bidder|prebid.bidder.{bidder}}` key MUST match the bidder name (lowercased, no hyphens). For the auction request: `imp.ext.bidder` is sometimes used as the alias for the configured bidder; verify the field name matches the IT class's `@Bidder` annotation (cross-skill: read `{X}Test.java`).
3. **Currency convention**: most fixtures implicitly use USD via `cur: ["USD"]` in the auction request. If the PR adds a fixture with a non-USD currency, verify the adapter code (`{X}Bidder.java`) handles currency conversion — surface to `bidder-class-pr-review` as: `CROSS-SKILL: IT fixture {file} uses non-USD currency. Verify {X}Bidder constructor receives CurrencyConversionService.`
4. **`impid` linkage**: each `seatbid[].bid[].impid` in the bid-response MUST match the corresponding `imp[].id` in the bid-request. Severity: **FAIL** on mismatch (the IT will fail at assertion time).
5. **F-new-49 trailing whitespace**: Lombok-template-emitted JSON sometimes has stray whitespace before `]` array closers. Pre-flag with: `IT fixture {file}:{line} has trailing whitespace before ']'. Lombok-template emit defect (F-new-49). Reviewers prefer clean JSON.` Severity: **INFO** (not CI-blocking).

5b. **F-new-60 multi-scenario fixture-filename ↔ test-method-name parity**: When a multi-scenario fixture is added (`test-{scenario}-{x}-bid-request.json` etc.), the corresponding IT `@Test` method must use camelCase per the F-new-60 trap (`scenarioForAppSimpleBanner`, NOT `scenario_for_app_simple_banner`). The IT class is owned by `bidder-class-pr-review`, so this skill cannot directly verify the method name — but it MUST cross-skill nudge: `CROSS-SKILL: New multi-scenario fixture {file} added — verify {X}Test.java's @Test method uses camelCase (F-new-60 trap: snake_case fails checkstyle MethodName).` Severity: **INFO**; the fixture filename itself is the structural cross-reference target.
6. **F-new-52 pre-flag** (Rule 35 typed-config interaction): when the bidder has `{X}BidderConfigurationProperties.java` (Rule 35 typed-config subclass) AND the PR adds new IT fixtures, verify the IT test class's `setUp()` injects the typed subclass. Cross-skill: surface to `bidder-class-pr-review` as: `CROSS-SKILL: New IT fixtures added for {x} (Rule 35 typed-config bidder). Verify {X}Test.java setUp instantiates {X}BidderConfigurationProperties.` Severity: **INFO**.
7. **JSON formatting**: fixtures should use 2-space indentation (the dominant pattern in `it/openrtb2/`). Tabs or 4-space indentation are non-canonical. Severity: **INFO**.
8. **Scenario completeness**: when adding a new scenario, all 4 files (`bid-request`, `bid-response`, `auction-request`, `auction-response`) MUST be added together (Rule 36). Severity: **FAIL** when a scenario is partial (e.g., only `bid-request` added without `auction-request`).
9. **Cross-skill: IT class fixture-reference verification**. The IT test class (`{X}Test.java`, owned by `bidder-class-pr-review`) references these fixtures by exact path in `assertThat(jsonFrom("openrtb2/{bidder}/test-{name}-bid-request.json"))`-style calls. If a PR adds a fixture with no matching `@Test` method, surface to `bidder-class-pr-review`: `CROSS-SKILL: IT fixture {file} added but {X}Test.java has no @Test method referencing it. Orphan fixture.`

### Workflow: Cross-File Consistency

**Triggers when:** Any owned file type changed for a bidder. Check all 3 file types even if only 1 or 2 changed in this PR.

**Missing file detection:** When a schema property is **added**, the corresponding POJO field and (typically) IT fixture coverage should also be added. Apply this logic:

- **Property added in schema** → POJO MUST also add a matching field (severity: **FAIL** if missing). IT fixture SHOULD exercise the property (severity: **WARN** if missing).
- **Property removed from schema** → POJO SHOULD remove the field (**WARN** if not — orphan field will go unused). IT fixtures SHOULD update (**WARN** if not).
- **Required-set changed (required ↔ optional)** → POJO field type may not need changes (Java boxed types are nullable regardless); IT fixtures SHOULD update to cover the new presence semantics.
- **Constraint changed (`minLength`, `enum`, `pattern`, `maximum`, etc.)** → POJO doesn't need changes; IT fixtures MAY need updates.
- **POJO field added without matching schema property** → schema MUST also add the property OR the field is dead code (**FAIL**). Surface to `bidder-class-pr-review` if the adapter code uses the field — that's where the orphan would manifest.

Verification steps:

1. **Schema ↔ POJO sync**: every property in the JSON schema has a matching Java field (by `@JsonProperty` value, `@JsonAlias` entry, or default Lombok field name). For added properties, the POJO MUST be updated in the same PR.
2. **Required ↔ Java-type sync**: schema `required` fields map to Java boxed types (Integer / Boolean) or `String`; the runtime validator (`BidderParamValidator`) enforces presence at request time, not the type system.
3. **Schema ↔ IT fixture sync**: every required schema property appears in at least one IT fixture's `imp[].ext.bidder.{property}` block. For added required properties, the fixture SHOULD be updated.
4. **Bidder-name consistency**: the filename slug matches across all 3 file types (`{bidder}.json`, `ExtImp{Bidder}.java` in `request/{bidder}/`, fixtures in `it/openrtb2/{bidder}/test-{bidder}-*.json`). Severity: **FAIL** on mismatch.
5. **IT fixture 4-file Rule 36 completeness**: every scenario added must include all 4 files (see [IT Fixture Changed](#workflow-it-fixture-changed) step 8).

---

## Cross-Skill References (Read-Only)

This skill may read files owned by sibling skills for context, but does NOT create tasks for them:

- `bidder-config/{x}.yaml` (owned by `bidder-config-pr-review`) — to verify the bidder is NOT an alias of another bidder (aliases inherit the parent's params; their own `bidder-params/{x}.json` should not exist per `BidderParamValidator.createSchemaNode` fallback logic).
- `bidder-config/{x}.yaml` `endpoint:` field — to verify endpoint-template macros (e.g. `{adUnitId}` — single brace, RFC 6570) map to schema-declared params; cross-reference to ensure the template-token list aligns with `properties`.
- `{X}Bidder.java` (owned by `bidder-class-pr-review`) — to verify the adapter code uses every field declared in `ExtImp{X}.java` (orphan fields are dead code).
- `{X}BidderTest.java` (owned by `bidder-class-pr-review`) — to verify unit-test coverage exists for params parsing (catches missing test coverage for new schema fields).
- `{X}Test.java` (the IT class, owned by `bidder-class-pr-review`) — to verify each IT fixture file is referenced by a `@Test` method (no orphan fixtures).

Cross-skill concerns surfaced TO sibling skills (severity: WARN unless escalated by a dual-spec assertion):

| Source (this skill) | Target (sibling) | Concern |
|---|---|---|
| ExtImp{X}.java field with no matching schema property | `bidder-class-pr-review` | Adapter may use stale field name; field is dead code |
| Helper proto in `proto/openrtb/ext/request/{x}/` not referenced by adapter | `bidder-class-pr-review` | Orphan class |
| IT fixture with no `@Test` method referencing it | `bidder-class-pr-review` | Orphan fixture |
| IT fixture using non-USD currency | `bidder-class-pr-review` | Verify CurrencyConversionService injection |
| Rule 35 + new IT fixtures (F-new-52) | `bidder-class-pr-review` | Verify IT setUp injects typed-config subclass |
| `endpoint:` template-token not declared in `properties` | `bidder-config-pr-review` | Template macro will leave literal in URL |
| Capabilities (`app-media-types` / `site-media-types`) inconsistent with schema | `bidder-config-pr-review` | Schema accepts shapes the bidder cannot serve |

---

## Reference Documentation

This skill ships a single consolidated references/ deep-dive in this PR (step 3, commit `c618fde`):

- [`references/params-type-index.md`](references/params-type-index.md) — covers JSON Schema type → Java POJO type mapping (Part B.4), JSON Schema draft-04 rules + `com.networknt.schema` library quirks (Part A), reserved OpenRTB fields that must NOT be bidder params (Part E), Lombok `@Value`/`@Builder`/`@Data` + Jackson `@JsonProperty`/`@JsonAlias`/`@JsonDeserialize` annotation matrix (Part B.1/B.2), Rule 36 4-file IT fixture template (Part C), Rule 9 flexible-type idiom matrix (Part B.5), and Rule 38 cross-language byte-fidelity rules (Part D).

The previously-planned topic-split files (`schema-type-matrix.md`, `draft-04-rules.md`, `reserved-openrtb-fields.md`, `lombok-jackson-matrix.md`, `it-fixture-rule36-template.md`) are consolidated into the one params-type-index.md to keep cross-reference and review surfaces compact. The embedded subset of content in this SKILL.md (the activation table, workflow ordering) stays compact and points to params-type-index.md for the deep-dive lookup.

---

## Shared Framework Reference

For framework-wide concerns (Lombok annotation conventions, JacksonMapper deserialization patterns, `com.networknt.schema` draft-04 validator behavior, the runtime `BidderParamValidator` mechanism, Java vs Go flexible-type idioms per port-translation Rule 9, byte-fidelity Rule 38, helper-proto co-location conventions, IT fixture Rule 36), this skill references:

- `../../../read/skills/shared/framework-utilities-java.md` — read-side companion for Java framework conventions
- [`../shared/framework-utilities-java.md`](../shared/framework-utilities-java.md) — review-side companion adding reviewer-specific anti-patterns + verbatim policy quotes (LANDED in this PR, step 2, commit `63be93d`)
- `../../../../docs/methodology/java-review-skill-design.md` — design contract (file ownership map, cross-language hook symmetry, open questions)
- `../pr-triage-java/SKILL.md` — orchestrator that emits the routing manifest this skill consumes
- `../../../../prebid-server-go/review/skills/bidder-params-pr-review/SKILL.md` — Go-side analog; cross-language symmetry reference
- `../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml` — Rules 9 (flexible-type idiom mismatch), 36 (4-file IT fixture set), 38 (bidder-params byte-fidelity)
- `../../../../cross-language-pairs/{bidder}.dual-spec-assertions.yaml` — when present, canonical port-fidelity assertions with severity (the **aax** entry is the reference case for `severity: fail`)
