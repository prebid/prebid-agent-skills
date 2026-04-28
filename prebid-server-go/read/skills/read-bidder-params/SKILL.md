---
name: read-bidder-params
description: Reads `static/bidder-params/{xyz}.json`, the corresponding `openrtb_ext/imp_{xyz}.go` ext struct, and `adapters/{xyz}/params_test.go` to populate the `bidder_params_json:`, `bidder_params_sha256:`, and `params:` blocks of an Adapter Specification. USE WHEN the read-adapter-orchestrator dispatches the bidder-params domain, or directly when a user wants the params section of a spec for a single Go adapter. Preserves the JSON schema bytes verbatim (cross-language byte-identical contract — Rule 5 / Rule R2), produces a stable sha256, normalizes the schema for interpretation, classifies the Go ext struct (with `jsonutil.StringInt|IntString` flexible-type detection and custom `UnmarshalJSON` detection), and counts test cases. Surfaces the `bidder-constant-mismatch` warning that catches real bugs like kobler `params_test.go:47` referencing `BidderKrushmedia`. Do NOT use for `static/bidder-info/{xyz}.yaml` (that is `read-bidder-info`), for `adapters/{xyz}/{xyz}.go` adapter implementation (that is `read-adapter-code`), or for the Java sibling files (those are `read-bidder-params-java`).
version: 1.0.0
---

# Read Bidder Params (Go)

The Go-side reader skill that owns three files for one adapter:

1. `static/bidder-params/{xyz}.json` — the publisher-facing JSON schema.
2. `openrtb_ext/imp_{xyz}.go` — the Go struct backing the schema.
3. `adapters/{xyz}/params_test.go` — the unit-test file that exercises the schema.

Output goes into the Adapter Specification blocks `bidder_params_json:`, `bidder_params_sha256:`, `params:` (with three sub-blocks `schema_interpretation`, `ext_struct`, `params_test`), and `ext_pojo_construction:`. Optionally produces `provenance.warnings[]` entries when read-time anomalies are detected (R7 bidder-constant-mismatch is the canonical case).

The skill is third-person procedural — it tells the reader what to do, what to emit, and how to handle every edge case. The skill does NOT run static-analysis tools beyond regex / JSON parsing / the Go AST as listed in Step 4. No HTTP calls beyond the orchestrator-supplied source mode.

## When to invoke

The orchestrator (`read-adapter-orchestrator`) dispatches this skill in parallel with `read-adapter-code` and `read-bidder-info` once the resolved commit and source mode are settled. The skill MAY also be invoked directly for a single bidder (e.g., `read-bidder-params --bidder=kobler --source-mode=local`) when only the params section is needed.

## Inputs

The skill receives from the orchestrator:

| Input | Where it comes from | Example |
|---|---|---|
| `bidder` | User invocation or orchestrator | `kobler` |
| `resolved_commit` | Orchestrator (Step 1 of orchestrator workflow) | `d7f8515b86258688304b0d9b6668c6a0e258bc9e` |
| `source_mode` | Orchestrator | `local-checkout`, `github-raw`, `gh-cli` |
| `repo_root_or_url_base` | Orchestrator | local path or `https://raw.githubusercontent.com/prebid/prebid-server/<sha>` |
| `is_alias` | Orchestrator (read from `static/bidder-info/{xyz}.yaml`) | `false`. If `true`, see [Alias short-circuit](#alias-short-circuit). |

The skill reads (in this order):

1. `static/bidder-params/{bidder}.json` — required unless alias.
2. `openrtb_ext/imp_{bidder}.go` — required unless alias.
3. `adapters/{bidder}/params_test.go` — required unless alias. Filename quirk: tolerate the singular form `param_test.go` (Ogury, PR #4082) — see `params-type-index.md` "Params Test Conventions".

If any required file is missing for a non-alias bidder, the skill emits a hard error to the orchestrator (R1: every referenced file must exist at the resolved commit).

## Alias short-circuit

If the orchestrator passes `is_alias: true`, none of the three files should exist for this bidder (the alias inherits from its parent). The skill emits:

- `bidder_params_json: null`
- `bidder_params_sha256: null`
- `params: { schema_interpretation: null, ext_struct: null, params_test: null }`
- `ext_pojo_construction: { framework_choice: go-struct, flexible_extension_used: false, custom_unmarshal: { kind: none, accepts_shapes: [], where_branched: null } }`

If any of the three files DOES exist for an alias, emit a `provenance.warnings[]` entry of type `alias-has-own-params-files` (file:line) — this is the same suspicious pattern flagged by `bidder-params-pr-review` Step 3 (PR-level alias check).

## Workflow

### Step 1: Read the JSON schema verbatim

Read `static/bidder-params/{bidder}.json` in **binary mode** (preserve every byte: trailing whitespace, BOM if any, terminal newline presence/absence, indentation). Do NOT round-trip through a JSON parser before emitting `bidder_params_json:`.

Emit the bytes:

- **Default**: YAML literal block scalar `bidder_params_json: |` followed by indented content. Preserves multi-line content while losing trailing-newline-presence and trailing whitespace on otherwise blank lines.
- **When the file has trailing whitespace on blank lines, no terminal newline, or any non-LF newline that the literal-block scalar would normalize**: emit a YAML double-quoted scalar with explicit escapes (`\n`, `\t`, etc.). The `optidigital.golden.spec.yaml` golden uses this form because the source file has `"  \n"` on one blank line and no terminal newline. Add a YAML comment explaining the choice (the optidigital golden has a 4-line comment block above the field).
- **Acceptance test**: re-read the field, decode the YAML scalar back to bytes, and confirm `sha256(decoded) == bidder_params_sha256` (R2). If R2 fails, the encoding choice was wrong — switch to double-quoted form and retry.

### Step 2: Compute SHA-256

Compute `sha256` of the raw bytes from Step 1 (NOT of the YAML-encoded form). Emit:

```yaml
bidder_params_sha256: <hex-sha256>
```

This is the cross-language contract (R2). The Java sibling skill `read-bidder-params-java` reads `src/main/resources/static/bidder-params/{bidder}.json` from the Java repo and MUST produce the same SHA. Mismatch surfaces as a port-fidelity violation in the cross-language test harness (see `shared/port-translation-rules.md` Rule 5 — bidder_params_json byte-identical contract).

For verified canonical SHAs of corpus adapters (cross-checked at v4.1.0):

| Bidder | SHA |
|---|---|
| `kobler` | `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685` |
| `optidigital` | `6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31` |

If a re-read of these files produces a different SHA on master, the orchestrator emits a `master-drift` warning — the schema bytes changed upstream.

### Step 3: Parse the JSON schema for interpretation

Parse the JSON (use `encoding/json` or any draft-04-aware parser) and produce `params.schema_interpretation`. The classification rules and JSON-Schema-draft-04 grounding live in [references/schema-interpretation.md](references/schema-interpretation.md) — that file is the source-of-truth for `$schema`, combinators, flexible types, and the `properties[]` normalization shape.

Concretely emit:

```yaml
params:
  schema_interpretation:
    properties: []          # Normalized field list — see references/schema-interpretation.md "Normalized properties[]".
    required_fields: []     # Top-level "required" array verbatim.
    flexible_types: []      # Names of properties whose `type` is an array (e.g., ["integer","string"]).
    combinators_used: []    # Subset of: oneOf, anyOf, not, oneOf-of-oneOf, json-aliases-present.
```

The `combinators_used[]` enum is canonicalized in `shared/behavior-taxonomy.md` `params.schema_interpretation.combinators_used[]`. Emit `oneOf-of-oneOf` only when a `oneOf` branch's items themselves contain `oneOf` (Appnexus pattern). Emit `json-aliases-present` only on the Java side; on the Go side that value is unused.

Cross-reference: type-by-type interpretation rules (e.g., `"type": ["integer","string"]` → flexible_types entry, `"type": "object"` no `properties` → permissive map) are documented in [references/schema-interpretation.md](references/schema-interpretation.md). The master JSON-Schema → Go-type table is REUSED from `review/skills/bidder-params-pr-review/references/params-type-index.md` — do NOT re-list the table in this skill.

### Step 4: Read the Go ext struct file

Read `openrtb_ext/imp_{bidder}.go`. Parse via Go AST (`go/parser`) when available, otherwise via regex on the package declaration + struct-type literal. Emit:

```yaml
params:
  ext_struct:
    package: openrtb_ext
    file: openrtb_ext/imp_{bidder}.go
    type_name: ExtImp{Bidder} | ImpExt{Bidder}      # Whichever the file actually declares.
    fields:
      - name: <Go field name>
        json_tag: <json tag value, before the comma>
        type_native: <Go type as written in source>
        omitempty: <bool — true iff `,omitempty` appears in the json tag>
        notes: []
    custom_unmarshal: <bool>
    custom_unmarshal_accepts: []
```

#### Field type classification

For each field, emit `type_native` exactly as written in source (e.g., `string`, `bool`, `int`, `int64`, `*bool`, `[]string`, `jsonutil.StringInt`, `jsonutil.IntString`, `json.RawMessage`, `map[string]any`). This is the Go-native type — not a normalized cross-language type.

Special notes to add to `notes[]`:

- If `type_native` is `jsonutil.StringInt` AND the schema declares `"type": ["integer","string"]` for the same field: append `"uses jsonutil.StringInt for integer-or-string flexibility"`. This pairs with `flexible_types[]` in `schema_interpretation`.
- If `type_native` is `jsonutil.IntString`: append `"uses jsonutil.IntString — schema declares integer but upstream may send string"`. Same field-by-field pairing.
- If `type_native` is `interface{}` or `any` AND the schema uses combinators (`anyOf`/`oneOf`): append `"interface{} chosen for combinator flexibility — flag as WARN (review/bidder-params-pr-review Workflow: Flexible Type Schema Field)"`.
- If the Go field name ≠ json tag in a non-conventional way (e.g., `pubclick` json tag where the surrounding adapter expects `pub_click`): append `"json key style mismatch — see Go edge case #7"`. The mismatch detection requires reading the adapter source for context; the bidder-params skill emits an INFO note, and `read-adapter-code` owns the actual FAIL. Cross-reference the canonical example (msft `pubclick` vs `pub_click`, PR #4592) in `references/schema-interpretation.md`.

Cross-references for canonical type mappings:
- JSON Schema → Go type: `review/skills/bidder-params-pr-review/references/params-type-index.md` (master truth).
- `jsonutil.StringInt` / `IntString` semantics: `review/skills/shared/framework-utilities.md` "util/jsonutil extras beyond Marshal/Unmarshal" section.

#### Custom UnmarshalJSON detection

Set `custom_unmarshal: true` when the file declares ANY method:

```go
func (<receiver>) UnmarshalJSON(data []byte) error
```

The receiver may be the parent `*ExtImp{Bidder}` or a TYPE declared inside the file (e.g., Appnexus's `ExtImpAppnexusKeywords`). Both count.

Detection methods (in order of preference):

1. **Go AST** (`go/parser` with `parser.SkipObjectResolution`): walk `*ast.FuncDecl` nodes, filter to those with `Recv != nil` and `Name.Name == "UnmarshalJSON"`. The receiver type identifies WHICH type in the file owns the custom unmarshal.
2. **Regex fallback**: `^func \([^)]+ \*?\w+\) UnmarshalJSON\(.*\) error`. False-negative on multi-line method signatures is rare but possible — prefer AST when the file size is non-trivial.

When `custom_unmarshal: true`, populate `custom_unmarshal_accepts[]` by inspecting the method body. The list captures which JSON shapes the method handles. Common patterns:

- `switch b[0] { case '{': ...; case '[': ...; }` → accepts `["object", "array"]`.
- `if data[0] == '"' { ... } else { ... }` → accepts `["string", <other>]`.
- `bytes.Equal(data, []byte("null"))` early-return → adds `"null"`.

The Appnexus canonical example: `ExtImpAppnexusKeywords.UnmarshalJSON` has `switch b[0] { case '{': ...; case '[': ...; }` → emit `custom_unmarshal_accepts: ["object", "array"]`. Branching point is on the type itself (the keyword field's own type), so `ext_pojo_construction.custom_unmarshal.where_branched: type-method`.

If the body is too convoluted to classify, emit `custom_unmarshal_accepts: ["custom"]` and add a `quirks[]` entry with `edge_case_taxon: incomplete-classification` per the Custom-with-quirks contract (`shared/behavior-taxonomy.md` "How to read this taxonomy" item 2).

### Step 5: Read params_test.go

Read `adapters/{bidder}/params_test.go`. Emit:

```yaml
params:
  params_test:
    file: adapters/{bidder}/params_test.go
    valid_cases_count: <int>
    invalid_cases_count: <int>
    bidder_constant_referenced: openrtb_ext.Bidder{Name}
```

#### Counting test cases

The canonical structure (see `review/skills/bidder-params-pr-review/references/params-type-index.md` "Params Test Conventions") is:

```go
var validParams = []string{
    `{}`,
    `{ "test": true }`,
}

var invalidParams = []string{
    ``,
    `null`,
}
```

Method (in order of preference):

1. **AST parse** the file, locate `*ast.GenDecl` for `validParams` and `invalidParams`, count elements in the `*ast.CompositeLit.Elts`.
2. **Regex fallback**: count backtick-delimited strings inside the `[]string{...}` literal between `var validParams` and the next `var` declaration. Same for `invalidParams`.
3. **Test-runner fallback**: when file has unusual structure, run `go test -run TestValidParams|TestInvalidParams -v -count=1` and count `--- PASS:` lines per subtest. This works only when the iteration is structured as table-driven subtests (rare for params_test.go — most use the `for _, validParam := range validParams` loop with a single t.Errorf per iteration). Use only as a last resort.

Empty arrays count as 0. Comments inside the array do NOT count.

#### Bidder-constant detection (R7)

Walk the file looking for the call:

```go
validator.Validate(openrtb_ext.Bidder{Name}, json.RawMessage(<param>))
```

The literal `openrtb_ext.Bidder<Name>` is the **bidder constant referenced**. Emit it verbatim as the `bidder_constant_referenced` value.

Both `TestValidParams` and `TestInvalidParams` typically reference the SAME constant. If they differ (or if only one references the wrong constant), use the value from `TestValidParams` for the `bidder_constant_referenced` field, and emit a `provenance.warnings[]` entry of type `bidder-constant-mismatch` for `TestInvalidParams`. This is the kobler real bug:

- `TestValidParams` line 24: `validator.Validate(openrtb_ext.BidderKobler, ...)` — correct
- `TestInvalidParams` line 47: `validator.Validate(openrtb_ext.BidderKrushmedia, ...)` — WRONG (copy-paste artifact)

Validation rule R7 (canonicalized in `shared/adapter-spec.md` "Validation rules R1-R10"): if the constant on either line ≠ the constant declared as `Bidder<X> BidderName = "<name>"` in `openrtb_ext/bidders.go` at the resolved commit, emit:

```yaml
provenance:
  warnings:
    - type: bidder-constant-mismatch
      file: adapters/{bidder}/params_test.go
      line: <line number where the wrong constant appears>
      summary: "validator.Validate called with openrtb_ext.<Wrong> (copy-paste artifact); should be openrtb_ext.<expected, looked up in bidders.go>. The Validate call still functions because the validator looks up the schema by name and rejects on schema mismatch — the test passes despite the wrong identifier."
```

The expected constant for any bidder is whatever appears as `Bidder<X> BidderName = "<name>"` in `openrtb_ext/bidders.go` at the resolved commit. Look it up directly — do NOT try to derive it via flat TitleCase on the bidder name. The constant generation rules are not deterministically derivable from the YAML name: brand acronyms are preserved (`AJA`, `MX`, `TV`, `BWX`, `AMX`, `CWire`), camelHumps are explicit (`AdTonos`, `HuaweiAds`, `BeyondMedia`, `BidsCube`, `BigoAd`, `ConnectAd`), and leading-digit names capitalize the first letter after the digit (`33across` → `Bidder33Across`, not `Bidder33across`). The `Bidder` prefix makes any bidder name a valid Go identifier; the precise capitalization is whatever the upstream maintainers chose. Treat the `bidders.go` declaration as ground truth.

The kobler canonical bug is the load-bearing test for this detection (see `shared/adapter-spec.md` "Worked example: Kobler" and the kobler golden spec at `read/test-fixtures/kobler.golden.spec.yaml` lines 23-25, 106). A successful run of this skill on kobler MUST emit BOTH the warning AND a `quirks[]` entry of type `bidder-constant-mismatch` (the quirks entry is added by the orchestrator on assembly, not by this skill — but the skill MUST emit the warning so the orchestrator can pair them).

### Step 6: Populate `ext_pojo_construction`

Always emit (Go-side):

```yaml
ext_pojo_construction:
  framework_choice: go-struct
  flexible_extension_used: false        # Java-only flag; always false on Go.
  custom_unmarshal:
    kind: <none | go-unmarshaljson>
    accepts_shapes: []                  # From Step 4's custom_unmarshal_accepts[].
    where_branched: <bidder-class | jsondeserializer-class | type-method | null>
```

`kind` is `go-unmarshaljson` iff Step 4 detected a custom UnmarshalJSON. Otherwise `none`.

`where_branched` for the Go side:

- `type-method` — the UnmarshalJSON is on a TYPE declared inside `imp_{xyz}.go` (Appnexus `ExtImpAppnexusKeywords`).
- `bidder-class` — the UnmarshalJSON is on the parent `*ExtImp{Bidder}` itself.
- `null` — when `kind: none`.

`accepts_shapes[]` is the same list as `custom_unmarshal_accepts[]` from Step 4.

### Step 7: Cross-link to other spec sections

This skill does NOT populate fields owned by other skills. But the orchestrator's assembly step relies on a few fields produced here; ensure they're emitted with the exact shape:

- `params.ext_struct.fields[].notes[]` — read by `read-adapter-code` for the JSON-tag-style-mismatch cross-check (Go edge case #7).
- `params.ext_struct.custom_unmarshal: true` — surfaces in `cross_language.port_concerns.custom_unmarshaljson_present: true` after assembly. The bidder-params skill does not set the cross-language flag itself.
- `params.params_test.bidder_constant_referenced` — used by the orchestrator to generate validation rule R7 warnings.
- `provenance.warnings[]` entries emitted by this skill are merged into the assembled `provenance.warnings[]` array; do NOT emit a top-level `warnings:` block, only the entries.

## Edge case mapping

This skill covers three of the 17 Go edge cases catalogued in the plan and `shared/adapter-spec.md`. For each, the skill emits structured fields that capture the case without falling into the `custom` + free-text quirks fallback.

| # | Edge case | Captured by |
|---|---|---|
| 6 | Custom UnmarshalJSON | Step 4 sets `custom_unmarshal: true` and populates `custom_unmarshal_accepts[]`; Step 6 emits `ext_pojo_construction.custom_unmarshal.{kind: go-unmarshaljson, accepts_shapes, where_branched}`. Canonical example: Appnexus `ExtImpAppnexusKeywords` (string \| object \| array). |
| 7 | Intentional JSON key style mismatch | Step 4 emits `params.ext_struct.fields[].notes[]` containing a `"json key style mismatch"` note when the json tag uses a different style than the surrounding adapter expects. The bidder-params skill records the INFO; `read-adapter-code` owns the actual FAIL (PR #4592 msft `pubclick` vs `pub_click`). |
| 17 | JSON Schema combinators | Step 3 emits `combinators_used[]` with the subset of `oneOf, anyOf, not, oneOf-of-oneOf` actually present. Canonical examples: Rubicon (`oneOf` for `accountId`), AppNexus (`anyOf` on keywords field; `oneOf-of-oneOf` for legacy/new naming pairs — see `references/schema-interpretation.md`). |

The skill does NOT cover: package-vs-directory mismatch (#1), adapter struct identifier (#2), test directory naming (#3), multi-file layout (#4), custom request body (#5), hardcoded constants (#8), endpoint construction (#10), batching (#11), status-code handling (#12), currency overwrite (#13), shallow-copy (#14), bid pointer pattern (#15), endpoint macros (#16). Those are owned by `read-adapter-code`, `read-bidder-info`, or the orchestrator's provenance assembly.

## Cross-language note

`bidder_params_json` is **byte-identical** between Go and Java repos for the same bidder (port-translation Rule 5 — the cross-language contract). The Java sibling skill `read-bidder-params-java` reads the same file from the Java repo's `src/main/resources/static/bidder-params/{bidder}.json` and emits the same `bidder_params_sha256`. A SHA mismatch is a port-fidelity violation:

| Spec field | Go side | Java side | Equality |
|---|---|---|---|
| `bidder_params_json` | bytes from Go repo | bytes from Java repo | byte-identical |
| `bidder_params_sha256` | sha of Go bytes | sha of Java bytes | identical |
| `params.schema_interpretation` | parsed Go-side | parsed Java-side | deep-equal (both languages parse the same bytes) |
| `params.ext_struct.package` | `openrtb_ext` | `org.prebid.server.proto.openrtb.ext.request.{xyz}` | divergent (language-native) |
| `params.ext_struct.type_name` | `ExtImp{Xyz}` or `ImpExt{Xyz}` | `ExtImp{Xyz}` (Lombok @Value @Builder) | divergent shape, same name pattern |
| `params.ext_struct.fields[].type_native` | Go primitives + `jsonutil.StringInt`/`IntString` | Java primitives + `Long` with `@JsonAlias` | divergent (Rule 9 — flexible-type translation) |
| `params.params_test.bidder_constant_referenced` | `openrtb_ext.Bidder{Name}` | not applicable (Java unit tests don't have a bidder constant) | Go-only |
| `ext_pojo_construction.framework_choice` | `go-struct` always | `lombok-value-builder` / `lombok-data` / `lombok-value-staticconstructor` | divergent |
| `ext_pojo_construction.custom_unmarshal.kind` | `none` or `go-unmarshaljson` | `none`, `jackson-jsondeserialize`, `jackson-jsonalias-only`, `runtime-isobject-isarray-branching` | divergent enum spaces, but `none` agrees |

Cross-reference Rule 9 (flexible-type translation): Go `jsonutil.StringInt` ↔ Java `@JsonAlias` + `Long`. Documented in `shared/port-translation-rules.md` Section "Imp.ext unmarshaling rules" implicitly via Rule 1; the explicit flexible-type rule is captured in the `notes[]` field on each side.

Verification by the cross-language CI harness: dual-spec assertions assert `bidder_params_sha256` equality and `params.schema_interpretation` deep-equality; `params.ext_struct` differs by language and is asserted only on shape (same field names + same `omitempty` values for fields that exist on both sides).

## Verification

The skill's correctness is anchored to two golden spec fixtures:

| Fixture | Path | What it pins |
|---|---|---|
| Optidigital | `read/test-fixtures/optidigital.golden.spec.yaml` | Clean baseline. JSON has trailing whitespace + missing terminal newline → `bidder_params_json` MUST use double-quoted YAML scalar (lines 64-68). 4 schema properties + 2 required. Legacy `ImpExt{Bidder}` naming. SHA `6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31`. |
| Kobler | `read/test-fixtures/kobler.golden.spec.yaml` | Bidder-constant-mismatch detection. `params_test.go` line 47 uses `BidderKrushmedia` (real bug). SHA `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685`. Single-property schema (`test: boolean`). 3 valid + 8 invalid params cases. |

Acceptance criteria for a clean run on either fixture:

1. `bidder_params_json` round-trips byte-equal: re-decoding the YAML scalar produces the same bytes as the source file (R2 test).
2. `bidder_params_sha256` matches the value in the golden spec (constant for that commit).
3. `params.schema_interpretation.combinators_used[]` is empty for kobler/optidigital; `["anyOf", "oneOf-of-oneOf"]` for appnexus.
4. `params.ext_struct.custom_unmarshal: false` for kobler/optidigital; `true` for appnexus.
5. For kobler: `provenance.warnings[]` includes a `bidder-constant-mismatch` entry pointing at line 47 of `params_test.go`.
6. For kobler: `params.params_test.bidder_constant_referenced: openrtb_ext.BidderKrushmedia` (the WRONG value, since `TestInvalidParams` is the line that surfaced; the orchestrator's assembly handles the warning pairing).

A reader skill that emits a `custom` value in any enumerated field MUST also emit a `quirks[]` entry referencing the same field — this is the Custom-with-quirks contract from `shared/behavior-taxonomy.md`. The `quirks[]` array is assembled by the orchestrator; this skill emits `quirks[]` candidates as `provenance.warnings[]` entries with appropriate `type` values, and the orchestrator promotes them into `quirks[]` per the `edge_case_taxon` registry (`shared/behavior-taxonomy.md` "quirks edge_case_taxon (full registry)").

## Determinism

Two runs of this skill on the same commit MUST produce byte-identical output (R4 — round-trip determinism). To achieve this:

- Read files in binary mode (no line-ending normalization).
- Sort `properties[]` in `schema_interpretation` in source order (the order they appear in the JSON schema), NOT alphabetically.
- Sort `fields[]` in `ext_struct` in source order (the order they appear in the Go struct), NOT alphabetically.
- Sort `combinators_used[]` alphabetically (`anyOf, json-aliases-present, not, oneOf, oneOf-of-oneOf`).
- Sort `flexible_types[]` alphabetically.
- Emit string keys in the order specified by `shared/adapter-spec.md`; do not let the YAML emitter re-order keys.

The orchestrator excludes `provenance.read.timestamp_utc` and `provenance.read.operator` from determinism comparison.

## How to test this skill

```bash
# Smoke test against the optidigital golden spec.
read-bidder-params --bidder=optidigital --source-mode=local --resolved-commit=d7f8515b8625... | \
    yq '.params, .bidder_params_sha256, (.provenance.warnings // [])'
# Expected:
#   bidder_params_sha256: 6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31
#   params.schema_interpretation.required_fields: [publisherId, placementId]
#   params.ext_struct.type_name: ImpExtOptidigital      (legacy naming — surfaces as INFO quirk in orchestrator assembly)
#   provenance.warnings: []                              (no anomalies)

# Smoke test against the kobler golden — must capture the bidder-constant-mismatch.
read-bidder-params --bidder=kobler --source-mode=local --resolved-commit=d7f8515b8625... | \
    yq '.params.params_test, (.provenance.warnings | map(select(.type == "bidder-constant-mismatch")))'
# Expected:
#   params.params_test.bidder_constant_referenced: openrtb_ext.BidderKrushmedia
#   provenance.warnings:
#     - type: bidder-constant-mismatch
#       file: adapters/kobler/params_test.go
#       line: 47
#       summary: "validator.Validate called with openrtb_ext.BidderKrushmedia ..."

# Round-trip determinism: two consecutive runs at the same commit must produce identical output
# (modulo provenance.read.timestamp_utc and provenance.read.operator).
diff <(read-bidder-params --bidder=kobler --resolved-commit=<sha>) \
     <(read-bidder-params --bidder=kobler --resolved-commit=<sha>)
# Expected: empty (no diff)
```

## Sources

- Plan: `~/.claude/plans/you-are-right-lets-mighty-wombat.md` (Phase B Go suite, `read-bidder-params` skill).
- Canonical schema: `prebid-server-go/read/skills/shared/adapter-spec.md` (sections `bidder_params_json`, `bidder_params_sha256`, `params`, `ext_pojo_construction`; validation rules R1, R2, R4, R7).
- Behavior taxonomy: `prebid-server-go/read/skills/shared/behavior-taxonomy.md` (`params.schema_interpretation.combinators_used[]`, `ext_pojo_construction.framework_choice`, `ext_pojo_construction.custom_unmarshal.kind`, `quirks edge_case_taxon` registry — `bidder-constant-mismatch`, `legacy-impext-naming`, `json-key-style-mismatch`, `incomplete-classification`).
- Port translation rules: `prebid-server-go/read/skills/shared/port-translation-rules.md` (Rule 1 standard ExtPrebid two-phase, Rule 2 direct-to-custom-wrapper, Rule 3 free-form; cross-language flexible-type translation noted on Rule 1).
- Schema-to-Go type mapping (REUSED, not duplicated): `prebid-server-go/review/skills/bidder-params-pr-review/references/params-type-index.md` (master truth — JSON Schema → Go type table).
- Framework helpers (REUSED): `prebid-server-go/review/skills/shared/framework-utilities.md` (`util/jsonutil` extras: `StringInt`, `IntString`, `MergeClone`, `FindElement`, `DropElement`, `ParseIntoString`).
- Review skill (LINKED, NOT copied): `prebid-server-go/review/skills/bidder-params-pr-review/SKILL.md` (verification workflows for diff-based PR review; complementary scope to the read skill which extracts full-file specs).
- Local schema-interpretation reference: [references/schema-interpretation.md](references/schema-interpretation.md).
- Golden specs: `prebid-server-go/read/test-fixtures/optidigital.golden.spec.yaml`, `prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`.
- Live source files (verified at v4.1.0, commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e`):
  - `static/bidder-params/kobler.json` (sha `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685`)
  - `openrtb_ext/imp_kobler.go` (5 LOC, 1 field, no custom UnmarshalJSON)
  - `adapters/kobler/params_test.go` (line 47: `validator.Validate(openrtb_ext.BidderKrushmedia, ...)` — the canonical bidder-constant-mismatch bug)
  - `static/bidder-params/optidigital.json` (sha `6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31`, trailing whitespace + no terminal newline)
  - `openrtb_ext/imp_optidigital.go` (legacy `ImpExtOptidigital` naming)
  - `openrtb_ext/imp_appnexus.go` (canonical custom UnmarshalJSON on `ExtImpAppnexusKeywords` accepting string/object/array)
