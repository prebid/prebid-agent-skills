# Cross-Skill Integration

How the `read/` skill suites compose with the rest of the prebid-agent-skills ecosystem. The `read/` orchestrators (Go and Java) emit a canonical Adapter Specification — that spec is the contract that downstream skills consume. This document maps every consumer (`write/`, `port-go2java/`, `port-java2go/`, opt-in `review/` composition) to the spec fields it reads, identifies the verbatim vs. derived fields each consumer treats as load-bearing, and surfaces the limitations that survive the contract.

The intended audience is a developer authoring or maintaining a downstream skill. It is NOT an end-user document — end users invoke the read orchestrator and consume the spec directly.

---

## 1. Overview

The two `read/` orchestrators (one per language) produce the same canonical YAML spec defined at [`adapter-spec.md`](adapter-spec.md). Two specs of the same bidder — one Go-source, one Java-source — agree byte-for-byte on cross-language fields and diverge only on language-specific blocks (Go: `code.adapter_struct`, `code.builder`; Java: `spring_config`, `bidder_class`).

Five downstream surfaces consume the spec:

| Consumer | Direction | Status | Input fields | Output |
|---|---|---|---|---|
| `prebid-server-go/write/` | spec → Go adapter | Future (Phase E) | All sections; verbatim `bidder_params_json` is byte-load-bearing | New adapter PR ready for `prebid/prebid-server` |
| `prebid-server-java/write/` | spec → Java adapter | Future (Phase E) | All sections; verbatim `bidder_params_json` is byte-load-bearing | New adapter PR ready for `prebid/prebid-server-java` |
| `prebid-server-java/port-go2java/` | Go-source spec → Java adapter | Future (Phase D) | `cross_language.*`, [`port-translation-rules.md`](port-translation-rules.md) Rules 1–46 | New Java adapter port PR |
| `prebid-server-go/port-java2go/` | Java-source spec → Go adapter | Future (Phase D) | Symmetric inverse of the above | New Go adapter port PR |
| `prebid-server-go/review/skills/pr-triage/` | spec as `prior_spec` | Existing (opt-in hook) | Whole spec read as comparator; behavioral regression detection | PR-triage manifest with `prior-spec-comparison` block |

The orchestrator does NOT call any of these skills. It produces a spec and stops. Each consumer reads the spec independently — the contract is unidirectional.

```
              prebid-server-go/                          prebid-server-java/
              read/skills/                               read/skills/
              read-adapter-orchestrator                  read-bidder-orchestrator
                          \                              /
                           \                            /
                            v                          v
                       Adapter Specification (canonical YAML)
                                       |
        +-------------+----------------+----------------+----------------+
        |             |                |                |                |
        v             v                v                v                v
     write/        write/         port-go2java/     port-java2go/      review/
     (Go)          (Java)         (Java)            (Go)               pr-triage
                                                                       (opt-in
                                                                        prior_spec)
```

---

## 2. `read` → `write` (creating a new adapter from a spec)

The `write/` skill is the symmetric inverse of `read/`: spec → adapter files. Where `read/` extracts behavior from source, `write/` synthesizes source from behavior.

### 2.1 Verbatim file outputs (byte-for-byte)

A `write/` skill MUST emit these files byte-identical to the spec's verbatim copies. Re-reading the written adapter MUST produce the same `bidder_params_sha256`.

| Spec field | Output file (Go target) | Output file (Java target) | Notes |
|---|---|---|---|
| `bidder_params_json` (verbatim string) | `static/bidder-params/{xyz}.json` | `src/main/resources/static/bidder-params/{xyz}.json` | The cross-language contract — same bytes on both sides. R2 hard-error if the SHA mismatches the verbatim. |
| `bidder_info.*` (entire subtree) | `static/bidder-info/{xyz}.yaml` | (folded into the unified `bidder-config/{xyz}.yaml` — see §2.3) | Endpoint, capabilities, geoscope, gvl_vendor_id, user_sync, yaml_extra_fields. |

Worked example — Optidigital. The spec at [`prebid-server-go/read/test-fixtures/optidigital.golden.spec.yaml`](../../test-fixtures/optidigital.golden.spec.yaml) line 68 carries the JSON Schema as a YAML double-quoted scalar (preserving the trailing `}` with no terminal newline). A `write/` skill must reconstruct those exact bytes — `bidder_params_sha256` is `6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31`, and a single-byte deviation breaks R2.

### 2.2 Behavioral fields drive code generation

The behavioral sections of the spec (`code.make_requests.*`, `code.make_bids.*`, `tests.*`) drive template-based code generation. The mapping is field-driven:

| Spec field | `write/` action |
|---|---|
| `code.make_requests.batching.rules: [{ kind: single-batched }]` | Emit one HTTP request from `MakeRequests` (Go) / `makeHttpRequests` (Java); use `BidderUtil.defaultRequest` on Java. |
| `code.make_requests.batching.rules: [{ kind: per-imp }]` | Emit a `for _, imp := range request.Imp` loop; one RequestData per iteration. |
| `code.make_requests.batching.rules: [{ kind: max-imps-per-request, max: N }]` | Emit a chunking helper per Rule 16; `const maxImpsPerRequest = N` in Go. |
| `code.make_requests.batching.rules: [{ kind: format-split, formats: [...] }]` | Emit one HTTP request per media type; preserve `formats[]` order (deterministic test fixture matching depends on this — Rule 18). |
| `code.make_requests.batching.rules: [{ kind: pod-grouping, key: imp.id-prefix-before-underscore }]` | Emit `groupByPod` helper per Rule 17. Compose with sibling rules in declared order. |
| `code.make_requests.endpoint_resolution.kind: static` | Hardcoded URL reference — no template parsing. |
| `code.make_requests.endpoint_resolution.kind: single-token-substitution` + `mechanism_go: text/template` | Builder parses `template.New(...).Parse(config.Endpoint)`; per Rule 11. |
| `code.make_requests.endpoint_resolution.kind: query-parameter-augmentation` + `mechanism_go: net/url` | Use `url.Parse(...) + url.Values.Set(...)`; per Rule 12. |
| `code.make_requests.endpoint_resolution.kind: dev-prod-toggle` | Two adapter-struct fields (`endpoint`, `devEndpoint`) + ternary branch. NOTE: `write/` should consult the `quirks[]` for `hardcoded-config-as-anti-pattern` and prefer YAML config over hardcoded const — Kobler's Java port made this fix (Rule 13). |
| `code.make_bids.bid_type_resolution.method_chain` | Switch / chained `if`-`else` per ordered chain. Each step's `fallback_action: {next, return-default, throw}` selects the failure path. |
| `code.make_bids.http_status_handling.kind: canonical-go-helpers` | Emit `adapters.IsResponseStatusCodeNoContent` + `adapters.CheckResponseStatusCodeForErrors` (Rule 30). |
| `code.make_bids.http_status_handling.kind: legacy-raw-go` | Emit raw `responseData.StatusCode == 204` checks; surface a TODO suggesting migration to canonical helpers. |
| `currency_conversion.used: true` + `injection: function-arg` | Pass `reqInfo *adapters.ExtraRequestInfo` through to the helper that performs `ConvertCurrency`. |
| `currency_conversion.used: true` + `injection: dependency` (Java) | Inject `CurrencyConversionService` via constructor. |

### 2.3 YAML topology — Go split vs. Java unified

Go reads two YAML files; Java reads one. A `write/` skill must perform the inverse of the `read/` split/unify operation:

- Go target: emit `static/bidder-info/{xyz}.yaml` carrying `bidder_info.*` AND emit a registration entry that points the main `config.yaml` (or the static bidder loader) at the new bidder.
- Java target: emit `src/main/resources/bidder-config/{xyz}.yaml` carrying the unified shape (`adapters.{xyz}.{endpoint, meta-info, dev-endpoint, modifying-vast-xml-allowed, ortb-version, geoscope, ...}`) plus the alias children (parent declares `aliases: { child: ~ }`).

Field-name conventions also differ — Go uses camelCase (`endpointCompression`); Java uses kebab-case (`endpoint-compression`). The `read/` orchestrator captures observed style in `bidder_info.yaml_field_name_quirks[]`; the `write/` skill MUST emit canonical style for the target language regardless of what the source spec recorded (camelCase for Go, kebab-case for Java).

### 2.4 `quirks[]` surface as TODO comments

`quirks[]` entries cannot be auto-applied in code generation. They are the exit-hatch from the deterministic spec → code mapping. A `write/` skill MUST surface every quirk as a TODO comment in the generated source, citing the quirk's `id` and `summary`:

```go
// TODO[hardcoded-dev-endpoint]: devBidderEndpoint is a const at line 23; should live
// in YAML config (Kobler internal-test-campaign justification noted in code comment
// lines 82-83). Consider promoting to BidderConfigurationProperties subclass on the
// Java port (Rule 35; cross-language win).
const devBidderEndpoint = "..."
```

Worked example — Kobler. The spec at [`prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) carries two quirks (`hardcoded-dev-endpoint` and `dev-prod-toggle-via-imp-ext-test-flag`). Both must round-trip into TODO comments — `write/` cannot infer whether the user wants to keep the anti-pattern or fix it.

### 2.5 Tests

`write/` regenerates test fixtures from `tests.fixture_inventory.*`. With `fixture_handling: count-only` (default), the skill emits empty placeholder fixtures and surfaces a TODO. With `fixture_handling: verbatim`, the JSON bodies are inline and can be written byte-identical. With `summary`, the skill has structural information but not the full body — emits the structural skeleton plus a TODO.

---

## 3. `read` (Go) → `port-go2java`

Translate a Go-source spec into Java adapter artifacts. The skill consumes the spec's `cross_language.*` block (path hints, port concerns, lineage) plus the [`port-translation-rules.md`](port-translation-rules.md) Rules 1–46 indexed by the spec field that drives them.

### 3.1 Trigger fields

| `cross_language.port_concerns.*` flag | What `port-go2java` does |
|---|---|
| `aliases_inverted: true` (always for Java target) | MOVE alias declaration from Go's child YAML (`static/bidder-info/{child}.yaml: aliasOf: {parent}`) to Java's parent YAML (`bidder-config/{parent}.yaml: aliases: { {child}: ~ }`). Apply Rule 33. |
| `yaml_unification: true` (always for Java target) | MERGE Go's `static/bidder-info/{xyz}.yaml` + main config + alias chain into Java's unified `src/main/resources/bidder-config/{xyz}.yaml`. Apply Rule 34. |
| `mutation_idiom_divergence: true` | TRANSLATE every `code.make_requests.mutation.go_idiom: ptrutil.Clone` / `shallow-copy` / `direct-pointer-mutation` into the corresponding `java_idiom: lombok-tobuilder` invocation. Apply Rules 4, 5, 6, 7. |
| `package_directory_mismatch: true` | CHECK Java's TitleCase-acronym preservation requirements. 33across-style mismatches (directory `33across`, package `ttx`) translate to `code_naming.identifier_workaround: digit-leading-rename` (top-level) for Java's digit-leading bidders (e.g., `OneFiveTwoMediaTest`). |
| `multi_file_layout: true` | PRESERVE the multi-file split. msft (Go: 5 files) → Java: 1 main bidder class + N helper classes co-located in `bidder/{xyz}/` per `bidder_class.helper_classes_co_located[]`. |
| `custom_unmarshaljson_present: true` | TRANSLATE Go's `UnmarshalJSON` method to Java's `@JsonDeserialize(using = XyzDeserializer.class)`. Surfaces in `ext_pojo_construction.custom_unmarshal.where_branched: jsondeserializer-class`. |

### 3.2 Spec field → Java artifact map

| Go-source spec field | Java artifact |
|---|---|
| `code.adapter_struct.fields: [{ name: endpoint, type: string }]` | `bidder_class.constructor.parameters: [{ name: endpointUrl, type: String, source: config-field }]` + `spring_config.bidder_creator_lambda` constructs `new XyzBidder(cfg.getEndpoint(), ...)`. |
| `code.builder.signature_canonical: true` | `spring_config.factory_method` produces a `BidderDeps` from `config + dependencies`. |
| `code.imports.has_jsonutil: true` | Java has no equivalent — emit framework-supplied `JacksonMapper` constructor injection. |
| `code.imports.has_currency_helper: true` | Inject `CurrencyConversionService` via constructor. NOTE: signature differs (R32) — Java's `convertCurrency` takes 4 args (price, bidRequest, from, to); Go's takes 3 (price, from, to). Java's bidRequest arg passes time-context. |
| `currency_conversion.bid_request_passed_for_context: false` (Go default) → flip to `true` (Java target) | The port MUST add the bidRequest argument; surfaces in `quirks[]` as `currency-conversion-bidrequest-context`. |
| `code.make_requests.imp_ext_unmarshal.kind: standard-two-phase` + `mechanism_go: jsonutil-two-phase` | Java emits a `static final TypeReference<ExtPrebid<?, ExtImpXyz>> XYZ_EXT_TYPE_REFERENCE` + `mapper.mapper().convertValue(imp.getExt(), XYZ_EXT_TYPE_REFERENCE).getBidder()` per Rule 1. |
| `code.make_requests.imp_ext_unmarshal.kind: direct` + `wrapper_type: <X>` | Java emits a `TypeReference<X>` directly; no `getBidder()` call (Appnexus-style). Rule 2. |
| `code.make_requests.endpoint_resolution.kind: dev-prod-toggle` + Go uses hardcoded `const devBidderEndpoint` | Java port SHOULD promote to YAML `dev-endpoint:` field + `BidderConfigurationProperties` subclass with `@NotBlank private String devEndpoint`. Apply Rule 35 (cross-language win — fixes the Go-side anti-pattern). |
| `iab_category_storage.storage_kind: go-data-table` + `go_data_file: adapters/{xyz}/iab_categories.go` + `table_size: N` | Java port SHOULD inline the table as a YAML `iab-categories:` block under `adapters.{xyz}.iab-categories` and inject via constructor-arg. (Appnexus did this in Java with 95 entries — see [`prebid-server-java/read/test-fixtures/appnexus.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/appnexus.golden.spec.yaml) line 70 + 812.) Apply Rule 42 (IAB-categories storage cross-language translation) in `port-translation-rules.md`. |
| `tests.fixture_inventory.exemplary[]` (Go single-file) | Java port emits 4 separate files per case: `test-{xyz}-bid-request.json`, `test-{xyz}-bid-response.json`, `test-auction-{xyz}-request.json`, `test-auction-{xyz}-response.json`. Apply Rule 36. |
| `tests.go_directory_naming: legacy-test` (msft) | Java target uses canonical layout regardless — `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/`. The legacy Go pattern is Go-only. |

### 3.3 Per-alias asymmetry

The most expensive cross-language asymmetry is per-alias test-fixture cost (Rule 37). Go aliases are a single YAML file; Java aliases require an IT class + 4-file fixture set + `test-application.properties` registry append.

Worked example — Adverxo. The Go side has `adverxotest/` with N fixtures total (parent's tests cover all aliases). The Java port (#3705) ships `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java` — three IT classes + 12 fixture files (4 × 3 aliases) + 6–12 lines appended to `test-application.properties`. The spec carries this asymmetry under `aliases[].test_assets.{it_class, fixture_dir, fixture_file_count}`.

### 3.4 What `port-go2java` does NOT translate

- Go-only quirks — listed under `cross_language.go_specific_concerns[]`. The porter must hand-translate or surface a TODO. Examples: the msft adapter's `initDisplayManageVerBuilder` closure (msft.go:141-170) memoizes display-manage-ver across imps via a Go closure with `hasRun bool` capture; Java's natural rewrite is a sealed `Supplier` with a `Holder<String>` wrapper or a `Memoizer.suppliers.memoize` idiom — non-trivial port-fidelity concern surfaced in [`msft.golden.spec.yaml`](../../test-fixtures/msft.golden.spec.yaml) line 750.
- Go-only validation rule warnings — `provenance.warnings[]` of types `legacy-encoding-json-direct-usage` (R9), `legacy-test-helpers-imported` (R10), and `bidder-name-rebrand` (msft). Java has no equivalent constants — these warnings do NOT translate.
- Quirks marked with `edge_case_taxon: hardcoded-config-as-anti-pattern` — the porter SHOULD apply the cross-language fix (promote to YAML) and emit a `dev-endpoint-config-promotion` quirk on the Java side (Kobler did this).

---

## 4. `read` (Java) → `port-java2go`

Symmetric inverse of §3. The skill consumes a Java-source spec and emits Go adapter artifacts.

### 4.1 Trigger fields

| `cross_language.port_concerns.*` flag | What `port-java2go` does |
|---|---|
| `aliases_inverted: true` | SPLIT Java's parent YAML's `aliases: { child: ~ }` map into N child YAMLs at `static/bidder-info/{child}.yaml` each declaring `aliasOf: {parent}`. (Inverse of Rule 33.) |
| `yaml_unification: true` | SPLIT Java's unified `bidder-config/{xyz}.yaml` into Go's `static/bidder-info/{xyz}.yaml` (just bidder_info fields) plus a registration entry. (Inverse of Rule 34.) |
| `mutation_idiom_divergence: true` | TRANSLATE Java's `lombok-tobuilder` calls into Go's pointer mutation OR `ptrutil.Clone` calls. Choose `ptrutil.Clone` when the entity has nested pointers (Source.Ext.Schain — Rule 6); choose pointer mutation when shallow (Imp value — Rule 4). |
| `bidder_class.parameterized_request_type: <CustomType>` | EMIT a Go custom struct (`type {xyz}Request struct {...}`) and explicitly `jsonutil.Marshal` it. Inverse of Rule 9. |
| `bidder_class.helper_classes_co_located[]` | EMIT each helper as a Go file in `adapters/{xyz}/` — co-location is preserved. Java's helper class becomes a Go function or struct in a co-located `.go` file. |
| `bidder_class.helper_classes_in_proto[]` | EMIT each proto class as a Go file in `openrtb_ext/imp_{xyz}.go` (or sibling `openrtb_ext/imp_{xyz}_<helper>.go` if multiple). |
| `spring_config.configuration_properties_class.extra_fields[]` | TRANSLATE custom YAML fields into Go's `extra_info: '{"...":"..."}'` opaque JSON OR into Go's adapter struct fields parsed via `parseExtraInfo` in the Builder. Inverse of Rule 35. |
| `iab_category_storage.storage_kind: yaml-inlined` | TRANSLATE the inlined YAML map into a Go data file `adapters/{xyz}/iab_categories.go` with package-level `var iabCategoryMap = map[string]string{...}`. Apply Rule 42 (inverse direction — Java YAML-inlined → Go data table). |

### 4.2 Spec field → Go artifact map

| Java-source spec field | Go artifact |
|---|---|
| `bidder_class.constructor.parameters[]` | Go adapter struct fields: each `properties` parameter becomes a struct field; `framework-injected` parameters (CurrencyConversionService, JacksonMapper) become Go's per-call args (`reqInfo *adapters.ExtraRequestInfo`) or `jsonutil` direct calls. |
| `currency_conversion.helper.java_signature` (4-arg) | Go translates to 3-arg `reqInfo.ConvertCurrency(value, from, to)`. The bidRequest argument is dropped — Go has no time-context concept on currency. The asymmetry surfaces as a quirk; the Go code MUST NOT silently rely on bid-request-time context. (R32.) |
| `code.make_requests.endpoint_resolution.mechanism_java: string-replace` | Go maps to `mechanism_go: text/template` (preferred for type safety) OR `string-concat` (legacy). The porter selects based on the macro count: > 2 macros → `text/template`; ≤ 1 macro → `string-concat`. |
| `code.make_requests.endpoint_resolution.mechanism_java: URIBuilder` | Go maps to `mechanism_go: net/url` per Rule 12. |
| `tests.integration_test_pattern: 4-file-split` | Go merges 4 files per case into a single `httpCalls[]` array within an exemplary fixture. (Inverse of Rule 36.) |
| `aliases[].test_assets.it_class` (per-alias) | Go aliases need NO test files — the parent's tests cover them. (Inverse of Rule 37.) |
| `tests.test_application_properties_entries_added: N` | Go has no equivalent — the per-bidder enable/endpoint config lives elsewhere. The N entries do NOT translate. |
| `headers_constructed.pre_built_in_constructor: true` (Rubicon basic-auth) | Go translates the pre-built header into a Builder-time computation stored on the adapter struct. Apply Rule 20. |

### 4.3 What `port-java2go` does NOT translate

- Spring DI machinery (`spring_config.*`) is wholly Java-specific. The factory class, factory method, `@PropertySource` annotation, `BidderConfigurationProperties` subclass — all dropped. Go uses the `Builder` function pattern which the porter generates from the spec.
- `iab_category_storage.delivery_mechanism: constructor-arg` (Java) translates to Go's `static-init` — the Go data file is package-level static, not constructor-injected.
- `tests.unit_test_methods_count` (Java JUnit `@Test` count) does NOT translate — Go uses JSON-fixture-driven tests via `RunJSONBidderTest`. The hand-written test methods are Java-only.
- Java-only `cross_language.java_specific_concerns[]` entries — porter surfaces TODOs.

---

## 5. `read` ↔ `review` opt-in hook (`pr-triage` prior-spec comparison)

The `prebid-server-go/review/skills/pr-triage/SKILL.md` skill is the entry point of every Go PR review. It can OPTIONALLY load a previously persisted spec as `prior_spec` and pass it forward to downstream reviewer skills, allowing them to flag behavioral regressions on the PR diff.

### 5.1 Detection

`pr-triage` checks for a file at `prebid-server-go/read/specs/{bidder}/latest.yaml`. If present, it loads the YAML and adds a `--- PRIOR SPEC COMPARISON ---` block to the routing manifest. If absent, behavior is unchanged — the hook is purely additive.

The `read/specs/` directory is `.gitignore`'d by default. Users opt into checking specs in if they want diff-comparison workflows; otherwise, specs persist locally and are recomputed per-machine.

### 5.2 Detection examples

| PR diff signal | Spec field signal | Flag |
|---|---|---|
| PR adds `import "text/template"` to `adapters/{xyz}/{xyz}.go` | `prior_spec.code.imports.has_template_engine: false` AND `prior_spec.code.make_requests.endpoint_resolution.kind: static` | "Endpoint kind changing from `static` to `template-macro`. Was this intentional? If yes, the spec should be re-read." |
| PR adds `func (e *ExtImpXyz) UnmarshalJSON(data []byte) error` | `prior_spec.params.ext_struct.custom_unmarshal: false` | "Custom UnmarshalJSON added. Verify `ext.accepts_shapes` captures the new flexibility." |
| PR removes `kobler.go:23` const declaration | `prior_spec.quirks[]` contains `id: hardcoded-dev-endpoint` referencing that file/line | Flag for orchestrator: quirk's source line is gone — quirk should be removed from spec on next read. |
| PR changes `imp.ext.bidder.test` lookup from "first imp only" to "any imp" | `prior_spec.quirks[]` contains `id: dev-prod-toggle-via-imp-ext-test-flag` | "Quirk semantics changed. Re-read the spec to update the quirk summary." |
| PR adds a new alias YAML at `static/bidder-info/connektai.yaml` | `prior_spec.meta.parent_aliases` does not contain `connektai` | "New alias detected. Java port (if any) needs a corresponding `aliases: { connektai: ~ }` entry in the parent's bidder-config YAML (Rule 33)." |
| PR changes `adapter` struct field from `endpoint string` to `endpointTemplate *template.Template` | `prior_spec.code.adapter_struct.fields` shows old shape; `prior_spec.code.builder.template_parsed_at_build: false` | "Builder now parses template at build time. `endpoint_resolution.mechanism_go` should change to `text/template`." |
| PR adds `disabled: true` to `static/bidder-info/{xyz}.yaml` | `prior_spec.meta.disabled: false` | "Bidder being disabled. If a deploy-time token is being introduced (`#{REGION}#`-style), confirm with reviewer. Reference: PR #4502 appStockSSP." |

### 5.3 What the hook does NOT do

- The hook does NOT block PR review or change activation rules. Reviewer skills run their full workflows regardless of whether `prior_spec` is present.
- The hook does NOT auto-update the spec after the PR merges — that's the user's responsibility (re-run the orchestrator on the post-merge commit).
- The hook does NOT compare across languages — `pr-triage` is Go-only. A Java equivalent would live at `prebid-server-java/review/skills/pr-triage/` (not yet authored).

### 5.4 Where the hook is documented

The opt-in section is added to `pr-triage/SKILL.md` (separate file). See `## Optional: Prior-Spec Comparison (read/ integration)` in that file for the user-facing instructions and detection examples.

---

## 6. Spec lifecycle

### 6.1 Authoring cadence

Specs are authored on-demand:

- **One-time read** — user invokes `read-adapter-orchestrator --bidder=kobler` to understand an adapter. Output streams to stdout. Most common invocation pattern.
- **Per-release snapshot** — power user invokes `read-adapter-orchestrator --bidder=kobler --persist` after each prebid-server release. Spec is checked into the user's local read/specs/ for diff-comparison.
- **Per-major-PR snapshot** — when a PR substantially changes adapter behavior (new endpoint resolution kind, new batching rule, new quirk), the user re-runs the orchestrator to refresh `latest.yaml`.

### 6.2 Persistence

`--persist` (off by default) writes to `prebid-server-{lang}/read/specs/{bidder}/{shortsha}.{yaml,md}` and refreshes the `latest.yaml` symlink. The `read/specs/` directory is `.gitignore`'d by default — a user opting into checked-in specs must remove the gitignore entry.

The shortsha is the first 7 chars of `provenance.source.resolved_commit`. A directory may accumulate multiple snapshots over time (e.g., `read/specs/kobler/d7f8515.yaml`, `read/specs/kobler/8fb24e0.yaml`, ... + `latest.yaml` → newest).

### 6.3 Determinism guarantee

R4 (round-trip determinism) requires that re-running the orchestrator on the same commit produces a byte-identical YAML modulo `provenance.read.timestamp_utc` and `provenance.read.operator`. This is essential for diff comparison — a non-deterministic spec generates noise on every read.

A consumer (write/, port-go2java/, port-java2go/, pr-triage prior_spec) MAY rely on the YAML being byte-stable as long as the upstream commit is identical.

---

## 7. Cross-language workflow

When a user wants to port an adapter Go ↔ Java (or vice versa):

```
1. Read source-language spec
   prebid-server-go/read/skills/read-adapter-orchestrator --bidder=kobler --persist
   → read/specs/kobler/{shortsha}.yaml (source_language: go)

2. (Future) Run port-{lang2lang} skill
   prebid-server-java/port-go2java --in-spec=read/specs/kobler/latest.yaml
   → emits Java adapter PR-ready files

3. Read destination-language spec on the resulting branch
   prebid-server-java/read/skills/read-bidder-orchestrator --bidder=kobler --persist
   → read/specs/kobler/{shortsha}.yaml (source_language: java)

4. Verify with dual-spec assertion
   diff <(yq '.bidder_params_sha256' go-spec) <(yq '.bidder_params_sha256' java-spec)
   diff <(yq '.bidder_info.capabilities' go-spec) <(yq '.bidder_info.capabilities' java-spec)
   diff <(yq '.params.schema_interpretation' go-spec) <(yq '.params.schema_interpretation' java-spec)
   # All three MUST be byte-identical (R5).

5. CI on both sides
   prebid-server-go: go test ./adapters/kobler/...
   prebid-server-java: mvn -pl :prebid-server -Dtest=KoblerBidderTest test
```

The `cross_language.port_lineage.{source_pr, destination_pr}` field is populated from the dual-PR pair — for Kobler, that's `prebid/prebid-server#3904 → prebid/prebid-server-java#3684`. The list of port pairs is sourced from the reference list at `prebid-server-java/references/new-bid-adapter-prs.md` — entries tagged `port-from-go` carry the lineage. The Java reference list shows that many 2025 Java adapters are explicit ports from Go: Adverxo (#3705), Connatix (#3781), Ogury (#3788), Kobler (#3684), FeedAd (#3869), Seedtag (#3916), Kueez (#3930), Mobkoi (#3942), Adagio (#4027), Optidigital (#4054), Mediasquare (#4031), and more.

---

## 8. Limitations

The contract has bounded fidelity. Consumers MUST NOT assume:

### 8.1 Spec captures observed behavior, not intent

The `read/` orchestrator records what the source code does, not what it should do. A quirk pinned via `read/` may persist into a generated adapter via `write/` even when the quirk is an anti-pattern. Quirks-pinning often needs human refinement — that's why every quirk surfaces as a TODO in `write/` output and is NOT auto-applied.

Example: Kobler's `dev-prod-toggle-via-imp-ext-test-flag` quirk records that the testMode flag is pulled from imp.ext.bidder.test of the FIRST imp only (kobler.go line 55, `i==0`); other imps' test flags are ignored. A `write/` skill that round-trips the spec will preserve this behavior — but a reviewer might judge it as a bug. The spec cannot disambiguate.

### 8.2 Goldens must be re-authored when master moves

Golden specs at `prebid-server-go/read/test-fixtures/{bidder}.golden.spec.yaml` and `prebid-server-java/read/test-fixtures/{bidder}.golden.spec.yaml` are pinned to specific commits (`provenance.source.resolved_commit`). When prebid-server master moves significantly, the golden's behavioral fields may no longer match a fresh read. Stale goldens MUST be marked explicitly and re-authored — auto-regenerating goldens defeats the purpose of catching regressions.

### 8.3 R5 byte-equality is rare in practice

The `bidder_params_sha256` cross-language equality (R5) is the ideal — same JSON Schema bytes on both sides. In practice, most port pairs have whitespace divergence:

- Go writes 4-space indent with stray blank lines and no trailing newline (Optidigital, msft).
- Java writes 2-space indent with trailing newlines (most adapters).

Worked example — Optidigital. The Java spec at [`prebid-server-java/read/test-fixtures/optidigital.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/optidigital.golden.spec.yaml) line 22 carries a `cross-language-byte-divergence` warning: Go SHA `6bc977807ee6d779cd6fa167f9e152219cc2af6d151fac90606dcae1045eda31` ≠ Java SHA `93bad2a9790ba8dd6e38d2c88206910e10a9c682af7be2b726b5d64318bc6832`. Files are SEMANTICALLY identical (same properties, types, descriptions, required) but byte-divergent. R5 cross-language parity FAILS — port-fidelity violation that should be reconciled by reformatting one side to match the other.

The Appnexus pair has the same divergence (Java spec line 21–24): Java raw SHA `5946ec7d034be6f6f4033913751d074ffe75dacd9df542b30e1a44f41333ee12` ≠ Go SHA `20a3f193c62b1b3d6d2a0daf5dfaa3935a045c52b83af236693ebe9c3459106d`. Reviewer should regenerate the Java JSON from the Go canonical form to restore byte parity.

Consumers MUST treat R5 failures as port-fidelity warnings, not hard errors — most port pairs in the wild fail it.

### 8.4 Reviewer cohort is per-language

The Go and Java reviewer cohorts are wholly disjoint (only @bretg crosses both as cross-language coordinator). Review-pattern matchers (a hypothetical mechanism that "this reviewer always asks for X") MUST NOT be auto-transferred between languages. See [`review-pattern-transfer-policy.md`](review-pattern-transfer-policy.md) for the explicit ban. This affects a `pr-triage` style review skill but does NOT affect read/, write/, or port-{lang2lang}/ — those skills are language-aware by construction.

### 8.5 Custom quirks may exceed the taxonomy

Every behavioral field in the spec has a `custom` value as the escape hatch. R3 requires that `custom` be paired with a `quirks[]` entry. A consumer that hits `kind: custom` MUST consult the paired quirk for context — there is no enumerated mapping from `custom` to generated code. `write/` surfaces these as TODO comments; `port-{lang2lang}` surfaces them in `cross_language.{source}_specific_concerns[]`.

Example: msft's `iab_categories.go` has a 95-entry hardcoded map with custom curation logic. The spec captures `iab_category_storage.storage_kind: go-data-table, table_size: 95`, but the curation rules (which IAB IDs map to which Microsoft labels) are content not structure. A porter must hand-translate the curation table; the skills cannot infer it.

---

## 9. Summary

The Adapter Specification is the unidirectional contract between `read/` and four downstream consumers. Each consumer reads the spec independently; no consumer talks to another consumer through the spec. Determinism (R4) and cross-language structural parity (R5) are the two correctness guarantees that survive the contract — everything else is a hint, a TODO, or a quirk for human judgment.

The 46 port-translation rules at [`port-translation-rules.md`](port-translation-rules.md) are the contract for the language-pivoting consumers (`port-go2java`, `port-java2go`); the 15 enumerated behavioral fields at [`behavior-taxonomy.md`](behavior-taxonomy.md) are the contract for the language-internal consumer (`write/`).

The opt-in `pr-triage` hook is the only reverse-direction integration: review/ reads a spec to detect regressions on PR diffs. It is purely additive — review/ continues to function without read/.

---

## 10. Testing model — goldens vs. `evals.json`

### What this repo uses

The read-skill suite tests via THREE complementary mechanisms:

1. **Golden Adapter Specifications** at `prebid-server-{go,java}/read/test-fixtures/*.golden.spec.yaml`. Hand-authored YAML emissions pinned to specific upstream commits. Each is the byte-deterministic ground truth for one bidder-at-one-commit.
2. **Dual-spec assertions** at `cross-language-pairs/*.dual-spec-assertions.yaml`. Per-bidder cross-language equivalence/divergence declarations consumed by R5-strict and R5-divergent.
3. **R1–R10 CI rules** at `scripts/round-trip-ci.py`. Schema-driven invariants (file-reachability, sha integrity, custom-quirk pairing, round-trip determinism, cross-language parity, naming consistency, taxa registry, harness flag).

An additional CI gate at `scripts/tests/test_schema_contract.py` augments this with phantom-path detection — verifying every dotted reference in a SKILL.md resolves to a path defined in `adapter-spec.schema.json` or `behavior-taxonomy.md`.

### What standard skill-creator uses

Anthropic's skill-creator framework standardizes testing through `evals/evals.json` files alongside each skill. An entry there has the shape:

```json
{
  "skill": "<name>",
  "tests": [
    { "id": "...", "input": "...", "script_eval": "<bash assertion>" },
    { "id": "...", "input": "...", "model_eval": "<assertion prompt>" }
  ]
}
```

`script_eval` runs a deterministic bash check; `model_eval` invokes a secondary model to score the primary skill's output against an assertion. Both are oriented at runnable skills (e.g., a Python helper that returns a value) — the test harness invokes the skill, captures its output, and applies the assertion.

### Why we diverge

Read skills are NOT directly executable. They are LLM workflows: a SKILL.md instructs the operator (a Claude instance) to read source files, classify behavior against the taxonomy, and emit a YAML spec. There is no Python function to call, no return value to inspect. Three concrete consequences:

- **Determinism is the whole game.** R4 is the load-bearing rule: the same skill on the same commit must produce a byte-identical spec. Goldens give byte-deterministic regression coverage that `script_eval` would have to reconstruct from scratch — and `model_eval` would inject judgment-noise on every check.
- **Cross-language coupling.** R5 fails on the dual-spec-assertion level when Go and Java specs diverge on contract fields. This is a per-pair invariant — `evals.json`'s per-skill model can't natively express "the output of skill A and the output of skill B must agree."
- **Schema-anchored invariants.** R1–R10 are properties of the spec schema, not of any one skill's output. Any read skill that contributes to an emission shares the same rules — there's no per-skill `script_eval` that captures, say, R3's `custom`-quirk pairing without re-encoding the schema in the eval file.

Goldens + R-rules give us byte-stable artifacts AND schema-anchored invariants in one place. `evals.json` would partially duplicate this across each of the 8 (4 Go + 4 Java) skills' evals files.

### When to use which

- **Goldens (this repo's approach).** Use when the skill is an LLM-following-the-skill workflow whose output is a text artifact (YAML, JSON, Markdown report). Determinism is testable by comparing artifacts; correctness is testable by R-rules over the artifact. The 4 read-skill suites (per-language) all fit.
- **`evals.json` (skill-creator standard).** Use when the skill is, or embeds, a runnable script. Examples for the future:
  - A Python helper for fixture validation that exposes a CLI surface (`fixture-lint --fixture path/to/golden.yaml`). `script_eval` confirms exit codes; `model_eval` confirms the diagnostic text quality.
  - A future schema-migration helper that takes an old spec and a target `adapter_spec_version` and emits a migrated spec.
  - Any wrapper around `round-trip-ci.py` that re-runs it under matrix conditions (different upstream commits).
  In each case, the skill IS a function with a return value; `evals.json` covers it idiomatically.

### How they interoperate

They don't overlap, so they don't need to. Read skills stay on the goldens model; runnable helpers (when they appear) use `evals.json`. The two coexist in the same repo with disjoint test inputs (read skills test against goldens; runnable helpers test against scripted inputs). A SKILL.md that grows BOTH a workflow component AND a runnable component (rare; not expected for any current read skill) would land in both — its workflow side checked by goldens, its runnable side checked by `evals.json`.

### Migration anti-pattern (what NOT to do)

Don't translate the R-rules into per-skill `script_eval` entries. The result would be 8 SKILLs each shipping a copy of the same 10 bash assertions, drifting independently as the schema evolves. The single authoritative `round-trip-ci.py` + the schema-contract test (`test_schema_contract.py`) cover the same ground in one place, versioned alongside the schema documents they enforce.

---

## Sources

- Master plan: (Claude Code planning artifact) — Phase E section "Cross-skill integration + handoff" + the spec format definition.
- Canonical schema: [`adapter-spec.md`](adapter-spec.md) — full Adapter Specification format with worked Kobler dual-spec example.
- Port translation rules: [`port-translation-rules.md`](port-translation-rules.md) — 46 explicit Go ↔ Java rules indexed by spec field driver.
- Behavior taxonomy: [`behavior-taxonomy.md`](behavior-taxonomy.md) — enumerated values for behavioral fields and the `quirks[].edge_case_taxon` registry.
- Review-pattern transfer policy: [`review-pattern-transfer-policy.md`](review-pattern-transfer-policy.md) — disjoint reviewer-cohort finding and the transfer ban.
- Sibling Go orchestrator: [`../read-adapter-orchestrator/SKILL.md`](../read-adapter-orchestrator/SKILL.md) — discovery, fetch, dispatch, assembly, validation, emission for prebid-server-go.
- Sibling Java orchestrator: [`../../../../prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md`](../../../../prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md) — same role for prebid-server-java with Spring DI / unified YAML / inverted-alias / 4-file-split divergences.
- Opt-in hook in pr-triage: [`../../../review/skills/pr-triage/SKILL.md`](../../../review/skills/pr-triage/SKILL.md) — `## Optional: Prior-Spec Comparison (read/ integration)` section.
- Golden specs cited: [`../../test-fixtures/optidigital.golden.spec.yaml`](../../test-fixtures/optidigital.golden.spec.yaml), [`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml), [`../../test-fixtures/msft.golden.spec.yaml`](../../test-fixtures/msft.golden.spec.yaml), [`../../../../prebid-server-java/read/test-fixtures/optidigital.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/optidigital.golden.spec.yaml), [`../../../../prebid-server-java/read/test-fixtures/appnexus.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/appnexus.golden.spec.yaml), [`../../../../prebid-server-java/read/test-fixtures/rubicon.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/rubicon.golden.spec.yaml).
- Reference lists: `prebid-server-go/references/new-bid-adapter-prs.md` (Go new-adapter PRs with `Patterns Demonstrated` tags), `prebid-server-java/references/new-bid-adapter-prs.md` (Java new-adapter PRs; `port-from-go` tag identifies port pairs).
- Phase 2 reconnaissance findings (in master plan): cross-language hypothesis confirmation, 17 Go + 17 Java edge cases, taxonomy refactor (scalar→rules-list), 46 port-translation rules.
