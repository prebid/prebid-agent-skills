# Proto POJO Patterns (Java)

Detail-heavy reference for Java-side `ExtImp{Xyz}` and helper-proto class extraction. Consumed by [SKILL.md](../SKILL.md) Step 7 (`ext_pojo_construction.*`) and Step 2 (`bidder_class.helper_classes_in_proto[]` + `bidder_class.parameterized_request_type`). Cross-language schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md#ext_pojo_construction](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md#ext_pojo_construction).

This file documents:

1. The standard `@Value @Builder @Jacksonized` pattern + framework variants.
2. Jackson annotations: `@JsonProperty`, `@JsonAlias`, `@JsonDeserialize`, `@JsonIgnore`.
3. `FlexibleExtension` base class for `@JsonAnyGetter`/`@JsonAnySetter` patterns.
4. Custom deserializer detection rules (where the branching happens).
5. Field-type detection (`Long`, `String`, `JsonNode`, `ExtRequest`, `ObjectNode`, `BigDecimal`, etc.).
6. `Bidder<T>` generic parameterization for custom request payloads.
7. Helper proto co-location rules (`proto/openrtb/ext/request/{xyz}/`).

---

## The standard ExtImp pattern

The canonical `ExtImp{Xyz}` POJO uses Lombok's `@Value @Builder @Jacksonized`:

```java
package org.prebid.server.proto.openrtb.ext.request.appnexus;

@Value(staticConstructor = "of")
public class ExtImpAppnexus {

    @JsonProperty("placement_id")
    Integer placementId;

    @JsonProperty("invCode")
    String invCode;

    @JsonProperty("member")
    String member;

    @JsonAlias({"keywords", "keyword"})
    JsonNode keywords;

    Integer reserve;
}
```

### Class-level Lombok annotations

| Annotation | Effect | `framework_choice` value |
|---|---|---|
| `@Value @Builder` | Immutable POJO with builder; generates `getX()` accessors. The default Java pattern. | `lombok-value-builder` |
| `@Value @Builder @Jacksonized` | Same as above + Jackson can use the builder for deserialization. Modern preferred form. | `lombok-value-builder` |
| `@Value(staticConstructor = "of")` | Immutable POJO with `Xyz.of(...)` factory; no builder. Kobler's choice. | `lombok-value-staticconstructor` |
| `@Data @NoArgsConstructor` | Mutable POJO. Rare for ExtImp; common for ConfigurationProperties subclasses. | `lombok-data` |

### Detection rules

1. Read the class declaration.
2. Look for the FIRST class-level Lombok annotation in this priority order:
   - `@Value(staticConstructor = "of")` → `lombok-value-staticconstructor`.
   - `@Value @Builder` (with or without `@Jacksonized`) → `lombok-value-builder`.
   - `@Value` alone (no `@Builder`) → `lombok-value-staticconstructor` (the default factory in `@Value`).
   - `@Data` → `lombok-data`.
3. If the class extends `FlexibleExtension`, set `flexible_extension_used: true` (still record the framework_choice from above).

The `go-struct` value of `framework_choice` is Go-only and never set on Java specs.

---

## Jackson annotations to recognize

### `@JsonProperty("name")`

Field-level. Maps the Java field name to a JSON key. The most common annotation; appears on virtually every field.

```java
@JsonProperty("placement_id")
Integer placementId;
```

In the spec's `params.ext_struct.fields[]`, record `json_tag: placement_id` (the JSON key, not the Java name).

### `@JsonAlias({"a", "b", "c"})`

Field-level. Adds alternative JSON keys for compatibility — Jackson accepts any of the listed keys during deserialization. Used for legacy field-name compatibility.

```java
@JsonAlias({"keywords", "keyword"})
JsonNode keywords;
```

When ANY field on the class has `@JsonAlias`, set `ext_pojo_construction.custom_unmarshal.kind: jackson-jsonalias-only` UNLESS a full `@JsonDeserialize` is also present (which takes precedence). Set `accepts_shapes[]` based on the field types involved.

In the spec's `params.schema_interpretation.combinators_used[]`, add `json-aliases-present` (informational).

### `@JsonDeserialize(using = XyzDeserializer.class)`

Field-level OR class-level. Indicates a custom `JsonDeserializer<T>` class handles deserialization.

```java
@JsonDeserialize(using = AppnexusKeywordsDeserializer.class)
JsonNode keywords;
```

When present, set `ext_pojo_construction.custom_unmarshal.kind: jackson-jsondeserialize` and `where_branched: jsondeserializer-class`. The deserializer class is a separate file (role: `deserializer`) — the inputs to the SKILL include it.

Inside the deserializer, the typical pattern is:

```java
public class AppnexusKeywordsDeserializer extends JsonDeserializer<JsonNode> {
    @Override
    public JsonNode deserialize(JsonParser p, DeserializationContext ctxt) throws IOException {
        final JsonNode node = p.readValueAsTree();
        if (node.isArray()) { /* handle array form */ }
        if (node.isObject()) { /* handle object form */ }
        if (node.isTextual()) { /* handle string form */ }
        return node;
    }
}
```

Populate `accepts_shapes[]` from the `is*()` checks (`array, object, textual` → `[array, object, string]`).

### `@JsonIgnore`

Field-level. Excludes the field from JSON serialization/deserialization. Rare on `ExtImp` POJOs but appears on helper proto classes for transient fields. Record the field but flag with `notes: ["@JsonIgnore"]`.

### `@JsonInclude(JsonInclude.Include.NON_NULL)`

Class-level OR field-level. Suppresses null-valued fields during serialization. Java's equivalent of Go's `omitempty`. When present at class level, set `omitempty: true` on every field (unless individually overridden).

### `@JsonRawValue`

Field-level. The field's String value is emitted verbatim as JSON (no quoting). Used by Mediasquare's `MediasquareCode` to pass through JSON fragments.

---

## FlexibleExtension base class

The framework provides `FlexibleExtension` as a base class for ext POJOs that need to preserve unknown JSON fields:

```java
package org.prebid.server.proto.openrtb.ext;

public abstract class FlexibleExtension {

    @JsonAnyGetter
    public Map<String, Object> getProperties() { ... }

    @JsonAnySetter
    public void addProperty(String key, Object value) { ... }
}
```

When an `ExtImp{Xyz}` extends this base (e.g., Appnexus's `ExtImpAppnexus extends FlexibleExtension`), unknown JSON fields are preserved in a `properties` map rather than dropped.

### Detection rules

1. Read the class declaration and inheritance clause (`extends FlexibleExtension`).
2. Set `ext_pojo_construction.flexible_extension_used: true`.
3. The `framework_choice` is determined independently (Lombok annotations as above).
4. When the bidder mutates the extension via `fillExtension(...)` (a `FlexibleExtension` helper), set `mutation.java_idiom: flexible-extension-fillExtension` (this is rare; `lombok-tobuilder` is the typical idiom).

---

## Custom deserializer detection — the `where_branched` field

The `ext_pojo_construction.custom_unmarshal.where_branched` field captures WHERE the runtime branching happens. The three possible values:

| Value | When | Example |
|---|---|---|
| `bidder-class` | The branching happens inside the bidder class itself (e.g., the bidder reads a `JsonNode` and checks `node.isObject()` vs `node.isArray()` before processing). Common for ad-hoc handling of polymorphic params. | Appnexus keywords field (the bidder class reads keywords into a `JsonNode` and branches at processing time). |
| `jsondeserializer-class` | The branching happens inside a separate `JsonDeserializer<T>` class (file role: `deserializer`). The bidder class never sees the polymorphism. | `AppnexusKeywordsDeserializer` (when one is declared). |
| `type-method` | The branching happens inside an `UnmarshalJSON`-style method on the type itself. Rare in Java; this is more common in Go. | Hand-rolled `@JsonCreator` constructor doing branch logic. |
| `null` | When `kind: none` (no custom unmarshal). | Most adapters. |

### Decision tree

For each ExtImp class:

1. Does any field have `@JsonDeserialize(using = X.class)`? → `kind: jackson-jsondeserialize`, `where_branched: jsondeserializer-class`.
2. Does any field have `@JsonAlias` ONLY (no full deserializer)? → `kind: jackson-jsonalias-only`, `where_branched: bidder-class` (the bidder reads the field via the alias).
3. Does the class have a `@JsonCreator` constructor with branching logic? → `kind: custom`, `where_branched: type-method`. REQUIRES a quirk.
4. Does the bidder class read a polymorphic `JsonNode` field and branch on `isObject()`/`isArray()` at processing time? → `kind: runtime-isobject-isarray-branching`, `where_branched: bidder-class`.
5. Otherwise: `kind: none`, `where_branched: null`.

### Worked example — Appnexus keywords

The `keywords` field accepts THREE shapes:

- A string (legacy form): `"keywords": "key1=v1,key2=v2"`.
- An object (modern map form): `"keywords": {"key1": "v1", "key2": "v2"}`.
- An array (alternate form): `"keywords": [{"key": "key1", "value": "v1"}]`.

The Java side stores it as a `JsonNode` and the bidder class branches at processing time:

```java
private List<String> extractKeywords(JsonNode keywordsNode) {
    if (keywordsNode == null) { return Collections.emptyList(); }
    if (keywordsNode.isObject()) { /* parse map form */ }
    if (keywordsNode.isArray())  { /* parse list form */ }
    if (keywordsNode.isTextual()) { /* parse string form */ }
    return Collections.emptyList();
}
```

Spec emits:

```yaml
ext_pojo_construction:
  framework_choice: lombok-value-builder
  flexible_extension_used: false               # Or true if extends FlexibleExtension.
  custom_unmarshal:
    kind: runtime-isobject-isarray-branching
    accepts_shapes: [object, array, string]
    where_branched: bidder-class
```

---

## Field-type detection

Java field types in `ExtImp` POJOs map to spec `type_native` values:

| Java type | `type_native` | Notes |
|---|---|---|
| `Boolean` (boxed) | `Boolean` | `@JsonProperty` may map to `"test"`. |
| `boolean` (primitive) | `boolean` | Rare; boxed is preferred. |
| `Integer` (boxed) | `Integer` | Standard for nullable integer fields. |
| `Long` (boxed) | `Long` | Used for IDs that exceed Integer range. |
| `String` | `String` | Standard for text fields. |
| `BigDecimal` | `BigDecimal` | Standard for currency / bidfloor. |
| `JsonNode` | `JsonNode` | Polymorphic; signals custom unmarshal. |
| `ObjectNode` | `ObjectNode` | Specifically requires JSON object shape. |
| `ArrayNode` | `ArrayNode` | Specifically requires JSON array shape. |
| `List<String>` | `List<String>` | Common for tag/category lists. |
| `Map<String, String>` | `Map<String, String>` | Common for free-form key/value maps. |
| `ExtRequest` | `ExtRequest` | Framework type for extending OpenRTB request. |
| `ExtBidPrebid` | `ExtBidPrebid` | Framework type for `bid.ext.prebid`. |

When a field has type `JsonNode` or `ObjectNode`, the field is polymorphic and `ext_pojo_construction.custom_unmarshal.kind` is likely non-`none`.

The `omitempty` field on each spec field maps to the `@JsonInclude(NON_NULL)` annotation:

- `omitempty: true` when class-level `@JsonInclude(JsonInclude.Include.NON_NULL)` is present OR field-level overrides apply.
- `omitempty: false` otherwise.

---

## `Bidder<T>` generic parameterization (edge case #28)

The bidder class implements `Bidder<T>`. The default `T` is `BidRequest` (the OpenRTB type). Some adapters use a custom type:

| Adapter | `Bidder<T>` value | Custom request POJO |
|---|---|---|
| Most adapters (Kobler, Optidigital, Appnexus, etc.) | `Bidder<BidRequest>` | n/a — uses OpenRTB shape. |
| Mediasquare | `Bidder<MediasquareRequest>` | `proto/openrtb/ext/request/mediasquare/MediasquareRequest.java` |
| Huaweiads | `Bidder<HuaweiAdsRequest>` | `proto/openrtb/ext/request/huaweiads/HuaweiAdsRequest.java` |

### Detection rules

1. Read the class declaration: `public class XyzBidder implements Bidder<T> { ... }`.
2. Extract `T`. The default `BidRequest` does NOT need quirk emission; ANY non-`BidRequest` value DOES.
3. Set `bidder_class.parameterized_request_type` to the verbatim type name.
4. When non-default, the corresponding custom request POJO MUST exist in `proto/openrtb/ext/request/{xyz}/`. List it under `bidder_class.helper_classes_in_proto[]`.
5. Set `code.make_requests.request_body.kind: custom` and `custom_body_type: <type-name>`.

For the rare adapters that ALSO parameterize a custom response (rare; Mediasquare's response is parsed via `mapper.decodeValue(..., MediasquareResponse.class)` rather than via `Bidder<T>`), set `bidder_class.parameterized_response_type` accordingly.

### Multi-class proto-request-response split (edge case from PR #4031)

When a Java port preserves a Go-side multi-file split, the `proto/openrtb/ext/request/{xyz}/` package contains multiple classes:

- `MediasquareRequest.java` — top-level request payload.
- `MediasquareCode.java` — per-imp code subobject.
- `MediasquareResponse.java` — top-level response payload.
- `MediasquareBid.java` — per-bid response item.
- `ExtImpMediasquare.java` — the params POJO.

List ALL of them under `bidder_class.helper_classes_in_proto[]`. The pattern tag for the reference list is `multi-class-proto-request-response-split`.

---

## Helper proto co-location rules

Helper proto classes live in `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/`. The package name is always lowercase {xyz}. The folder may contain:

- `ExtImp{Xyz}.java` — the params POJO. Always present unless edge case `free-form-imp-ext-no-proto` (Ogury — Edge case in Pattern Index).
- Custom request POJOs (Mediasquare, Huaweiads).
- Custom response POJOs (Mediasquare).
- Custom deserializer classes (`{Xyz}KeywordsDeserializer.java`).
- Helper sub-types (sub-objects within the request/response).

### Detection rules

1. Read every `*.java` file in the folder.
2. The file with name matching `ExtImp{Xyz}.java` is the canonical params POJO.
3. Other files are helper proto classes — list under `bidder_class.helper_classes_in_proto[]`.
4. A file ending in `Deserializer.java` is the custom deserializer. Tag it with role `deserializer` (separate from `proto-helper`).

### Co-located in `bidder/{xyz}/` (NOT proto)

Some adapters co-locate small helper classes in `bidder/{xyz}/` next to the bidder class:

| Adapter | Helper |
|---|---|
| Mediasquare | `MediasquareUtil.java` (parsing helpers) |
| Kueez | `KueezExtractor.java` (response extraction) |
| (none) | (most adapters keep bidder/ single-file) |

These go under `bidder_class.helper_classes_co_located[]`. Do NOT confuse with helper proto classes — co-located helpers are typically static utility classes; helper proto classes are DTOs.

### Multi-file detection

Set `code.file_layout.kind: multi-file` ONLY when more than one bidder-package `*.java` file exists (excluding `proto/`, `spring/`, and tests). The Mediasquare adapter is the canonical multi-file example.

---

## Worked example — Kobler ExtImpKobler

```java
package org.prebid.server.proto.openrtb.ext.request.kobler;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Value;

@Value(staticConstructor = "of")
public class ExtImpKobler {
    Boolean test;
}
```

Spec emits (matches Kobler golden lines 83-94):

```yaml
ext_struct:
  package: org.prebid.server.proto.openrtb.ext.request.kobler
  file: src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/ExtImpKobler.java
  type_name: ExtImpKobler
  fields:
    - name: test
      json_tag: test
      type_native: Boolean
      omitempty: false
      notes:
        - "@Value(staticConstructor=of)"
  custom_unmarshal: false
  custom_unmarshal_accepts: []
```

And:

```yaml
ext_pojo_construction:
  framework_choice: lombok-value-staticconstructor
  flexible_extension_used: false
  custom_unmarshal:
    kind: none
    accepts_shapes: []
    where_branched: null
```

The `notes: ["@Value(staticConstructor=of)"]` entry on the field is informational — the `@Value(staticConstructor)` is class-level, not field-level, but the note flags the class's framework_choice as a porter hint.

---

## Sources

- Plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md`.
- Schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md).
- Taxonomy: [../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md](../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md) — `ext_pojo_construction.framework_choice` and `custom_unmarshal.kind` enumerations.
- Java reference PR list: [../../../../references/new-bid-adapter-prs.md](../../../../references/new-bid-adapter-prs.md) — see Pattern Index tags `custom-typed-payload-Bidder-T`, `multi-class-proto-request-response-split`, `free-form-imp-ext-no-proto`, `multi-file-go-preserved`.
- Golden spec: [../../../test-fixtures/kobler.golden.spec.yaml](../../../test-fixtures/kobler.golden.spec.yaml) — `ext_struct:` (lines 83–95), `ext_pojo_construction:` (lines 325–331), `bidder_class.helper_classes_in_proto:` (line 316).
- Phase 2 reconnaissance findings (in plan): `Bidder<T>` generic observed on Mediasquare (`MediasquareRequest`) and Huaweiads (`HuaweiAdsRequest`); `runtime-isobject-isarray-branching` observed on Appnexus keywords field; `lombok-value-staticconstructor` observed on Kobler.
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
