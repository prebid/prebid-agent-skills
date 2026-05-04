---
name: read-bidder-params
description: Populate `bidder_params_json`, `bidder_params_sha256`, and `params` blocks of an Adapter Specification from `static/bidder-params/*.json`, `openrtb_ext/imp_*.go`, and `adapters/*/params_test.go`. USE WHEN read-adapter-orchestrator dispatches the bidder-params domain, or directly for a Go adapter's params section. Preserves JSON bytes verbatim (Rule R2), classifies the ext struct, counts test cases, surfaces bidder-constant-mismatch warnings. Do NOT use for `static/bidder-info/*.yaml` (read-bidder-info), adapter Go code (read-adapter-code), or Java sibling (read-bidder-params-java).
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

This is the cross-language byte-fidelity contract ([Rule 38](../shared/port-translation-rules.md)). The Java sibling skill `read-bidder-params-java` reads `src/main/resources/static/bidder-params/{bidder}.json` from the Java repo and MUST produce the same SHA. Mismatch surfaces as a port-fidelity violation in the cross-language test harness (R5). Verified canonical SHAs for corpus adapters live in the goldens at `../../test-fixtures/*.golden.spec.yaml`; if a re-read on master produces a different SHA, the orchestrator emits a `master-drift` warning.

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

Special `notes[]` to append per field:

- `jsonutil.StringInt` + schema declares `"type": ["integer","string"]` → `"uses jsonutil.StringInt for integer-or-string flexibility"` (pairs with `flexible_types[]`).
- `jsonutil.IntString` → `"uses jsonutil.IntString — schema declares integer but upstream may send string"`.
- `interface{}` or `any` + combinators (`anyOf`/`oneOf`) → `"interface{} chosen for combinator flexibility — flag as WARN"`.
- Go field name ≠ json tag style (e.g., `pubclick` vs `pub_click`) → `"json key style mismatch — see Go edge case #7"` (INFO; `read-adapter-code` owns the FAIL — canonical: msft PR #4592).

Canonical JSON Schema → Go type table is REUSED from `review/skills/bidder-params-pr-review/references/params-type-index.md`; `jsonutil.StringInt`/`IntString` semantics from `review/skills/shared/framework-utilities.md`. Do NOT re-list either here.

#### Custom UnmarshalJSON detection

Set `custom_unmarshal: true` when the file declares any `UnmarshalJSON` method on `*ExtImp{Bidder}` OR on a type declared inside the file (e.g., Appnexus's `ExtImpAppnexusKeywords`). Use Go AST (`go/parser` with `parser.SkipObjectResolution`) to walk `*ast.FuncDecl` nodes; regex fallback `^func \([^)]+ \*?\w+\) UnmarshalJSON\(.*\) error` for non-AST contexts.

Populate `custom_unmarshal_accepts[]` by inspecting the method body. Common patterns: `switch b[0] { case '{': ...; case '[': ... }` → `["object", "array"]`; `if data[0] == '"'` → `["string", ...]`; `bytes.Equal(data, []byte("null"))` early-return adds `"null"`. Appnexus's `ExtImpAppnexusKeywords.UnmarshalJSON` is canonical (object | array; `where_branched: type-method`). Convoluted bodies emit `custom_unmarshal_accepts: ["custom"]` paired with a `quirks[]` `incomplete-classification` entry per the Custom-with-quirks contract.

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

When `TestValidParams` and `TestInvalidParams` reference different constants (e.g., copy-paste artifact), emit the **last-observed** constant in source order — both calls' mismatches against the canonical constant from `bidders.go` emit paired `bidder-constant-mismatch` warnings. The kobler canonical bug surfaces at `params_test.go:47` referencing `openrtb_ext.BidderKrushmedia` (correct: `BidderKobler` at line 24). A successful run on kobler emits the warning AND a `quirks[]` entry of taxon `bidder-constant-mismatch` (the orchestrator pairs them on assembly).

Validation rule R7: if the constant on either line ≠ the constant declared as `Bidder<X> BidderName = "<name>"` in `openrtb_ext/bidders.go` at the resolved commit, emit a `bidder-constant-mismatch` warning with `{type, file, line, summary}`. The expected constant comes from the `bidders.go` declaration verbatim — do NOT derive it via TitleCase rules; constant capitalization is upstream-author-chosen (acronyms preserved, camelHumps explicit, leading-digit names capitalize after the digit). Treat `bidders.go` as ground truth.

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

## Edge cases covered

This skill covers Go edge cases #6 (custom UnmarshalJSON), #7 (JSON key style mismatch), and #17 (JSON Schema combinators). Each maps to a typed field — none fall through to `custom` + quirks. The full Go edge case mapping table lives in [`../shared/adapter-spec.md`](../shared/adapter-spec.md). Edge cases owned by sibling skills (`read-adapter-code`, `read-bidder-info`) are not covered here.

## Cross-language note

`bidder_params_json` is **byte-identical** between Go and Java repos for the same bidder (port-translation [Rule 38](../shared/port-translation-rules.md) — the cross-language byte-fidelity contract). The Java sibling skill `read-bidder-params-java` emits the same `bidder_params_sha256`; mismatch is a port-fidelity violation surfaced by R5 in the round-trip CI harness.

Field-by-field cross-language equality (which fields are byte-identical, deep-equal, or per-language-divergent) is canonicalized in [`../shared/port-translation-rules.md`](../shared/port-translation-rules.md) Rules 38, 39 (params), and 1 (imp.ext unmarshal). The dual-spec assertion files at `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` codify the must-match set; this skill does not duplicate it.

## Verification

Correctness is anchored to two goldens:

- `optidigital.golden.spec.yaml` — clean baseline with the trailing-whitespace + missing-terminal-newline edge that forces `bidder_params_json` into double-quoted YAML scalar form. Legacy `ImpExtOptidigital` naming.
- `kobler.golden.spec.yaml` — pins R7 `bidder-constant-mismatch` detection via `params_test.go:47` referencing `openrtb_ext.BidderKrushmedia`.

Acceptance criteria: (1) `bidder_params_json` round-trips byte-equal under YAML scalar decode; (2) `bidder_params_sha256` matches the golden's value; (3) `combinators_used[]` is empty for kobler/optidigital, `["anyOf", "oneOf-of-oneOf"]` for appnexus; (4) `custom_unmarshal: false` for kobler/optidigital, `true` for appnexus; (5) kobler emits a `bidder-constant-mismatch` warning at line 47; (6) `bidder_constant_referenced: openrtb_ext.BidderKrushmedia` (wrong-on-purpose; last-observed wins).

Custom-with-quirks contract: any `custom` value in an enumerated field MUST be paired with a `quirks[]` entry referencing the same field. This skill emits `provenance.warnings[]` candidates; the orchestrator promotes them into `quirks[]` per the registry in [`../shared/behavior-taxonomy.yaml`](../shared/behavior-taxonomy.yaml).

## Determinism

Two runs at the same commit MUST produce byte-identical output (R4). Read files in binary mode; sort `properties[]` and `ext_struct.fields[]` in source order (NOT alphabetically); sort `combinators_used[]` and `flexible_types[]` alphabetically; emit keys in the order specified by `../shared/adapter-spec.schema.json`. The orchestrator excludes `provenance.read.timestamp_utc` and `provenance.read.operator` from determinism comparison.

## Sources

- Schema (canonical): [`../shared/adapter-spec.schema.json`](../shared/adapter-spec.schema.json), [`../shared/adapter-spec.md`](../shared/adapter-spec.md).
- Taxonomy: [`../shared/behavior-taxonomy.yaml`](../shared/behavior-taxonomy.yaml) — `combinators_used[]`, `framework_choice`, `custom_unmarshal.kind`, `bidder-constant-mismatch` + `legacy-impext-naming` taxa.
- Port rules: [`../shared/port-translation-rules.yaml`](../shared/port-translation-rules.yaml) — Rules 1, 2, 3, 38, 39.
- Local: [`references/schema-interpretation.md`](references/schema-interpretation.md). REUSED (NOT duplicated): `review/skills/bidder-params-pr-review/references/params-type-index.md`, `review/skills/shared/framework-utilities.md`. Goldens: `../../test-fixtures/optidigital.golden.spec.yaml`, `../../test-fixtures/kobler.golden.spec.yaml`.
