# JSON Schema → Adapter Spec interpretation rules (Java side)

Reference for the `read-bidder-params-java` skill. Defines the algorithm that maps a JSON Schema document at `src/main/resources/static/bidder-params/{xyz}.json` to the `params.schema_interpretation` block of the Adapter Specification, plus the rules for detecting Java POJO ext patterns (Lombok variants, Jackson annotations, FlexibleExtension), and the rules for counting Java JUnit test methods.

The interpretation algorithm is **identical to the Go-side `read-bidder-params` interpretation algorithm** because the JSON file is byte-identical between the two repos (port translation rule R5 in [`../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md`](../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md)). What differs is the Java-side ext-POJO detection (this file) versus Go's struct-tag detection.

---

## Part 1 — JSON Schema → `schema_interpretation` (cross-language)

This section is identical to the Go-side reference. The output `params.schema_interpretation` block MUST be byte-equal between Go and Java specs of the same bidder.

### Walking the schema

The bidder-params schema is JSON Schema draft-04 (declared in `$schema`). The reader walks the schema and emits four top-level lists.

#### `properties[]`

For each entry under top-level `"properties": { ... }`:

- `name` — the JSON key.
- `type` — the value of `"type":` field. Either a single string (`"string"`, `"integer"`, `"boolean"`, `"number"`, `"object"`, `"array"`) or an array (e.g., `["integer", "string"]`) for flexible-type fields.
- `description` — the `"description":` value verbatim, or `null` if absent.

Nested properties (under `properties[X].properties`) are NOT flattened into the top-level list — they are listed as sub-properties under their parent's entry only when the parent's `type` is `object` AND the schema author has elected to declare nested structure. Most bidder-params schemas keep nesting shallow (≤ 1 level of object nesting under top-level keys).

#### `required_fields[]`

The contents of the top-level `"required":` array. Empty list when no required fields.

#### `flexible_types[]`

Field names whose `"type":` value is an array. Each entry: `{ name, accepted_types: [...] }`. These are the fields that drive port translation rule R9 (flexible-type idiom mismatch between Go and Java).

Example schema fragment:

```json
"placementId": { "type": ["integer", "string"], "description": "..." }
```

→ `flexible_types: [{ name: placementId, accepted_types: [integer, string] }]`.

The Go side handles this via `jsonutil.StringInt` / `jsonutil.IntString` (a type that unmarshals from either a JSON number or a JSON string). The Java side typically handles this via `Long` + `@JsonAlias` for legacy field-name compat (this is a different concern — alias handles renames, not flexible types) OR via a custom `@JsonDeserialize` that accepts both shapes. See Part 3 below for Java-side detection.

#### `combinators_used[]`

Walk the entire schema (every nesting depth) and emit one entry for each JSON Schema combinator detected. Values are from [`../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md#paramsschema_interpretationcombinators_used`](../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md):

| Value | Trigger |
|---|---|
| `oneOf` | Any `"oneOf":` array anywhere in the schema. |
| `anyOf` | Any `"anyOf":` array. |
| `not` | Any `"not":` clause. |
| `oneOf-of-oneOf` | A `"oneOf":` array whose entries themselves contain `"oneOf"` (nested compositional). |
| `json-aliases-present` | NOT detected from schema — populated in Part 3 if the Java POJO carries `@JsonAlias`. Informational only; surfaces in `combinators_used[]` so the spec view captures the Java-side compatibility shim. |

The combinators list is unordered (emit as a deduplicated list).

### Identical-output guarantee

The Go-side `read-bidder-params` reader and the Java-side `read-bidder-params-java` reader MUST produce byte-equal `schema_interpretation` blocks for the same bidder. The orchestrator computes a stable hash of `schema_interpretation` and surfaces a `schema-interpretation-divergence` warning if Go and Java disagree. The single exception is `combinators_used[]` containing `json-aliases-present` — that entry is Java-only because it derives from the POJO, not the schema.

---

## Part 2 — Java POJO ext detection (Lombok + Jackson)

The Java POJO at `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` carries the params type. Detection rules:

### Class-level annotations → `framework_choice`

```yaml
ext_pojo_construction:
  framework_choice: lombok-value-builder | lombok-value-staticconstructor | lombok-data | custom
```

Decision rules (apply in order; first match wins):

1. **`@Value` + `@Builder`** (with optional `@Jacksonized`, `@AllArgsConstructor(access = AccessLevel.PRIVATE)`, `@NoArgsConstructor(access = AccessLevel.PRIVATE, force = true)`) → `lombok-value-builder`. This is the most common Java pattern. Gives an immutable POJO with builder API; Jackson uses the builder via `@Jacksonized`.

2. **`@Value(staticConstructor = "of")`** (Lombok's static-factory shortcut) → `lombok-value-staticconstructor`. Yields a `ExtImpKobler.of(true)` factory method. Used by Kobler. Less common than `@Value @Builder`.

3. **`@Data` + `@NoArgsConstructor`** (mutable POJO) → `lombok-data`. Rare for ExtImp because Jackson default-constructs and field-injects, but found on a few legacy adapters. Pairs with Jackson's standard property setter detection.

4. **No Lombok annotations** (plain Java POJO with hand-written getters/setters) → `custom`. REQUIRES a `quirks[]` entry. This is rare in modern Java prebid-server adapters but possible for adapters that pre-date Lombok adoption.

### `extends FlexibleExtension` → `flexible_extension_used`

If the class declaration extends `FlexibleExtension` (full type: `org.prebid.server.proto.openrtb.ext.FlexibleExtension`), set `flexible_extension_used: true`.

The `FlexibleExtension` base class provides `@JsonAnyGetter`/`@JsonAnySetter` plumbing so the POJO preserves unknown JSON keys verbatim (round-trip fidelity). Adapters that need to pass through arbitrary publisher/buyer keys without losing them set this. Appnexus is the canonical example.

If `FlexibleExtension` is NOT extended but the class has explicit `@JsonAnyGetter`/`@JsonAnySetter` methods, ALSO emit `flexible_extension_used: true` (the structural behavior is the same).

### Field-level annotations → `fields[].notes[]`

For each field declaration (`private final {Type} {name}` or `private {Type} {name}`):

| Annotation | Effect on `notes[]` and other spec fields |
|---|---|
| `@JsonProperty("alt-name")` | Sets `json_tag: alt-name` (overrides the default Java field name). No `notes` entry — this is the standard renaming mechanism. |
| `@JsonProperty(value = "...", required = true)` | Add note: `"required at deserialization time"`. (Note: this is Jackson-level required, distinct from JSON Schema `required`.) |
| `@JsonAlias({"a","b"})` | Add note: `"@JsonAlias({\"a\",\"b\"}) — accepts legacy field names a, b"`. ALSO add `json-aliases-present` to `params.schema_interpretation.combinators_used[]` (informational). |
| `@JsonDeserialize(using = XyzDeserializer.class)` | Set `params.ext_struct.custom_unmarshal: true`. Set `ext_pojo_construction.custom_unmarshal.kind: jackson-jsondeserialize` and `where_branched: jsondeserializer-class`. Add note: `"custom deserializer: XyzDeserializer"`. |
| `@JsonInclude(JsonInclude.Include.NON_NULL)` (on field or class) | Set field-level (or class-default) `omitempty: true`. |
| `@JsonInclude(JsonInclude.Include.NON_EMPTY)` | Set `omitempty: true` and add note: `"omits empty collections and strings"`. |
| `@JsonRawValue` | Add note: `"@JsonRawValue — value serialized as raw JSON"`. |
| `@JsonAnyGetter` / `@JsonAnySetter` | Confirms FlexibleExtension semantics on a method; pairs with `flexible_extension_used: true`. |

### Type-driven notes (port translation rule R9 surfaces)

The Java field type may have a Go-side counterpart that uses a flexible-type idiom. When detected, add a note pointing to R9.

| Java type | Likely Go counterpart | Note text |
|---|---|---|
| `Long` (paired with `@JsonAlias` on the same field for accepting both string and integer JSON values) | `jsonutil.StringInt` | `"flexible-type idiom mismatch with Go (R9): Go uses jsonutil.StringInt, Java uses Long + @JsonAlias for legacy spellings"` |
| `String` (paired with `@JsonAlias` accepting integer JSON values via the deserializer) | `jsonutil.IntString` | `"flexible-type idiom mismatch with Go (R9): Go uses jsonutil.IntString, Java uses String + custom @JsonDeserialize"` |
| `JsonNode` (raw) | `json.RawMessage` | `"raw JsonNode passthrough — adapter parses at runtime"` (typically pairs with `runtime-isobject-isarray-branching`) |
| `ObjectNode` (raw) | `json.RawMessage` (when Go also accepts only object-shaped values) | Same note as `JsonNode` plus `"object-shape constraint enforced"`. |
| `Map<String, JsonNode>` | `map[string]json.RawMessage` | `"untyped JSON object — keys typed, values raw"`. |
| Custom helper class (e.g., `ExtImp{Xyz}Param`, `ExtImp{Xyz}Banner`) | A nested Go struct (e.g., `ExtImp{Xyz}Param`) | No special note; the helper class is recorded in `bidder_class.helper_classes_in_proto[]` by `read-bidder-class`. |

The R9 detection requires reading BOTH the Java POJO AND the Go-side schema.json fields list. The skill surfaces R9 only when:

1. The JSON Schema field has `flexible_types` (i.e., `type: ["integer","string"]`), AND
2. The Java POJO uses a single non-flexible type (`Long`, `String`) for that field (rather than a custom polymorphic deserializer).

If the JSON Schema field is non-flexible-type but the Java POJO uses `@JsonAlias`, that is NOT R9 — it is `jackson-jsonalias-only` for legacy field-name compatibility (different concern).

### Custom deserializer detection

A class is a custom deserializer if:

- It `extends StdDeserializer<T>` (Jackson's standard base class), OR
- It implements `JsonDeserializer<T>`, OR
- It is referenced in a `@JsonDeserialize(using = ...)` annotation.

Read the deserializer's `deserialize(JsonParser p, DeserializationContext ctxt)` method body and extract the accepted shapes:

| Source pattern in deserialize() | accepts_shapes entry |
|---|---|
| `node.isArray()` | `array` |
| `node.isObject()` | `object` |
| `node.isTextual()` or `node.asText()` direct | `string` |
| `node.isNumber()` or `node.intValue()` direct | `number` |
| `node.isBoolean()` | `boolean` |

`accepts_shapes` is unordered; deduplicate.

`where_branched` is set to `jsondeserializer-class` when the branching lives in a separate JsonDeserializer class file in proto/.

If the bidder class itself (in `src/main/java/org/prebid/server/bidder/{xyz}/{Xyz}Bidder.java`) does the branching (rather than a deserializer), set `where_branched: bidder-class`. The skill detects this by looking for `JsonNode.isArray()`, `JsonNode.isObject()` calls in the bidder class body — but the bidder-class file is owned by `read-bidder-class`, so this skill defers the check to that skill and accepts a hint via the orchestrator's shared state.

### `helper_classes_in_proto[]` (recorded but not owned)

The proto/ directory may contain multiple classes:

- The primary `ExtImp{Xyz}.java` (main params POJO) — recorded under `params.ext_struct`.
- Helper POJOs like `ExtImp{Xyz}Banner.java`, `ExtImp{Xyz}Video.java`, `ExtImp{Xyz}Param.java` — listed under `bidder_class.helper_classes_in_proto[]`.
- Custom request/response payload POJOs for adapters with `Bidder<T>` generic (Mediasquare's `MediasquareRequest`, Huaweiads's `HuaweiAdsRequest`).
- Custom JsonDeserializer classes — listed under `bidder_class.helper_classes_in_proto[]` plus the parent field's `notes[]`.

This skill ENUMERATES the proto/ directory and emits the file list to the orchestrator. The actual `bidder_class.helper_classes_in_proto[]` field is populated by `read-bidder-class` (which owns that block). The two skills coordinate via the orchestrator's shared file-inventory step.

---

## Part 3 — Java JUnit test method counting

The Java unit test class at `src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java` is a hand-written JUnit class extending `VertxTest` (the canonical Java test base class). It contains `@Test`-annotated methods that exercise valid and invalid bidder behavior.

### Valid-cases counting

A method counts as "valid case" if it carries `@Test` AND its name matches one of:

- `should_*` — but NOT `should_returnError_*` and NOT `should_throwError_*`.
- `make*ShouldReturn*` — typical positive-expectation pattern (`makeHttpRequestsShouldReturnExpectedRequest`, `makeBidsShouldReturnBid*`).
- `*ShouldUseDefault*` — covers default-value tests.
- `*ShouldAdd*` — covers field-addition tests.
- `*ShouldConvert*` — covers transformation tests.
- `*ShouldSanitize*` — covers data-cleansing tests.
- `*ShouldUse*Endpoint*` — covers endpoint-routing tests.
- `*ShouldDefaultTo*` — covers default-fallback tests.
- `*ShouldReturnEmpty*` — borderline; treat as valid (the absence of bids is a valid outcome).
- `*ShouldReturnBid*` (without "Error") — clearly valid.

### Invalid-cases counting

A method counts as "invalid case" if it carries `@Test` AND its name matches one of:

- `should_returnError_when_*`
- `*ShouldReturnError*`
- `*ShouldFail*`
- `*ShouldThrow*`
- `creationShouldFailOn*` — covers constructor-validation tests (e.g., `creationShouldFailOnInvalidEndpointUrl`).
- `*WhenInvalid*`, `*OnInvalid*`, `*Invalid*Should*`

### Border cases

- A method that tests "should return empty list when seatbid is empty" is borderline. It validates a graceful no-error path; count it as **valid**.
- A method that tests "should add error when ..." but the adapter still returns a valid response (errors collected as side channel) is also borderline; count it as **invalid** because the test's assertion focuses on the error.
- A method that tests both a success path and an error path in branches (less common) — count as **valid** if the primary assertion is on a successful return.

When a name does NOT match any pattern, count it under valid_cases_count by default and surface a `quirks` entry with taxon `incomplete-classification` listing the unmatched method names.

### Total = valid + invalid

The total method count should equal the sum (`valid_cases_count + invalid_cases_count`). If a method was unclassifiable, the totals will be off; the quirk records the discrepancy.

### `bidder_constant_referenced` is null

Java does NOT have a bidder constant analog. Go uses `openrtb_ext.BidderXyz` enum-like constants in `params_test.go` (e.g., `validator.Validate(openrtb_ext.BidderKobler, ...)`); Java uses YAML names directly as strings (e.g., `"kobler"` literal in test code). The skill ALWAYS emits `bidder_constant_referenced: null` for Java specs.

The Go-only `bidder-constant-mismatch` warning (validation rule R7 in [`../../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md)) does NOT apply on the Java side. The skill SKIPS the rule R7 check entirely.

A Java spec MAY carry `bidder-constant-mismatch` quirks under `quirks[]` if the cross-language port pair (Go side) has the bug — see Kobler Java golden, where the Java spec records the Go-side `kobler_test.go` and `params_test.go` mismatches under quirks for cross-language port awareness. These are NOT Java-side bugs; they are Go-side bugs surfaced for porter awareness.

---

## Part 4 — Worked example: Kobler Java

For Kobler, the inputs are:

1. `prebid-server-java/src/main/resources/static/bidder-params/kobler.json` — byte-identical to `prebid-server-go/static/bidder-params/kobler.json`. SHA: `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685`.

2. `prebid-server-java/src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/ExtImpKobler.java` — declaration:

```java
@Value(staticConstructor = "of")
public class ExtImpKobler {
    Boolean test;
}
```

→ Detection:
- `framework_choice: lombok-value-staticconstructor` (rule 2 from Part 2).
- `flexible_extension_used: false` (no `extends FlexibleExtension`).
- Field `test`: `name: test`, `json_tag: test` (no `@JsonProperty`), `type_native: Boolean`, `omitempty: false` (no `@JsonInclude`), `notes: ["@Value(staticConstructor=of)"]`.
- `custom_unmarshal: false` (no `@JsonDeserialize`, no `JsonDeserializer<T>` class in proto/).
- `custom_unmarshal.kind: none`.

3. `prebid-server-java/src/test/java/org/prebid/server/bidder/kobler/KoblerBidderTest.java` — 14 `@Test` methods (per Java kobler golden):

| Method name | Classification |
|---|---|
| `creationShouldFailOnInvalidEndpointUrl` | Invalid (constructor validation failure) |
| `makeHttpRequestsShouldReturnErrorIfNoValidImps` | Invalid (error case) |
| `makeHttpRequestsShouldConvertBidFloorCurrency` | Valid (positive transformation) |
| `makeHttpRequestsShouldUseDevEndpointWhenTestModeEnabled` | Valid (positive routing) |
| `makeHttpRequestsShouldUseDefaultEndpointWhenTestModeDisabled` | Valid |
| `makeHttpRequestsShouldUseDefaultEndpointWhenTestModeAbsent` | Valid |
| `makeHttpRequestsShouldAddUsdToCurrenciesIfMissing` | Valid (positive addition) |
| `makeHttpRequestsShouldSanitizeDeviceAndUserData` | Valid (positive sanitization) |
| `makeBidsShouldReturnErrorIfResponseBodyIsInvalid` | Invalid |
| `makeBidsShouldReturnEmptyListWhenBidResponseIsNull` | Valid (graceful no-bid) |
| `makeBidsShouldReturnEmptyListWhenSeatbidIsEmpty` | Valid (graceful no-bid) |
| `makeBidsShouldReturnBidWithBannerType` | Valid |
| `makeBidsShouldReturnBannerWhenTypeIsNullOrMissing` | Valid (default fallback) |
| `makeBidsShouldDefaultToBannerWhenPrebidTypeIsMissing` | Valid (default fallback) |

→ `valid_cases_count: 11`, `invalid_cases_count: 3`, `bidder_constant_referenced: null`.

Note: The Java kobler golden currently emits `valid_cases_count: null` and `invalid_cases_count: null` because the Java spec convention is to record total `unit_test_methods_count: 14` (under `tests:`) instead of splitting valid/invalid for the params block — Java unit tests cover the entire bidder, not just params. The skill emits the split counts when `params_test_method_split_mode: true` is set on the orchestrator (off by default for Java); when off, both fields are null.

---

## Part 5 — Edge cases and quirks

| Pattern | Detection | Quirk taxon |
|---|---|---|
| Multi-class proto/ split (custom request/response payload) | More than one class in `proto/openrtb/ext/request/{xyz}/` | None — recorded structurally in `bidder_class.helper_classes_in_proto[]`. |
| FlexibleExtension AND `@JsonDeserialize` together | Both class-level annotations present | None — recorded structurally in `flexible_extension_used: true` AND `custom_unmarshal.kind: jackson-jsondeserialize`. |
| `@JsonAlias` on every field of a class with no `@JsonDeserialize` | All fields carry `@JsonAlias` | `custom_unmarshal.kind: jackson-jsonalias-only`. No quirk. |
| Test class missing (alias bidders that have only an integration test) | File-not-found at `bidder/{xyz}/{Xyz}BidderTest.java` | `incomplete-classification` quirk; `params_test: null`. |
| Test class present but extends `IntegrationTest` instead of `VertxTest` | Test class extends wrong base | `legacy-test-helpers-imported` quirk + `provenance.warnings`. |
| Field type that is a generic helper class not in proto/ (e.g., a shared `org.prebid.server.proto.openrtb.ext.request.Format`) | Field type fully-qualified outside proto/{xyz}/ | None — common pattern. |
| ExtImp class missing entirely (Java code uses raw `JsonNode` parsing in the bidder class) | No `ExtImp{Xyz}.java` file | `params.ext_struct: null`; `quirks: incomplete-classification` with note explaining no proto. Possibly Ogury-style free-form-imp-ext-no-proto pattern (Pattern Index in `prebid-server-java/references/new-bid-adapter-prs.md`). |

---

## Sources

- Canonical schema: [`../../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md) (`bidder_params_json:`, `bidder_params_sha256:`, `params:` block, `ext_pojo_construction`, validation rules R5 + R7)
- Behavior taxonomy: [`../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md`](../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md) (`combinators_used[]`, `framework_choice` enum, `custom_unmarshal.kind` enum, `where_branched` enum)
- Port translation rules: [`../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md`](../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md) (R5 — bidder_params_json byte-identical contract; R9 — flexible-type idiom mismatch Go `jsonutil.StringInt` ↔ Java `Long` + `@JsonAlias`)
- Java kobler golden: [`../../../test-fixtures/kobler.golden.spec.yaml`](../../../test-fixtures/kobler.golden.spec.yaml)
- Go counterpart kobler golden: [`../../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml)
- Java reference list (Lombok and Jackson patterns under "Code & Adapter Patterns (Java-specific)"): [`../../../../references/new-bid-adapter-prs.md`](../../../../references/new-bid-adapter-prs.md)
- Sister Go skill (structural template, written in parallel): `prebid-server-go/read/skills/read-bidder-params/`
- Skill body: [`../SKILL.md`](../SKILL.md)
