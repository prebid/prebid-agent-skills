---
name: read-bidder-class
description: Extracts the `code:`, `bidder_class:`, `spring_config:`, `iab_category_storage:`, `ext_pojo_construction:`, `currency_conversion:`, `headers_constructed:`, and `tests:` fragments of an Adapter Specification from prebid-server-java adapter source. USE WHEN the orchestrator dispatches read-time analysis for `src/main/java/org/prebid/server/bidder/{xyz}/*.java`, `src/main/java/org/prebid/server/spring/config/bidder/{Xyz}Configuration.java`, `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/*.java`, plus the unit-test class, integration-test class(es), 4-file Wiremock fixtures, and the `test-application.properties` registry append. Owns Java file inventory, class-hierarchy extraction, Spring DI extraction, behavioral classification (same taxonomy as Go), JUnit method counting, IT fixture inventory, and `quirks[]` emission.
version: 1.0.0
---

# read-bidder-class (Java)

This skill is the heaviest of the four Java read-skills. It walks every `*.java` file in `src/main/java/org/prebid/server/bidder/{xyz}/`, the Spring `XyzConfiguration` class under `spring/config/bidder/`, the proto package under `proto/openrtb/ext/request/{xyz}/`, plus the unit-test class, integration-test classes, and IT JSON fixtures. It classifies each file by role, extracts the class hierarchy and Spring DI structure, applies the language-neutral behavior taxonomy (same enums as Go), inventories hand-written `@Test` methods and the 4-file Wiremock fixture set, and emits the dense Java fragments of the canonical Adapter Specification (see [../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../prebid-server-go/read/skills/shared/adapter-spec.md)).

The skill operates in read mode against a single resolved commit. Re-running on the same commit yields a byte-identical fragment modulo `provenance.read.timestamp_utc` (Validation Rule R4).

## What this skill produces

It owns these top-level spec keys (all dense on Java-source specs):

- `code.*` — `package_or_class` (Java class name), `directory_name`, `package_directory_mismatch`, `file_layout`, `imports`, `make_requests.*`, `make_bids.*`. The `adapter_struct` and `builder` siblings are null on Java specs.
- `bidder_class.*` — Java-specific shape (Go uses `code.adapter_struct` instead): `name`, `parameterized_request_type`, `parameterized_response_type`, `override_methods[]`, `constructor.{arity, parameters[]}`, `static_fields[]`, `helper_classes_co_located[]`, `helper_classes_in_proto[]`.
- `spring_config.*` — `factory_class`, `factory_method`, `bidder_creator_lambda` (verbatim), `property_source_path`, `configuration_properties_class.{name, extends, extra_fields[], nested_classes[], lombok_annotations[]}`, `bean_dependencies[]`.
- `iab_category_storage.*` — `storage_kind`, `yaml_field`, `table_size`, `injection`. `go_data_file` stays null on Java specs.
- `ext_pojo_construction.*` — `framework_choice`, `flexible_extension_used`, `custom_unmarshal.{kind, accepts_shapes, where_branched}`.
- `currency_conversion.*` — `used`, `helper.java_signature`, `injection`, `bid_request_passed_for_context`. `helper.go_signature` stays null on Java specs.
- `headers_constructed.*` — `pre_built_in_constructor`, `per_request_dynamic`, `custom_headers[]`, `authentication_kind`, `authentication_input[]`.
- `tests.*` — `test_root_directory`, `java_it_folder_naming`, `fixture_inventory.integration[]`, `uses_canonical_harness` (VertxTest), `unit_test_methods_count`, `unit_test_loc`, `hand_written_test_methods[]`, `test_application_properties_entries_added`, `integration_test_class`, `integration_test_pattern`. The Go-only fixture buckets (`exemplary, supplemental, amp, video, videosupplemental`) stay empty on Java specs.
- `cross_language.java_artifacts.*` — Java-side path hints (densely populated).
- `cross_language.go_artifacts.*` — Go-side path hint stubs (sparse — this skill does not read Go).
- `cross_language.java_specific_concerns[]` — free-text Java-only port-fidelity concerns (densely populated).
- `cross_language.go_specific_concerns[]` — empty list on Java-source specs.
- `cross_language.port_concerns.{multi_file_layout, package_directory_mismatch, custom_unmarshaljson_present, mutation_idiom_divergence, yaml_unification}` — booleans this skill computes (always sets `yaml_unification: true` since Java unifies what Go splits).
- `quirks[]` — entries whose evidence lives in adapter Java code or test fixtures.
- `code.naming.*` — `yaml_name`, `class_name_root`, `identifier_workaround`, `preserves_acronym_case` (Java edge cases #26, #27).
- `aliases[].test_assets.*` — populated when the parent's YAML `aliases:` map declares children that ship per-alias IT classes (edge case #24).
- `registry.test_application_properties.entries_added` — count of lines this bidder adds to the central registry (edge case #25).

It does **not** own (defer to sibling skills): `bidder_info.*` (read-bidder-config), `bidder_params_json` / `params.*` (read-bidder-params-java), `meta.*` and `provenance.*` (read-bidder-orchestrator).

## Inputs from the orchestrator

```yaml
inputs:
  bidder_name: kobler                            # The {xyz} slug (lowercase / per yaml file name).
  resolved_commit: SHA                           # Frozen commit.
  fetch_method: github-raw | local-checkout | gh-cli
  files:                                         # Pre-discovered paths owned by this skill.
    bidder_class_files:                          # bidder/{xyz}/*.java
      - src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java
    spring_config_files:                         # spring/config/bidder/{Xyz}Configuration.java + ConfigurationProperties subclass (often inner)
      - src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java
    proto_ext_files:                             # proto/openrtb/ext/request/{xyz}/*.java
      - src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/ExtImpKobler.java
    unit_test_files:                             # bidder/{xyz}/*Test.java
      - src/test/java/org/prebid/server/bidder/kobler/KoblerBidderTest.java
    integration_test_files:                      # it/{Xyz}Test.java (and per-alias siblings)
      - src/test/java/org/prebid/server/it/KoblerTest.java
    integration_test_fixtures:                   # it/openrtb2/{xyz}/**/*.json
      - src/test/resources/org/prebid/server/it/openrtb2/kobler/test-kobler-bid-request.json
      - src/test/resources/org/prebid/server/it/openrtb2/kobler/test-kobler-bid-response.json
      - src/test/resources/org/prebid/server/it/openrtb2/kobler/test-auction-kobler-request.json
      - src/test/resources/org/prebid/server/it/openrtb2/kobler/test-auction-kobler-response.json
    test_application_properties: src/test/resources/test-application.properties
  parent_aliases: []                             # Per-alias IT class set, populated by orchestrator from read-bidder-config.
  fixture_mode: count-only | summary | verbatim
```

## Workflow

### Step 1 — Inventory `*.java` files; classify by role

For each file in the inputs:

1. Read the file at `provenance.source.resolved_commit` (orchestrator-provided; do not re-fetch).
2. Compute `loc`.
3. Tag the file with one role from this enum: `bidder, configuration, configuration-properties, proto-ext, proto-helper, deserializer, test-unit, test-it`. Detection rules and worked examples live in [references/spring-config-patterns.md](references/spring-config-patterns.md) (for `configuration` / `configuration-properties`), [references/proto-pojo-patterns.md](references/proto-pojo-patterns.md) (for `proto-ext` / `proto-helper` / `deserializer`), and [references/junit-it-patterns.md](references/junit-it-patterns.md) (for `test-unit` / `test-it`).

Record the bidder-package files in `code.file_layout.files[]`. Set `code.file_layout.kind: multi-file` if more than one bidder-package `*.java` file (e.g., Mediasquare's `MediasquareBidder.java` + `MediasquareUtil.java` co-located helper); otherwise `single-file`. Counts apply only to bidder-package files — `proto/`, `spring/config/`, `test/` files do NOT inflate the layout count.

### Step 2 — Extract `bidder_class.*`

From the file with role=`bidder`:

1. Parse the class declaration line. Extract:
   - `name` — the class identifier (e.g., `KoblerBidder`).
   - `parameterized_request_type` — the type argument of `Bidder<T>`. Default `BidRequest`. Custom values: `MediasquareRequest` (Mediasquare), `HuaweiAdsRequest` (Huaweiads). Edge case #28.
   - `parameterized_response_type` — typically null. Populated only for the rare adapters that parameterize a custom response (edge case #28 second leg).
2. `override_methods[]` — locate every method annotated `@Override`. Typically `[makeHttpRequests, makeBids]`. Adapters that delegate via `BidderUtil.defaultRequest` may collapse `makeHttpRequests` to a thin wrapper but still list it here.
3. `constructor.arity` — count of parameters in the public constructor.
4. `constructor.parameters[]` — for each parameter, record `{ name, type, source, role }`:
   - `source ∈ {config-field, framework-injected}`. `config-field` when the value is read from `BidderConfigurationProperties` getters in the lambda (e.g., `cfg.getEndpoint()`, `cfg.getDevEndpoint()`); `framework-injected` when it is an autowired Spring bean in the factory method (`currencyConversionService`, `mapper`).
   - `role ∈ {properties, helper-collaborator, framework-injected}`. `properties` when the parameter is a config-derived String/primitive; `helper-collaborator` when it is a domain helper (`CurrencyConversionService`, `JacksonMapper`, `IdGenerator`, `Clock`, `BidderUtil`); `framework-injected` for everything else autowired but neither config nor a known helper.
   - The standard collaborator catalog (`JacksonMapper`, `CurrencyConversionService`, `IdGenerator`, `Clock`, `BidderUtil`) lives in [references/spring-config-patterns.md](references/spring-config-patterns.md#standard-collaborators).
5. `static_fields[]` — class-level constants: TypeReferences (`KOBLER_EXT_TYPE_REFERENCE`), default-currency strings (`DEFAULT_BID_CURRENCY`), ext-key strings (`EXT_PREBID`). Record `{ name, type, value? }`.
6. `helper_classes_co_located[]` — non-bidder classes co-located in `bidder/{xyz}/` (e.g., `MediasquareUtil`, `KueezExtractor`).
7. `helper_classes_in_proto[]` — DTO classes in `proto/openrtb/ext/request/{xyz}/` (e.g., `ExtImpKobler`, plus any helper proto types like `MediasquareCode`, `HuaweiAdsRequestExt`).

### Step 3 — Extract `spring_config.*`

From the file with role=`configuration`:

1. `factory_class` — the class identifier (e.g., `KoblerConfiguration`). Naming variance: `<Name>Configuration` (Kobler, Optidigital) vs `<Name>BidderConfiguration` (Adverxo). Edge case #19; record either name verbatim.
2. `factory_method` — the `@Bean` method returning `BidderDeps`. Naming: `<name>BidderDeps` (e.g., `koblerBidderDeps`).
3. `property_source_path` — the value of `@PropertySource` on the class. Canonical: `classpath:/bidder-config/{xyz}.yaml`.
4. `bidder_creator_lambda` — the verbatim lambda body inside `BidderDepsAssembler.bidderCreator(cfg -> new XyzBidder(...))`. Preserve indentation, line breaks, and constructor argument order — round-trip fidelity is load-bearing for porters.
5. `configuration_properties_class.*` — populated when the adapter declares a subclass of `BidderConfigurationProperties` (typically as an inner static class on the factory class):
   - `name` — the subclass identifier (e.g., `KoblerConfigurationProperties`).
   - `extends` — typically `BidderConfigurationProperties`.
   - `extra_fields[]` — each declared field with `{ name, type, validations[] }`. Validations are Bean Validation annotations: `@NotBlank`, `@NotNull`, `@Size`, etc. Edge case #20 examples: Kobler's `@NotBlank private String devEndpoint`; Appnexus's `platformId` + `iabCategories` (Map<String, Long>).
   - `nested_classes[]` — additional inner static classes (e.g., Huaweiads/NextMillennium `ExtraInfo`).
   - `lombok_annotations[]` — class-level Lombok annotations: `[Data, EqualsAndHashCode, NoArgsConstructor]` for the canonical case; record verbatim.
   - When the factory class declares NO subclass (default `BidderConfigurationProperties` is enough), set `configuration_properties_class: null`.
6. `bean_dependencies[]` — every `@Autowired` constructor parameter or `@Value(${...})` injection on the factory method. Record `{ name, type, source }`. The standard collaborators list (`CurrencyConversionService`, `JacksonMapper`, `@Value(${external-url})`) lives in [references/spring-config-patterns.md](references/spring-config-patterns.md#bean-dependencies-extraction).

### Step 4 — Classify `code.make_requests.*`

Locate `makeHttpRequests(BidRequest bidRequest)` in the bidder class. Apply rules from [../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md):

1. **`batching.rules[]`** — ordered list using the SAME taxonomy as Go (`single-batched, per-imp, max-imps-per-request, format-split, deals-split, pod-grouping, imp-flatten-aggregate, filtered-subset, grouped-by-key`). Default `[{ kind: single-batched }]` when one `HttpRequest<T>` is returned with all imps. Set `batching.applied_in_order: true`.
2. **`request_body.kind`** — `openrtb2-passthrough`, `openrtb2-modified`, or `custom`. When `custom`, set `custom_body_type` to the parameterized request type from `bidder_class.parameterized_request_type` (Mediasquare's `MediasquareRequest`).
3. **`mutation.entity_strategies`** — same enum as Go (`none, copy-then-mutate, in-place, append-if-missing, immutable-rebuild`). Java adapters typically emit `immutable-rebuild` for OpenRTB entities (Lombok `toBuilder().build()`); `append-if-missing` for currency lists; `in-place` is rare (Java POJOs default to immutable).
4. **`mutation.java_idiom`** — `lombok-tobuilder` (default), `flexible-extension-fillExtension` (when extending `FlexibleExtension`), `none`. `mutation.go_idiom` stays null on Java specs.
5. **`imp_ext_unmarshal.kind`** — `standard-two-phase` (default), `direct`, `none`, `custom`.
6. **`imp_ext_unmarshal.mechanism_java`** — `typeref-extprebid` (canonical: `new TypeReference<ExtPrebid<?, ExtImp{Xyz}>>(){}`, then `mapper.convertValue(imp.getExt(), ...).getBidder()`), `typeref-custom-wrapper` (custom wrapper TypeReference, e.g., Appnexus's `AppnexusExtImp`), `direct-class` (deserialize directly into params type, no wrapper), `null` when `kind: none`. Set `target_type` to `ExtImp{Xyz}` and `wrapper_type` only on `direct`/`typeref-custom-wrapper`.
7. **`endpoint_resolution.kind`** + **`endpoint_resolution.mechanism_java`** — kinds match Go (`static, single-token-substitution, multi-token-substitution, query-parameter-augmentation, runtime-region-selection, deploy-time-token, dev-prod-toggle, custom`). Java mechanisms: `string-replace` (canonical: `endpoint.replace("{{.X}}", value)`), `URIBuilder` (`new URIBuilder(endpointUrl).addParameter(...)`), `custom-resolver-class` (a co-located `<Name>UriBuilder`), `null`. Populate `macro_field_set[]` with the substituted macro names.
8. **`helpers[]`** — every private method on the bidder class (excluding `makeHttpRequests` and `makeBids`). Record `{ name, signature }` with the Java method signature verbatim.

### Step 5 — Classify `code.make_bids.*`

Locate `makeBids(BidderCall<BidRequest> httpCall, BidRequest bidRequest)` in the bidder class. Apply rules:

1. **`response_type`** — `BidResponse` (canonical, `com.iab.openrtb.response.BidResponse`) or `custom` with `custom_response_type` populated (e.g., Mediasquare's `MediasquareResponse`).
2. **`http_status_handling.kind`** — Java values: `framework-default` (default — adapter relies on Vert.x framework auto-handling via `HttpUtil.validateResponse`); `framework-default-plus-empty-seatbid-shortcircuit` (canonical for many Java adapters: framework-default plus an early `if (CollectionUtils.isEmpty(bidResponse.getSeatbid())) return Collections.emptyList()` guard); `custom-status-checks` (bespoke 4xx handling). The `canonical-go-helpers` and `legacy-raw-go` values are Go-only.
3. **`application_status_handling.kind`** — `none` default; `retcode-field` when adapter checks an in-body status field (canonical: Huaweiads `retcode`). Populate `field, success_codes, error_codes` when `retcode-field`.
4. **`bid_type_resolution.method_chain[]`** — same enum as Go (`by-imp-mediatype, by-bid-mtype, by-bid-ext-typed-field, by-imp-id-suffix, imp-prefix-lookup, by-response-payload-shape, hardcoded, custom`). Each step `{ method, field?, hardcoded_value?, fallback_action: next | return-default | throw }`. Populate `default_value` when the last step's `fallback_action: return-default`. `multi_format_detection: strict | lenient | none`. Java's `getXNative()` (the JSON-tag-renamed `native` accessor) is the typical signal that the chain reads from imp media types.
5. **`bid_pointer_pattern`** — Java specs almost always emit `flatten-streams` (`bidResponse.getSeatbid().stream().flatMap(seatBid -> seatBid.getBid().stream())...`). The `indexed-iteration` and `pointer-iteration` values are typical of Go but valid here for adapters that use indexed for-loops. `bid_pointer_go_sibling` stays null on Java specs.
6. **`currency_overwrite_safety`** — same enum (`guarded, unguarded, unguarded-hardcoded, passthrough-from-response, none`). Java's canonical pattern is `BidderBid.of(bid, type, bidResponse.getCur())` → `passthrough-from-response`.

### Step 6 — Extract `iab_category_storage.*`

The IAB-categories lookup is captured at adapter level even though the storage may live in the Spring config or YAML. From the inputs:

1. `storage_kind`:
   - `yaml-inlined` — the bidder's `bidder-config/{xyz}.yaml` contains an inlined map of IAB categories (Java pattern). Canonical: Appnexus 120-entry `iab-categories`. Edge case #21.
   - `none` — no IAB lookup (the typical case: Kobler, Optidigital).
   - `dynamic-fetched` — runtime fetch (rare; not yet seen in Java).
   - `go-data-table` — Go-only; never set on Java specs.
2. `yaml_field` — when `storage_kind: yaml-inlined`, the YAML field name (e.g., `iab-categories`).
3. `table_size` — count of entries in the inlined map.
4. `injection`:
   - `constructor-arg` — the table is injected into the bidder class via the factory's `bidder_creator_lambda` (e.g., `cfg -> new AppnexusBidder(..., cfg.getIabCategories())`).
   - `static-init` — the table is a static field initialized at class load.
   - `null` when `storage_kind: none`.

The YAML field-level evidence is read by `read-bidder-config`; this skill cross-references it via the orchestrator-merged `bidder_info.yaml_extra_fields` map. When a `iab-categories` (or similar) key appears under that map AND the bidder constructor accepts the table, set the four fields above.

### Step 7 — Extract `ext_pojo_construction.*`

From the file(s) with role=`proto-ext`:

1. `framework_choice`:
   - `lombok-value-builder` — `@Value @Builder @Jacksonized` on the class. Default Java pattern.
   - `lombok-data` — `@Data @NoArgsConstructor` (mutable POJO; rare for ExtImp).
   - `lombok-value-staticconstructor` — `@Value(staticConstructor = "of")` (Kobler's choice — yields `ExtImpKobler.of(true)` factory).
   - `go-struct` — Go-only; never set on Java specs.
2. `flexible_extension_used` — true when the class extends `FlexibleExtension` (the framework base class with `@JsonAnyGetter` / `@JsonAnySetter` for unknown-field passthrough).
3. `custom_unmarshal.kind`:
   - `none` — default (framework handles unmarshal).
   - `jackson-jsondeserialize` — `@JsonDeserialize(using = XyzDeserializer.class)` paired with a separate `JsonDeserializer<T>` class (file role: `deserializer`).
   - `jackson-jsonalias-only` — `@JsonAlias({...})` on individual fields only, no full deserializer (Appnexus Java).
   - `runtime-isobject-isarray-branching` — runtime branch on JSON shape (`isObject() vs isArray()`).
   - `go-unmarshaljson` — Go-only; never set on Java specs.
   - `custom` — anything else (REQUIRES quirk).
4. `custom_unmarshal.accepts_shapes[]` — the JSON shapes accepted (`object, array, string, integer, boolean`).
5. `custom_unmarshal.where_branched`:
   - `bidder-class` — branching happens in the bidder class (e.g., Appnexus keywords field check).
   - `jsondeserializer-class` — branching in the separate `JsonDeserializer<T>`.
   - `type-method` — branching in a method on the type itself.
   - `null` when `kind: none`.

The class-level annotations and Jackson annotations to recognize are catalogued in [references/proto-pojo-patterns.md](references/proto-pojo-patterns.md).

### Step 8 — Extract `currency_conversion.*`

Cross-reference the bidder-class constructor and method bodies:

1. `used` — true when any constructor parameter has type `CurrencyConversionService` AND the field is invoked.
2. `helper.java_signature` — verbatim signature of the helper invocation, e.g., `currencyConversionService.convertCurrency(value, bidRequest, from, to) BigDecimal`. Java's signature has 4 args including `bidRequest` for time-context.
3. `helper.go_signature` — null on Java specs (orchestrator may merge in for round-trip fidelity).
4. `injection: dependency` — Java always uses constructor-injected dependency. (`function-arg` is Go-only — `reqInfo.ConvertCurrency` is passed via `ExtraRequestInfo`.)
5. `bid_request_passed_for_context: true` — Java passes `bidRequest` to the helper for time-context (currency rates can vary by `request.tmax` / time-of-bid). This is the Phase 2 cross-language asymmetry; surfaces as quirk `currency-conversion-bidrequest-context` when the spec is read for port comparison.

### Step 9 — Extract `headers_constructed.*`

Locate header construction in the bidder class (typically inside `makeHttpRequests` or a private `headers()` helper):

1. `pre_built_in_constructor` — true when the constructor pre-computes a header (typically the `Authorization` for basic-auth) and stores it as a field (Rubicon `authHeader` pattern).
2. `per_request_dynamic` — true when headers are built per-request inside `makeHttpRequests` (the typical case: `MultiMap headers = HttpUtil.headers()` plus optional bidder additions).
3. `custom_headers[]` — the literal headers added beyond the `HttpUtil.headers()` defaults. Canonical: `{ name: Content-Type, value: "application/json;charset=utf-8" }`.
4. `authentication_kind` — `none, basic-auth, bearer-token, hmac-digest, custom`.
5. `authentication_input[]` — the YAML/config fields used to compute the auth value (e.g., `["XAPI.Username", "XAPI.Password"]` for Rubicon, the HMAC-secret YAML field for Huaweiads).

When the adapter does NOT customize headers beyond `HttpUtil.headers()` defaults, set `pre_built_in_constructor: false`, `per_request_dynamic: true`, `custom_headers: []`, `authentication_kind: none`. Setting `per_request_dynamic: true` always (even for "no customization" cases) reflects that `HttpUtil.headers()` is invoked per request — this matches the Kobler golden.

### Step 10 — Inventory `tests:`

#### Unit tests (file role=`test-unit`)

1. `tests.test_root_directory` — the bidder unit-test directory: `src/test/java/org/prebid/server/bidder/{xyz}/`.
2. `tests.uses_canonical_harness: true` if the test class extends `VertxTest` (the canonical Java harness) — this is the Java equivalent of Go's `RunJSONBidderTest`. False if the class avoids `VertxTest` and uses bespoke setup; emit `legacy-test-helpers-imported` quirk + `provenance.warnings` entry (Validation Rule R10).
3. `tests.unit_test_methods_count` — count of `@Test`-annotated methods (regex: `^\s*@Test\b` on the file). Canonical Kobler: 14.
4. `tests.unit_test_loc` — total line count of the unit-test file. Canonical Kobler: 320.
5. `tests.hand_written_test_methods[]` — list every method name annotated `@Test`, in declaration order. Canonical Kobler list of 14 methods including `creationShouldFailOnInvalidEndpointUrl`, `makeHttpRequestsShouldConvertBidFloorCurrency`, `makeBidsShouldDefaultToBannerWhenPrebidTypeIsMissing`, etc.

The detailed regex / parser rules and the per-method-naming convention live in [references/junit-it-patterns.md](references/junit-it-patterns.md#unit-test-method-counting).

#### Integration tests (file role=`test-it`)

1. `tests.integration_test_class` — the IT class name (e.g., `KoblerTest`). When more than one IT class exists for the same bidder (per-alias case — Adverxo's `AdportTest`, `BidsmindTest`, `MobuppsTest`), record only the parent's IT class here; the per-alias IT classes go into `aliases[].test_assets.it_class` (see Step 11).
2. `tests.integration_test_pattern`:
   - `4-file-split` — canonical Wiremock pattern: 1 outbound bidder request + 1 mock bidder response + 1 inbound auction request + 1 outbound auction response.
   - `6-file-with-cache` — adds 2 additional fixture files for cache-flow testing.
   - `multi-folder` — Rubicon-style with multiple sibling folders.
   - `none` — adapter has no integration test (rare; flagged as a gap).
3. `tests.fixture_inventory.integration[]` — for each fixture file in `inputs.files.integration_test_fixtures`, record `{ filename, sha256, bytes, role }`. The `role` enum:
   - `bidder-bid-request` — `test-{xyz}-bid-request.json` (outbound to bidder).
   - `bidder-bid-response` — `test-{xyz}-bid-response.json` (mock bidder response).
   - `auction-request` — `test-auction-{name}-request.json` (inbound auction request to PBS).
   - `auction-response` — `test-auction-{name}-response.json` (expected outbound auction response).

The folder convention: `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/`. `tests.java_it_folder_naming: canonical` when the folder follows this exactly; `suffix-augmented` when the folder has an extra suffix (rare); `multi-folder` for Rubicon-style multiple sibling folders; `custom` otherwise (REQUIRES quirk).

### Step 11 — Per-alias IT class set

When `inputs.parent_aliases` is non-empty (the bidder is a parent declaring `aliases: { name: ~ }` children — edge case #24), each alias requires its own IT class + fixture set:

1. For each alias, locate `src/test/java/org/prebid/server/it/{Name}Test.java` (e.g., Adverxo ships `AdportTest`, `BidsmindTest`, `MobuppsTest` — ALL three required).
2. Locate the per-alias fixture folder: `src/test/resources/org/prebid/server/it/openrtb2/{name}/`.
3. Populate `aliases[].test_assets`:
   - `it_class` — the alias-specific IT class name.
   - `fixture_dir` — the alias-specific fixture folder.
   - `fixture_file_count` — count of JSON files in that folder (typically 4 for the canonical pattern).

When an alias does NOT ship an IT class (a gap that reviewers flag), emit a quirk with `edge_case_taxon: incomplete-classification`.

Identifier-rule workaround (edge case #26): for digit-leading bidders (`152media` → `OneFiveTwoMediaTest`), record:

- `code.naming.yaml_name: 152media`
- `code.naming.class_name_root: OneFiveTwoMedia`
- `code.naming.identifier_workaround: true`

Plus a quirk with `edge_case_taxon: identifier-rule-workaround`.

TitleCase brand-acronym preservation (edge case #27): when the class name preserves acronym casing (`ElementalTV` not `ElementalTv`, `FeedAd` not `FeedAd` lowercase d, `BidTheatre`), record:

- `code.naming.preserves_acronym_case: true`

Plus a quirk with `edge_case_taxon: acronym-case-preservation` only when the casing diverges from a strict TitleCase normalization (i.e., `TV`, `Ad` are preserved as-is).

### Step 12 — Registry append count

Read `src/test/resources/test-application.properties`. Count lines that begin with `adapters.{xyz}.` for THIS bidder (and any parent_aliases). The canonical pattern is 2-4 lines per bidder:

```
adapters.{xyz}.enabled=true
adapters.{xyz}.endpoint=http://localhost:8090/{xyz}-exchange
# Plus per-alias lines:
adapters.{xyz}.aliases.{name}.enabled=true
adapters.{xyz}.aliases.{name}.endpoint=http://localhost:8090/{name}-exchange
```

Emit `tests.test_application_properties_entries_added: <count>` and `registry.test_application_properties.entries_added: <count>` (both fields are populated for downstream consumers — the `tests.*` form is the spec field; the `registry.*` form is a top-level summary the orchestrator merges).

When the count is zero (the bidder is added BUT no IT class exists, a gap that reviewers flag), emit a quirk with `edge_case_taxon: incomplete-classification`.

### Step 13 — Emit `quirks[]` and populate `cross_language.*`

For each unclassifiable pattern observed in any of Steps 4–12, add an entry to `quirks[]`. Every `custom` value in an enumerated field REQUIRES a quirk entry (Validation Rule R3). The `edge_case_taxon` MUST be picked from the registry at [../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md#quirks-edge_case_taxon-full-registry).

Densely populate `cross_language.java_specific_concerns[]` with free-text observations a Go porter must address. Examples (verbatim from Kobler Java golden — see [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml) lines 404–412):

- Bean-construction-time URL validation that triggers `IllegalArgumentException` (e.g., `KoblerBidder` constructor calls `HttpUtil.validateUrl(endpointUrl)` at line 60).
- Static `TypeReference<ExtPrebid<?, ExtImp{Xyz}>>` constructed once at class init.
- Multi-imp callers cannot toggle dev endpoint per-imp (mirrors Go `i==0` branch behaviour).
- `BidderUtil.defaultRequest(modifiedRequest, endpoint, mapper)` collapses what Go expands inline.
- Optional chains with redundant filters (e.g., double `JsonNode::isObject` after `ObjectNode::class` cast) — describe behaviour, do not over-flag.
- `ExtImp{Xyz}` framework choice (`@Value(staticConstructor=of)` is rare for params POJOs).
- Empty-seatbid shortcircuit ordering (returns `Collections.emptyList()` BEFORE bid extraction stream).
- Stream-pipeline defensive `Objects::nonNull` filters that have no Go counterpart (Go ranges never iterate over nil-element slots).

Set `cross_language.go_specific_concerns: []` (this skill does not read Go).

Populate `cross_language.port_concerns`:

- `multi_file_layout` — from Step 1.
- `package_directory_mismatch` — `code.directory_name` should equal lowercase(`bidder_class.name` minus `Bidder` suffix); deviation flags this. Java edge cases #26 (digit-leading) and #27 (acronym-case) are NOT mismatches per se — they're typed under `code.naming` instead.
- `custom_unmarshaljson_present` — true when any class in `proto/openrtb/ext/request/{xyz}/` declares `@JsonDeserialize(using = ...)` or extends `JsonDeserializer<T>`. Triggers a quirk with the appropriate taxon.
- `mutation_idiom_divergence` — `true` whenever Java mutates request entities at all using `lombok-tobuilder` (matches Kobler precedent — divergence is the rule, not the exception).
- `yaml_unification: true` — Java always unifies what Go splits; set unconditionally for Java-source specs.
- `aliases_inverted` — set by `read-bidder-config` (parent-side aliases map). Default `false` if no aliases.

Populate `cross_language.java_artifacts`:

- `bidder_dir: src/main/java/org/prebid/server/bidder/{xyz}/`
- `bidder_class: <Name>Bidder`
- `config_class: <Name>Configuration` (or `<Name>BidderConfiguration` per edge case #19)
- `yaml_path: src/main/resources/bidder-config/{xyz}.yaml`
- `proto_dir: src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/`

Stub `cross_language.go_artifacts` with path hints only:

- `bidder_dir: adapters/{xyz}/`
- `package_name: {xyz}` (lowercase)
- `bidder_constant: openrtb_ext.Bidder<TitleCase>` (best-guess; orchestrator may overwrite when round-tripping from Go)

Populate `cross_language.reviewer_cohort.java[]` from the actual review history in [../../../references/new-bid-adapter-prs.md](../../../references/new-bid-adapter-prs.md) (cohort is wholly disjoint from Go — see Cross-language note below). `reviewer_cohort.go: []` on Java-source specs. `cross_language_coordinator: bretg` always.

## Edge case mapping (Java cases #18-#34)

Each Java edge case maps to specific spec fields owned by this skill. Quirks are reserved for genuinely unclassifiable patterns.

| # | Edge case | Captured by |
|---|---|---|
| 18 | Spring `@Configuration` class with `@PropertySource` | `spring_config.{factory_class, factory_method, property_source_path}` |
| 19 | Configuration-class naming variance (`KoblerConfiguration` vs `AdverxoBidderConfiguration`) | `spring_config.factory_class` (verbatim) |
| 20 | `BidderConfigurationProperties` subclass (Kobler `devEndpoint`, Appnexus `platformId`+`iabCategories`, Huaweiads `ExtraInfo`) | `spring_config.configuration_properties_class.{name, extends, extra_fields[], nested_classes[], lombok_annotations[]}` |
| 21 | IAB categories inlined in YAML (Appnexus 120 entries) | `iab_category_storage.{storage_kind: yaml-inlined, yaml_field, table_size, injection}` |
| 22 | Hand-written N `@Test` methods (no JSON harness) | `tests.{unit_test_methods_count, unit_test_loc, uses_vertx_test, hand_written_test_methods[]}` |
| 23 | Wiremock 4-file IT fixture pattern | `tests.integration_test_pattern: 4-file-split`, `tests.fixture_inventory.integration[]` |
| 24 | Per-alias IT class + 4-file fixture set required | `aliases[].test_assets.{it_class, fixture_dir, fixture_file_count}` |
| 25 | Central `test-application.properties` registry append | `registry.test_application_properties.entries_added: N` (also `tests.test_application_properties_entries_added`) |
| 26 | Class names break Java identifier rules for digit-leading bidders | `code.naming.{yaml_name, class_name_root, identifier_workaround: true}` + quirk `identifier-rule-workaround` |
| 27 | TitleCase brand-acronym preservation | `code.naming.preserves_acronym_case: true` + quirk `acronym-case-preservation` |
| 28 | `Bidder<T>` generic for custom payloads (Mediasquare, Huaweiads) | `bidder_class.parameterized_request_type` + `code.make_requests.request_body.{kind: custom, custom_body_type}` |
| 29 | `ortb-version: "2.6"` quoted-string field | `bidder_info.ortb_version` (owned by `read-bidder-config`; this skill does not own) |
| 30 | `enabled: false` opt-in default | `bidder_info.default_enabled: false` (owned by `read-bidder-config`) |
| 31 | `modifying-vast-xml-allowed: true` | `bidder_info.modifying_vast_xml_allowed: true` (owned by `read-bidder-config`) |
| 32 | Tilde-syntax empty alias `oldname: ~` | `aliases[].config_form: tilde_inherit` (owned by `read-bidder-config`) |
| 33 | Bidder rename three-step refactor (DELETE old YAML + CREATE new YAML + alias-back via tilde) | `lifecycle.rename.*` (orchestrator-merged) |
| 34 | `endpoint-compression` vs `endpointCompression` typo regression | `bidder_info.yaml_field_name_quirks[]` (owned by `read-bidder-config`) |

The 17 Java edge cases #18-#34 above are surfaced by the Phase 2 reconnaissance findings. None require `custom`+`quirks` fallback because each maps to a typed field. Quirks emit only for genuinely unclassifiable patterns.

## Cross-language note

Java's reviewer cohort is **wholly disjoint** from Go's. Phase 2 reconnaissance confirmed the Java-side reviewers (CTMBNara, AntoxaAntoxic, EmilNadimanov, sangarbe, osulzhenko) have NO overlap with Go-side reviewers (bsardo, SyntaxNode, hhhjort). Only `@bretg` crosses both repos as the cross-language coordinator.

This has TWO consequences for read-bidder-class output:

1. **Port-fidelity is the #1 review theme on Java-side adapter PRs.** Reviewers cite "I don't see that in Go" as a blocker. The skill's `cross_language.java_specific_concerns[]` SHOULD be populated densely so a porter (or a downstream review skill) can address each port-fidelity concern explicitly. The Kobler Java golden's 9-entry list at [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml) lines 404-412 is the model.

2. **Review-pattern matchers must NOT be auto-transferred between languages.** A Go-side review pattern (e.g., "use `ptrutil.Clone` for nested-pointer entities") does NOT translate to a Java-side review pattern. Skills downstream of `read-bidder-class` (e.g., a future `port-go2java` review consumer) must consult `cross_language.reviewer_cohort.java[]` to source correct review-pattern matchers, and `cross_language.reviewer_cohort.cross_language_coordinator` (`bretg`) for cross-language coordination PRs.

The list of Java reference PRs with `Patterns Demonstrated` tags lives in [../../../references/new-bid-adapter-prs.md](../../../references/new-bid-adapter-prs.md). The skill's classification rules cite tags from that list when populating `quirks[].edge_case_taxon` and `port_lineage.fidelity_review_themes`.

## Verification

The Java Kobler golden is the proof-of-concept output:

- [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml) — currency conversion, dev-prod toggle, configuration-properties subclass with `@NotBlank devEndpoint`, 14 hand-written `@Test` methods, 4-file Wiremock IT fixture set. This skill owns lines covering `code.*` (lines 102–193), `bidder_class.*` (lines 279–316), `spring_config.*` (lines 245–277), `iab_category_storage.*` (lines 318–323), `ext_pojo_construction.*` (lines 325–331), `currency_conversion.*` (lines 333–339), `headers_constructed.*` (lines 341–348), `tests.*` (lines 195–243), the 5 quirks (lines 352–372), and `cross_language.{java_artifacts, port_concerns, java_specific_concerns, reviewer_cohort.java}` (lines 379–418).

A reader following this SKILL.md should produce a spec that matches the golden byte-for-byte modulo `provenance.read.timestamp_utc`. Validation Rule R4 (round-trip determinism) is enforced by the orchestrator's CI harness.

Spot-check verification: re-run the workflow on Appnexus (the most complex Java adapter — multi-format, IAB-categories inlined in YAML, custom `AppnexusExtImp` wrapper, `runtime-isobject-isarray-branching` keywords field, multi-step bid-type chain). Expected outputs:

- `iab_category_storage.{storage_kind: yaml-inlined, yaml_field: iab-categories, table_size: ~120, injection: constructor-arg}`.
- `imp_ext_unmarshal.{kind: direct, mechanism_java: typeref-custom-wrapper, target_type: AppnexusExtImp, wrapper_type: AppnexusExtImp}`.
- `ext_pojo_construction.custom_unmarshal.{kind: jackson-jsonalias-only or runtime-isobject-isarray-branching, where_branched: bidder-class}`.
- `code.make_requests.batching.rules: [{ kind: max-imps-per-request, max: 10 }, { kind: pod-grouping, key: imp.id-prefix-before-underscore }]`.
- `bid_type_resolution.method_chain` 3-step or 2-step depending on master.

The exhaustive Appnexus golden is out of scope for this skill but the spot-check above validates the skill's classification rules cover the edge cases.

## Cross-skill references (read-only, do not duplicate)

- **[../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../prebid-server-go/read/skills/shared/adapter-spec.md)** — canonical schema + Kobler worked example (Go and Java side by side).
- **[../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md)** — every enumerated value with cross-references.
- **[../../../../prebid-server-go/read/skills/shared/port-translation-rules.md](../../../../prebid-server-go/read/skills/shared/port-translation-rules.md)** — 37 Go↔Java port rules; the `cross_language.java_specific_concerns[]` text should reference rule numbers when applicable.
- **[../../../references/new-bid-adapter-prs.md](../../../references/new-bid-adapter-prs.md)** — 49 reference PRs with Patterns Demonstrated tags + the Pattern Index.
- **[references/spring-config-patterns.md](references/spring-config-patterns.md)** — Spring DI patterns (factory class naming, `BidderConfigurationProperties` subclass detection, bean dependencies, standard collaborators, Lombok annotations to recognize).
- **[references/proto-pojo-patterns.md](references/proto-pojo-patterns.md)** — Java POJO patterns (`@Value @Builder @Jacksonized`, `@JsonProperty`, `@JsonAlias`, `@JsonDeserialize`, `FlexibleExtension`, helper proto co-location, `Bidder<T>` generic parameterization).
- **[references/junit-it-patterns.md](references/junit-it-patterns.md)** — JUnit unit-test patterns + IT 4-file/6-file fixture inventory + per-alias IT class detection + central registry append count.

## Sources

- Plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md`.
- Schema: [../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../prebid-server-go/read/skills/shared/adapter-spec.md).
- Taxonomy: [../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md).
- Port-translation rules: [../../../../prebid-server-go/read/skills/shared/port-translation-rules.md](../../../../prebid-server-go/read/skills/shared/port-translation-rules.md).
- Java reference PR list: [../../../references/new-bid-adapter-prs.md](../../../references/new-bid-adapter-prs.md).
- Golden specs: [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml) (Java-source); [../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml](../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml) (Go-source counterpart for cross-language alignment).
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
