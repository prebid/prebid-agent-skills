---
name: bidder-params-pr-review
description: Reviews changes to bidder parameter schemas (static/bidder-params/*.json), impression extension Go structs (openrtb_ext/imp_*.go), and parameter validation tests (adapters/*/params_test.go). USE WHEN any of those files are added/modified/removed. Verifies JSON Schema draft-04 correctness, Go struct alignment, reserved-OpenRTB-field exclusions, jsonutil.StringInt usage for flexible types, and test coverage. Do NOT use for adapters/{bidder}/{bidder}.go (adapter implementation), static/bidder-info/*.yaml, or non-imp_*.go files in openrtb_ext/.
version: 1.1.0
---

# Bidder Params PR Review

Review pull requests that touch bidder parameter definitions: JSON schemas, Go impression extension structs, and parameter validation tests. For every changed property or field, apply the matching verification workflow to produce actionable review findings.

## Core Principle: Review Only What Changed

**You are a PR reviewer, not a full-file auditor.** The PR diff is your single source of truth. Only create verification tasks for properties/fields that actually changed in the diff. Properties that already exist unchanged in the file were approved in a prior PR and are out of scope.

- **NEVER** review unchanged properties just because they exist in a file
- **NEVER** verify struct fields, test cases, etc. unless the diff shows them as added or modified
- **DO** verify every line that appears as added (`+`) or modified in the diff
- The number of verification tasks should correspond 1:1 with changed items, not with total items in the file

## Activation

This skill activates when a PR adds, modifies, or removes any file matching:
- `static/bidder-params/*.json`
- `openrtb_ext/imp_*.go`
- `adapters/*/params_test.go`

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model,
which can paraphrase source code and lose raw JSON structure. `curl` returns
exact, deterministic content. Parse the raw JSON output directly.

### Step 1: Receive Triage Data

This skill receives pre-fetched PR data from the **pr-triage** skill. Do NOT re-fetch PR files or run drift checks.

**1a. Accept the routing manifest.**

The pr-triage skill provides:
- The complete file list filtered to files owned by this skill (`static/bidder-params/*.json`, `openrtb_ext/imp_*.go`, `adapters/*/params_test.go`)
- Each file's `filename`, `status`, and `patch` (diff hunks)
- Drift check results for `openrtb_ext/bidders.go` validator mechanism
- CI status summary
- PR type classification
- PR description analysis (docs PR link, template completeness, feature rationale)
- Commit history (count, messages, head SHA)
- PR comments (reviewer feedback, CI bot reports, author responses) — categorized and summarized
- Duplicate PR search results
- Bidder metadata (aliasOf status, capabilities if available from the PR)

- `--- PRIOR AGENT FINDINGS ---` block (when a prior-agent review was recorded; consumed in Step 1d)
- `--- PRIOR SPEC COMPARISON ---` block (same-language regression detection; opt-in; deduped like `--- PRIOR AGENT FINDINGS ---`)
- `--- PRIOR SOURCE SPEC COMPARISON ---` block (cross-language port-fidelity detection; opt-in; consumed in Step 1g)
**1b. Handle drift warnings.**

If the triage manifest reports drift for bidder-params, include the drift warning in the review output. Do not re-fetch `bidders.go`.

**1c. Handle CI status.**

If CI status is `blocked`, acknowledge in the summary and note that review findings are preliminary until CI passes.

**1d. Incorporate reviewer feedback.**

Cross-reference the PR comments from the triage manifest against your review findings:
- If a reviewer has already flagged an issue you also find, note: `Previously flagged by {reviewer}` and reference their comment
- If a CI bot report indicates a failure relevant to your scope (e.g., schema validation, struct compilation), use it as additional evidence for your verification steps
- If the author has responded to reviewer feedback with fixes, check whether the current diff reflects those fixes

- If the manifest carries a `--- PRIOR AGENT FINDINGS ---` block (a CodeRabbit / Copilot / ChatGPT review recorded via `agent_review: yes`), cross-reference each of your findings against the listed flags. An exact duplicate — same file, same rule, same severity — dedupes as `Previously flagged by prior agent` rather than emitting a fresh finding; net-new findings emit normally.
**1e. Fetch full file content when needed.**

For files with status `modified`, the patch contains only changed regions. When verification requires full file context (e.g., checking all properties in a schema, verifying struct field alignment):

```bash
# Full file for modified schemas/structs
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/{head_sha}/{filename}"
# Check if bidder is alias (to verify it shouldn't have its own params)
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/{head_sha}/static/bidder-info/{bidder}.yaml"
```

- For `added` files: full content is already in the patch (all `+` lines) — do NOT re-fetch
- For `modified` files: only fetch if the verification workflow requires context beyond the diff hunks
- Cache fetched content — do not re-fetch the same file multiple times

**1f. Handle shared file: openrtb_ext/bidders.go.**

If the triage manifest includes `openrtb_ext/bidders.go` in this skill's file list (because the diff touched `NewBidderParamsValidator` or schema validation logic), include it in scope. Otherwise, ignore this file even if it appears in the PR.

**1g. Consume `--- PRIOR SOURCE SPEC COMPARISON ---` (cross-language ports).**

When the manifest carries this block, the PR is a cross-language port — for a Go PR, typically a Java → Go port via `port-java2go`. Severity tiers, the dedup phrase, the Step 5 emission template, and reflection-loop routing all live in [the port-fidelity hook contract](../shared/framework-utilities.md#cross-language-port-fidelity-hook-contract); do not restate them here. Use the source-spec context to inform Step 4 verification.

If the block is absent, or reads `prior_source_spec not present — section omitted`, skip this substep: the PR is not a cross-language port.

Worked examples for this skill's scope, each citing a dual-spec key path:

| Divergence | Severity | Evidence |
|---|---|---|
| `bidder_params_sha256` differs semantically, not just by whitespace — the two schemas are not the same schema. This is the suite's canonical `fail`, and it becomes `urgent` when the PR diff touches the field in question (aax: Java omits `minLength: 1` on `cid` / `crid`). | `fail`, `urgent` when the diff touches it | `aax.dual-spec-assertions.yaml` → `bidder_params_sha256` |
| `bidder_params_sha256` differs by formatting only — tabs against spaces, or trailing-newline. Rule 38 makes the canonical bytes the source of truth, so do not "fix" the target to match your editor. | `warn` | `thetradedesk.dual-spec-assertions.yaml` → `bidder_params_sha256` |
| A required field is required on one side only, or a `oneOf` / `anyOf` combinator appears on one side only. | `warn`, `fail` when the pair file records one | the pair file's `params_schema_interpretation` block |
| The params schema accepts a value the adapter code rejects (Rule 48 validation-layering: a code-level allow-list beside a permissive schema). Source-faithful; do not tighten the schema unilaterally. | `info` | Rule 48 in `port-translation-rules.md` |

Surface `warn` / `fail` / `urgent` in the Step 5 summary; suppress `info` unless the diff elevates it — for example a documented camelCase↔kebab-case `info` becomes `warn` when the Go-side change drops an R5-strict shared field entirely.

### Step 2: Extract Changes From the Diff

Group changed files by bidder name (extracted from filename patterns). For each bidder, identify which of the 3 file types changed:

- `static/bidder-params/{bidder}.json` — schema changes
- `openrtb_ext/imp_{bidder}.go` — struct changes
- `adapters/{bidder}/params_test.go` — test changes

For each changed file, parse the diff to identify exactly what changed:

- **Added file** (entire file is new) — every property/field/test case is new and needs review
- **Modified file** (some lines changed) — **ONLY** review the specific lines that changed. Unchanged properties/fields are out of scope.
- **Removed file** (entire file deleted) — create a single task to validate the removal is intentional

**Comment-only changes:** If all changed lines are comments or whitespace with no actual property/field/test changes, the file has **zero changed items**. Skip to Step 5 and recommend fast-track approval.

### Step 3: Build Verification Task List

There are two categories of tasks:

**1. PR-level task (at most one):** A single task covering PR-wide checks that don't map to a specific property:
- **Alias check**: If the bidder has `aliasOf` in its bidder-info YAML, it should NOT have its own params schema, imp ext struct, or params test — these inherit from the parent. Flag if present.
- **Cross-file consistency**: If multiple file types changed for the same bidder, verify they are in sync (see [Cross-File Consistency](#workflow-cross-file-consistency) workflow)
The adapter-code JSON-tag cross-reference is **not** a PR-level task and produces **no finding** — see Step 5. Its trigger condition (`openrtb_ext/imp_{bidder}.go` and `adapters/{bidder}/` both in the diff) is satisfied by every new-adapter PR, so emitting it as an INFO put a guaranteed non-finding in the findings stream of every such review.

**2. Item-level tasks (one per changed item):** For each changed property, struct field, or test case, look up the matching Verification Workflow:

For **schema changes** (`static/bidder-params/{bidder}.json`):
1. Changed/added properties — use [Schema Property Changed](#workflow-schema-property-changed)
2. Changed `required` array — use [Required Fields Changed](#workflow-required-fields-changed)
3. Changed conditional validation (`oneOf`/`anyOf`/`not`) — use [Conditional Validation Changed](#workflow-conditional-validation-changed)
4. Schema-level changes (`$schema`, `title`, `description`, `type`) — use [Schema Metadata Changed](#workflow-schema-metadata-changed)

For **struct changes** (`openrtb_ext/imp_{bidder}.go`):
5. Changed/added struct fields — use [Struct Field Changed](#workflow-struct-field-changed)
6. Changed type name or package — use [Struct Declaration Changed](#workflow-struct-declaration-changed)

For **test changes** (`adapters/{bidder}/params_test.go`):
7. Changed valid/invalid params — use [Params Test Changed](#workflow-params-test-changed)

**Do NOT create separate "new params file" tasks.** For new files, the relevant checks are folded into the item-level workflows.

**Sanity check**: The number of item-level tasks must equal the number of changed items across all files. If you have more tasks than changed items, you are reviewing out-of-scope content — remove the excess tasks. The PR-level task does not count toward this check.

### Step 4: Execute Verification Tasks

Work through tasks, parallelizing where possible. For each task:

1. Mark the task `in_progress`
2. Execute every verification step from the matching workflow
3. Record each step's result as PASS, FAIL, or WARN with evidence
4. Mark the task `completed` with findings

### Step 5: Summary

After all tasks are complete, produce a review summary:

- Files changed (with category: added/modified/removed)
- Items changed per file
- Verification steps executed
- Issues found (critical / warning / info)
- Recommendation (approve, request changes, or comment)
- **Cross-skill note (summary text only — never a finding):** when the diff contains both `openrtb_ext/imp_{bidder}.go` and files under `adapters/{bidder}/`, close the summary with one line naming adapter-code-pr-review as the owner of the JSON-tag spelling-consistency check (`pubclick` vs `pub_click`, PR #4592), which is a **FAIL** there. This skill neither verifies the mismatch nor records a finding for it — the note exists so a reviewer reading only bidder-params findings knows where that check lives.

---

## Verification Workflows

### Workflow: Schema Property Changed

**Triggers when:** A property is added or modified in `static/bidder-params/{bidder}.json`.

1. **No post-draft-04 keywords in use**: `if`/`then`/`else`, `const`, and `contentEncoding` are not draft-04 constructs. Flag actual *use* of one as **FAIL** — the validator loads each file under the draft its own `$schema` names, and a draft-04 file using a draft-07 keyword silently ignores that constraint, so the schema does not validate what the author thinks it does. (The `$schema` string itself is a separate, softer check — see Workflow: Schema Metadata Changed.)
2. **Type correctness**: Property `type` must be a valid JSON Schema type (`string`, `integer`, `number`, `boolean`, `object`, `array`) or an array of types (e.g., `["integer", "string"]`)
3. **Not a reserved OpenRTB field**: Property should not duplicate standard OpenRTB 2.x fields. The reserved list is **split by severity** — see [params-type-index.md](references/params-type-index.md#reserved-openrtb-fields-must-not-be-bidder-params):
   - **FAIL** for the hard exclusions (`schain`, GDPR consent, US Privacy, COPPA, GPP) — zero upstream counterexamples.
   - **WARN** (ASK) for the soft exclusions, notably `bidfloor`/`bidFloor`: 24 `static/bidder-params/*.json` declare it at master @0ba3523, so a FAIL here blocks a shape the repo routinely merges. Ask why the standard floor path is insufficient and accept a bidder-specific reason.
   - For **existing** properties being modified (e.g., relaxing type constraints on an established `bidfloor`), stay at **WARN** or below — the field is already merged
4. **Naming convention**: New property names should be lowercase. camelCase is tolerated for legacy fields but not encouraged for new ones
5. **Description present**: New properties **MUST** have a `"description"` string explaining what the property is. Severity: **FAIL** for new properties without description. For existing properties being modified, missing description is tolerated (do not churn).
6. **Constraints appropriate**: If `minLength`, `minimum`, `maximum`, `pattern`, `enum` are used, verify they match real-world values
7. **Struct alignment**: If the corresponding `openrtb_ext/imp_{bidder}.go` file exists, verify this property has a matching Go struct field with correct json tag
8. **Breaking change detection**: If a **required** property is renamed (old name removed, new name added) or removed entirely, flag as **FAIL** — this breaks existing publisher integrations. Require backward compatibility: the old property name should be kept (with deprecation note) alongside the new one, using `anyOf`/`oneOf` to accept either. Relaxing a type constraint (e.g., adding `"integer"` to a `"string"` field) is non-breaking and acceptable

### Workflow: Required Fields Changed

**Triggers when:** The `required` array is added or modified.

1. **Fields exist**: Every field in the `required` array must be defined in `properties`
2. **Genuinely required**: Required fields should be ones the adapter cannot function without (e.g., placement ID, account ID). Flag if a field is marked required but the adapter code has fallback logic
3. **Struct alignment**: Required schema fields should map to non-pointer Go struct fields (a required field should not be `*string` in Go)
4. **Test coverage**: `TestInvalidParams` should have a case for each required field missing individually

### Workflow: Conditional Validation Changed

**Triggers when:** `oneOf`, `anyOf`, `allOf`, or `not` constructs are added or modified.

1. **Draft-04 compatible**: The construct must be valid in JSON Schema draft-04
2. **Logical correctness**: The conditions should make semantic sense for the adapter:
   - `anyOf` — at least one group of fields is needed (OR logic)
   - `oneOf` — exactly one group of fields is needed (XOR logic)
   - `not` — prevents invalid combinations
3. **No contradictions**: Combined constraints should not make it impossible to produce valid input
4. **Test coverage**: `TestValidParams` should have cases covering each branch of the conditional. `TestInvalidParams` should cover cases that violate each condition

### Workflow: Flexible Type Schema Field

**Triggers when:** A schema property uses `"type": ["integer", "string"]` (or similar polymorphic type array) — typically used for placement IDs that can be either form.

1. **Use `jsonutil.StringInt`**: The Go struct field type SHOULD be `jsonutil.StringInt` (from `github.com/prebid/prebid-server/v4/util/jsonutil`). This handles both forms cleanly.
2. **Avoid `interface{}`**: A struct field type of `interface{}` (or `any`) handles polymorphic types but loses type safety and forces every adapter caller to type-assert. Flag as **WARN** with recommendation to use `jsonutil.StringInt`.
3. **Avoid bidder-specific decoders**: Don't write a custom `UnmarshalJSON` for this — `jsonutil.StringInt` already handles both forms. Flag custom decoders as **WARN**.

See [../shared/framework-utilities.md](../shared/framework-utilities.md) for the framework helper table.

### Workflow: Schema Metadata Changed

**Triggers when:** `$schema`, `title`, `description`, or top-level `type` is changed.

1. **$schema draft string — WARN, not FAIL**: `"http://json-schema.org/draft-04/schema#"` is the overwhelming house style (271 of 272 files at master @0ba3523), but it is **not enforced by the loader**. `NewBidderParamsValidator` (`openrtb_ext/bidders.go:783-830`) hands each file to `gojsonschema` via `newReferenceLoader`/`newSchema` and pins no draft — the draft comes from each file's own `$schema`. `static/bidder-params/ogury.json` declares `https://json-schema.org/draft/2020-12/schema` and loads fine. Flag a non-draft-04 string as **WARN** (ASK: "house style is draft-04; confirm the newer draft is intentional"), never FAIL. Regenerate the distribution: `grep -ho '"\$schema": *"[^"]*"' static/bidder-params/*.json | sort | uniq -c`
2. **type must be object**: Top-level `"type": "object"` is required
3. **properties must exist**: Even adapters with no params must have `"properties": {}`
4. **Title format**: Should follow `"{Bidder} Adapter Params"` convention

### Workflow: Struct Field Changed

**Triggers when:** A field is added or modified in `openrtb_ext/imp_{bidder}.go`.

1. **JSON tag matches schema**: The `json:"tagName"` must exactly match the property name in the JSON schema (case-sensitive). If only the Go field name changed (e.g., `ApiKey`→`APIKey` for Go naming conventions) but the json tag is unchanged, verify the tag still matches the schema — the rename is cosmetic and acceptable. Go field-name capitalization fixes (e.g., `ApiKey` → `APIKey` per Go acronym conventions) are non-functional if `json:"..."` tags are unchanged. Accept without follow-up.
2. **Go type matches schema type**: See type mapping table in [params-type-index.md](references/params-type-index.md). Flag overly permissive types like `map[string]any` for schema `"type": "object"` with no property constraints
3. **Pointer and omitempty semantics correct**: Required schema fields should be value types (not pointers) and must NOT have `omitempty` in their json tag — `omitempty` on a required field means a zero-value (`""`, `0`, `false`) won't be serialized, which can mask missing data. Optional fields should use `omitempty` and optionally pointer types
4. **Package is openrtb_ext**: File must be in `package openrtb_ext`
5. **Type is exported**: Struct name must start with uppercase (e.g., `ImpExt{Bidder}` or `ExtImp{Bidder}`)
6. **No unexported fields**: All fields should be exported (uppercase) to support JSON unmarshaling

### Workflow: Struct Declaration Changed

**Triggers when:** A new struct type is added to the file, OR an existing struct type name, package declaration, or import block changes.

1. **Naming convention**: **Canonical type name is `ExtImp{Bidder}`** (e.g., `ExtImpAax`, `ExtImpAdkernel`, `ExtImp33across`) — the majority pattern in current master. The legacy `ImpExt{Bidder}` pattern (including `ImpExtMsft`) is a substantial minority in older files and is NOT recommended for new adapters. When reviewing a NEW adapter that uses `ImpExt{Bidder}`, flag as **INFO** — recommend converting for consistency. When reviewing modifications to existing files, do not require renames. Helper types (e.g., `ExtImpGumGumBanner`) are acceptable if they support the main imp ext struct.
2. **Package is openrtb_ext**: Must not be in a different package
3. **No breaking rename**: If the type name changed, the adapter code must also be updated (this is an adapter-code-pr-review concern, but flag as cross-reference)
4. **Helper type justification**: New types that don't directly map to schema properties should be used by the adapter code — flag as INFO if the type appears unused

### Workflow: Params Test Changed

**Triggers when:** `adapters/{bidder}/params_test.go` is added or modified.

1. **Correct bidder constant**: `openrtb_ext.Bidder{Name}` must match the bidder
2. **Correct schema path**: Must use `"../../static/bidder-params"` relative path
3. **validParams coverage** — **INFO** (NOTE) for anything missing; report the gaps as one note, never one finding per item, and never FAIL. Suggested cases:
   - Required-fields-only case
   - All-optional-fields populated (if applicable)
   - Edge cases for flexible types (e.g., both `int` and `string` for `["integer", "string"]` fields)
4. **invalidParams coverage** — **INFO** (NOTE) for anything missing, same reporting rule as step 3. Suggested cases:
   - Primitive type rejections: empty string, `null`, `true`, `5`, `4.2`, `[]`
   - Empty object `{}` (if fields are required)
   - Missing each required field individually
   - Wrong type for each field
   - Empty strings for fields with `minLength: 1`

   **Why INFO and not WARN**: the primitive-rejection list is a real house style but far from universal. At master @0ba3523, 72 of 235 `params_test.go` files (31%) contain all six primitives and 92 contain none; per-item rates are `null` 59%, empty string 56%, `[]` 54%, `true` 53%, `5` 36%, `4.2` 31%. Treating the list as a WARN gate would open a change request on roughly two thirds of merged adapters. The escalation that *is* a **FAIL** is unrelated to list length: a `required` schema field with no `TestInvalidParams` case omitting it, when that PR is the one adding the field (Workflow: Required Fields Changed step 4).
   ```bash
   # in a prebid-server checkout
   python3 - <<'EOF'
   import glob, re, collections
   pats = {'empty': r'^\s*(``|"")\s*,', 'null': r'`null`', 'true': r'`true`',
           '5': r'`5`', '4.2': r'`4\.2`', '[]': r'`\[\]`'}
   have, full, files = collections.Counter(), 0, sorted(glob.glob('adapters/*/params_test.go'))
   for f in files:
       t = open(f, errors='ignore').read()
       m = re.search(r'invalidParams\s*=\s*\[\]string\{(.*?)\n\}', t, re.S)
       hits = [k for k, p in pats.items() if re.search(p, m.group(1) if m else t, re.M)]
       have.update(hits)
       full += len(hits) == len(pats)
   print(len(files), full, dict(have))
   # 235 72 {'empty': 131, 'null': 139, 'true': 124, '5': 84, '4.2': 72, '[]': 128}
   EOF
   ```
5. **No duplicate test cases**: Each test case should exercise a distinct validation path
6. **Test function names**: Must be `TestValidParams` and `TestInvalidParams`
7. **Filename canonical**: The test file MUST be named `params_test.go` (plural). Flag the singular form `param_test.go` as **WARN** for new files (PR #4082 Ogury merged with the singular form — tolerated for that one but new adapters should use the plural). For modifications to an existing `param_test.go` file, do not request a rename.
8. **No `ext` field in validParams**: Test cases in `validParams` should validate ONLY fields defined in the schema's `properties`. Including `ext` keys (or other fields not in the schema) was rejected in PR #4243 review. Flag as **WARN** with note: "test cases should align with what the schema actually validates."

### Workflow: Cross-File Consistency

**Triggers when:** Any owned file type changed for a bidder. Check all 3 file types even if only 1 or 2 changed in this PR.

**Missing file detection:** When a schema property is **added**, the corresponding struct field and test case should also be added. When a schema property is **removed** or a requirement is **relaxed**, the struct and test may not need changes. Apply this logic:

- **Property added in schema** → struct file MUST also add a matching field (flag as FAIL if missing). Test file SHOULD add coverage (flag as WARN if missing).
- **Property removed from schema** → struct file SHOULD remove the field (WARN if not), test SHOULD update (WARN if not)
- **Requirement changed (required↔optional)** → struct may not need changes (pointer semantics), test SHOULD update to cover the new valid/invalid cases
- **Constraint changed (minLength, enum, etc.)** → struct doesn't need changes, test SHOULD update

Verification steps:

1. **Schema ↔ Struct sync**: Every property in the JSON schema has a Go struct field with matching json tag (and vice versa). For added properties, the struct MUST be updated in the same PR
2. **Required ↔ Pointer sync**: Schema `required` fields are non-pointer Go types; optional fields use `omitempty`
3. **Schema ↔ Test sync**: Every schema property appears in at least one validParams and one invalidParams case. For added properties, the test SHOULD be updated in the same PR
4. **Bidder name consistency**: The filename slug matches across all three files (`{bidder}.json`, `imp_{bidder}.go`, `params_test.go` in `adapters/{bidder}/`)

---

## Cross-Skill References (Read-Only)

This skill may read files owned by other skills for context, but does NOT create tasks for them:

- `static/bidder-info/{bidder}.yaml` — read to check if bidder is an alias (aliases inherit parent params)
- `adapters/{bidder}/{bidder}.go` — read to verify the adapter code actually uses the declared params (informational, not a task)

---

## Reference Documentation

See [params-type-index.md](references/params-type-index.md) for:
- JSON Schema type to Go type mapping
- Go struct naming conventions
- JSON Schema draft-04 rules and common mistakes
- Reserved OpenRTB fields that must not be bidder params
- Common parameter patterns across existing adapters
- Alias behavior (inherits parent params)

For framework-wide concerns (helper functions including `jsonutil.StringInt`, error types, marshal-error-safety, anti-patterns), see [../shared/framework-utilities.md](../shared/framework-utilities.md) — this skill references that file rather than duplicating its content.
