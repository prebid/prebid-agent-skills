---
name: read-bidder-class
description: Extract code, bidder_class, spring_config, iab_category_storage, ext_pojo_construction, currency_conversion, headers_constructed, and tests fragments of an Adapter Specification from prebid-server-java sources. USE WHEN the orchestrator dispatches read-time analysis for the bidder package, its Configuration.java factory, ext-request POJOs, unit and 4-file Wiremock IT tests, and the test-application.properties registry. Owns Java file inventory, class hierarchy, Spring DI, behavioral classification (same taxonomy as Go), JUnit method counting, IT fixture inventory, and quirks emission.
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
- `iab_category_storage.*` — `storage_kind`, `yaml_field`, `table_size`, `delivery_mechanism`. `go_data_file` stays null on Java specs.
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
- `code_naming.*` (top-level) — `yaml_name`, `class_name_root`, `identifier_workaround` (enum: `null | digit-leading-rename | acronym-collision | custom`), `preserves_acronym_case` (bool), `notes[]` (Java edge cases #26, #27). The block is null on Go-source specs.
- `aliases[].test_assets.*` — populated when the parent's YAML `aliases:` map declares children that ship per-alias IT classes (edge case #24).

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
    test_application_properties: src/test/resources/org/prebid/server/it/test-application.properties
  parent_aliases: []                             # Per-alias IT class set, populated by orchestrator from read-bidder-config.
  fixture_mode: count-only | summary | verbatim
```

## Workflow

### Step 1 — Inventory `*.java` files; classify by role

For each file in the inputs:

1. Read the file at `provenance.source.resolved_commit` (orchestrator-provided; do not re-fetch).
2. Compute `loc` as the stdout of `<fetch> | wc -l` (V4 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)) — a command's number, never an estimate from a viewer's last line number.
3. Tag the file with one role from this 5-value enum: `implementation, models, parsers, types, utils`. Deterministic filename → role mapping rules live in [references/file-role-heuristics.md](references/file-role-heuristics.md). Cross-language note: Go's enum is the same 5 values plus `data-table` (Go-only — Java records IAB-category tables as `iab_category_storage.storage_kind: yaml-inlined` per ADR-001 D2). The other references in this directory cover deeper Java extraction patterns referenced from later Steps, NOT role tagging: [references/spring-config-patterns.md](references/spring-config-patterns.md) (Step 3 — `spring_config.*` and Step 2 parameter-role classification), [references/proto-pojo-patterns.md](references/proto-pojo-patterns.md) (Step 7 — `ext_pojo_construction.*`), and [references/junit-it-patterns.md](references/junit-it-patterns.md) (Steps 10–12 — `tests.*`). The lint at `scripts/lib/lint-java-roles.py` gates the enum at CI time.

Record the bidder-package files in `code.file_layout.files[]`. Set `code.file_layout.kind: multi-file` if more than one bidder-package `*.java` file (e.g., Mediasquare's `MediasquareBidder.java` + `MediasquareUtil.java` co-located helper); otherwise `single-file`. Counts apply only to bidder-package files — `proto/`, `spring/config/`, `test/` files do NOT inflate the layout count.

### Step 2 — Extract `bidder_class.*`

From the file with role=`implementation` (the `{Xyz}Bidder.java` file declaring `class XyzBidder implements Bidder<T>`):

1. Parse the class declaration line. Extract:
   - `name` — the class identifier (e.g., `KoblerBidder`).
   - `parameterized_request_type` — the type argument of `Bidder<T>`. Default `BidRequest`. Custom values: `MediasquareRequest` (Mediasquare), `HuaweiAdsRequest` (Huaweiads). Edge case #28.
   - `parameterized_response_type` — typically null. Populated only for the rare adapters that parameterize a custom response (edge case #28 second leg).
2. `override_methods[]` — locate every method annotated `@Override`. Typically `[makeHttpRequests, makeBids]`. Adapters that delegate via `BidderUtil.defaultRequest` may collapse `makeHttpRequests` to a thin wrapper but still list it here.
3. `constructor.arity` — count of parameters in the public constructor.
4. `constructor.parameters[]` — for each parameter, record `{ name, type, source, role }`:
   - `source` is FREE-TEXT carrying the lambda-binding expression verbatim. Common shapes observed in goldens: `"config.endpoint"`, `"config.xapi.username"`, `"config.devEndpoint"` (dotted path into a `BidderConfigurationProperties` getter), `"framework-injected"` (autowired Spring bean — `currencyConversionService`, `mapper`, `idGenerator`), `"@Value(${external-url})"` (Spring property injection), `"factory-constant"` (Rubicon `bidderName`), `"factory-instantiated (new UUIDIdGenerator())"` (factory creates fresh instance), `"config.generateBidId (defaults true)"` (annotated-with-default narrative). Round-trip preserves the verbatim string.
   - `role ∈ {properties, helper-collaborator, framework-injected, authentication-input}`. `properties` when the parameter is a config-derived String/primitive; `helper-collaborator` when it is a domain helper (`CurrencyConversionService`, `JacksonMapper`, `IdGenerator`, `Clock`, `BidderUtil`); `framework-injected` for everything else autowired but neither config nor a known helper; `authentication-input` for parameters whose sole purpose is to feed a pre-built basic-auth or HMAC-digest header (canonical: Rubicon `xapiUsername`, `xapiPassword`).
   - The standard collaborator catalog (`JacksonMapper`, `CurrencyConversionService`, `IdGenerator`, `Clock`, `BidderUtil`) lives in [references/spring-config-patterns.md](references/spring-config-patterns.md#standard-collaborators).
5. `static_fields[]` — class-level constants: TypeReferences (`KOBLER_EXT_TYPE_REFERENCE`), default-currency strings (`DEFAULT_BID_CURRENCY`), ext-key strings (`EXT_PREBID`). Record `{ name, type, value? }`. The `value` is a **verbatim field** under V1 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4): copy the initializer text out of the fetched bytes (`<fetch> | sed -n '<start>,<end>p'`) and keep the source file's reference (`{ path, resolved_commit, sha256, bytes }`) so the value stays re-derivable. Do not normalize a currency literal, expand a generic parameter, or reconstruct a constant from its name.
6. `helper_classes_co_located[]` — non-bidder classes co-located in `bidder/{xyz}/` (e.g., `MediasquareUtil`, `KueezExtractor`).
7. `helper_classes_in_proto[]` — DTO classes in `proto/openrtb/ext/request/{xyz}/` (e.g., `ExtImpKobler`, plus any helper proto types like `MediasquareCode`, `HuaweiAdsRequestExt`).

### Step 3 — Extract `spring_config.*`

From `src/main/java/org/prebid/server/spring/config/bidder/{Xyz}Configuration.java` (the Spring factory class — lives OUTSIDE the bidder package and is therefore NOT recorded in `code.file_layout.files[]`; locate it by canonical path). Apply the extraction rules at [references/spring-config-patterns.md](references/spring-config-patterns.md) (the canonical home — factory class shape, `BidderConfigurationProperties` subclass detection per edge case #20, bean dependencies + standard collaborator catalog, Lombok annotation recognition, plus worked examples).

Per-step output fields:

1. `factory_class` — naming variance per edge case #19 (`<Name>Configuration` vs `<Name>BidderConfiguration`). Record verbatim.
2. `factory_method` — `@Bean` method returning `BidderDeps` (e.g., `koblerBidderDeps`).
3. `property_source_path` — `@PropertySource` value (canonical: `classpath:/bidder-config/{xyz}.yaml`).
4. `bidder_creator_lambda` — verbatim lambda body from `BidderDepsAssembler.bidderCreator(...)`. Round-trip fidelity load-bearing for porters; preserve indentation, line breaks, and constructor argument order. This is a **verbatim field** under V1 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4): extract the byte span from the fetched `{Xyz}Configuration.java` (`<fetch> | sed -n '<start>,<end>p'`), keep that file's reference (`sha256` + `bytes`) in the spec so the span is re-derivable, and choose the YAML encoding with the V3 probe instead of defaulting to a literal block. Do not retype the lambda from the constructor signature.
5. `configuration_properties_class.*` — populated when the factory declares a `BidderConfigurationProperties` subclass; `null` otherwise. See references doc for the full sub-field shape (name, extends, extra_fields[] with verbatim `@Validation` annotations, nested_classes[], lombok_annotations[]).
6. `bean_dependencies[]` — every `@Autowired` constructor parameter or `@Value(${...})` injection on the factory method. Record `{ name, type, source }` per the [Bean dependencies extraction](references/spring-config-patterns.md#bean-dependencies-extraction) section.

### Step 4 — Classify `code.make_requests.*`

Locate `makeHttpRequests(BidRequest bidRequest)`. Apply the cross-language taxonomy from [`../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml):

- **`batching.rules[]`** — same enum as Go (`single-batched, per-imp, max-imps-per-request, format-split, deals-split, pod-grouping, imp-flatten-aggregate, filtered-subset, grouped-by-key`); set `applied_in_order: true`.
- **`request_body.kind`** — `openrtb2-passthrough | openrtb2-modified | custom`; when `custom`, set `custom_body_type` to match `bidder_class.parameterized_request_type` (Mediasquare's `MediasquareRequest`).
- **`mutation.entity_strategies`** — same enum as Go; Java adapters typically emit `immutable-rebuild` (Lombok `toBuilder().build()`) for OpenRTB entities. **`mutation.java_idiom`** — `lombok-tobuilder` default; `flexible-extension-fillExtension` for `FlexibleExtension` subclasses. `mutation.go_idiom` stays null.
- **`imp_ext_unmarshal.kind`** — `standard-two-phase` default; **`mechanism_java`** — `typeref-extprebid` canonical (`TypeReference<ExtPrebid<?, ExtImp{Xyz}>>`), `typeref-custom-wrapper` (Appnexus's `AppnexusExtImp`), `direct-class`, or `null`.
- **`endpoint_resolution.{kind, mechanism_java}`** — kinds match Go; Java mechanisms are `string-replace`, `URIBuilder`, `custom-resolver-class`, `null`. Populate `macro_field_set[]`.
- **`helpers[]`** — every private method on the bidder class (excluding `makeHttpRequests`/`makeBids`); record `{ name, signature }`. `signature` is a **verbatim field** under V1 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4): copy the declaration line from the fetched bytes (`<fetch> | grep -n 'private .*<name>('`), against the file reference recorded in `code.file_layout.files[]`. Do not reconstruct a signature from the call site, drop a modifier, or shorten a generic type.

### Step 5 — Classify `code.make_bids.*`

Locate `makeBids(BidderCall<BidRequest> httpCall, BidRequest bidRequest)`:

- **`response_type`** — `BidResponse` canonical; or `custom` with `custom_response_type` (Mediasquare's `MediasquareResponse`).
- **`http_status_handling.kind`** — Java enum: `framework-default`, `framework-default-plus-empty-seatbid-shortcircuit` (canonical guard), or `custom-status-checks`. Go-only values (`canonical-go-helpers`, `legacy-raw-go`) never set.
- **`application_status_handling.kind`** — `none` default; `retcode-field` when adapter checks an in-body status (Huaweiads `retcode`); populate `field, success_codes, error_codes`.
- **`bid_type_resolution.method_chain[]`** — same enum as Go; each step `{ method, field?, hardcoded_value?, fallback_action: next | return-default | throw }`. Populate `default_value` for `return-default`. `multi_format_detection: strict | lenient | none`.
- **`bid_pointer_pattern`** — Java almost always `flatten-streams`; `bid_pointer_go_sibling` stays null.
- **`currency_overwrite_safety`** — Java canonical `passthrough-from-response` (`BidderBid.of(bid, type, bidResponse.getCur())`).

### Step 6 — Extract `iab_category_storage.*`

Set `storage_kind`: `yaml-inlined` (Java pattern, Appnexus `iab-categories`, edge case #21), `none` (typical: Kobler, Optidigital), or `dynamic-fetched` (rare). `go-data-table` is Go-only. When `yaml-inlined`, populate `yaml_field`, `table_size`, and `delivery_mechanism: constructor-arg | static-init` (the field is `delivery_mechanism` per ADR-001 D2). The YAML evidence is provided by `read-bidder-config` via orchestrator-merged `bidder_info.yaml_extra_fields`.

`table_size` is a computed value (V4 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)) — count the entries in the YAML block, do not carry over a cardinality from a review comment or a sibling spec:

```bash
<fetch bidder-config/{xyz}.yaml> | awk '/^[[:space:]]*iab-categories:/{f=1;next} f&&/^[[:space:]]*[a-z-]+:[[:space:]]*$/{exit} f' | grep -c ':'
```

For appnexus at master this prints 95, matching both appnexus goldens. Rule 42 makes the cardinality a cross-language fidelity invariant, so an asserted number that was never counted breaks the Go↔Java comparison silently.

### Step 7 — Extract `ext_pojo_construction.*`

From the param-ext POJO at `proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` (recorded in `file_layout.files[]` with role=`models` per the heuristics doc; located by canonical path) plus any sibling `proto/{Xyz}*Ext{Imp,Bid,Req}*.java` files in the bidder package (also role=`models`):

- **`framework_choice`** — `lombok-value-builder` (`@Value @Builder @Jacksonized`, default), `lombok-value-staticconstructor` (Kobler's `@Value(staticConstructor = "of")`), `lombok-data` (rare). `go-struct` never set.
- **`flexible_extension_used`** — true when the class extends `FlexibleExtension` (`@JsonAnyGetter`/`@JsonAnySetter` passthrough).
- **`custom_unmarshal.kind`** — `none` default; `jackson-jsondeserialize` (paired with `<Xyz>Deserializer`), `jackson-jsonalias-only` (Appnexus `@JsonAlias`), `runtime-isobject-isarray-branching` (runtime shape branch). `go-unmarshaljson` never set; `custom` REQUIRES a quirk.
- **`custom_unmarshal.{accepts_shapes[], where_branched}`** — `where_branched`: `bidder-class | jsondeserializer-class | type-method | null`.

Annotation catalog (verbatim Lombok + Jackson signatures): [`references/proto-pojo-patterns.md`](references/proto-pojo-patterns.md).

### Step 8 — Extract `currency_conversion.*`

Set `used: true` when a `CurrencyConversionService` constructor parameter is present AND invoked. `helper.java_signature` is verbatim (Java has 4 args including `bidRequest` for time-context — the canonical cross-language asymmetry vs Go's 3-arg `reqInfo.ConvertCurrency`). `injection: dependency` always (Java is always DI; `function-arg` is Go-only). `bid_request_passed_for_context: true` always on Java; surfaces as quirk `currency-conversion-bidrequest-context` for cross-language port comparison.

### Step 9 — Extract `headers_constructed.*`

`pre_built_in_constructor: true` when the constructor pre-computes a header (Rubicon `authHeader` basic-auth pattern); else false. `per_request_dynamic: true` always (Java invokes `HttpUtil.headers()` per request even when no customization). `custom_headers[]` is the literal headers beyond `HttpUtil.headers()` defaults. `authentication_kind: none | basic-auth | bearer-token | hmac-digest | custom`. `authentication_input[]` lists the YAML/config field paths used to compute the auth value.

**ADR-007 F2 (`language_stamped_headers[]`)**: set `language_stamped: true` and populate `language_stamped_headers[]` with `{ name, go_value, java_value, rationale }` per item when the adapter emits a header whose VALUE differs by language. Master sample: `freewheelssp` emits `Componentid: prebid-java` (Java) ↔ `prebid-go` (Go) — same header name, different value, byte-asymmetric outbound. Both sides record the same `language_stamped_headers[]` array (per-side spec carries the full cross-language pair so cross-language consumers can diff without consulting the other-language spec). One-sided header additions (Java emits a header Go doesn't, e.g., `aduptech` Java's lone `Componentid: prebid-java` with no Go counterpart) are NOT F2 — record them as quirks instead per ADR-007's footnote on one-sided header mutations.

### Step 10 — Inventory `tests:`

**Unit tests** (`*Test.java` files; NOT recorded in `code.file_layout.files[]` — see [`references/file-role-heuristics.md`](references/file-role-heuristics.md) "Multi-file detection" for the layout/test split): `tests.test_root_directory: src/test/java/org/prebid/server/bidder/{xyz}/`. `uses_canonical_harness: true` when the test class extends `VertxTest` (Java's `RunJSONBidderTest` analog); `false` triggers a `legacy-test-helpers-imported` quirk + warning (R10). `unit_test_methods_count` and `unit_test_loc` are computed values (V4 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)) — record each command's stdout:

```bash
<fetch {Xyz}BidderTest.java> | grep -c '^[[:space:]]*@Test'   # unit_test_methods_count
<fetch {Xyz}BidderTest.java> | wc -l                          # unit_test_loc
```

`hand_written_test_methods[]` lists method names in declaration order, and its length must equal the `grep -c` output; a mismatch means the listing missed a method — re-extract the names rather than editing the count. Detailed regex / naming conventions: [`references/junit-it-patterns.md`](references/junit-it-patterns.md).

**Integration tests** (`*IT.java` files; NOT recorded in `code.file_layout.files[]`): `integration_test_class` is the parent IT class (per-alias IT classes go into `aliases[].test_assets`). `integration_test_pattern: 4-file-split` (canonical Wiremock: bid-request + bid-response + auction-request + auction-response), `6-file-with-cache`, `multi-folder` (Rubicon), or `none`. `fixture_inventory.integration[]` records each fixture-file `{ filename, sha256, bytes, role }` where `role ∈ {bidder-bid-request, bidder-bid-response, auction-request, auction-response}` (per-fixture role; distinct from the file-level `role` enum). `sha256` and `bytes` are mandatory in all three `--fixture-mode` values, including `verbatim`, and both come from the fetch pipe rather than from the inlined body (V1/V2 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)). Folder convention: `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/`; deviations populate `java_it_folder_naming` (`canonical | suffix-augmented | multi-folder | custom`).

### Step 11 — Per-alias IT class set + naming workarounds

When `inputs.parent_aliases` is non-empty (edge case #24), each alias requires its own IT class + 4-file fixture set. Populate `aliases[].test_assets.{it_class, fixture_dir, fixture_file_count}` per alias; missing IT triggers `incomplete-classification` quirk.

Top-level `code_naming` block records the Java class-naming workarounds:
- Digit-leading rename (#26): `code_naming.{yaml_name, class_name_root, identifier_workaround: digit-leading-rename}` + quirk `identifier-rule-workaround`. Example: `152media → OneFiveTwoMedia`.
- Acronym-case preservation (#27): `code_naming.preserves_acronym_case: true` + quirk `acronym-case-preservation` only when casing diverges from strict TitleCase. Examples: `ElementalTV`, `FeedAd`, `BidTheatre`.

### Step 12 — Registry append count

The registry file is `src/test/resources/org/prebid/server/it/test-application.properties` — its location both on current master and at the Phase A-4 pinned commit `69b1993c`, where `src/test/resources/test-application.properties` does not exist. Resolve the path at the read's own commit rather than assuming either form. `tests.test_application_properties_entries_added` is a computed value (V4 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)) — the stdout of:

```bash
<fetch src/test/resources/org/prebid/server/it/test-application.properties> | grep -c '^adapters\.{xyz}\.'
```

Canonically 2–4 lines per bidder (`enabled=true`, `endpoint=...`, plus per-alias variants); for kobler at master the command prints 2. Per-alias detail goes under `aliases[].test_application_properties_entries[]` as `{ key, value, line }`, whose length must equal the counted total. A zero count when an IT class exists triggers `incomplete-classification` — and a zero that came from grepping the wrong path is an instrument failure, not a finding: confirm the file exists at the resolved commit first.

### Step 13 — Emit `quirks[]` and populate `cross_language.*`

For unclassifiable patterns from Steps 4–12, add `quirks[]` entries. Every `custom` value REQUIRES a quirk (R3). `edge_case_taxon` MUST be from the registry at [`../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml).

Densely populate `cross_language.java_specific_concerns[]` with port-fidelity observations (Kobler Java golden's 9-entry list is the model). Examples: bean-construction URL validation, static `TypeReference<ExtPrebid<?, ExtImp{Xyz}>>` at class init, `BidderUtil.defaultRequest` collapsing what Go expands inline, empty-seatbid shortcircuit ordering, stream-pipeline `Objects::nonNull` filters with no Go counterpart. Set `cross_language.go_specific_concerns: []`.

Populate `cross_language.port_concerns`: `multi_file_layout` from Step 1; `package_directory_mismatch` true when `directory_name ≠ lowercase(bidder_class.name minus Bidder suffix)` (#26/#27 are typed under `code_naming`, NOT mismatches); `custom_unmarshaljson_present` true when proto-ext classes declare `@JsonDeserialize` / extend `JsonDeserializer<T>`; `mutation_idiom_divergence: true` whenever Java mutates via `lombok-tobuilder`; `yaml_unification: true` always for Java; `aliases_inverted` from `read-bidder-config`.

Populate `cross_language.java_artifacts`: `bidder_dir: src/main/java/org/prebid/server/bidder/{xyz}/`, `bidder_class: <Name>Bidder`, `config_class: <Name>Configuration | <Name>BidderConfiguration` (#19), `yaml_path: src/main/resources/bidder-config/{xyz}.yaml`, `proto_dir: src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/`.

Stub `cross_language.go_artifacts` with path hints (`bidder_dir: adapters/{xyz}/`, `package_name: {xyz}` lowercase, `bidder_constant: openrtb_ext.Bidder<X>` looked up verbatim from Go-side `bidders.go` when available — do NOT derive). Emit `reviewer_cohort: null` — the field is inert (no skill may key a check on reviewer identity, per [`../../../../prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md`](../../../../prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md)) and is slated for removal in the next schema major.

## Edge case mapping (Java cases #18–#34)

Full 17-case catalog with field mappings, master samples, and owner skills: [`../../../references/java-edge-cases.md`](../../../references/java-edge-cases.md). This skill owns #18–#28 (Spring/Java patterns); #29–#34 are owned by `read-bidder-config`. None require `custom`+quirks fallback.

## Cross-language note

Review expectations do not carry between the two repos; the transfer ban is canonicalized at [`../../../../prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md`](../../../../prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md). Two consequences for `read-bidder-class` output:

1. Port-fidelity is a live review theme on Java adapter PRs that port from Go ("I don't see that in Go" is a common blocker), and it is structurally asymmetric — the Go side of the same port has nothing to be faithful to. Populate `cross_language.java_specific_concerns[]` densely; the Kobler Java golden's 9-entry list is the model.
2. Review-pattern matchers MUST NOT auto-transfer between languages, and no output field may be used to key a check on reviewer identity. `cross_language.reviewer_cohort` is inert and slated for removal in the next schema major.

## Verification

The Java Kobler golden ([`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml)) is the proof-of-concept output: currency conversion, dev-prod toggle, `BidderConfigurationProperties` subclass with `@NotBlank devEndpoint`, 14 hand-written `@Test` methods, 4-file Wiremock IT fixture set, 5 quirks, 9 `java_specific_concerns[]`. A reader following this SKILL produces output that matches byte-for-byte modulo `provenance.read.timestamp_utc` (R4).

Appnexus is the complexity-high spot-check: `iab_category_storage.{storage_kind: yaml-inlined, table_size: 95 (counted per Step 6, not asserted), delivery_mechanism: constructor-arg}`; custom `AppnexusExtImp` wrapper; `runtime-isobject-isarray-branching` keywords field; 2-step `batching.rules` (max-imps + pod-grouping). Full Appnexus golden is the canonical Phase 2 fixture.

## Sources

- Schema: [`../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json`](../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json), [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md).
- Taxonomy: [`../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml).
- Port rules (46 Go↔Java rules): [`../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml). Reference rule numbers in `cross_language.java_specific_concerns[]` text.
- Java edge cases #18–#34 catalog: [`../../../references/java-edge-cases.md`](../../../references/java-edge-cases.md).
- Java reference PRs: [`../../../references/new-bid-adapter-prs.md`](../../../references/new-bid-adapter-prs.md).
- Local references: [`references/spring-config-patterns.md`](references/spring-config-patterns.md), [`references/proto-pojo-patterns.md`](references/proto-pojo-patterns.md), [`references/junit-it-patterns.md`](references/junit-it-patterns.md).
- Goldens: [`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) (Java) + [`../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../../../prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml) (Go counterpart for cross-language alignment).
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
