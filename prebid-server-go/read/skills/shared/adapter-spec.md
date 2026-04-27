# Adapter Specification (canonical schema)

The canonical YAML schema for prebid-server adapter specifications. Language-neutral at the behavioral level with explicit per-language sub-blocks for divergences. Consumed by all read skills (Go and Java), the future `write/` skill, and the future `port-go2java` / `port-java2go` skills. Two specs for the same bidder produced from each language MUST agree on cross-language fields (`bidder_params_json` byte-identical, `bidder_info.capabilities`, `params.schema_interpretation`) and MAY differ only on language-specific blocks.

---

## Versioning policy

`adapter_spec_version` is a single integer that follows semver-major rules: bumped only when the schema breaks downstream consumers (a field renamed, a default value changed, a required field added). Additive changes (new optional field, new enum value with a `custom` fallback already in place) do NOT bump the version. Current version: `1`.

A reader skill MUST emit the version it produced. A consumer (write, port) MUST refuse a version higher than its own and SHOULD warn on a lower version.

---

## Top-level structure

```yaml
adapter_spec_version: 1
spec_kind: prebid-server-adapter              # Reserved for future spec kinds.
source_language: go | java                    # Which read-skill produced this spec.

provenance:                                   # Read-time identity.
  source:
    repo: prebid/prebid-server | prebid/prebid-server-java
    ref: { branch: master | commit: SHA | pr: N | tag: vX.Y.Z }
    resolved_commit: SHA                      # ALWAYS populated; spec is frozen at this commit.
    fetch_method: github-raw | local-checkout | gh-cli
  read:
    skill_versions: { orchestrator: 1.0.0, ... }
    timestamp_utc: ISO8601
    operator: claude-code/<model-id>
  warnings: []                                # Non-blocking read-time anomalies (see warnings schema below).

meta:                                         # Static identity facts.
  bidder_name: kobler
  is_alias: false
  alias_of: null                              # Go: child→parent. Java's alias inversion handled in cross_language.
  parent_aliases: []                          # If THIS bidder is a parent, list child aliases.
  whitelabel_only: false
  disabled: false
  module_path_major: v4                       # Go-only.
  java_artifact_version: null                 # Java-only.

bidder_info:                                  # Owned by read-bidder-info / read-bidder-config.
  endpoint: ...
  endpoint_construction:
    kind: static | template-macro | url-with-query | dev-prod-toggle | hardcoded-toggle | runtime-region-selection | deploy-time-token | custom
    macros_used: []                           # Subset of macros.EndpointTemplateParams (Go) or Java macro list.
    placeholders_unresolved: []               # Non-template tokens (e.g., #{REGION}#) — also surfaced via deploy_time_tokens.
  endpoint_compression: gzip | null
  ortb_version: "2.6" | null                  # Java-quoted-string; Go does not declare.
  default_enabled: true                       # `enabled:` from YAML, default true if absent.
  modifying_vast_xml_allowed: false
  maintainer: { email: ... }
  capabilities:
    site: { mediaTypes: [...] }
    app: { mediaTypes: [...] }
    dooh: { mediaTypes: [...] }
  geoscope: []
  gvl_vendor_id: 12345
  user_sync: { ... }                          # Verbatim subtree (Go layout).
  yaml_extra_fields: {}                       # Anything outside the canonical field index, preserved verbatim.
  yaml_field_name_quirks: []                  # E.g., `endpointCompression` vs `endpoint-compression` typo regression.

bidder_params_json: |                         # VERBATIM BYTES of static/bidder-params/{xyz}.json.
  {"$schema":"http://json-schema.org/draft-04/schema#",...}
bidder_params_sha256: 125fef34...             # Cross-language contract: Go sha == Java sha for the same bidder.

params:
  schema_interpretation:
    properties: [...]                         # Normalized field list.
    required_fields: []
    flexible_types: []                        # Fields with type ["integer","string"] etc.
    combinators_used: []                      # oneOf | anyOf | not | oneOf-of-oneOf | json-aliases-present.
  ext_struct:
    package: openrtb_ext | org.prebid.server.proto.openrtb.ext.request.xyz
    file: ...
    type_name: ExtImpKobler
    fields:
      - name: Test
        json_tag: test
        type_native: bool | Boolean
        omitempty: true
        notes: []
    custom_unmarshal: false
    custom_unmarshal_accepts: []
  params_test:
    file: ...
    valid_cases_count: 3
    invalid_cases_count: 8
    bidder_constant_referenced: openrtb_ext.BidderKobler

code:                                         # Owned by read-adapter-code / read-bidder-class.
  package_or_class: kobler | KoblerBidder
  directory_name: kobler
  package_directory_mismatch: false           # Go edge-case 1.
  file_layout:
    kind: single-file | multi-file
    files: [{ name: ..., role: implementation|types|parsers|utils|models|data-table, loc: N }]
  imports:
    has_template_engine: false
    has_currency_helper: true
    has_jsonutil: true                        # Go-specific; Java uses JacksonMapper.
    third_party: []
  adapter_struct:                             # Go shape; Java uses bidder_class instead.
    type_name: adapter
    type_visibility: unexported | exported
    fields: [{ name: endpoint, type: string }, ...]
  builder:                                    # Go-only. Java construction lives in spring_config.
    signature_canonical: true
    extra_adapter_info_used: false
    template_parsed_at_build: false
    errors_returned: []
  make_requests:
    batching:
      applied_in_order: true
      rules: []                               # Ordered list of rule kinds; see behavior-taxonomy.md.
    request_body:
      kind: openrtb2-passthrough | openrtb2-modified | custom
      custom_body_type: null
    mutation:
      mutates_request: true
      entity_strategies:                      # Map of entity → strategy.
        Site: copy-then-mutate | none
        App: ...
        Source: ...
        Imp: in-place | immutable-rebuild
        Banner: ...
        Device: in-place
      go_idiom: ptrutil.Clone | shallow-copy | direct-pointer-mutation | none
      java_idiom: lombok-tobuilder | flexible-extension-fillExtension | none
    imp_ext_unmarshal:
      kind: standard-two-phase | direct | none | custom
      mechanism_go: jsonutil-two-phase | null
      mechanism_java: typeref-extprebid | typeref-custom-wrapper | direct-class | null
      target_type: openrtb_ext.ExtImpKobler | ExtImpKobler
      wrapper_type: null                      # E.g., AppnexusExtImp; null when standard.
    endpoint_resolution:
      kind: static | single-token-substitution | multi-token-substitution | query-parameter-augmentation | runtime-region-selection | deploy-time-token | dev-prod-toggle | custom
      mechanism_go: text/template | macros.NewStringIndexBasedReplacer | net/url | string-concat | null
      mechanism_java: string-replace | URIBuilder | custom-resolver-class | null
      macro_field_set: []
      template_params_struct_field_count: null
    helpers: [{ name, signature }]
  make_bids:
    response_type: openrtb2.BidResponse | custom
    custom_response_type: null
    http_status_handling:
      kind: framework-default | framework-default-plus-empty-seatbid-shortcircuit | custom-status-checks | canonical-go-helpers | legacy-raw-go
    application_status_handling:
      kind: none | retcode-field | custom-body-flag
      field: null                             # E.g., "retcode" for Huaweiads.
      success_codes: []
      error_codes: []
    bid_type_resolution:
      method_chain: []                        # Ordered chain; see behavior-taxonomy.md.
      default_value: banner | null
      multi_format_detection: strict | lenient | none
    bid_pointer_pattern: indexed-iteration | pointer-iteration | flatten-streams
    bid_pointer_go_sibling: indexed-seatbid | range-value-pointer | null
    currency_overwrite_safety: guarded | unguarded | unguarded-hardcoded | passthrough-from-response | none

tests:                                        # Owned by read-adapter-code (Go) / read-bidder-class (Java).
  test_root_directory: koblertest
  go_directory_naming: canonical | legacy-test | custom
  java_it_folder_naming: canonical | suffix-augmented | multi-folder | custom
  fixture_inventory:
    exemplary: [{ filename, sha256, bytes }]
    supplemental: [...]
    amp: [...]
    video: [...]
    videosupplemental: [...]
    integration: []                           # Java 4-file split: request/response/auction-request/auction-response.
  uses_canonical_harness: true                # Go: RunJSONBidderTest. Java: VertxTest pattern (the canonical harness IS VertxTest on Java).
  unit_test_methods_count: null               # Java JUnit count; null on Go.
  unit_test_loc: null                         # Java only.
  hand_written_test_methods: []               # Java JUnit method names.
  fixture_handling: count-only | summary | verbatim
  test_application_properties_entries_added: 0  # Java-only registry append count.
  integration_test_class: KoblerTest          # OPTIONAL, Java-only. Java IT class name (no path; located under src/test/java/org/prebid/server/it/).
  integration_test_pattern: 4-file-split | 6-file-with-cache | multi-folder | none  # OPTIONAL. Layout pattern for integration test fixtures (file count and folder shape). The fixture filenames themselves live in fixture_inventory.integration[].

spring_config:                                # Java-only; null on Go.
  factory_class: KoblerConfiguration
  factory_method: koblerBidderDeps
  property_source_path: classpath:/bidder-config/kobler.yaml
  bidder_creator_lambda: |                    # Verbatim lambda body for round-trip fidelity.
    cfg -> new KoblerBidder(cfg.getEndpoint(), cfg.getDevEndpoint(), currencyConversionService, mapper)
  configuration_properties_class:
    name: KoblerConfigurationProperties
    extends: BidderConfigurationProperties
    extra_fields:
      - name: devEndpoint
        type: String
        validations: [NotBlank]
    nested_classes: []
    lombok_annotations: [Data, EqualsAndHashCode, NoArgsConstructor]
  bean_dependencies:
    - { name: currencyConversionService, type: CurrencyConversionService }
    - { name: externalUrl, type: String, source: "@Value(${external-url})" }
    - { name: mapper, type: JacksonMapper }

bidder_class:                                 # Java-specific shape; Go uses code.adapter_struct.
  name: KoblerBidder
  parameterized_request_type: BidRequest
  parameterized_response_type: null           # Most adapters use the default; non-null for Mediasquare's custom payload.
  override_methods: [makeHttpRequests, makeBids]
  constructor:
    arity: 4
    parameters:
      - { name: endpointUrl, type: String, source: config-field, role: properties }
      - { name: devEndpoint, type: String, source: config-field, role: properties }
      - { name: currencyConversionService, type: CurrencyConversionService, source: framework-injected, role: helper-collaborator }
      - { name: mapper, type: JacksonMapper, source: framework-injected, role: helper-collaborator }
  static_fields:
    - { name: KOBLER_EXT_TYPE_REFERENCE, type: TypeReference }
    - { name: DEFAULT_BID_CURRENCY, type: String }
    - { name: EXT_PREBID, type: String }
  helper_classes_co_located: []
  helper_classes_in_proto: [ExtImpKobler]

iab_category_storage:                         # Replaces boolean iab_category_lookup.
  storage_kind: yaml-inlined | go-data-table | dynamic-fetched | none
  yaml_field: null                            # E.g., "iab-categories" for Appnexus Java.
  go_data_file: null                          # E.g., "iab_categories.go" for MSFT Go.
  table_size: null
  injection: constructor-arg | static-init | null

ext_pojo_construction:                        # Cross-language; describes how ExtImp{Xyz} is shaped.
  framework_choice: lombok-value-builder | lombok-data | lombok-value-staticconstructor | go-struct
  flexible_extension_used: false              # Java FlexibleExtension @JsonAnyGetter/Setter.
  custom_unmarshal:
    kind: none | go-unmarshaljson | jackson-jsondeserialize | jackson-jsonalias-only | runtime-isobject-isarray-branching
    accepts_shapes: []
    where_branched: bidder-class | jsondeserializer-class | type-method | null

currency_conversion:                          # Cross-language consolidation of currency fields.
  used: true
  helper:
    go_signature: "reqInfo.ConvertCurrency(value, from, to) (float64, error)"
    java_signature: "currencyConversionService.convertCurrency(value, bidRequest, from, to) BigDecimal"
  injection: dependency | function-arg
  bid_request_passed_for_context: false       # Java passes bidRequest for time-context; Go does not.

headers_constructed:
  pre_built_in_constructor: false             # E.g., Rubicon basic-auth header pre-built.
  per_request_dynamic: true
  custom_headers: []                          # E.g., "Content-Type: application/json;charset=utf-8".
  authentication_kind: none | basic-auth | bearer-token | hmac-digest | custom
  authentication_input: []                    # E.g., ["XAPI.Username","XAPI.Password"] for Rubicon.

deploy_time_tokens: []                        # E.g., [{ token: REGION, file: rubicon.yaml, notes: "operator substitutes pre-deployment" }].

quirks:                                       # Free-text bucket with optional taxon.
  - id: ...
    file: ...
    summary: ...
    edge_case_taxon: see behavior-taxonomy.md "quirks edge_case_taxon (full registry)" for the canonical list of ~22 registered taxa

cross_language:
  go_artifacts:
    bidder_dir: adapters/kobler/
    package_name: kobler
    bidder_constant: openrtb_ext.BidderKobler
  java_artifacts:
    bidder_dir: src/main/java/org/prebid/server/bidder/kobler/
    bidder_class: KoblerBidder
    config_class: KoblerConfiguration
    yaml_path: src/main/resources/bidder-config/kobler.yaml
    proto_dir: src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/
  port_concerns:
    aliases_inverted: true
    yaml_unification: true
    mutation_idiom_divergence: true           # Go-pointer vs lombok-tobuilder.
    package_directory_mismatch: false
    multi_file_layout: false
    custom_unmarshaljson_present: false
  go_specific_concerns: []                    # Free-text list (Go-only quirks the porter must address): port-fidelity issues that don't translate cleanly to Java. Populated dense in Go-source spec; sparse/empty in Java-source spec.
  java_specific_concerns: []                  # Same shape, mirror semantics for Java.
  port_lineage:
    source_language: go
    source_pr: prebid/prebid-server#3904
    destination_language: java
    destination_pr: prebid/prebid-server-java#3684
    fidelity_review_themes: [port-fidelity, currency-conversion-divergence]
  reviewer_cohort:
    go: [bsardo, SyntaxNode, hhhjort]
    java: [CTMBNara, AntoxaAntoxic, EmilNadimanov, sangarbe, osulzhenko]
    cross_language_coordinator: bretg
```

---

## Per-section field reference

### `provenance`

| Field | Type | Required | Description |
|---|---|---|---|
| `source.repo` | string | yes | One of `prebid/prebid-server`, `prebid/prebid-server-java`. |
| `source.ref` | object | yes | Exactly one of `branch`, `commit`, `pr`, `tag`. |
| `source.resolved_commit` | string (40-char SHA) | yes | Always populated; spec is frozen at this commit. |
| `source.fetch_method` | enum | yes | `github-raw`, `local-checkout`, `gh-cli`. |
| `read.skill_versions` | object | yes | Map of skill name → semver. |
| `read.timestamp_utc` | ISO8601 string | yes | Excluded from round-trip determinism comparison. |
| `read.operator` | string | yes | E.g., `claude-code/opus-4-7`. Excluded from determinism comparison. |
| `warnings` | array | yes | Empty array if no anomalies. See warnings schema below. |

**Warnings schema** — each entry is `{ type, file, line, summary }`. Known types: `bidder-constant-mismatch`, `yaml-field-name-typo`, `package-directory-mismatch`, `endpoint-placeholder-unresolved`, `legacy-test-helpers-imported`, `module-major-drift`. The Kobler test file emits a `bidder-constant-mismatch` warning because `kobler_test.go:12` references `openrtb_ext.BidderKargo` (copy-paste artifact) — see worked example below.

### `meta`

| Field | Type | Required | Description |
|---|---|---|---|
| `bidder_name` | string | yes | All-lowercase or snake_case directory name. |
| `is_alias` | bool | yes | True if this bidder has no implementation, only a YAML referencing a parent. |
| `alias_of` | string | yes (null if not alias) | Parent bidder name. |
| `parent_aliases` | array | yes | If THIS is a parent, list child aliases. |
| `whitelabel_only` | bool | yes | YAML `whiteLabelOnly` field. |
| `disabled` | bool | yes | YAML `disabled` field. |
| `module_path_major` | string \| null | yes | E.g., `v4`. Null on Java specs. |
| `java_artifact_version` | string \| null | yes | E.g., `3.41.0`. Null on Go specs. |

### `bidder_info`

The YAML-derived metadata. Field-by-field structure follows the `BidderInfo` Go struct (see `review/skills/bidder-info-pr-review/references/field-index.md`). Key cross-language differences:

- `endpoint_compression` (Go: `endpointCompression`, Java: `endpoint-compression`) — both feed the same field; if YAML uses the wrong style for the language, surface as `yaml_field_name_quirks` entry.
- `ortb_version` is Java-only (quoted string `"2.6"` in YAML); Go specs always emit null.
- `default_enabled` defaults to `true`; Java's `enabled: false` opt-in pattern (Optidigital, Adverxo aliases) flips this to `false`.
- `modifying_vast_xml_allowed` is a recent Java-side addition (FeedAd, Mediasquare).

### `bidder_params_json` (verbatim) + `bidder_params_sha256`

The cross-language contract. The exact bytes of `static/bidder-params/{xyz}.json` (Go) and `src/main/resources/static/bidder-params/{xyz}.json` (Java) MUST be byte-identical for the same bidder.

**SHA verification process:**

1. Read the file in binary mode (preserve trailing newlines, BOM, encoding).
2. Compute SHA-256 of the raw bytes.
3. Emit BOTH `bidder_params_json` (verbatim string) AND `bidder_params_sha256`.
4. When two specs (one Go, one Java) reference the same bidder, the SHAs MUST match. A diff in SHA is a port-fidelity violation and surfaces as a port-translation rule failure.

The verbatim JSON makes the spec round-trippable: a `write/` skill can reconstruct the file byte-for-byte from the spec without re-parsing.

### `params`

Three sub-blocks:

- `schema_interpretation` — normalized JSON Schema interpretation. `properties` lists every field name + type + description. `combinators_used` enumerates which JSON Schema combinators appear (`oneOf`, `anyOf`, `not`, `oneOf-of-oneOf`, `json-aliases-present`). Identical across Go and Java specs of the same bidder.
- `ext_struct` — the language-specific POJO/struct backing the params. `fields[]` lists each field with native type and JSON tag/annotation. `custom_unmarshal` flags non-default unmarshaling (Go `UnmarshalJSON`, Java `@JsonDeserialize`).
- `params_test` — the unit-test file metadata: `valid_cases_count`, `invalid_cases_count`, and `bidder_constant_referenced`. The latter is load-bearing: a mismatch between this constant and the actual bidder name surfaces as a `bidder-constant-mismatch` warning.

### `code`

The heaviest section. Organized as:

- `package_or_class` (Go: package name; Java: class name) and `directory_name`.
- `package_directory_mismatch` — Go edge case 1 (33across vs ttx). Java equivalent: `directory_name == bidder_class.toLowerCase()` should hold; failure flags a TitleCase-acronym preservation case.
- `file_layout` — `kind` is `single-file` (default for both languages) or `multi-file`; `files[]` enumerates each file with its `role` (`implementation`, `types`, `parsers`, `utils`, `models`, `data-table`).
- `imports` — language-specific signal extraction. Go: `has_template_engine` for `text/template` import; `has_jsonutil` distinguishes `jsonutil` from raw `encoding/json`.
- `adapter_struct` — Go-only. Java's equivalent lives in `bidder_class` (top-level, separate section).
- `builder` — Go-only `Builder()` function. Java construction is described under `spring_config.bidder_creator_lambda`.
- `make_requests` — the canonical request-shaping behavior. Sub-sections for `batching` (rules list — see `behavior-taxonomy.md#code-make_requests-batching-rules`), `request_body`, `mutation` (entity-by-entity strategies + per-language idioms), `imp_ext_unmarshal`, `endpoint_resolution` (kind + per-language mechanism).
- `make_bids` — response-shaping behavior. Sub-sections for `http_status_handling` and `application_status_handling` (split for Huaweiads-style `retcode` body field), `bid_type_resolution.method_chain[]` (see `behavior-taxonomy.md`), `bid_pointer_pattern`, `currency_overwrite_safety`.

The `code.make_requests.batching.rules[]` and `code.make_bids.bid_type_resolution.method_chain[]` are ordered lists, not scalar enums. This is the Phase 2 refactor: Appnexus emits `[max-imps-per-request: 10, pod-grouping]` (two rules); Aax has a 3-step bid-type chain (`by-bid-ext-typed-field → by-imp-mediatype → throw`).

### `tests`

Language-divergent fixture format:

- **Go**: `httpCalls` array embedded in a single JSON test file. Subdirectories `exemplary/`, `supplemental/`, `amp/`, `video/`, `videosupplemental/`. Canonical harness: `RunJSONBidderTest`. Canonical root directory naming: `<bidder>test/`.
- **Java**: 4-file split per integration test case — request, response, auction-request, auction-response. JUnit `@Test` methods are hand-written; `unit_test_methods_count` and `unit_test_loc` are populated. Per-alias IT class is required (Adverxo's `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`).

`fixture_handling` (`count-only` default, `summary`, `verbatim`) is a per-invocation knob: `count-only` lists filename + sha + bytes; `summary` adds extracted media types per fixture; `verbatim` inlines the full JSON body.

### `spring_config` (Java-only; null on Go)

Captures Spring DI structure:

- `factory_class` and `factory_method` — the `@Configuration` class + `@Bean` method that creates the `BidderDeps`.
- `property_source_path` — the YAML file the `@PropertySource` annotation points at.
- `bidder_creator_lambda` — the verbatim lambda body inside `BidderDepsAssembler.bidderCreator(cfg -> new XyzBidder(...))`. Round-trip fidelity matters: a porter must reconstruct the exact constructor arg order.
- `configuration_properties_class` — when an adapter declares custom YAML fields beyond the default `BidderConfigurationProperties`, this captures the subclass. Examples:
  - **Kobler**: `KoblerConfigurationProperties extends BidderConfigurationProperties` with `@NotBlank private String devEndpoint`.
  - **Appnexus**: extra `platformId` field + inlined `iabCategories` map (120 entries).
  - **Huaweiads / NextMillennium**: nested `ExtraInfo` static class.
- `bean_dependencies` — every `@Autowired` or `@Value` collaborator. `source` field distinguishes `framework-injected` (CurrencyConversionService, JacksonMapper) from `@Value(${...})` (externalUrl).

### `bidder_class` (Java-specific shape; Go uses `code.adapter_struct`)

Captures the Java class hierarchy:

- `name` — class name, must match `directory_name` capitalized + `Bidder` suffix in canonical cases.
- `parameterized_request_type` — defaults to `BidRequest`. Non-default for Mediasquare (`Bidder<MediasquareRequest>`), Huaweiads (`Bidder<HuaweiAdsRequest>`).
- `parameterized_response_type` — null for the canonical case.
- `override_methods` — typically `[makeHttpRequests, makeBids]`.
- `constructor.parameters[]` — each parameter has `source` (`config-field`, `framework-injected`) and `role` (`properties`, `helper-collaborator`, `framework-injected`). Drives port-translation rules for currency injection, mapper injection, etc.
- `static_fields[]` — class-level constants (TypeReferences, default-currency strings, ext-key strings).
- `helper_classes_co_located[]` — helpers in `bidder/{xyz}/` (e.g., `KueezExtractor`, `MediasquareUtil`). Distinct from:
- `helper_classes_in_proto[]` — DTOs in `proto/openrtb/ext/request/{xyz}/` (e.g., `ExtImpKobler`).

### `iab_category_storage`

Replaces the old boolean `iab_category_lookup`. Adapters look up IAB categories from one of:

- `yaml-inlined` — Java's Appnexus inlines a 120-entry `iabCategories` map directly in `bidder-config/appnexus.yaml`. Captured via `yaml_field`.
- `go-data-table` — Go's MSFT puts the lookup in `adapters/msft/iab_categories.go` as a generated table. Captured via `go_data_file` and `table_size`.
- `dynamic-fetched` — the adapter fetches categories at runtime (rare).
- `none` — no IAB lookup.

`injection` (`constructor-arg`, `static-init`, null) describes how the lookup table reaches the adapter.

### `ext_pojo_construction`

Describes the shape of `ExtImp{Xyz}` (the params POJO/struct):

- `framework_choice`:
  - `lombok-value-builder` (Java default — `@Value @Builder`).
  - `lombok-data` (Java mutable — `@Data @NoArgsConstructor`; rare for ExtImp).
  - `lombok-value-staticconstructor` (Java's `@Value(staticConstructor = "of")` — Kobler uses this).
  - `go-struct` (Go default — plain struct with json tags).
- `flexible_extension_used` — Java only; whether the POJO extends `FlexibleExtension` (`@JsonAnyGetter/Setter`) for unknown-field passthrough.
- `custom_unmarshal.kind`:
  - `go-unmarshaljson` — Go custom `UnmarshalJSON` method.
  - `jackson-jsondeserialize` — Java `@JsonDeserialize(using = XyzDeserializer.class)`.
  - `jackson-jsonalias-only` — Java `@JsonAlias({...})` for legacy field-name compatibility (no full deserializer).
  - `runtime-isobject-isarray-branching` — Appnexus keywords field accepts string/object/array via runtime branching.
  - `none` — default.
- `where_branched` — for runtime-branching cases, identifies the branch point (`bidder-class`, `jsondeserializer-class`, `type-method`).

### `currency_conversion`

Cross-language consolidated description. The Go and Java helpers have different signatures:

- Go: `reqInfo.ConvertCurrency(value, from, to) (float64, error)` — accessible only inside `MakeRequests`.
- Java: `currencyConversionService.convertCurrency(value, bidRequest, from, to) BigDecimal` — bidRequest arg passed for time-context.

`bid_request_passed_for_context` differs between languages and is a port-translation concern.

### `headers_constructed`

- `pre_built_in_constructor` — true when the adapter constructs static headers (basic-auth) once at construction time. Rubicon does this.
- `per_request_dynamic` — true when headers are constructed per-request (dynamic body-hash, time-stamped HMAC). Huaweiads HMAC-SHA256 falls here.
- `custom_headers` — the literal header tuples added beyond the framework-default `Content-Type: application/json`.
- `authentication_kind` — `none`, `basic-auth`, `bearer-token`, `hmac-digest`, `custom`.
- `authentication_input` — the config fields used to compute the auth header (e.g., `["XAPI.Username","XAPI.Password"]`).

### `deploy_time_tokens[]`

Distinct from runtime template macros. Each entry: `{ token, file, notes }`. Captures Rubicon-style `REGION` placeholder that the operator must substitute pre-deployment. Reviewers reject endpoints with unresolved non-template placeholders unless paired with `disabled: true` (canonical: PR #4502 appStockSSP `#{REGION}#`). The token itself surfaces here; the broader policy lives in `review/skills/shared/framework-utilities.md`.

### `quirks[]`

Free-text bucket with optional taxon. Each entry: `{ id, file, summary, edge_case_taxon }`.

The full registry of `edge_case_taxon` values is canonical in [behavior-taxonomy.md](behavior-taxonomy.md#quirks-edge_case_taxon-full-registry). That file lists ~22 taxa with descriptions and surfaces. New taxa are added there atomically when Phase 2+ findings surface them; this `adapter-spec.md` file does NOT duplicate the registry.

A `custom` value in any enumerated behavioral field REQUIRES a corresponding `quirks` entry. This prevents un-classified behavior from silently flowing through.

### `cross_language`

REQUIRED in every spec, regardless of source language. Both `go_artifacts` and `java_artifacts` are present:

- The source-language reader densely populates its own block.
- The other-language block is populated with **path hints only**: `bidder_dir`, `bidder_class` / `package_name`, `config_class`, `yaml_path`, `proto_dir`. These tell port skills the destination layout.

`port_concerns` flags the structural divergences a porter must handle:

- `aliases_inverted` — Go child declares `aliasOf: parent`; Java parent declares `aliases: { child: ~ }`.
- `yaml_unification` — Java's `bidder-config/{xyz}.yaml` unifies what Go splits into `static/bidder-info/` + main config.
- `mutation_idiom_divergence` — Go pointer mutation vs Java Lombok `toBuilder().build()`.
- `package_directory_mismatch`, `multi_file_layout`, `custom_unmarshaljson_present` — boolean flags a porter consults.

`go_specific_concerns[]` and `java_specific_concerns[]` are free-text lists of language-only quirks the porter must address — port-fidelity issues that don't translate cleanly to the other language. The source-language spec populates its own list densely (e.g., a Go-source spec lists Go-only iteration idioms, value-receivers, package-level consts); the other-language list is sparse/empty.

`port_lineage` is populated only for cross-language ports: `{ source_language, source_pr, destination_language, destination_pr, fidelity_review_themes[] }`. Captures the actual PR numbers (Kobler: Go #3904 → Java #3684). `fidelity_review_themes` lists themes pulled from the destination PR's review history (port-fidelity is the dominant Java review theme per Phase 2 findings).

`reviewer_cohort` has three sub-fields: `go: [<github-username>...]` (active Go-team reviewers), `java: [<github-username>...]` (active Java-team reviewers), and `cross_language_coordinator: <github-username>` (the lone reviewer active across both repos — `bretg` per Phase 2 findings). Per Phase 2 the per-language cohorts are wholly disjoint; `cross_language_coordinator` is encoded separately so port skills can cc the coordinator on cross-language coordination PRs without conflating them with a single language's reviewer pool.

---

## Worked example: Kobler (port pair)

Kobler is a clean port pair: Go (PR #3904, kobler.go = 177 LOC) → Java (PR #3684, KoblerBidder.java = 195 LOC). Both repos carry a byte-identical `static/bidder-params/kobler.json` (sha256: `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685`). Two specs follow.

### Go-source spec (excerpt)

```yaml
adapter_spec_version: 1
spec_kind: prebid-server-adapter
source_language: go

provenance:
  source: { repo: prebid/prebid-server, ref: { branch: master }, resolved_commit: <sha>, fetch_method: github-raw }
  warnings:
    - type: bidder-constant-mismatch
      file: adapters/kobler/kobler_test.go
      line: 12
      summary: Builder called with openrtb_ext.BidderKargo (copy-paste artifact); should be BidderKobler.
    - type: bidder-constant-mismatch
      file: adapters/kobler/params_test.go
      line: 47
      summary: validator.Validate called with openrtb_ext.BidderKrushmedia; should be BidderKobler.

meta:
  bidder_name: kobler
  is_alias: false
  module_path_major: v4

bidder_info:
  endpoint: "https://bid.essrtb.com/bid/prebid_server_rtb_call"
  endpoint_construction: { kind: dev-prod-toggle, macros_used: [], placeholders_unresolved: [] }
  endpoint_compression: gzip
  maintainer: { email: bidding-support@kobler.no }
  capabilities:
    site: { mediaTypes: [banner] }
    app:  { mediaTypes: [banner] }
  geoscope: [NOR, SWE, DNK]
  gvl_vendor_id: 0

bidder_params_json: |
  {"$schema":"http://json-schema.org/draft-04/schema#","title":"Kobler Adapter Params",...}
bidder_params_sha256: 125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685

params:
  schema_interpretation:
    properties: [{ name: test, type: boolean, description: "Whether the request is for testing only..." }]
    required_fields: []
    combinators_used: []
  ext_struct:
    package: openrtb_ext
    file: openrtb_ext/imp_kobler.go
    type_name: ExtImpKobler
    fields: [{ name: Test, json_tag: test, type_native: bool, omitempty: false }]
    custom_unmarshal: false
  params_test:
    file: adapters/kobler/params_test.go
    valid_cases_count: 3
    invalid_cases_count: 8
    bidder_constant_referenced: openrtb_ext.BidderKrushmedia    # MISMATCH — surfaces in warnings.

code:
  package_or_class: kobler
  directory_name: kobler
  package_directory_mismatch: false
  file_layout:
    kind: single-file
    files: [{ name: kobler.go, role: implementation, loc: 177 }]
  imports: { has_template_engine: false, has_currency_helper: true, has_jsonutil: true, third_party: [] }
  adapter_struct:
    type_name: adapter
    type_visibility: unexported
    fields: [{ name: endpoint, type: string }, { name: devEndpoint, type: string }]
  builder:
    signature_canonical: true
    extra_adapter_info_used: false
    template_parsed_at_build: false
    errors_returned: []
  make_requests:
    batching: { applied_in_order: true, rules: [{ kind: single-batched }] }
    request_body: { kind: openrtb2-modified }
    mutation:
      mutates_request: true
      entity_strategies:
        Device: in-place                       # device.IP="" device.IPv6=""
        User: in-place                         # request.User = nil
        Cur: append-if-missing                 # appends "USD" if not present
        Imp: in-place                          # ConvertCurrency mutates BidFloor
      go_idiom: shallow-copy                   # sanitizeRequest copies the request struct value
    imp_ext_unmarshal:
      kind: standard-two-phase
      mechanism_go: jsonutil-two-phase
      target_type: openrtb_ext.ExtImpKobler
    endpoint_resolution:
      kind: dev-prod-toggle
      mechanism_go: string-concat              # No template; toggle between two const-like strings
      macro_field_set: []
  make_bids:
    response_type: openrtb2.BidResponse
    http_status_handling: { kind: legacy-raw-go }   # Direct StatusCode == 204 / != 200 checks; not the canonical helpers
    application_status_handling: { kind: none }
    bid_type_resolution:
      default_value: banner
      multi_format_detection: none
      method_chain:
        - { method: by-bid-ext-typed-field, fallback_action: return-default }
    bid_pointer_pattern: indexed-iteration
    bid_pointer_go_sibling: indexed-seatbid
    currency_overwrite_safety: passthrough-from-response

tests:
  test_root_directory: koblertest
  go_directory_naming: canonical
  fixture_inventory:
    exemplary: [{ filename: site-simple_banner.json, ... }, { filename: app-simple_banner.json, ... }]
    supplemental: [{ filename: status-204.json, ... }, { filename: status-404.json, ... }, ... ]
  uses_canonical_harness: true
  fixture_handling: count-only

spring_config: null                            # Go has no Spring DI.

bidder_class: null                             # Go uses code.adapter_struct.

iab_category_storage: { storage_kind: none }

ext_pojo_construction:
  framework_choice: go-struct
  flexible_extension_used: false
  custom_unmarshal: { kind: none }

currency_conversion:
  used: true
  helper: { go_signature: "reqInfo.ConvertCurrency(value, from, to) (float64, error)", java_signature: null }
  injection: function-arg
  bid_request_passed_for_context: false

headers_constructed:
  pre_built_in_constructor: false
  per_request_dynamic: true
  custom_headers: [{ name: Content-Type, value: "application/json;charset=utf-8" }]
  authentication_kind: none

deploy_time_tokens: []

quirks:
  - id: hardcoded-dev-endpoint
    file: kobler.go
    summary: devBidderEndpoint is a const at line 23; should live in YAML config (Kobler internal-test-campaign justification noted in code comment lines 82-83).
    edge_case_taxon: hardcoded-config-as-anti-pattern
  - id: dev-prod-toggle-via-imp-ext-test-flag
    file: kobler.go
    summary: testMode flag pulled from imp.ext.bidder.test of the FIRST imp only (line 55 - i==0); other imps' test flags are ignored.
    edge_case_taxon: hardcoded-config-as-anti-pattern

cross_language:
  go_artifacts:
    bidder_dir: adapters/kobler/
    package_name: kobler
    bidder_constant: openrtb_ext.BidderKobler
  java_artifacts:
    bidder_dir: src/main/java/org/prebid/server/bidder/kobler/
    bidder_class: KoblerBidder
    config_class: KoblerConfiguration
    yaml_path: src/main/resources/bidder-config/kobler.yaml
    proto_dir: src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/
  port_concerns:
    aliases_inverted: false                    # No aliases on either side.
    yaml_unification: true
    mutation_idiom_divergence: true
    package_directory_mismatch: false
    multi_file_layout: false
    custom_unmarshaljson_present: false
  port_lineage:
    source_language: go
    source_pr: prebid/prebid-server#3904
    destination_language: java
    destination_pr: prebid/prebid-server-java#3684
    fidelity_review_themes: [currency-conversion-bidrequest-context, mutation-idiom-tobuilder]
  reviewer_cohort:
    go: [bsardo, SyntaxNode]
    java: [CTMBNara, AntoxaAntoxic]
    cross_language_coordinator: bretg
```

### Java-source spec (excerpt)

```yaml
adapter_spec_version: 1
spec_kind: prebid-server-adapter
source_language: java

provenance:
  source: { repo: prebid/prebid-server-java, ref: { branch: master }, resolved_commit: <sha> }
  warnings: []                                 # Java side has no copy-paste artifact.

meta:
  bidder_name: kobler
  java_artifact_version: "3.41.0"

bidder_info:
  endpoint: "https://bid.essrtb.com/bid/prebid_server_rtb_call"
  endpoint_construction: { kind: dev-prod-toggle, macros_used: [], placeholders_unresolved: [] }
  endpoint_compression: gzip                   # YAML uses `endpoint-compression: gzip` (kebab-case).
  ortb_version: null
  default_enabled: true
  modifying_vast_xml_allowed: false
  maintainer: { email: bidding-support@kobler.no }
  capabilities:
    site: { mediaTypes: [banner] }
    app:  { mediaTypes: [banner] }
  geoscope: [NOR, SWE, DNK]
  gvl_vendor_id: 0
  yaml_extra_fields: { dev-endpoint: "https://bid-service.dev.essrtb.com/bid/prebid_server_rtb_call" }

bidder_params_json: |
  {"$schema":"http://json-schema.org/draft-04/schema#","title":"Kobler Adapter Params",...}
bidder_params_sha256: 125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685    # IDENTICAL TO GO.

params:
  schema_interpretation:                       # IDENTICAL TO GO (cross-language contract).
    properties: [{ name: test, type: boolean, description: "Whether the request is for testing only..." }]
    required_fields: []
    combinators_used: []
  ext_struct:
    package: org.prebid.server.proto.openrtb.ext.request.kobler
    file: src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/ExtImpKobler.java
    type_name: ExtImpKobler
    fields: [{ name: test, json_tag: test, type_native: Boolean, omitempty: false, notes: ["@Value(staticConstructor=of)"] }]
    custom_unmarshal: false
  params_test:
    file: src/test/java/org/prebid/server/bidder/kobler/KoblerBidderTest.java
    valid_cases_count: ~                       # Java unit tests are method-counted, not case-counted.
    invalid_cases_count: ~
    bidder_constant_referenced: null

code:
  package_or_class: KoblerBidder
  directory_name: kobler
  package_directory_mismatch: false
  file_layout:
    kind: single-file
    files: [{ name: KoblerBidder.java, role: implementation, loc: 195 }]
  imports: { has_template_engine: false, has_currency_helper: true, has_jsonutil: false, third_party: [BooleanUtils, CollectionUtils] }
  adapter_struct: null                         # Java uses bidder_class instead.
  builder: null                                # Java construction described in spring_config.
  make_requests:
    batching: { applied_in_order: true, rules: [{ kind: single-batched }] }
    request_body: { kind: openrtb2-modified }
    mutation:
      mutates_request: true
      entity_strategies:
        Device: immutable-rebuild              # device.toBuilder().ipv6(null).ip(null).build()
        User: immutable-rebuild                # user(null) on root-level toBuilder
        Cur: append-if-missing
        Imp: immutable-rebuild                 # modifyImp via toBuilder
      java_idiom: lombok-tobuilder
    imp_ext_unmarshal:
      kind: standard-two-phase
      mechanism_java: typeref-extprebid        # KOBLER_EXT_TYPE_REFERENCE: TypeReference<ExtPrebid<?, ExtImpKobler>>
      target_type: ExtImpKobler
    endpoint_resolution:
      kind: dev-prod-toggle
      mechanism_java: string-replace           # Conditional pick between endpointUrl / devEndpoint; no URI building.
      macro_field_set: []
  make_bids:
    response_type: BidResponse                 # com.iab.openrtb.response.BidResponse
    http_status_handling: { kind: framework-default-plus-empty-seatbid-shortcircuit }
    application_status_handling: { kind: none }
    bid_type_resolution:
      default_value: banner
      multi_format_detection: none
      method_chain:
        - { method: by-bid-ext-typed-field, fallback_action: return-default }
    bid_pointer_pattern: flatten-streams       # bidResponse.getSeatbid().stream().flatMap(...)
    bid_pointer_go_sibling: null
    currency_overwrite_safety: passthrough-from-response   # BidderBid.of(bid, type, bidResponse.getCur())

tests:
  test_root_directory: src/test/java/org/prebid/server/bidder/kobler/
  java_it_folder_naming: canonical
  fixture_inventory:
    integration: []                            # 4-file split fixtures live under src/test/resources/org/prebid/server/it/openrtb2/kobler/
  uses_canonical_harness: true                 # VertxTest pattern.
  unit_test_methods_count: ~                   # Populated by read-bidder-class.
  fixture_handling: count-only
  test_application_properties_entries_added: 0

spring_config:
  factory_class: KoblerConfiguration
  factory_method: koblerBidderDeps
  property_source_path: classpath:/bidder-config/kobler.yaml
  bidder_creator_lambda: |
    cfg -> new KoblerBidder(cfg.getEndpoint(), cfg.getDevEndpoint(), currencyConversionService, mapper)
  configuration_properties_class:
    name: KoblerConfigurationProperties
    extends: BidderConfigurationProperties
    extra_fields: [{ name: devEndpoint, type: String, validations: [NotBlank] }]
    nested_classes: []
    lombok_annotations: [Data, EqualsAndHashCode, NoArgsConstructor]
  bean_dependencies:
    - { name: currencyConversionService, type: CurrencyConversionService, source: framework-injected }
    - { name: externalUrl, type: String, source: "@Value(${external-url})" }
    - { name: mapper, type: JacksonMapper, source: framework-injected }

bidder_class:
  name: KoblerBidder
  parameterized_request_type: BidRequest
  parameterized_response_type: null
  override_methods: [makeHttpRequests, makeBids]
  constructor:
    arity: 4
    parameters:
      - { name: endpointUrl, type: String, source: config-field, role: properties }
      - { name: devEndpoint, type: String, source: config-field, role: properties }
      - { name: currencyConversionService, type: CurrencyConversionService, source: framework-injected, role: helper-collaborator }
      - { name: mapper, type: JacksonMapper, source: framework-injected, role: helper-collaborator }
  static_fields:
    - { name: KOBLER_EXT_TYPE_REFERENCE, type: TypeReference }
    - { name: DEFAULT_BID_CURRENCY, type: String, value: "USD" }
    - { name: EXT_PREBID, type: String, value: "prebid" }
  helper_classes_co_located: []
  helper_classes_in_proto: [ExtImpKobler]

iab_category_storage: { storage_kind: none }

ext_pojo_construction:
  framework_choice: lombok-value-staticconstructor
  flexible_extension_used: false
  custom_unmarshal: { kind: none }

currency_conversion:
  used: true
  helper:
    go_signature: null
    java_signature: "currencyConversionService.convertCurrency(value, bidRequest, from, to) BigDecimal"
  injection: dependency
  bid_request_passed_for_context: true

headers_constructed:
  pre_built_in_constructor: false
  per_request_dynamic: true
  custom_headers: [{ name: Content-Type, value: "application/json;charset=utf-8" }]
  authentication_kind: none

deploy_time_tokens: []

quirks:
  - id: hardcoded-dev-endpoint-now-in-config
    file: src/main/resources/bidder-config/kobler.yaml
    summary: dev-endpoint moved into BidderConfigurationProperties subclass — fixes the Go-side hardcoded-const anti-pattern. Cross-language win.
    edge_case_taxon: port-fidelity-divergence

cross_language:
  go_artifacts:
    bidder_dir: adapters/kobler/
    package_name: kobler
    bidder_constant: openrtb_ext.BidderKobler
  java_artifacts:
    bidder_dir: src/main/java/org/prebid/server/bidder/kobler/
    bidder_class: KoblerBidder
    config_class: KoblerConfiguration
    yaml_path: src/main/resources/bidder-config/kobler.yaml
    proto_dir: src/main/java/org/prebid/server/proto/openrtb/ext/request/kobler/
  port_concerns:
    aliases_inverted: false
    yaml_unification: true
    mutation_idiom_divergence: true
    package_directory_mismatch: false
    multi_file_layout: false
    custom_unmarshaljson_present: false
  port_lineage:
    source_language: go
    source_pr: prebid/prebid-server#3904
    destination_language: java
    destination_pr: prebid/prebid-server-java#3684
    fidelity_review_themes: [currency-conversion-bidrequest-context, mutation-idiom-tobuilder, dev-endpoint-config-promotion]
  reviewer_cohort:
    go: [bsardo, SyntaxNode]
    java: [CTMBNara, AntoxaAntoxic]
    cross_language_coordinator: bretg
```

### Cross-language assertions for the Kobler pair

The dual-spec assertion file at `cross-language-pairs/kobler.dual-spec-assertions.yaml` enforces:

| Assertion | Expected |
|---|---|
| `bidder_params_sha256` equality | Go = Java = `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685` |
| `bidder_info.capabilities` equality | site/app banner-only on both |
| `bidder_info.maintainer.email` equality | `bidding-support@kobler.no` on both |
| `bidder_info.geoscope` equality | `[NOR, SWE, DNK]` on both |
| `params.schema_interpretation` deep equality | Both list `test: boolean`, no required, no combinators |
| `code.make_requests.batching.rules[].kind` equality | Both emit `[single-batched]` |
| `code.make_bids.bid_type_resolution.method_chain[].method` equality | Both emit `[by-bid-ext-typed-field]` with `return-default` |
| `code.make_requests.endpoint_resolution.kind` equality | Both emit `dev-prod-toggle` |
| `cross_language.port_lineage` equality | Both reference Go #3904 → Java #3684 |
| `spring_config != null` only on Java | Go has null; Java has full block |
| `bidder_class != null` only on Java | Go has null; Java has full block |
| `code.adapter_struct != null` only on Go | Go has full block; Java has null |
| `currency_conversion.bid_request_passed_for_context` | Go = false, Java = true (intentional divergence) |
| `code.make_requests.mutation.go_idiom` Go-only | Go = `shallow-copy`; Java has `java_idiom: lombok-tobuilder` instead |

A dual-spec assertion FAIL is a port-fidelity violation that surfaces in the cross-language test harness.

---

## Validation rules (R1-R10)

The orchestrator enforces these rules at read time. Failures are emitted under `provenance.warnings` (non-blocking) or surface as hard errors that abort the read.

| Rule | Description | Enforcement |
|---|---|---|
| R1 | Spec must reference only files reachable at `provenance.source.resolved_commit`. A reference to a file that doesn't exist at that commit is a hard error. | Hard error |
| R2 | `bidder_params_sha256` must match `sha256(bidder_params_json)`. The Go and Java reader for the same bidder MUST produce identical SHA. | Hard error |
| R3 | No invented fields. Every behavioral field has either a default flag (with structural evidence affirmatively matching the default) or a regex/AST/JSON-parse evidence pointer. A `custom` value REQUIRES a matching `quirks` entry. | Hard error |
| R4 | Round-trip determinism. Re-running the read on the same commit produces a byte-identical spec modulo `provenance.read.timestamp_utc` and `provenance.read.operator`. | Hard error in CI; warning interactively |
| R5 | Cross-language structural parity for port pairs. For any bidder present in both repos, `bidder_params_sha256`, `bidder_info.capabilities`, `params.schema_interpretation`, and `bidder_info.gvl_vendor_id` MUST be identical. | Surfaces as `port_concerns` warning + dual-spec-assertion FAIL |
| R6 | `meta.bidder_name == cross_language.go_artifacts.package_name` AND `meta.bidder_name.toLowerCase() == directory_name(cross_language.java_artifacts.bidder_dir)`. Mismatch is a `package-directory-mismatch` warning. | `provenance.warnings` |
| R7 | If `params.params_test.bidder_constant_referenced != openrtb_ext.Bidder{Xyz}` (Go) or doesn't match the Java equivalent, emit `bidder-constant-mismatch` warning with file:line. | `provenance.warnings` |
| R8 | If `bidder_info.endpoint` contains a `{{.XYZ}}` macro and `XYZ` is not in `macros.EndpointTemplateParams` (Go) or the Java macro list, emit `endpoint-placeholder-unresolved` warning. | `provenance.warnings` |
| R9 | If `code.imports.has_jsonutil == false` AND any `Marshal` or `Unmarshal` call appears in the adapter code (Go), emit `legacy-encoding-json-direct-usage` warning (recommended migration to `jsonutil`). | `provenance.warnings` |
| R10 | If `tests.uses_canonical_harness == false` (Go: `RunJSONBidderTest` not called; Java: `VertxTest` not extended), emit `legacy-test-helpers-imported` warning. | `provenance.warnings` |

Validation rule R7 is load-bearing: Phase 2 found two real source-code bugs in `kobler_test.go` and `params_test.go` (BidderKargo and BidderKrushmedia copy-paste artifacts) that pass tests because the validator/builder don't cross-check the constant. The spec's read-time validation surfaces these.

---

## Sources

- Phase 2 reconnaissance findings (in conversation): 17 Go edge cases + 17 Java edge cases identified across `optidigital, kobler, 33across, mediasquare, msft, appnexus, adkernel` (Go) and `kobler, adverxo, ogury, feedad, seedtag, optidigital, mediasquare, elementaltv, 152media` (Java) plus the broader 9-adapter Java behavior taxonomy stress-test (`appnexus, rubicon, generic, aax, adview, kobler, mediasquare, nextmillennium, huaweiads`).
- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27).
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
- `prebid-server-go/references/new-bid-adapter-prs.md` — 89 reference PRs with `Patterns Demonstrated` tags.
- `prebid-server-java/references/new-bid-adapter-prs.md` — 49 reference PRs with `Patterns Demonstrated` tags.
- Sibling shared file: `prebid-server-go/review/skills/shared/framework-utilities.md`.
- Sibling shared file: `prebid-server-go/read/skills/shared/behavior-taxonomy.md`.
- Sibling shared file: `prebid-server-go/read/skills/shared/port-translation-rules.md`.
