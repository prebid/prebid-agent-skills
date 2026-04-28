# Schema Interpretation Reference

Rules and procedures for interpreting `static/bidder-params/{xyz}.json` into the Adapter Specification's `params.schema_interpretation` block, and for classifying the corresponding Go ext struct in `params.ext_struct`. Consumed by the `read-bidder-params` SKILL.md.

The master JSON Schema → Go type mapping table is canonical at [`../../../review/skills/bidder-params-pr-review/references/params-type-index.md`](../../../review/skills/bidder-params-pr-review/references/params-type-index.md). This file references that table — do NOT duplicate the table here.

The `combinators_used[]` enum is canonical at [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md) under `params.schema_interpretation.combinators_used[]`.

Framework helper signatures (`jsonutil.StringInt`, `IntString`, etc.) are canonical at [`../../../review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md) under "util/jsonutil extras beyond Marshal/Unmarshal". This file references that file — do NOT duplicate.

---

## `$schema` draft handling

The schema's `$schema` declaration is read but NOT emitted directly into `schema_interpretation`. Acceptable values for current master:

- `"http://json-schema.org/draft-04/schema#"` — REQUIRED for all canonical adapters. PBS uses the `gojsonschema` library which is draft-04. Surfaces no spec field.
- Any other value — emit a `provenance.warnings[]` entry of type `non-draft-04-schema` (file:line, the actual `$schema` value). Treat the rest of the schema as draft-04 anyway since `gojsonschema` will at runtime; the warning surfaces the divergence.

The `$schema`, `title`, and top-level `description` are part of the verbatim `bidder_params_json` and the SHA — they round-trip into the spec via that channel and don't need separate fields.

The top-level `"type": "object"` is REQUIRED for all canonical adapters; `"type"` other than `"object"` at the top level is unsupported by the validator and emits a `non-object-top-type` warning.

---

## Normalized `properties[]` shape

Each entry in `params.schema_interpretation.properties[]` has:

```yaml
- name: <string>          # The JSON property name verbatim.
  type: <string>          # See "Type field encoding" below.
  description: <string>   # The JSON Schema "description" verbatim, or null if absent.
  constraints:            # OPTIONAL — present only when the schema declares constraints.
    minLength: <int>      # Per "minLength".
    maxLength: <int>      # Per "maxLength".
    minimum: <number>     # Per "minimum".
    maximum: <number>     # Per "maximum".
    pattern: <string>     # Per "pattern" (regex source verbatim).
    enum: [<values>]      # Per "enum".
    minItems: <int>       # Per "minItems" (arrays).
    maxItems: <int>       # Per "maxItems" (arrays).
```

Property emission order: source order (the order properties appear in the JSON file). NOT alphabetical. Determinism (R4) requires this.

### Type field encoding

| JSON Schema `type` | Emit as `type` |
|---|---|
| `"string"` | `string` |
| `"integer"` | `integer` |
| `"number"` | `number` |
| `"boolean"` | `boolean` |
| `"object"` | `object` |
| `"array"` | `array` |
| `["integer","string"]` | `["integer","string"]` (preserve the array, sorted alphabetically by element string) |
| `["string","integer"]` | `["integer","string"]` (NORMALIZE alphabetical) |
| Type omitted (e.g., property uses only `anyOf`/`oneOf`) | `null` |

The alphabetical normalization of multi-type arrays is required for round-trip determinism — JSON Schema has no canonical ordering for the array, but the spec emits a stable form.

### Description field

`description` is verbatim from the schema. If absent, emit `null`. Multi-line descriptions are preserved as YAML literal block scalars when they contain embedded newlines.

### Constraints emission

Emit `constraints:` only when at least one constraint key is present. An empty constraints block (`constraints: {}`) is NOT emitted — omit the key entirely.

The `minLength`/`maxLength` values are emitted as integers (not strings). `pattern` is emitted as the verbatim regex source — do NOT compile it.

`enum` values are emitted in source order (the order they appear in the JSON), with their original types preserved (string enums stay strings; integer enums stay integers).

---

## `required_fields[]` extraction

The top-level `required` array of the schema. Emit verbatim, in source order:

```json
"required": ["publisherId", "placementId"]
```

→

```yaml
required_fields:
  - publisherId
  - placementId
```

Required fields nested inside combinator branches (`oneOf[].required`, `anyOf[].required`) are NOT included in `required_fields[]` — those are owned by the combinator branch and surface via `combinators_used[]` instead. The `required_fields[]` field is exactly the top-level `"required"` array.

If the schema has no top-level `required`, emit `required_fields: []`.

---

## `flexible_types[]` detection

A property is "flexible-typed" when its `type` field is an ARRAY of types (the JSON Schema construct for accepting multiple primitive types):

```json
"placement_id": {
    "type": ["integer", "string"],
    "description": "An ID which identifies this placement of the impression"
}
```

For each such property, append the property NAME to `flexible_types[]`:

```yaml
flexible_types:
  - placement_id
  - placementId
  - member
```

Sort alphabetically (R4 determinism). Empty list when no flexible-typed properties exist.

The values inside the type array do NOT influence `flexible_types[]` — only the fact that the type is an array. So both `["integer","string"]` and `["string","number"]` cause the property to appear in `flexible_types[]`.

The companion Go-type rule for this property (REUSED from `review/skills/bidder-params-pr-review/references/params-type-index.md`):

| Schema `type` array | Recommended Go type | Anti-pattern |
|---|---|---|
| `["integer","string"]` | `jsonutil.StringInt` | `interface{}` (loses type safety) |
| `["string","number"]` | `interface{}` (no canonical helper exists) | n/a — `interface{}` is acceptable here |

When the Go ext struct uses `jsonutil.StringInt` for a flexible-typed field, append the note `"uses jsonutil.StringInt for integer-or-string flexibility"` to that field's `notes[]`. When the Go ext struct uses `interface{}` for a `["integer","string"]` schema, append the note `"interface{} chosen for flexibility — recommend jsonutil.StringInt (review/bidder-params-pr-review Workflow: Flexible Type Schema Field)"`.

The cross-language port-translation rule (Rule 9 from `shared/port-translation-rules.md` — flexible-type Go ↔ Java mapping) maps Go `jsonutil.StringInt` to Java `@JsonAlias` + `Long` with custom deserialization; that rule is enforced on the Java side, not by this skill.

---

## `combinators_used[]` detection

Walk the top-level schema and immediate `properties[*]` looking for the four JSON Schema combinator keywords. Emit a sorted list of detected combinators:

| JSON Schema construct | Emit value | Detection rule |
|---|---|---|
| `"oneOf": [...]` at top level OR inside any property | `oneOf` | Any `oneOf` key whose value is a non-empty array. |
| `"anyOf": [...]` at top level OR inside any property | `anyOf` | Any `anyOf` key whose value is a non-empty array. |
| `"not": {...}` at top level OR inside any property | `not` | Any `not` key with a non-null value. |
| `"oneOf": [{ "oneOf": [...] }, ...]` (any branch's items contain `oneOf`) | `oneOf-of-oneOf` AND `oneOf` | Both the outer and the nesting are emitted (the `oneOf-of-oneOf` value is additive). |
| Java only: `@JsonAlias({...})` on the POJO field | `json-aliases-present` | Java-side detection only — Go specs never emit this value. |

Sort alphabetically: `[anyOf, json-aliases-present, not, oneOf, oneOf-of-oneOf]` (any subset).

### `oneOf` (XOR — exactly one branch satisfied)

Canonical Rubicon pattern (`accountId` accepts string OR int):

```json
"oneOf": [
    { "type": "string" },
    { "type": "integer" }
]
```

Emits `combinators_used: [oneOf]`. The `oneOf` is logically equivalent to `type: ["string","integer"]` BUT the spec records both: `oneOf` in `combinators_used[]` AND the field appears in `flexible_types[]` only if the schema actually used the `type: [...]` form. The two encodings are NOT cross-emitted — match what the schema literally declares.

### `anyOf` (OR — at least one branch satisfied)

Canonical Appnexus pattern (`keywords` accepts string OR array-of-objects):

```json
"keywords": {
    "anyOf": [
        { "type": "string", "minLength": 1 },
        { "type": "array", "minItems": 1, "items": { ... } }
    ]
}
```

Emits `combinators_used: [anyOf]`. The Go ext struct typically backs this with a custom-typed field that has its own `UnmarshalJSON` method (Appnexus's `ExtImpAppnexusKeywords` accepts string / object / array via `switch b[0]`).

### `not` (negation)

Canonical Appnexus legacy pattern:

```json
"not": { "required": ["placementId", "invCode", "member"] }
```

Emits `combinators_used: [not]`. Rare — most adapters use `oneOf`/`anyOf` instead.

### `oneOf-of-oneOf` (nested)

Canonical Appnexus legacy/new naming pattern:

```json
"oneOf": [
    { "oneOf": [
        { "required": ["placementId"] },
        { "required": ["placement_id"] }
    ]},
    { "oneOf": [
        { "required": ["invCode", "member"] },
        { "required": ["inv_code", "member"] }
    ]}
]
```

Emits `combinators_used: [oneOf, oneOf-of-oneOf]` (both — the nested form is ADDITIVE, not REPLACING). The detection rule: any `oneOf` whose elements themselves are objects containing `oneOf` triggers `oneOf-of-oneOf`. Nesting depth >2 is theoretically possible but unobserved in master — if encountered, still emit `oneOf-of-oneOf` (no separate `oneOf-of-oneOf-of-oneOf` value).

The Java sibling expresses this same constraint via `@JsonAlias({"placement_id"})` on the `placementId` field — surfaces in the Java spec's `combinators_used: [oneOf, oneOf-of-oneOf, json-aliases-present]`. The Go side never emits `json-aliases-present`.

### Schema-level `allOf`

`allOf` is supported by gojsonschema but rarely used in master adapters. It is NOT included in the `combinators_used[]` enum because no master adapter declares it for behavioral purposes. If encountered, emit a `quirks[]` candidate of `edge_case_taxon: incomplete-classification` and ALSO emit `combinators_used: [allOf]` as a `custom` value — pair with a free-text quirks entry per the Custom-with-quirks contract (`shared/behavior-taxonomy.md`).

---

## Ext struct detection rules

For `params.ext_struct`, the skill reads `openrtb_ext/imp_{xyz}.go`. The Go AST or regex extracts:

1. **Package declaration** — must be `openrtb_ext`. Other packages emit a `quirks[]` candidate of `edge_case_taxon: incomplete-classification`.
2. **Type name** — the EXPORTED struct type. Two patterns are observed:
   - `ExtImp{Bidder}` — canonical (~160 of ~235 in master).
   - `ImpExt{Bidder}` — legacy (~75 in master, e.g., `ImpExtOptidigital`, `ImpExtMsft`).
   
   The skill emits `type_name` verbatim. The orchestrator's assembly may emit a `legacy-impext-naming` quirk for the latter form (canonical example: optidigital — see `read/test-fixtures/optidigital.golden.spec.yaml` lines 274-277).
3. **Fields[]** — each field declared on the chosen struct type. Fields on helper types (e.g., `extImpAppnexusKeyVal` for keyword pairs) are NOT emitted in this list — only fields on the principal `ExtImp{Xyz}` / `ImpExt{Xyz}` type. Helper types appear in `quirks[]` only if the read-adapter-code skill flags them.

### Per-field shape

```yaml
- name: <Go field name>           # Verbatim from struct.
  json_tag: <tag value>           # The string after `json:"`, before the comma.
  type_native: <Go type>          # Verbatim Go type as written.
  omitempty: <bool>               # true iff `,omitempty` appears in the json tag.
  notes: []                       # See note rules below.
```

`type_native` examples (verbatim from source):

- `string`, `int`, `int64`, `bool`, `float64`
- Pointer: `*string`, `*int`, `*bool`
- Slice: `[]string`, `[]int`, `[]NestedStruct`
- Map: `map[string]any`, `map[string]string`
- Framework: `jsonutil.StringInt`, `jsonutil.IntString`
- Stdlib: `json.RawMessage`
- Empty interface: `interface{}` or `any` (modern Go form)

The skill does NOT normalize these to a cross-language type — that's the job of the spec consumers (porters). The `type_native` is the verbatim Go source.

### Notes rules

Append a string to `notes[]` for each of these conditions (test independently — multiple notes can apply to one field):

| Condition | Note text |
|---|---|
| `type_native == "jsonutil.StringInt"` AND schema declares `"type": ["integer","string"]` for this field | `"uses jsonutil.StringInt for integer-or-string flexibility"` |
| `type_native == "jsonutil.IntString"` | `"uses jsonutil.IntString — schema declares integer but upstream may send string"` |
| `type_native == "interface{}"` or `"any"` AND schema uses combinators on this field | `"interface{} chosen for combinator flexibility — flag as WARN (review/bidder-params-pr-review Workflow: Flexible Type Schema Field)"` |
| `type_native == "map[string]any"` AND schema declares `"type": "object"` with no `properties` | `"map[string]any for opaque pass-through — recommended only when truly opaque"` |
| Json tag uses style different from rest of struct (camelCase among snake_case, etc.) | `"json key style mismatch — see Go edge case #7"` (canonical example: msft `pubclick` vs `pub_click`, PR #4592) |
| Schema property has `"required": true` AND Go field is a pointer (`*T`) | `"required schema field declared as pointer — risks zero-value silently dropped on omitempty"` |
| Schema property has `"required": false` (i.e., not in the top-level `required[]`) AND Go field is a non-pointer non-bool primitive without `omitempty` | `"optional schema field without ,omitempty — zero value will serialize"` |

Each note is a single string. The order of notes inside `notes[]` is alphabetical (R4 determinism). Empty `notes: []` when no conditions apply.

### `omitempty` detection

The skill parses the json tag's comma-separated options:

```go
TagID string `json:"tagid,omitempty"`
//                  ^^^^^  ^^^^^^^^^
//                  tag    options[0]
```

`omitempty: true` iff `omitempty` appears in the options list. Other options (`string`, `-`) are tolerated but not surfaced (no spec field). If the json tag is `-` (excluded from JSON), the field is NOT emitted in `fields[]` at all.

### Custom UnmarshalJSON detection

A custom UnmarshalJSON is detected when the file declares ANY function:

```go
func (<receiver>) UnmarshalJSON(data []byte) error
```

The receiver type identifies which type owns the custom unmarshal. Detection is positive when:

- The receiver is `*ExtImp{Bidder}` or `ExtImp{Bidder}` (the principal type) — `where_branched: bidder-class`.
- The receiver is a named type declared INSIDE the same `imp_{xyz}.go` file (e.g., `*ExtImpAppnexusKeywords`) — `where_branched: type-method`.
- The receiver is in any other package or any other file — NOT counted by this skill (those are owned by `read-adapter-code` if they exist in the adapter directory).

#### Inferring `accepts_shapes[]` from the method body

Walk the method body looking for branching on JSON shape:

| Body pattern | Inferred shape |
|---|---|
| `switch b[0]` or `switch data[0]` with case `'{'` | `object` |
| Same with case `'['` | `array` |
| Same with case `'"'` | `string` |
| `bytes.Equal(data, []byte("null"))` early-return | `null` |
| `if data[0] == '"' { ... } else if isDigit(data[0]) { ... }` | `string`, `number` (or `integer` if integer-only path) |
| `json.Unmarshal(data, &<bool>)` or `data[0] == 't' \|\| data[0] == 'f'` | `boolean` |

The detection is heuristic — for a pathological method body that combines unusual branching, emit `accepts_shapes: ["custom"]` and add a `provenance.warnings[]` candidate of `incomplete-classification` so the orchestrator can promote it to a `quirks[]` entry.

Sort `accepts_shapes[]` alphabetically: `[array, boolean, null, number, object, string]` (any subset). Determinism R4.

The Appnexus canonical example: `ExtImpAppnexusKeywords.UnmarshalJSON` body has `switch b[0] { case '{': ...; case '[': ...; }` AND a final fallthrough that treats the input as a string. Emit `accepts_shapes: [array, object, string]`.

---

## `params_test.go` parsing

The skill counts test cases and extracts the bidder constant.

### Counting

The canonical structure (REUSED from `review/skills/bidder-params-pr-review/references/params-type-index.md` "Standard Structure"):

```go
var validParams = []string{
    `{}`,
    `{ "test": true }`,
}

var invalidParams = []string{
    ``,
    `null`,
}

func TestValidParams(t *testing.T) {
    for _, validParam := range validParams { ... }
}

func TestInvalidParams(t *testing.T) {
    for _, invalidParam := range invalidParams { ... }
}
```

`valid_cases_count` = number of elements in the `validParams` slice literal.
`invalid_cases_count` = number of elements in the `invalidParams` slice literal.

Method (in order of preference):

1. **Go AST** — find `*ast.GenDecl` for `Tok == token.VAR`, walk to find names `validParams` and `invalidParams`, count the `*ast.CompositeLit.Elts` length.
2. **Regex fallback** — find `var validParams = []string{` and the matching `}`, count backtick-delimited strings between (regex `` `[^`]*` `` matched non-greedily). Same for `invalidParams`.
3. **`go test` runner fallback** — only when the file uses non-standard structure (e.g., a different variable name or a method-table). Run `go test -run 'TestValidParams|TestInvalidParams' -v -count=1 ./adapters/{bidder}/...` and count `--- PASS:` / `--- FAIL:` lines per test. NOT reliable for the canonical for-each-loop form (which has only ONE test name) — works only if the loop is restructured as `t.Run(name, ...)` subtests, which is rare for params_test.go.

Comments inside the slice literal do NOT count as elements. Trailing-comma is tolerated by Go and does not affect the count.

If either variable is missing or the file uses a non-standard shape, emit `valid_cases_count: null` and/or `invalid_cases_count: null` and a `provenance.warnings[]` entry of type `incomplete-classification` (file:line, free-text summary).

### `bidder_constant_referenced` extraction

The canonical call inside both test functions:

```go
validator.Validate(openrtb_ext.BidderKobler, json.RawMessage(validParam))
//                 ^^^^^^^^^^^^^^^^^^^^^^^^
//                 bidder constant
```

Walk the file looking for `*ast.SelectorExpr` whose `X.Name == "openrtb_ext"` and `Sel.Name` starts with `Bidder` — that's the bidder constant.

Both `TestValidParams` and `TestInvalidParams` typically reference the same constant. When they DIFFER (the kobler bug), use the value from `TestValidParams` for the field's primary value, and emit a `provenance.warnings[]` entry pointing at the line where the WRONG constant appears in `TestInvalidParams`.

The kobler real bug (REAL evidence — see `adapters/kobler/params_test.go` at master commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e`):

```go
// Line 24 (TestValidParams):
if err := validator.Validate(openrtb_ext.BidderKobler, json.RawMessage(validParam)); err != nil {
//                           ^^^^^^^^^^^^^^^^^^^^^^^^ correct
    t.Errorf("Schema rejected Kobler params: %s", validParam)
}

// Line 47 (TestInvalidParams):
if err := validator.Validate(openrtb_ext.BidderKrushmedia, json.RawMessage(invalidParam)); err == nil {
//                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^ WRONG — copy-paste from another adapter
    t.Errorf("Schema allowed unexpected params: %s", invalidParam)
}
```

The test passes despite the wrong identifier because:
- `validator.Validate(BidderKrushmedia, raw)` looks up the schema for `krushmedia` (which exists as an unrelated adapter) and validates `raw` against THAT schema.
- If `raw` is malformed enough to be rejected by both the kobler schema and the krushmedia schema (which is the case for `null`, `5`, `[]`, `true`, etc. — all rejected by every schema), the test still passes.

The kobler golden spec at `read/test-fixtures/kobler.golden.spec.yaml` lines 18-25 captures this as a `bidder-constant-mismatch` warning AND lines 290-298 capture the corresponding `quirks[]` entries. The skill emits the warning; the orchestrator promotes it to a quirks entry per the `bidder-constant-mismatch` taxon (`shared/behavior-taxonomy.md` "quirks edge_case_taxon (full registry)").

#### TitleCase rule

The expected bidder constant for bidder `<name>` is whatever appears as `Bidder<X> BidderName = "<name>"` in `openrtb_ext/bidders.go` at the resolved commit. Look it up directly — do NOT try to derive it from `<name>` via TitleCase. The constant generation rules are not deterministically derivable from the YAML name; treat `bidders.go` as ground truth.

Examples (verified at master commit `d7f8515b`):

| Bidder name | Constant |
|---|---|
| `kobler` | `BidderKobler` |
| `optidigital` | `BidderOptidigital` |
| `33across` | `Bidder33Across` (capital A after the digit) |
| `cadent_aperture_mx` | `BidderCadentApertureMX` (acronym MX preserved) |
| `appnexus` | `BidderAppnexus` |
| `aja` | `BidderAJA` (acronym preserved) |
| `e_volution` | `BidderEVolution` (camelHump after underscore drop) |
| `huaweiads` | `BidderHuaweiAds` (explicit camelHump) |
| `adtonos` | `BidderAdTonos` (explicit camelHump) |

The categories that diverge from a flat `TitleCase(name)`:

- **Acronym preservation** (`AJA`, `MX`, `TV`, `BWX`, `AMX`, `CWire`, etc.) — upstream maintainers chose to keep the brand's all-caps form in the identifier.
- **Explicit camelHumps** for multi-word brands (`AdTonos`, `BeyondMedia`, `BidsCube`, `BigoAd`, `ConnectAd`, `HuaweiAds`, etc.) — the YAML name is lowercase but the constant carries the brand's intended capitalization.
- **Leading-digit names** (`33across` → `Bidder33Across`) capitalize the first letter after the digit. The `Bidder` prefix makes any name a valid Go identifier; the precise capitalization is upstream's choice.

When in doubt, grep `openrtb_ext/bidders.go` at the pinned commit. The list is small (~270 entries) and authoritative.

When the actual bidder constant in `params_test.go` ≠ the expected constant, emit:

```yaml
provenance:
  warnings:
    - type: bidder-constant-mismatch
      file: adapters/{bidder}/params_test.go
      line: <line where the wrong constant appears>
      summary: "<Test function name> calls validator.Validate with openrtb_ext.<Wrong> (copy-paste artifact); should be openrtb_ext.<Expected>. The Validate call still functions because the validator looks up the schema by name and rejects on schema mismatch — the test passes despite the wrong identifier."
```

The orchestrator's assembly step pairs this warning with a `quirks[]` entry of `edge_case_taxon: bidder-constant-mismatch`.

---

## Edge cases summary

The skill captures these edge cases via structured fields (no free-text quirks fallback):

| Edge case | Captured by |
|---|---|
| Custom UnmarshalJSON on principal type | `params.ext_struct.custom_unmarshal: true` + `where_branched: bidder-class` + `accepts_shapes[]` |
| Custom UnmarshalJSON on inner type (Appnexus keywords) | Same as above + `where_branched: type-method` |
| Flexible-typed schema (`["integer","string"]`) | `flexible_types[]` + per-field `notes[]` mentioning `jsonutil.StringInt` |
| Combinators (oneOf, anyOf, not, oneOf-of-oneOf) | `combinators_used[]` |
| JSON-key-style mismatch (msft `pubclick` vs `pub_click`) | `params.ext_struct.fields[].notes[]` containing the mismatch flag |
| Legacy `ImpExt{Bidder}` naming (optidigital) | `params.ext_struct.type_name: ImpExt<Bidder>` (verbatim); orchestrator emits `legacy-impext-naming` quirk |
| Bidder-constant-mismatch in tests (kobler `BidderKrushmedia`) | `provenance.warnings[]` entry of type `bidder-constant-mismatch` |
| Singular `param_test.go` filename (Ogury, PR #4082) | Tolerated; emit a `provenance.warnings[]` entry of type `singular-param-test-filename` for new adapters but NOT for existing files |

Cases NOT covered by this skill (delegated to other readers):

- Adapter implementation (`adapters/{xyz}/{xyz}.go`) — `read-adapter-code`.
- YAML bidder-info (`static/bidder-info/{xyz}.yaml`) — `read-bidder-info`.
- Test fixtures (`adapters/{xyz}/{xyz}test/*.json`) — `read-adapter-code`.
- Java sibling files — `read-bidder-params-java`.

---

## Sources

- Plan: `~/.claude/plans/you-are-right-lets-mighty-wombat.md` (Phase B Go suite, `read-bidder-params` skill scope).
- Canonical schema: `prebid-server-go/read/skills/shared/adapter-spec.md` (`params.schema_interpretation`, `params.ext_struct`, `params.params_test`, `ext_pojo_construction`; validation rules R1-R10).
- Behavior taxonomy: `prebid-server-go/read/skills/shared/behavior-taxonomy.md` (`combinators_used[]` enum, `framework_choice`, `custom_unmarshal.kind`, `quirks edge_case_taxon` registry).
- Port translation rules: `prebid-server-go/read/skills/shared/port-translation-rules.md` (Rule 1 standard ExtPrebid two-phase, Rule 9 flexible-type Go ↔ Java mapping note).
- JSON Schema → Go type table (REUSED, master truth): `prebid-server-go/review/skills/bidder-params-pr-review/references/params-type-index.md`.
- Framework helpers (REUSED): `prebid-server-go/review/skills/shared/framework-utilities.md` (`util/jsonutil` extras, `jsonutil.StringInt`, `jsonutil.IntString`, error type taxonomy).
- Review skill (LINKED): `prebid-server-go/review/skills/bidder-params-pr-review/SKILL.md` (Workflow: Schema Property Changed, Workflow: Required Fields Changed, Workflow: Flexible Type Schema Field, Workflow: Struct Field Changed, Workflow: Params Test Changed).
- Skill SKILL.md: [`../SKILL.md`](../SKILL.md).
- Live source files (verified at v4.1.0, commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e`):
  - `static/bidder-params/kobler.json` (sha `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685`).
  - `adapters/kobler/params_test.go` line 47 — canonical bidder-constant-mismatch with `BidderKrushmedia`.
  - `static/bidder-params/optidigital.json` (sha `6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31`) — trailing whitespace + missing terminal newline (drives the YAML double-quoted scalar choice).
  - `openrtb_ext/imp_optidigital.go` — legacy `ImpExtOptidigital` naming.
  - `openrtb_ext/imp_appnexus.go` — canonical `ExtImpAppnexusKeywords.UnmarshalJSON` accepting object/array/string via `switch b[0]`.
  - `static/bidder-params/appnexus.json` — canonical `anyOf` (keywords) + `oneOf-of-oneOf` (placement_id/placementId legacy/new pairing) + flexible-typed `placement_id`/`placementId`/`member`.
- Golden specs: `prebid-server-go/read/test-fixtures/optidigital.golden.spec.yaml`, `prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`.
