# Behavior Taxonomy (canonical enumerations)

Enumerated values for behavioral fields in the Adapter Specification. Each enumerated field has a default, an ordered or unordered set of allowed values, a `custom` fallback, and (for the rules-list patterns) `applied_in_order: true` semantics. The `custom` value REQUIRES a corresponding `quirks` entry — un-classified behavior cannot silently flow through. Defaults are emitted only when structural evidence affirmatively matches them; absence of evidence emits no default.

This file is the source-of-truth for behavioral enums consumed by all 8 reader skills (4 Go + 4 Java) and the future write/port skills. Two specs for the same bidder produced from each language MUST agree on cross-language behavioral fields and MAY differ only on per-language idiom siblings (`go_idiom`, `java_idiom`, `mechanism_go`, `mechanism_java`).

---

## How to read this taxonomy

1. **Default emission rule.** An enumerated field's default is emitted only when the structural evidence affirmatively matches the default. For example, `make_requests.batching.rules[]` defaults to `[{ kind: single-batched }]` only when the reader confirms exactly one HTTP request is constructed and all imps are passed in it. If the reader cannot confirm, it emits no rules and surfaces an `incomplete-classification` quirk.

2. **Custom-with-quirks contract.** Any enumerated value of `custom` REQUIRES a `quirks[]` entry referencing the same field with a free-text summary. Readers that emit `custom` without a paired quirk fail validation rule R3.

3. **Rules-list semantics.** Rules-list fields (`batching.rules[]`, `bid_type_resolution.method_chain[]`) carry `applied_in_order: true`. Composability is allowed — Appnexus emits `[max-imps-per-request: 10, pod-grouping]`; Rubicon emits `[format-split, deals-split]`. Each rule MAY carry rule-specific fields (e.g., `max` on `max-imps-per-request`).

4. **Per-language idiom siblings.** Cross-language enumerated kinds live at the parent level (e.g., `mutation.entity_strategies`); the language-specific idiom lives under a sibling key (`mutation.go_idiom`, `mutation.java_idiom`). A spec emits BOTH the cross-language kind AND the relevant idiom for its source language.

---

## `code.make_requests.batching.rules[]`

Refactored from scalar enum (`batching.kind`) to ordered list. Rules are applied in order; each rule may carry rule-specific fields.

| Rule kind | When it fires | Carries | Examples (bidder) | Composability |
|---|---|---|---|---|
| `single-batched` | One HTTP request, all imps passed in. Default if the reader confirms a single `RequestData` carrying `len(request.Imp)` imps. | none | kobler, optidigital | Terminal — does not compose with split rules. |
| `per-imp` | One HTTP request per imp. Loop in MakeRequests/makeHttpRequests producing N RequestData. | none | adkernel (per-imp split for some param combinations) | Terminal. |
| `max-imps-per-request` | Imps split into batches of size N. | `max: <int>` | appnexus (`max: 10`) | Composes with `pod-grouping` (Appnexus does both). |
| `format-split` | One request per media type on multi-format imps. | `formats: [banner, video, native, audio]` | rubicon (multi-format split), adkernel (multi-format) | Composes with `deals-split`. |
| `deals-split` | One request per deal line item on imps with deals. | `deal_field: imp.pmp.deals[].id` | rubicon | Composes with `format-split`. |
| `pod-grouping` | Group imps by `imp.id` prefix before underscore (video adpod). | `key: imp.id-prefix-before-underscore` | appnexus video adpod | Composes with `max-imps-per-request`. |
| `imp-flatten-aggregate` | Multiple imps coalesce into one custom request (the bidder's request shape is not OpenRTB-shaped). | `custom_body_type: <type>` | mediasquare (`MediasquareRequest`) | Terminal. |
| `filtered-subset` | Filter imps by bidder-specific predicate before batching. | `predicate: <free-text>` | ogury (filters imps where `imp.ext.bidder` is non-null) | Composes with `single-batched`, `per-imp`. |
| `grouped-by-key` | Group imps by an arbitrary key (publisher ID, account ID). | `key: <field-path>`, `group_id_construction: <expr>` | huaweiads (group by token), 33across (group by accountId) | Composes with `max-imps-per-request`. |
| `custom` | Anything not captured above. REQUIRES `quirks` entry. | n/a | n/a | n/a |

**Default**: `[{ kind: single-batched }]` when the reader observes one RequestData carrying all imps and no slicing logic.

---

## `code.make_bids.bid_type_resolution.method_chain[]`

Refactored from scalar enum (`method`) to ordered chain. Each step has `{ method, field?, hardcoded_value?, fallback_action }`. `fallback_action` is one of:

- `next` — try the next step in the chain.
- `return-default` — return `default_value` and stop.
- `throw` — emit a `BadServerResponse` error and stop.

> **Cross-reference**: The full `errortypes.*` registry (BadInput, BadServerResponse, FailedToMarshal, FailedToUnmarshal, etc.) is documented at [`../../../review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md) (Error-Type Taxonomy section).

Plus top-level `default_value` (default `banner`) and `multi_format_detection: { strict | lenient | none }`.

Per-step schema:

```yaml
method_chain:
  - method: <enum>           # by-imp-mediatype | by-bid-mtype | by-bid-ext-typed-field | by-imp-id-suffix | imp-prefix-lookup | by-response-payload-shape | hardcoded | custom
    field: <string>          # OPTIONAL. Required when method=by-bid-ext-typed-field. Path within bid.ext (e.g., "bid.ext.prebid.type", "bid.ext.appnexus.bidAdType").
    hardcoded_value: <enum>  # OPTIONAL. Required when method=hardcoded. The fixed BidType returned (e.g., BidTypeBanner).
    fallback_action: next | return-default | throw
default_value: <BidType>     # OPTIONAL. Used when fallback_action=return-default on the last step.
multi_format_detection: strict | lenient | none
```

| Method | What it does | Example (bidder) |
|---|---|---|
| `by-imp-mediatype` | Resolve from the corresponding `imp` (matched by `bid.impid`) — checks which of `imp.banner / imp.video / imp.native / imp.audio` is non-nil. Default first step. | optidigital, adagio |
| `by-bid-mtype` | Resolve from `bid.mtype` (canonical OpenRTB 2.6 field — `1=banner, 2=video, 3=audio, 4=native`). | seedtag, kueez |
| `by-bid-ext-typed-field` | Look up `bid.ext.{path}` for a typed field (e.g., `bid.ext.prebid.type`, `bid.ext.appnexus.bidAdType`). | kobler (`bid.ext.prebid.type`), appnexus (`bid.ext.appnexus.bidAdType`) |
| `by-imp-id-suffix` | Parse a suffix on `imp.id` to disambiguate multi-format imps (e.g., `imp.id` ends in `_b` for banner, `_v` for video). | adkernel multi-format split |
| `imp-prefix-lookup` | Use a prefix on `imp.id` (typically before underscore) to look up the original imp. | appnexus video adpod (paired with pod-grouping batching rule) |
| `by-response-payload-shape` | Inspect the bid response payload structure (e.g., `bid.video != null` test). | mediasquare (custom response with `video` sub-object) |
| `hardcoded` | Always return a fixed media type. | optidigital (always banner) — note: even single-mediatype adapters typically use `by-imp-mediatype`; `hardcoded` is rare |
| `custom` | Anything not captured. REQUIRES `quirks` entry. | n/a |

**Default**: `[{ method: by-imp-mediatype, fallback_action: throw }]` when the reader confirms the standard MType switch with no fallback.

**Examples of multi-step chains:**

- **Aax**: `[{ method: by-bid-ext-typed-field, fallback_action: next }, { method: by-imp-mediatype, fallback_action: next }, { method: throw }]` — three steps, strict multi-format detection.
- **Kobler**: `[{ method: by-bid-ext-typed-field, fallback_action: return-default }]` — one step with `default_value: banner`. The Go and Java specs MUST agree here.
- **Generic openrtb**: `[{ method: by-bid-mtype, fallback_action: return-default }]` with `default_value: banner`.

`multi_format_detection`:

- `strict` — when imp has multiple media types and bid lacks `mtype`/typed-ext, throw.
- `lenient` — fall back to default media type or first non-nil imp media type.
- `none` — adapter does not handle multi-format imps.

---

## `code.make_bids.http_status_handling.kind`

Splits HTTP-level status handling from application-level status handling. Note: this captures HOW the adapter checks HTTP status, NOT the application-layer body flag (handled below).

| Kind | What it means | Examples |
|---|---|---|
| `framework-default` | Java pattern — adapter relies on framework-default `HttpUtil.validateResponse`. Returns errors auto-wrapped in `BidderError.badServerResponse`. | most Java adapters |
| `framework-default-plus-empty-seatbid-shortcircuit` | Java pattern — framework-default plus an early `if (CollectionUtils.isEmpty(bidResponse.getSeatbid())) return Collections.emptyList();` check. | kobler (Java), optidigital (Java) |
| `custom-status-checks` | Adapter implements bespoke status checks (e.g., specific 4xx codes treated as no-bid). | adview |
| `canonical-go-helpers` | Go pattern — adapter uses `adapters.IsResponseStatusCodeNoContent(resp)` and `adapters.CheckResponseStatusCodeForErrors(resp)`. The recommended pattern. | optidigital (Go), most modern Go adapters |
| `legacy-raw-go` | Go pattern — adapter directly inspects `responseData.StatusCode == http.StatusNoContent` / `!= http.StatusOK`. Not yet migrated to canonical helpers. | kobler (Go) |
| `custom` | Anything not captured. REQUIRES `quirks` entry. | n/a |

**Default**: For Go, `canonical-go-helpers` if the canonical helpers are imported and called; `legacy-raw-go` if the adapter rolls its own status checks. For Java, `framework-default` if no override.

> **Cross-reference**: Go's canonical helpers `IsResponseStatusCodeNoContent` and `CheckResponseStatusCodeForErrors` are documented in [`../../../review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md) (Test Harness Contract section). The `legacy-raw-go` value flags adapters that pre-date these helpers and use direct `responseData.StatusCode == 204` checks instead.

---

## `code.make_bids.application_status_handling`

Captures application-layer status indicators that live IN the response body, distinct from HTTP status. Paired with `http_status_handling`; both fields are always present in a spec.

```yaml
application_status_handling:
  kind: none | retcode-field | custom-body-flag
  field: null               # Path into the response body, e.g., "retcode".
  success_codes: []         # E.g., [0, 200] for huaweiads.
  error_codes: []           # E.g., [400, 401, 403, 404, 500, 503] for huaweiads.
```

| Kind | What it means | Example |
|---|---|---|
| `none` | Adapter does not check an application-layer status field. | kobler, optidigital |
| `retcode-field` | Adapter checks a `retcode` (or similar) field in the response body. Pairs `field`, `success_codes`, `error_codes`. | huaweiads (`retcode` with success in {200} and errors in {400, 401, 403, 404, 500, 503}) |
| `custom-body-flag` | Adapter checks a non-standard body flag. REQUIRES `quirks` entry. | n/a |

**Default**: `{ kind: none }` when no body-status check is found.

---

## `code.make_requests.endpoint_resolution`

Split into `kind` (semantic, cross-language) + `mechanism_go` / `mechanism_java` (language-specific implementation).

### Kinds (semantic)

| Kind | What it means | Example |
|---|---|---|
| `static` | A literal URL with no substitution. | kueez (single-string endpoint) |
| `single-token-substitution` | One macro field substituted (e.g., `{{.AccountID}}`). | adagio |
| `multi-token-substitution` | Multiple macros substituted. | rubicon (`{{.AccountID}}` + `{{.ZoneID}}`) |
| `query-parameter-augmentation` | Endpoint URL has query params appended at request time (e.g., `?member_id=123`). | appnexus (`member_id`) |
| `runtime-region-selection` | Endpoint URL chosen from a runtime context (e.g., country code → region). | huaweiads |
| `deploy-time-token` | Endpoint URL has a non-Go-template placeholder substituted pre-deployment by the operator. Surfaces in `deploy_time_tokens[]`. | rubicon (`REGION` token) |
| `dev-prod-toggle` | Endpoint chosen between two literal URLs based on a request-time flag. | kobler (`testMode` flag toggles between endpoint and devEndpoint) |
| `custom` | Anything else. REQUIRES `quirks` entry. | n/a |

### Mechanisms (per-language implementation)

**Go:**

| Mechanism | When |
|---|---|
| `text/template` | Adapter parses a Go template at Builder time. |
| `macros.NewStringIndexBasedReplacer` | Adapter uses the canonical replacer helper. |
| `net/url` | Adapter constructs the URL via `url.URL` / `url.Values`. |
| `string-concat` | Adapter concatenates strings or uses `fmt.Sprintf`. |
| `null` | When no mechanism applies (Java-source spec). |

**Java:**

| Mechanism | When |
|---|---|
| `string-replace` | Adapter calls `endpoint.replace("{{.X}}", value)`. |
| `URIBuilder` | Adapter uses `org.apache.http.client.utils.URIBuilder`. |
| `custom-resolver-class` | Adapter uses a co-located resolver class (e.g., `RubiconUriBuilder`). |
| `null` | When no mechanism applies (Go-source spec). |

A spec emits `kind` always and the relevant `mechanism_*` for its source language; the other-language mechanism is null.

---

## `code.make_requests.mutation`

```yaml
mutation:
  mutates_request: bool
  entity_strategies:        # Map of entity name → strategy.
    Site: ...
    App: ...
    Source: ...
    Imp: ...
    Banner: ...
    Device: ...
    User: ...
    Cur: ...
  go_idiom: ...             # Sibling — populated only on Go-source specs.
  java_idiom: ...           # Sibling — populated only on Java-source specs.
```

### Cross-language `entity_strategies` values

| Strategy | What it means | Go example | Java example |
|---|---|---|---|
| `none` | Entity is unchanged. | n/a | n/a |
| `copy-then-mutate` | Make a shallow or deep copy, mutate the copy, swap pointer. | optidigital (`siteCopy := *site; siteCopy.X = ...; request.Site = &siteCopy`) | n/a — Java doesn't naturally use this. |
| `immutable-rebuild` | Use a builder pattern to produce a new instance. | n/a — Go doesn't naturally use this. | kobler (`device.toBuilder().ipv6(null).ip(null).build()`) |
| `in-place` | Mutate the entity directly via pointer/reference. | kobler Go (`device.IP = ""`) | n/a — Java POJOs are typically immutable. |
| `append-if-missing` | Append a value to a list if not already present (e.g., currency list). | kobler Go (`Cur = append(Cur, "USD")` if not present) | kobler Java (`new ArrayList<>(currencies); newCurrencies.add(DEFAULT)`) |

### Go idioms (`mutation.go_idiom`)

| Idiom | When |
|---|---|
| `ptrutil.Clone` | Adapter uses `ptrutil.Clone[T]` for deep-copy of pointer fields. Recommended for `Site`, `App`, `Publisher` mutations. |
| `shallow-copy` | Adapter dereferences a pointer to copy a value, mutates fields, then re-points. |
| `direct-pointer-mutation` | Adapter mutates through the pointer directly (mutates input). NOT recommended — flagged by reviewers. |
| `none` | Adapter does not mutate. |

### Java idioms (`mutation.java_idiom`)

| Idiom | When |
|---|---|
| `lombok-tobuilder` | Adapter uses `entity.toBuilder().field(value).build()` to produce a new immutable instance. Default Java pattern. |
| `flexible-extension-fillExtension` | Adapter uses `FlexibleExtension.fillExtension` to add fields to an extension while preserving unknowns. |
| `none` | Adapter does not mutate. |

---

## `code.make_requests.imp_ext_unmarshal`

```yaml
imp_ext_unmarshal:
  kind: standard-two-phase | direct | none | custom
  mechanism_go: jsonutil-two-phase | null
  mechanism_java: typeref-extprebid | typeref-custom-wrapper | direct-class | null
  target_type: openrtb_ext.ExtImp{Xyz} | ExtImp{Xyz}
  wrapper_type: null | <wrapper-class-name>
```

### Kinds (cross-language)

| Kind | What it means | Example |
|---|---|---|
| `standard-two-phase` | First unmarshal `imp.Ext` to a wrapper (`ExtImpBidder` Go / `ExtPrebid` Java), then unmarshal the inner `bidder` field to `ExtImp{Xyz}`. Default. | kobler |
| `direct` | Unmarshal `imp.Ext` directly to a custom wrapper class — the framework's `ExtImpBidder` is not used. | appnexus (uses `AppnexusExtImp` direct wrapper) |
| `none` | Adapter does not unmarshal `imp.ext` (no bidder-specific params). | ogury (no proto) |
| `custom` | Anything else. REQUIRES `quirks` entry. | n/a |

### Mechanisms (per-language)

**Go:**

- `jsonutil-two-phase` — the canonical pattern: `jsonutil.Unmarshal(imp.Ext, &bidderExt); jsonutil.Unmarshal(bidderExt.Bidder, &impExt)`.
- `null` — when `kind: direct` or `none` or on Java-source specs.

**Java:**

- `typeref-extprebid` — canonical: `new TypeReference<ExtPrebid<?, ExtImp{Xyz}>>(){}` then `mapper.convertValue(imp.getExt(), TYPE_REFERENCE).getBidder()`.
- `typeref-custom-wrapper` — uses a custom wrapper TypeReference (e.g., Appnexus `AppnexusExtImp`).
- `direct-class` — the params type itself is the deserialization target (no wrapper).
- `null` — when no mechanism applies.

`wrapper_type` is null for the standard case; populated with the class/struct name for the direct/custom-wrapper cases.

---

## `code.make_bids.currency_overwrite_safety`

| Value | What it means | Example |
|---|---|---|
| `guarded` | Adapter overwrites `bidResponse.Currency` only when conditions are met (e.g., currency matches request currency). | n/a — rare in master. |
| `unguarded` | Adapter overwrites `bidResponse.Currency` unconditionally (potential data loss). | n/a — flagged by reviewers, typically removed. |
| `unguarded-hardcoded` | Adapter sets `bidResponse.Currency` to a hardcoded literal (e.g., `"USD"`) regardless of upstream value. | aax (forced USD) |
| `passthrough-from-response` | Adapter sets `bidResponse.Currency = response.Cur` from the upstream response. Default-recommended. | kobler (both Go and Java) |
| `none` | Adapter does not set `bidResponse.Currency`. The framework defaults the currency. | optidigital |

**Default**: `none` when no `bidResponse.Currency = ...` assignment is found.

---

## `code.make_bids.bid_pointer_pattern`

Cross-language values plus per-language siblings for Go-specific iteration idioms.

### Cross-language (`bid_pointer_pattern`)

| Value | What it means | Example |
|---|---|---|
| `flatten-streams` | Java stream pipeline using `flatMap` to flatten seatBid → bid pairs. | kobler (Java) |
| `indexed-iteration` | Loop using indexed access (`for i := range slice` / `for (int i = 0; i < ...; i++)`). | kobler (Go) |
| `pointer-iteration` | Loop using value-pointer references (Go: `&seatBid.Bid[i]`). | optidigital (Go) |

### Go sibling (`bid_pointer_go_sibling`)

| Value | When |
|---|---|
| `indexed-seatbid` | Adapter ranges over `response.SeatBid` indexed and bids indexed. Idiom: `for i := range response.SeatBid { for j := range response.SeatBid[i].Bid { ... } }`. |
| `range-value-pointer` | Adapter ranges over values with pointer indexing. Idiom: `for _, seatBid := range response.SeatBid { for i := range seatBid.Bid { ... } }`. |
| `null` | On Java-source specs. |

A spec emits `bid_pointer_pattern` always; `bid_pointer_go_sibling` is populated only on Go-source specs.

---

## `tests` directory naming

### Go (`tests.go_directory_naming`)

| Value | What it means | Example |
|---|---|---|
| `canonical` | Test root is `<bidder>test/` with no separator (e.g., `koblertest/`). | kobler, optidigital |
| `legacy-test` | Test root is `<bidder>/test/` (separator). Older convention. | msft (`adapters/msft/test/`) |
| `custom` | Anything else. REQUIRES `quirks` entry. | msft (`adapters/msft/test-extrainfo/` co-existing with `test/`) |

### Java (`tests.java_it_folder_naming`)

| Value | What it means | Example |
|---|---|---|
| `canonical` | IT fixtures under `src/test/resources/org/prebid/server/it/openrtb2/<bidder>/` with 4-file split (`test-{name}-bid-request.json`, `...-bid-response.json`, `test-auction-{name}-request.json`, `...-response.json`). | most adapters |
| `suffix-augmented` | The IT folder name carries an extra suffix (e.g., `<bidder>-cache/` for cache-flow tests). | n/a — rare. |
| `multi-folder` | Multiple sibling folders for different test flows (auction vs AMP vs video). | rubicon |
| `custom` | Anything else. REQUIRES `quirks` entry. | n/a |

---

## `params.schema_interpretation.combinators_used[]`

Unordered set; emitted as a list.

| Value | What it means | Example |
|---|---|---|
| `oneOf` | Schema uses `oneOf` for mutually-exclusive variants. | rubicon (`accountId` either string or int) |
| `anyOf` | Schema uses `anyOf` for any-of variants. | n/a — rare. |
| `not` | Schema uses `not` to negate. | n/a — very rare. |
| `oneOf-of-oneOf` | Schema uses nested `oneOf` (compositional). | rare; surfaces in port-translation as a fidelity concern. |
| `json-aliases-present` | Informational — Java POJO carries `@JsonAlias({...})` indicating legacy field-name compatibility. | appnexus (Java) |

**Default**: empty list when no combinators are used.

---

## `ext_pojo_construction.framework_choice`

| Language | Value | When |
|---|---|---|
| Go | `go-struct` | Always — Go has only one POJO style. |
| Java | `lombok-value-builder` | Default Java pattern: `@Value @Builder` on `ExtImp{Xyz}`. |
| Java | `lombok-data` | Mutable POJO `@Data @NoArgsConstructor`. Rare for ExtImp. |
| Java | `lombok-value-staticconstructor` | `@Value(staticConstructor = "of")` — Kobler's choice. |

---

## `ext_pojo_construction.custom_unmarshal.kind`

| Value | What it means | Example |
|---|---|---|
| `none` | Default — framework handles unmarshal. | kobler |
| `go-unmarshaljson` | Go custom `func (X *Type) UnmarshalJSON(data []byte) error`. | appnexus (Go — keywords field accepts string/object/array) |
| `jackson-jsondeserialize` | Java `@JsonDeserialize(using = XyzDeserializer.class)` paired with a custom `JsonDeserializer<T>` class. | n/a in Kobler; rubicon (Java) |
| `jackson-jsonalias-only` | Java `@JsonAlias({...})` on individual fields only — no full deserializer. Used for legacy field-name compatibility. | appnexus (Java) |
| `runtime-isobject-isarray-branching` | Adapter branches at runtime on JSON shape (`isObject() vs isArray()`). | appnexus keywords field |
| `custom` | Anything else. REQUIRES `quirks` entry. | n/a |

Sibling field `where_branched`:

- `bidder-class` — the branching happens in the bidder class itself.
- `jsondeserializer-class` — branching in a separate JsonDeserializer.
- `type-method` — branching in an `UnmarshalJSON` method on the type.
- `null` — when `kind: none`.

---

## `headers_constructed.authentication_kind`

| Value | What it means | Example |
|---|---|---|
| `none` | No authentication header. | kobler, optidigital |
| `basic-auth` | HTTP Basic auth (base64-encoded `user:pass`). Pre-built in constructor. | rubicon (`Authorization: Basic ...`) |
| `bearer-token` | Bearer token in Authorization header. | n/a in master sample. |
| `hmac-digest` | HMAC-SHA256 of body, computed per-request. | huaweiads |
| `custom` | Anything else. REQUIRES `quirks` entry. | n/a |

`authentication_input` lists the config fields used to compute the auth value (e.g., `["XAPI.Username", "XAPI.Password"]` for Rubicon).

---

## `iab_category_storage.storage_kind`

| Value | What it means | Example |
|---|---|---|
| `yaml-inlined` | The IAB-category lookup map is inlined directly in `bidder-config/{xyz}.yaml`. Java-only pattern. | appnexus (Java) — 120-entry `iabCategories` map. |
| `go-data-table` | The lookup is a Go data file (e.g., `iab_categories.go`) co-located in the adapter directory. | msft (Go) |
| `dynamic-fetched` | The lookup is fetched at runtime from an upstream service. Rare. | n/a in master sample. |
| `none` | Adapter does not perform IAB-category lookup. | kobler, optidigital |

Companion fields:

- `yaml_field` — the YAML field name (e.g., `iab-categories`).
- `go_data_file` — the Go file path (e.g., `adapters/msft/iab_categories.go`).
- `table_size` — the number of entries in the table.
- `injection` — `constructor-arg` (table is passed into the bidder constructor) or `static-init` (table is a package-level var) or `null`.

---

## quirks `edge_case_taxon` (full registry)

The flat list of all known taxa, each grounded in Phase 2 findings. A `custom` value in any enumerated behavioral field requires a `quirks` entry; the `edge_case_taxon` field on the entry MUST be one of these:

| Taxon | Description | Surfaces in |
|---|---|---|
| `hardcoded-config-as-anti-pattern` | Adapter hardcodes a value that should live in YAML config. Canonical: Kobler `devBidderEndpoint` constant. | quirks |
| `json-key-style-mismatch` | JSON tag uses a different style than surrounding adapter. Canonical: msft `pubclick` vs `pub_click`. | quirks + ext_struct.fields[].notes |
| `port-fidelity-divergence` | Java port differs from Go source in load-bearing way. Canonical: Kobler currency-conversion bidRequest context. | quirks + cross_language.port_concerns |
| `bidder-constant-mismatch` | Test/builder references the wrong bidder constant. Canonical: kobler_test.go `BidderKargo`, params_test.go `BidderKrushmedia`. | quirks + provenance.warnings |
| `yaml-field-name-typo` | YAML field uses a near-canonical name PBS silently ignores. | quirks + bidder_info.yaml_field_name_quirks |
| `multi-file-layout-justified` | Multi-file layout that the heuristic flags but reviewer accepted. Canonical: Mediasquare non-OpenRTB body justified split. | quirks |
| `legacy-go-pattern-pre-1.22` | Go code uses pattern that pre-dates Go 1.22 (e.g., capture-by-reference loop). | quirks |
| `identifier-rule-workaround` | Class name modified to satisfy Java identifier rules. Canonical: `152media` → `OneFiveTwoMediaTest`. | quirks + code.naming |
| `acronym-case-preservation` | TitleCase preserves brand acronym. Canonical: `ElementalTV`, `FeedAd`, `BidTheatre`. | quirks + code.naming.preserves_acronym_case |
| `tilde-alias-syntax` | YAML alias declared as `oldname: ~` rather than full block. | quirks + aliases[].config_form |
| `bidder-rename-three-step` | Bidder rename via DELETE old YAML + CREATE new YAML + alias-back via tilde. Canonical: Adoppler → ElementalTV. | quirks + lifecycle.rename |
| `endpoint-compression-typo` | Specific case of `yaml-field-name-typo` for the gzip-compression field. Canonical: Ogury `endpointCompression` vs `endpoint-compression`. | quirks + bidder_info.yaml_field_name_quirks |
| `currency-conversion-bidrequest-context` | Java passes `bidRequest` for time-context to currency helper; Go does not. Cross-language port concern. | quirks (Java spec only) |
| `mutation-idiom-tobuilder` | Java uses `lombok-tobuilder` where Go uses pointer-mutation. Cross-language port concern. | quirks |
| `dev-endpoint-config-promotion` | Java port moves a Go-side hardcoded constant into YAML config (Kobler `devEndpoint`). | quirks (cross-language win) |
| `incomplete-classification` | Reader could not classify a behavioral field with affirmative evidence. | quirks (read-time warning) |
| `legacy-encoding-json-direct-usage` | Go adapter uses `encoding/json` `Marshal`/`Unmarshal` directly instead of `jsonutil`. | quirks + provenance.warnings |
| `legacy-test-helpers-imported` | Adapter test imports `OrtbMockService`, `BidOnTags`, etc. — should migrate to JSON harness. | quirks + provenance.warnings |
| `unguarded-currency-overwrite` | Adapter sets `bidResponse.Currency = response.Cur` without guarding against empty string. Canonical: Optidigital. | quirks + code.make_bids.currency_overwrite_safety |
| `hardcoded-bid-type` | `MakeBids` returns a fixed BidType regardless of upstream response. Canonical: Optidigital always returns BidTypeBanner. | quirks + code.make_bids.bid_type_resolution.method_chain |
| `legacy-impext-naming` | Imp ext struct uses legacy `ImpExt{Bidder}` pattern instead of canonical `ExtImp{Bidder}`. Canonical: Optidigital `ImpExtOptidigital`. | quirks + params.ext_struct.type_name |

The taxon list is closed: a reader emitting a quirk MUST pick from this list, OR add a new taxon to this file (atomic with the spec change). New taxa REQUIRE Phase 2 sample evidence — the goal is to keep the taxonomy machine-readable.

---

## Sources

- Phase 2 reconnaissance findings (in conversation): 17 Go edge cases + 17 Java edge cases identified across `optidigital, kobler, 33across, mediasquare, msft, appnexus, adkernel` (Go) and `kobler, adverxo, ogury, feedad, seedtag, optidigital, mediasquare, elementaltv, 152media` (Java) plus the broader 9-adapter Java behavior taxonomy stress-test (`appnexus, rubicon, generic, aax, adview, kobler, mediasquare, nextmillennium, huaweiads`).
- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27).
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
- `prebid-server-go/references/new-bid-adapter-prs.md` — 89 reference PRs with `Patterns Demonstrated` tags.
- `prebid-server-java/references/new-bid-adapter-prs.md` — 49 reference PRs with `Patterns Demonstrated` tags.
- Sibling shared file: `prebid-server-go/review/skills/shared/framework-utilities.md`.
- Sibling shared file: `prebid-server-go/read/skills/shared/adapter-spec.md`.
- Sibling shared file: `prebid-server-go/read/skills/shared/port-translation-rules.md`.
