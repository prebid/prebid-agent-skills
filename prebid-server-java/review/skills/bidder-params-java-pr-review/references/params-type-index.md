# Bidder Params Type Index — Java

Mapping of JSON Schema draft-04 types to Lombok-annotated POJO conventions for the Java triplet:

1. `src/main/resources/static/bidder-params/{x}.json` — the draft-04 schema (byte-fidelity to Go per Rule 38).
2. `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/ExtImp{X}.java` (+ helper protos in the same package) — Lombok `@Value`-annotated POJO that Jackson deserializes `imp.ext.bidder` into.
3. `src/test/resources/org/prebid/server/it/openrtb2/{x}/test-{...}.json` — the Rule 36 4-file IT fixture set (no Go analog).

**Upstream pin:** `prebid/prebid-server-java` master @ SHA `a1fe64e123d6` (per `shared/framework-utilities-java.md`). Schema engine: `com.networknt.schema` (draft-04 via `SpecVersion.VersionFlag.V4`). Lombok: provided by Spring Boot 3.5.10 BOM.

**Sync policy:** Local snapshot. The `pr-triage-java` skill's Step 2 runs centralized drift checks; this skill's Step 1b reads results from the manifest. If upstream `BidderParamValidator.java` or the schema spec version changes, update this file.

For framework-wide concerns (Lombok annotation semantics, JacksonMapper conventions, checkstyle `ImportOrder` traps, IT-class WireMock binding patterns), see [../../shared/framework-utilities-java.md](../../shared/framework-utilities-java.md) — especially §2 (Lombok annotations) and §6 (mvn-checkstyle). This file references those sections rather than duplicating them.

**Companion Go-side index:** [`../../../../prebid-server-go/review/skills/bidder-params-pr-review/references/params-type-index.md`](../../../../prebid-server-go/review/skills/bidder-params-pr-review/references/params-type-index.md). Cross-reference for byte-fidelity (Rule 38) and flexible-type (Rule 9) asymmetries.

---

## Module path

The Java codebase uses Maven coordinates `org.prebid:prebid-server-aggregator` version `3.42.0-SNAPSHOT`. No `vN`-major-suffix gymnastics analogous to Go's `github.com/prebid/prebid-server/vN` module — Java versioning is in `pom.xml` only and does not affect file paths or imports. PR diffs do NOT have Go's v3↔v4 import-noise issue.

---

## Part A — `bidder-params/{x}.json` schema index

The JSON Schema draft-04 file fed into the Java runtime validator. Lives at `src/main/resources/static/bidder-params/{x}.json` (classpath resource).

### A.1 Top-level structure (mandatory)

| Key | Required | Canonical value | Notes |
|---|---|---|---|
| `$schema` | Yes | `"http://json-schema.org/draft-04/schema#"` | The `JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V4)` instance honors draft-04. Any other `$schema` value is silently ignored by the factory; reviewers should enforce this at PR time. **FAIL** on mismatch. |
| `title` | Yes (convention) | `"{Bidder} Adapter Params"` | Stylistic; e.g., `"Aax Adapter Params"`, `"Kobler Adapter Params"`. **WARN** on deviation. |
| `description` | Yes (convention) | `"A schema which validates params accepted by the {Bidder} adapter"` | One-line sentence. **WARN** if absent. |
| `type` | Yes | `"object"` | Required at top level. **FAIL** on mismatch. |
| `properties` | Yes | `{}` (empty object minimum) | Even adapters with no declared params must have `"properties": {}`. Without it, the validator treats arbitrary input as valid — an unsafe default. **FAIL** if absent. |
| `required` | Optional | array of property-key strings | Only present when 1+ fields are required. |
| `additionalProperties` | Optional | `false` (typically omitted) | Java does NOT enforce `additionalProperties:false` by default — unknown keys in `imp.ext.bidder` are tolerated. Only set when the adapter genuinely rejects unknown fields. |

### A.2 Property-type taxonomy

The 6 JSON-Schema-draft-04 primitive types — each with constraint subkeys supported by `com.networknt.schema` v4:

| JSON Schema type | Constraint subkeys | Notes |
|---|---|---|
| `"string"` | `minLength`, `maxLength`, `pattern` | `pattern` uses ECMA 262 regex per JSON Schema spec; Java's `Pattern` is mostly compatible BUT `\\Q ... \\E` literal-quoting is non-portable. Reviewers should run the regex through a draft-04 validator (the `com.networknt.schema` test infrastructure) before flagging it. |
| `"integer"` | `minimum`, `maximum`, `multipleOf`, `exclusiveMinimum`, `exclusiveMaximum` | Note: draft-04 `exclusiveMinimum`/`exclusiveMaximum` are **boolean** modifiers on `minimum`/`maximum` (NOT separate numeric values as in draft-06+). Mixing draft-04 and draft-07 forms here is a **FAIL**. |
| `"number"` | `minimum`, `maximum`, `multipleOf` | For currency / bid floors. Java side maps to `BigDecimal` per §B.4. |
| `"boolean"` | (none) | Pure tri-state via boxed `Boolean` on POJO side. |
| `"array"` | `items`, `minItems`, `maxItems`, `uniqueItems` | `items` is itself a property-spec sub-object. |
| `"object"` | `properties`, `required`, `additionalProperties` | Nested object — maps to a nested @Value class on POJO side. |

**Flexible types** — `"type": ["integer", "string"]` (Go's `jsonutil.StringInt` analog). See §A.5 + §B.5.

**Enum constraint** — `"enum": [value1, value2, ...]`. Verify each enum value matches what `{X}Bidder.java` switches on. Cross-skill nudge to `bidder-class-pr-review` if the adapter expects values outside the enum set.

### A.3 Conditional validation constructs

draft-04 supports `oneOf` / `anyOf` / `allOf` / `not`. Draft-07's `if`/`then`/`else` are NOT supported — **FAIL** on use.

| Construct | Semantics | Common bidder use |
|---|---|---|
| `required: [a, b]` | a AND b both required (simple list) | The 90% case (Adverxo: `["adUnitId", "auth"]`). |
| `anyOf: [{required:[a]}, {required:[b]}]` | OR — at least one branch satisfied | Multi-spelling alias support (Ix: 3 spellings of siteId). |
| `oneOf: [{required:[a]}, {required:[b]}]` | XOR — exactly one branch | Mutually-exclusive identifier modes. |
| `allOf: [...]` | AND — all branches satisfied | Composition / inheritance-like. |
| `not: {required:[a,b,c]}` | NEGATION — must NOT match | Prevent invalid combinations. |
| Nested `oneOf` in `oneOf` | Complex backward-compat | The AppNexus pattern — accept old `placement_id` OR new `placementId`, plus accept `inv_code+member` OR `invCode+member`. |

The `com.networknt.schema` validator does NOT detect logical contradictions at compile time; a logically-impossible schema accepts no input at runtime — the adapter becomes unreachable. **WARN** when reviewer spots obvious contradictions.

### A.4 Required-fields semantics

`required: ["field1", "field2"]` — top-level required-fields list. Every entry MUST exist in `properties` (otherwise `JsonSchemaFactory.getSchema(...)` rejects the schema at startup with `IllegalArgumentException: Couldn't parse {bidder} bidder schema` — server fails to boot).

**Cross-language symmetry per Rule 38.** The `bidder-params.json` file MUST be byte-identical between Go and Java (modulo trailing-newline whitespace). See §D for divergence enforcement.

### A.5 F-new-62 — the runtime validation path

Earlier execution-plan drafts referenced literal Java-side "schema files" as separate artifacts. They don't exist. **Java validates at runtime inside `BidderParamValidator.java`** (`src/main/java/org/prebid/server/validation/BidderParamValidator.java`). The validation flow:

```
BidderCatalog.names()  →  for each bidder:
                         createSchemaNode(schemaDir, bidder)
                             ↓
                         ResourceUtil.readFromClasspath("static/bidder-params/{x}.json")
                             ↓
                         mapper.mapper().readTree(content)  → JsonNode
                             ↓
                         JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V4)
                             .getSchema(jsonNode)           → JsonSchema (cached)
                             ↓
                         CaseInsensitiveMap<bidder, JsonSchema>
```

At request time, `imp.ext.bidder` is validated:

```java
bidderSchemas.get(bidder).validate(jsonNode).stream()
    .map(ValidationMessage::getMessage)
    .collect(Collectors.toSet());   // returns Set<String>; empty == valid
```

**Diagnostic shape.** When validation fails, the reviewer sees a `Set<ValidationMessage>` containing draft-04-formatted messages like:

- `$.cid: is missing but it is required`
- `$.adUnitId: must have a minimum value of 1`
- `$.auth: must be at least 6 characters long`

When the schema FILE itself is malformed, server startup throws:

- `IllegalArgumentException: Couldn't parse {bidder} bidder schema`  — caught at boot, server fails to start
- `IllegalArgumentException: Couldn't find {bidder} json schema at static/bidder-params/{x}.json` — missing file
- `IllegalArgumentException: Failed to load {bidder} json schema at static/bidder-params/{x}.json. File is empty`

**Alias fallback.** `BidderParamValidator.createSchemaNode` catches `IllegalArgumentException` from a missing file AND falls back to `bidderCatalog.bidderInfoByName(bidder).getAliasOf()` to load the parent's schema. This is the Java analog of Go's alias-inherit-parent pattern. Verify on alias PRs that NO own `bidder-params/{alias}.json` exists.

**Cross-reference to read-side companion.** The read-side `framework-utilities-java.md` covers the catalog wiring + `BidderCatalog.names()` source. This file covers the review-time validation diagnostics surface.

---

## Part B — `ExtImp{X}.java` Lombok POJO index

The Lombok-annotated `imp.ext.bidder` POJO that Jackson deserializes into. Lives in `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/`.

### B.1 Class-level annotations

| Annotation | Effect | Severity rules |
|---|---|---|
| `@Value` | Immutable POJO: `private final` fields, all-args constructor, getters (no setters), `equals`+`hashCode`+`toString`. Default for ExtImp. | **PASS** (canonical). |
| `@Value(staticConstructor = "of")` | Same as `@Value` PLUS a static factory `ExtImp{X}.of(arg1, arg2, ...)`. Kobler/Adverxo/Ix/TheTradeDesk variant. | **PASS** — accepted variant. |
| `@Builder` | Fluent builder: `ExtImp{X}.builder().field(...).build()`. Paired with `@Value` for a builder + immutable instance. Used by Appnexus (`@Builder(toBuilder = true) @Value`). | **PASS**; **WARN** if paired with `@Builder` but no `@Jacksonized` AND the field set has 2+ optional fields. |
| `@Jacksonized` | Wires Jackson to deserialize via the builder (`@JsonDeserialize(builder = ...)` + `@JsonPOJOBuilder` glue). Required for `@Builder + @Value` POJOs Jackson must deserialize. | **WARN** when `@Builder` is present without `@Jacksonized` AND the class is read via Jackson. |
| `@JsonDeserialize(using = {X}Deserializer.class)` | Custom deserializer (e.g., for shape-flexible inputs). Helper class `{X}Deserializer extends StdDeserializer<ExtImp{X}>` must exist in the same package. | **FAIL** if referenced class is missing. |
| `@Data` | Mutable POJO: getters + setters, non-final fields. **BANNED on ExtImp** — breaks immutability contract. | **FAIL** when seen on ExtImp{X}. (Acceptable on `{X}BidderConfigurationProperties` per Rule 35; see `shared/framework-utilities-java.md` §2.3.) |
| `@AllArgsConstructor` (alone) | Raw POJO with all-args constructor. | **WARN** — non-idiomatic without `@Value` / `@Builder`. |
| `@NoArgsConstructor` (on `@Value` class) | Forbidden combo — Lombok can't generate a no-args constructor on a class with final fields. Indicates copy-paste from a `@ConfigurationProperties` template. | **FAIL**. |
| `@JsonInclude(JsonInclude.Include.NON_NULL)` | Suppresses null fields on serialization. | **INFO** if absent (not required for read-only ExtImp); **PASS** when present and POJO is round-tripped. |

For full Lombok semantics, see `shared/framework-utilities-java.md` §2.1–§2.8.

### B.2 Field-level annotations

| Annotation | Effect | When required |
|---|---|---|
| `@JsonProperty("snake_case_name")` | Maps JSON key ↔ Java field. | Whenever JSON key differs from Java identifier. The `#1 misalignment trap` per SKILL.md Workflow §POJO Field Changed. |
| `@JsonAlias({"alt1", "alt2"})` | Accepts multiple JSON keys for the SAME logical field. | When `oneOf` in schema accepts multiple spellings (Ix `siteid`/`siteId`/`siteID`, Appnexus `placementId`/`placement_id`). |
| `@JsonDeserialize(using = X.class)` | Field-level custom deserializer. | When the field's accepted shapes exceed `@JsonAlias` capability. |
| `@Singular` | On `@Builder` collection fields — fluent single-element setter. | When @Builder is used and the field is a `List<T>`/`Set<T>` and builder users add elements one at a time. |
| `@NotBlank`, `@NotNull`, `@Min`, `@Max` | `jakarta.validation.constraints.*` — runtime validation on Spring beans. | Typical on `@ConfigurationProperties` subclasses; rare on ExtImp{X} (the schema validator handles params validation; see §A.5). |

### B.3 Field-name capitalization rules

Java field names MUST be camelCase per Java convention. Lombok / Jackson serialize verbatim — so the JSON tag DEFAULTS to the field name when no `@JsonProperty` is present.

**Examples (canonical, verified against upstream master @ SHA `a1fe64e123d6`):**

Kobler — single optional boolean, factory constructor:

```java
package org.prebid.server.proto.openrtb.ext.request.kobler;

import lombok.Value;

@Value(staticConstructor = "of")
public class ExtImpKobler {

    Boolean test;
}
```

Adverxo — required int + required string, explicit `@JsonProperty` on the int (defensive — Lombok would emit `adUnitId` anyway, but the annotation makes the mapping explicit):

```java
package org.prebid.server.proto.openrtb.ext.request.adverxo;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Value;

@Value(staticConstructor = "of")
public class ExtImpAdverxo {

    @JsonProperty("adUnitId")
    Integer adUnitId;

    String auth;
}
```

TheTradeDesk — pair of camelCase strings, `@JsonProperty` on both (defensive):

```java
@Value(staticConstructor = "of")
public class ExtImpTheTradeDesk {

    @JsonProperty("publisherId")
    String publisherId;

    @JsonProperty("supplySourceId")
    String supplySourceId;
}
```

Ix — multi-spelling alias via `@JsonAlias` (the Java-side answer to schema `oneOf` over spellings):

```java
@Value(staticConstructor = "of")
public class ExtImpIx {

    @JsonProperty("siteId")
    @JsonAlias({"siteid", "siteID"})
    String siteId;

    List<Integer> size;

    String sid;
}
```

Appnexus — `@Builder(toBuilder=true) @Value` with mixed `@JsonAlias` and `@JsonProperty`, plus raw `JsonNode` for the shape-flexible `keywords` field:

```java
@Builder(toBuilder = true)
@Value
public class ExtImpAppnexus {

    @JsonAlias("placementId")
    Integer placementId;

    @JsonAlias("invCode")
    String invCode;

    String member;

    JsonNode keywords;           // raw passthrough — shape-branched in adapter

    @JsonProperty("use_pmt_rule")
    @JsonAlias("use_payment_rule")
    Boolean usePaymentRule;

    JsonNode privateSizes;       // raw passthrough

    boolean generateAdPodId;     // primitive boolean — false default OK here

    // ... more fields
}
```

### B.4 Field-type mapping (JSON Schema → Java)

| JSON Schema type | Recommended Java type | Notes |
|---|---|---|
| `"string"` | `String` | Plain string. Use `String` (not `Optional<String>`); Jackson injects `null` for missing keys. |
| `"integer"` (small range) | `Integer` (boxed) | Boxed type allows `null` for absent fields. Use boxed even on required fields (the runtime validator enforces presence). |
| `"integer"` (wide IDs, > 2^31) | `Long` | For long-tail bidder IDs that may exceed Integer range. |
| `"number"` | `BigDecimal` | Currency / bid floors. NEVER `double` / `float` — precision loss is a known bug pattern in adapter code. |
| `"boolean"` | `Boolean` (boxed) | Use boxed on optional fields. Primitive `boolean` is acceptable on required fields where `false` is a meaningful default (e.g., Appnexus `generateAdPodId`). |
| `"array"` of primitives | `List<String>`, `List<Integer>`, etc. | Canonical; `Set<T>` only when dedup matters semantically (rare for ExtImp). |
| `"array"` of objects | `List<NestedClass>` | Where `NestedClass` is a nested @Value class. |
| `"object"` (nested, typed) | nested @Value class — typically `ExtImp{X}{Suffix}` (e.g., `ExtImpAppnexusKeywords`) | Helper proto co-located in same package. See §B.6. |
| `"object"` (opaque passthrough) | `JsonNode` or `ObjectNode` | Raw passthrough; adapter does runtime shape-branching. Pair with read-side companion's `ext_pojo_construction.custom_unmarshal.kind: runtime-isobject-isarray-branching`. |
| `["integer","string"]` (flexible) | See §B.5 — multiple idioms | Port-translation Rule 9 mismatch with Go's `jsonutil.StringInt`. |

### B.5 Flexible-type idiom matrix (port-translation Rule 9)

Go uses `jsonutil.StringInt` (a custom type unmarshaling both integer and string forms). Java's answer is asymmetric — four mechanisms, each with severity rules:

| Java mechanism | Pattern | Severity |
|---|---|---|
| **`Long` / `Integer` + `@JsonAlias({...})`** | The dominant idiom when the Java side wants both spellings of a SINGLE logical key. Does NOT solve Go's "accept both integer AND string for the SAME key" problem — only solves "accept multiple keys for the same field". | **INFO** — record the Go↔Java asymmetry as port-translation Rule 9. |
| **`JsonNode` raw passthrough** | Adapter code (`{X}Bidder.java`) does runtime shape-branching (`isObject()`, `isArray()`, `isTextual()`, `isNumber()`). Used in Appnexus `keywords`, `privateSizes`. Cross-reference read-side companion's `runtime-isobject-isarray-branching` taxonomy. | **INFO** (R9-tolerated). |
| **`@JsonDeserialize(using = {X}Deserializer.class)`** | Custom deserializer for fields needing more shape-flexibility than `@JsonAlias` provides. Verify `{X}Deserializer.java` exists in the same package and `extends StdDeserializer<{Type}>` (or implements `JsonDeserializer<{Type}>`). | **INFO** (legitimate); **FAIL** if deserializer class missing. |
| **Plain `Integer` / `String` (no alias, no deserializer)** | REGRESSION RISK on Go-symmetric `["integer","string"]` fields. Jackson rejects the form the schema accepts; IT fixture with the alternate form fails at `mvn test`. | **FAIL** — Java will fail deserialization on JSON the schema accepts. |

Cross-language symmetry verification (when `--- PRIOR SOURCE SPEC COMPARISON ---` is present in the manifest): see SKILL.md Step 1g rule 3 — flag asymmetries where Java cannot accept what Go accepts.

### B.6 Helper protos in the same package

Helper proto classes co-located with `ExtImp{X}.java`:

| Helper class | Role |
|---|---|
| `ExtImp{X}Banner.java`, `ExtImp{X}Video.java`, `ExtImp{X}Native.java` | Media-type sub-objects of the main ExtImp |
| `ExtImp{X}Keywords.java`, `ExtImp{X}Param.java` | Nested sub-objects of `imp.ext.bidder` |
| `ExtImp{X}BidExt.java`, `ExtImp{X}ResponseExt.java` | Bid-response `ext` blocks (used in `makeBids`, not `makeHttpRequests`) |
| `ExtImp{X}Deserializer.java`, `ExtImp{X}KeywordsDeserializer.java` | Custom Jackson deserializers (extends `StdDeserializer<T>`) |
| `ExtImp{X}Request.java`, `ExtImp{X}Response.java` | Outgoing bid-request / incoming bid-response DTOs (when the upstream bidder uses non-OpenRTB-2.x payload shape) |

Helper protos follow the same Lombok conventions as the parent (`@Value` typical; `@Value(staticConstructor="of")` accepted; `@Data` on a helper sub-object is **WARN**). Deserializer classes use plain Java (no Lombok) since they `extends StdDeserializer<T>`. See SKILL.md Workflow §Helper Proto Added for the deserializer correctness checks.

### B.7 Optional-vs-required + present-empty distinction (F-new-38)

Java does NOT have Go's `omitempty` vs non-omitempty distinction at the struct-tag level. Instead:

- **Schema `required: [x]` →** Java field typed `T x` (boxed Integer / Boolean / String). The runtime validator (`BidderParamValidator`) enforces presence AFTER Jackson deserialization. Java's TYPE SYSTEM does NOT enforce non-null on its own — Jackson will inject `null` for a missing key, and the validator's `Set<ValidationMessage>` reports it.
- **Schema optional field →** Java field typed `T x` with `null` as the implicit default.
- **Java `Optional<T>` is NOT canonical for ExtImp** — use nullable directly. `Optional` types serialize awkwardly with Jackson and contradict the immutable-record idiom.

**F-new-38 trap.** When a schema field is **optional** AND has `minLength: 1` (e.g., a string that may be absent BUT must be non-empty when present), the POJO field type `String` directly produces a deserialization gap:

1. Jackson sees `"field": ""` in input JSON.
2. Jackson deserializes to the Java `String` field as `""` (empty string).
3. The `BidderParamValidator` validates the `JsonNode` AFTER deserialization — it sees `""` and reports `must be at least 1 characters long`.
4. The auction pipeline rejects the imp BEFORE the adapter sees the partially-constructed POJO.

In practice, the order of operations is: validator runs first, adapter sees only schema-valid input. The F-new-38 pre-flag is defensive — when the schema has the optional+minLength:1 pattern, the reviewer should verify the adapter code (`{X}Bidder.java`) does not assume the schema enforces the constraint at the type level (e.g., does not call `.isEmpty()` and expect the validator to have caught empty strings). Severity: **WARN**. See SKILL.md Workflow §POJO Field Changed step 4.

### B.8 Class-naming convention

**Canonical type name: `ExtImp{X}`** (e.g., `ExtImpAax`, `ExtImpKobler`, `ExtImpAdverxo`, `ExtImpTheTradeDesk`). Helper protos follow `ExtImp{X}{Suffix}` (e.g., `ExtImpAppnexusKeywords`, `ExtImpAdverxoExt`).

Package MUST be `org.prebid.server.proto.openrtb.ext.request.{x}` (the bidder name, lowercased). Package mismatch is **FAIL**.

The checkstyle `OuterTypeFilename` rule (per `shared/framework-utilities-java.md` §6.7) requires the public class declared in `ExtImp{X}.java` to match the filename root (`public class ExtImp{X}`). Deviation triggers **F-new-79 trap** — won't compile. **FAIL** (CI-blocking).

Imports must follow the checkstyle 3-group convention (`shared/framework-utilities-java.md` §6.3): non-java/jakarta at top, blank separator, `java.*`/`jakarta.*` at bottom. **F-new-58** trap (`BidderDeps` out of order — does not apply to ExtImp since ExtImp doesn't import BidderDeps) and **F-new-59** trap (`lombok.Data` out of order — does not apply to ExtImp since ExtImp uses `@Value`, not `@Data`) primarily hit the Configuration files. For ExtImp, the typical import block is:

```java
import com.fasterxml.jackson.annotation.JsonAlias;
import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Value;

import java.util.List;
```

Non-java imports at top (lexically: `com.*`, `lombok.*`); blank line; `java.*` at bottom.

---

## Part C — IT fixture index

The Rule 36 4-file fixture set per scenario, lives under `src/test/resources/org/prebid/server/it/openrtb2/{x}/`. No Go analog — Go uses `exemplary/` + `supplemental/` directories under `{bidder}test/`.

### C.1 The 4-file set

| File | Role | What feeds it |
|---|---|---|
| `test-auction-{x}-request.json` | The publisher's OpenRTB auction request posted to `/openrtb2/auction`. Has `imp.ext.bidder.{property}` block. | Test client posts this to PBS's auction endpoint. |
| `test-auction-{x}-response.json` | The expected OpenRTB auction response PBS returns. | Test verifies actual response against this. |
| `test-{x}-bid-request.json` | The bidder-specific outbound request body PBS sends to the upstream bidder's endpoint. | WireMock matches `equalToJson(...)` against this. |
| `test-{x}-bid-response.json` | The mock bidder's response body returned by WireMock. | WireMock's `willReturn(aResponse().withBody(...))` |

### C.2 Linkage flow

```
test-auction-{x}-request.json
    ↓  POST /openrtb2/auction (test client)
prebid-server processing pipeline
    ↓  apply BidderParamValidator (schema validation of imp.ext.bidder)
    ↓  invoke {X}Bidder.makeHttpRequests
test-{x}-bid-request.json    ← matches WireMock stub's equalToJson(...)
    ↓  WireMock returns
test-{x}-bid-response.json    ← WireMock's willReturn body
    ↓  {X}Bidder.makeBids parses
prebid-server response assembly
    ↓  test verifies via assertJsonEquals(...)
test-auction-{x}-response.json
```

### C.3 WireMock binding (in `{X}Test.java` IT class)

The IT test class (owned by `bidder-class-pr-review`) drives the 4-file binding:

```java
WIRE_MOCK_RULE.stubFor(post(urlPathEqualTo("/{x}-exchange"))
        .withRequestBody(equalToJson(jsonFrom("openrtb2/{x}/test-{x}-bid-request.json")))
        .willReturn(aResponse().withBody(jsonFrom("openrtb2/{x}/test-{x}-bid-response.json"))));

final Response response = responseFor("openrtb2/{x}/test-auction-{x}-request.json",
        Endpoint.openrtb2_auction);

assertJsonEquals("openrtb2/{x}/test-auction-{x}-response.json", response, singletonList({X}));
```

The fixture-file paths in `jsonFrom(...)` calls must MATCH the actual fixture filenames exactly. A typo breaks the IT silently (test fails with file-not-found from classpath).

### C.4 Per-scenario method naming (F-new-60 + `to_camel` fix)

Multi-scenario bidders ship N × 4 files with the scenario name embedded:

- `test-video-{x}-bid-request.json`
- `test-video-{x}-bid-response.json`
- `test-auction-video-{x}-request.json`
- `test-auction-video-{x}-response.json`

The IT class's `@Test` method names MUST be camelCase per checkstyle `MethodName` (`shared/framework-utilities-java.md` §6.2). Snake_case method names like `scenarioFor_app_simple_banner` are **F-new-60** — Java's checkstyle blocks the build. Correct emission: `scenarioForAppSimpleBanner` (camelCase via the `to_camel` template macro from the F-new-60 fix). Severity: **MEDIUM**; owning skill: `bidder-class-pr-review` (this skill's IT-fixture review only flags the FIXTURE-file structural correctness, not the method name).

### C.5 IT fixture canonical example (Kobler — single-scenario)

Verified at `src/test/resources/org/prebid/server/it/openrtb2/kobler/`:

**`test-auction-kobler-request.json`** — publisher's OpenRTB auction request:

```json
{
  "id": "request_id",
  "imp": [{
    "id": "imp_id",
    "banner": {"w": 300, "h": 250},
    "secure": 1,
    "ext": {
      "tid": "${json-unit.any-string}",
      "bidder": {"test": false}
    }
  }],
  "site": {...},
  "device": {...},
  "at": 1,
  "tmax": "${json-unit.any-number}",
  "cur": ["USD"],
  ...
}
```

**`test-kobler-bid-request.json`** — outbound to upstream bidder:

```json
{
  "id": "request_id",
  "imp": [{
    "id": "imp_id",
    "banner": {"w": 300, "h": 250},
    "ext": {"kobler": {"test": false}}
  }],
  "tmax": 5000,
  "regs": {"ext": {"gdpr": 0}}
}
```

**`test-kobler-bid-response.json`** — mock bidder response:

```json
{
  "id": "request_id",
  "seatbid": [{
    "bid": [{
      "id": "bid_id", "impid": "imp_id", "price": 3.33,
      "adid": "adid001", "crid": "crid001", "cid": "cid001",
      "adm": "adm001", "mtype": 1, "h": 250, "w": 300
    }]
  }]
}
```

**`test-auction-kobler-response.json`** — expected PBS auction response:

```json
{
  "id": "request_id",
  "seatbid": [{...with full ext.prebid.meta.adaptercode, etc.}],
  "cur": "USD",
  "ext": {"responsetimemillis": {"kobler": "{{ kobler.response_time_ms }}"}, ...}
}
```

### C.6 IT fixture checks (mirrors SKILL.md Workflow §IT Fixture Changed)

1. **Filename pattern**: `test-{bidder|scenario}-{request,response,auction-request,auction-response}.json` exactly. **FAIL** on mismatch.
2. **Bidder-id consistency**: `imp[].ext.bidder.{property}` block keys MUST match the schema's `properties`. `imp[].ext.{x}` in `test-{x}-bid-request.json` is the OUTBOUND key — distinct from the inbound `imp[].ext.bidder` key.
3. **Currency**: `cur: ["USD"]` is canonical. Non-USD requires CurrencyConversionService injection — cross-skill nudge to `bidder-class-pr-review`.
4. **`impid` linkage**: every `seatbid[].bid[].impid` in `bid-response` MUST match the corresponding `imp[].id` in `bid-request`. **FAIL** on mismatch.
5. **F-new-49 trailing whitespace** before `]`: Lombok-template emit defect. **INFO** (not CI-blocking; reviewers prefer clean JSON).
6. **F-new-52 typed-config interaction**: when the bidder has `{X}BidderConfigurationProperties.java` (Rule 35) AND new IT fixtures are added, verify the IT class's `setUp()` injects the typed subclass. Cross-skill nudge to `bidder-class-pr-review`. **INFO**.
7. **2-space indentation**: dominant pattern in `it/openrtb2/`. Tabs or 4-space are non-canonical. **INFO**.
8. **Scenario completeness (Rule 36)**: when a new scenario is added, ALL 4 files must be present. Partial scenario (e.g., only `bid-request` added) is **FAIL**.
9. **Cross-skill: orphan fixture**: if a fixture file is added but `{X}Test.java` has no matching `@Test` method referencing it, surface to `bidder-class-pr-review`.

---

## Part D — Cross-language symmetry rules

Per port-translation Rule 38 (byte-fidelity for `bidder-params.json`):

### D.1 Rule 38 byte-equality

The `static/bidder-params/{x}.json` file MUST be byte-identical between Go and Java (modulo trailing newline). The orchestrator's `--- PRIOR SOURCE SPEC COMPARISON ---` block carries the Go-side `bidder_params_sha256`; the Java-side SHA comes from either the PR's `head_sha` (if `status=modified`) or the existing classpath file.

| Outcome | Action |
|---|---|
| Go SHA == Java SHA | No fidelity issue. Rule 38 holds. Suppress `info` entries about JSON schema bytes. |
| SHA mismatch | **WARN** + diff the schemas. Identify the diverging property + category (`minLength: 1` missing, `required[]` differs, `additionalProperties` differs, `pattern` differs, etc.). |

### D.2 Dual-spec assertion `severity: fail` elevation

If `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` exists AND declares the diverging field with `severity: fail`, ELEVATE the finding from **WARN** to **URGENT**.

### D.3 The canonical aax case

The reference `severity: fail` dual-spec is at `cross-language-pairs/aax.dual-spec-assertions.yaml`. The Java schema OMITS the `minLength: 1` constraint on `cid` and `crid` that the Go schema enforces:

```json
// Go static/bidder-params/aax.json:
"cid":  { "type": "string", "minLength": 1, "description": "..." }
"crid": { "type": "string", "minLength": 1, "description": "..." }

// Java src/main/resources/static/bidder-params/aax.json (the canonical divergence):
"cid":  { "type": "string", "description": "..." }
"crid": { "type": "string", "description": "..." }
```

Both files declare `required: [cid, crid]`. A publisher request with `imp.ext.bidder = {"cid": "", "crid": ""}` will be:

- **REJECTED** by Go (Go's validator fails on `minLength: 1`)
- **ACCEPTED** by Java (no `minLength` constraint, only presence required)

This is a real validation-behavior divergence — port-fidelity bug. The dual-spec records `severity: fail` and recommends:

> Add `"minLength": 1` to both `cid` and `crid` properties in the Java file at `src/main/resources/static/bidder-params/aax.json`. This is a one-line change that restores semantic parity.

When reviewing an aax PR (or any PR that introduces a similar omission), this skill emits:

```
[urgent] src/main/resources/static/bidder-params/{x}.json — PRIOR-SOURCE-SPEC dual-spec assertion declares this divergence as severity:fail.
  Field: {property}
  Java behavior: accepts empty string; Go rejects with minLength:1.
  Upstream recommendation: add "minLength": 1 to restore Rule 38 + R5 semantic parity.
  Severity: urgent — port-fidelity bug confirmed by canonical dual-spec assertion.
```

### D.4 Other Rule-38 cases beyond aax

The orchestrator's `--- PRIOR SOURCE SPEC COMPARISON ---` block reports byte-SHA mismatches for any pair. When no dual-spec exists (or when the dual-spec records `severity: warn` / `pass`), the finding remains **WARN** — the PR description should explain why the divergence is intentional.

Common categories of legitimate Rule-38 divergence:

| Category | Action |
|---|---|
| Whitespace / trailing newline only | **INFO** — cosmetic, no action |
| Description string formatting differs | **INFO** — descriptions are documentation, not behavior |
| One side has `additionalProperties: false`, the other omits | **WARN** — semantic divergence; check intent |
| Required-set differs | **WARN** — semantic divergence; check intent |
| Constraint differs (`minLength`, `maximum`, etc.) | **WARN**; elevate to **URGENT** if dual-spec `severity: fail` |

### D.5 Reviewer's cross-language diffing technique

When the orchestrator does NOT provide `--- PRIOR SOURCE SPEC COMPARISON ---` but Rule 38 verification is needed:

```bash
# Fetch both sides at the same SHA when possible (best fidelity check)
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server/master/static/bidder-params/{x}.json" > /tmp/go.json
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/{head_sha}/src/main/resources/static/bidder-params/{x}.json" > /tmp/java.json
diff /tmp/go.json /tmp/java.json
```

Note that the two repos do not have synchronized SHAs — Rule 38 byte-fidelity is best verified by content diff, not by SHA equality of repo trees.

---

## Part E — Reserved OpenRTB fields (must NOT be bidder params)

Same list as Go-side. These standard OpenRTB 2.x fields must not be duplicated as bidder-specific parameters:

| Field | Standard path | Why not a bidder param |
|---|---|---|
| Bid floor | `imp.bidfloor` / `ext.prebid.floors` | PBS handles floor management |
| Supply chain | `source.ext.schain` | Standard OpenRTB 2.5+ |
| Video params | `imp.video.*` | Standard OpenRTB 2.x |
| First-party data | `imp.ext.data`, `site.ext.data`, `user.ext.data` | PBS first-party data paths |
| GDPR consent | `regs.ext.gdpr`, `user.ext.consent` | Standard privacy path |
| US Privacy | `regs.ext.us_privacy` | Standard privacy path |
| COPPA | `regs.coppa` | Standard OpenRTB 2.x |
| GPP | `regs.gpp`, `regs.gpp_sid` | Standard OpenRTB 2.6 |
| Referrer | `site.page`, `site.ref` | Standard OpenRTB 2.x |

Reserved extension keys in `imp.ext.prebid`: `context`, `data` (first-party data), `gpid`, `skadn` (Apple SKAdNetwork), `tid`, `prebid`, `ae`, `igs` (PAAPI).

For **new** properties that duplicate a reserved OpenRTB field, **FAIL**. For existing properties being modified, **WARN** (the field is already established and removal would break publisher integrations).

---

## Part F — Alias behavior (BidderParamValidator fallback)

When a bidder is an alias (its parent's `bidder-config/{parent}.yaml` declares `aliases: { {alias}: ... }`), the Java schema validator falls back to the parent's schema via `BidderParamValidator.createSchemaNode`:

```java
private static JsonNode createSchemaNode(BidderCatalog bidderCatalog, ...) {
    try {
        return createSchemaNode(schemaDirectory, bidder, mapper);
    } catch (IllegalArgumentException e) {
        final String parentBidder = bidderCatalog.bidderInfoByName(bidder).getAliasOf();
        if (parentBidder != null) {
            return createSchemaNode(schemaDirectory, parentBidder, mapper);
        }
        throw e;
    }
}
```

Implications:

- Alias adapters MUST NOT have their own `static/bidder-params/{alias}.json` file — the fallback inherits from the parent.
- Alias adapters MUST NOT have their own `ExtImp{Alias}.java` file — the parent's `ExtImp{Parent}` is reused (Jackson resolves it via the parent's POJO at the catalog level).
- Alias adapters DO have their own IT class (`{Alias}Test.java`) per Java convention — that's how Java alias coverage is structured (no per-alias YAML). The IT fixture set may or may not exist (depends on whether the alias has its own scenarios).

If any of `bidder-params/{alias}.json` or `ExtImp{Alias}.java` exist for a known alias, flag as suspicious — the schema/POJO should inherit. **FAIL**.

Cross-skill: alias-vs-parent identity check is owned by `bidder-config-pr-review` (which reads the parent's YAML to determine alias status).

---

## Part G — Cross-file consistency reference

When multiple file types changed in the same PR (schema + POJO + fixtures), verify:

| Change in | Implied change in | Severity if absent |
|---|---|---|
| schema `properties` (added) | POJO field added | **FAIL** |
| schema `properties` (added) | IT fixture exercises the property | **WARN** |
| schema `properties` (removed) | POJO field removed | **WARN** (orphan field unused) |
| schema `properties` (removed) | IT fixture updated | **WARN** |
| schema `required[]` changed | POJO field type may not change (Java boxed types nullable regardless) | tolerated |
| schema `required[]` changed | IT fixture updated for new presence semantics | **WARN** |
| schema `minLength`/`enum`/`pattern`/`maximum` changed | POJO unchanged | tolerated |
| schema `minLength`/`enum`/`pattern`/`maximum` changed | IT fixture may need update | tolerated |
| POJO field added | schema `properties` updated | **FAIL** (otherwise field is dead code) |
| POJO field added | IT fixture exercises the field | **WARN** |
| Helper proto added | adapter code (`{X}Bidder.java`) references it | **INFO** + cross-skill nudge to `bidder-class-pr-review` |
| IT fixture added | `{X}Test.java` references it via `@Test` method | **INFO** + cross-skill nudge |

Bidder-name consistency: filename slug MUST match across all 3 file types — `{bidder}.json`, `ExtImp{Bidder}.java` under `request/{bidder}/`, fixtures under `it/openrtb2/{bidder}/test-{bidder}-*.json`. **FAIL** on mismatch.

---

## Sources

- `prebid/prebid-server-java` master @ SHA `a1fe64e123d6` (verified 2026-05-04)
- `src/main/java/org/prebid/server/validation/BidderParamValidator.java` (validation runtime path)
- `src/main/resources/static/bidder-params/{aax,adverxo,kobler}.json` (sample schemas)
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{adverxo,appnexus,ix,kobler,thetradedesk}/ExtImp{X}.java` (sample POJOs)
- `src/test/resources/org/prebid/server/it/openrtb2/kobler/` (sample 4-file IT fixture set)
- `cross-language-pairs/aax.dual-spec-assertions.yaml` (canonical `severity: fail` dual-spec)
- `../../shared/framework-utilities-java.md` §2 (Lombok), §6 (mvn-checkstyle)
- `prebid-server-go/review/skills/bidder-params-pr-review/references/params-type-index.md` (Go-side companion for Rule 38 / Rule 9 symmetry)
- `prebid-server-go/read/skills/shared/port-translation-rules.yaml` (Rules 9, 36, 38)
