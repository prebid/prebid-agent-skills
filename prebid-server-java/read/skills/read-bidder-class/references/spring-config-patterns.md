# Spring Config Patterns (Java)

Detail-heavy reference for Java-side Spring DI extraction. Consumed by [SKILL.md](../SKILL.md) Step 3 (`spring_config.*`) and Step 2 (`bidder_class.constructor.parameters[]` source/role classification). Cross-language schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json](../../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json) (top-level `spring_config` and `bidder_class` blocks; per ADR-001 these are nullable on Go specs and required-non-null on Java non-alias specs via `if/then/else` discrimination).

This file documents:

1. Factory class shapes (`@Configuration` + `@PropertySource` + `@Bean` factory method).
2. `BidderConfigurationProperties` subclass detection rules.
3. Bean dependencies extraction (constructor `@Autowired`, `@Value(${...})`, autowired beans).
4. Standard collaborator catalog (`JacksonMapper`, `CurrencyConversionService`, `IdGenerator`, `Clock`, `BidderUtil`).
5. Lombok annotations to recognize (class-level + field-level).

---

## Factory class shape

The `@Configuration` class is the entry point for Spring's Bean discovery. Canonical layout:

```java
@Configuration
@PropertySource(value = "classpath:/bidder-config/kobler.yaml", factory = YamlPropertySourceFactory.class)
@ConditionalOnProperty(name = "adapters.kobler.enabled", havingValue = "true")
public class KoblerConfiguration {

    private static final String BIDDER_NAME = "kobler";

    @Bean("koblerConfigurationProperties")
    @ConfigurationProperties("adapters.kobler")
    KoblerConfigurationProperties configurationProperties() {
        return new KoblerConfigurationProperties();
    }

    @Bean
    BidderDeps koblerBidderDeps(KoblerConfigurationProperties config,
                                CurrencyConversionService currencyConversionService,
                                @NotBlank @Value("${external-url}") String externalUrl,
                                JacksonMapper mapper) {
        return BidderDepsAssembler.<KoblerConfigurationProperties>forBidder(BIDDER_NAME)
                .withConfig(config)
                .usersyncerCreator(UsersyncerCreator.create(externalUrl))
                .bidderCreator(cfg -> new KoblerBidder(
                        cfg.getEndpoint(),
                        cfg.getDevEndpoint(),
                        currencyConversionService,
                        mapper))
                .assemble();
    }
}
```

### Extraction rules

| Spec field | Source | Notes |
|---|---|---|
| `factory_class` | Class declaration `public class <Name>Configuration` (or `<Name>BidderConfiguration` per edge case #19). | Record verbatim. |
| `factory_method` | The `@Bean` method that returns `BidderDeps`. Method-name convention: `<name>BidderDeps`. | One per factory class. |
| `property_source_path` | The `value` attribute of `@PropertySource`. | E.g., `classpath:/bidder-config/kobler.yaml`. |
| `bidder_creator_lambda` | The verbatim lambda body inside `.bidderCreator(cfg -> ...)`. | Preserve indentation, line breaks, constructor-arg order. Round-trip fidelity is load-bearing. |
| `bean_dependencies[]` | The `@Bean` method's parameter list. | Each parameter recorded as `{ name, type, source }`. |

### Factory class naming variance (edge case #19)

| Naming | Bidder examples | When |
|---|---|---|
| `<Name>Configuration` | Kobler, Optidigital, FeedAd, Mediasquare, most Java adapters | The dominant convention. |
| `<Name>BidderConfiguration` | Adverxo, a few legacy adapters | Equivalent class with extra `Bidder` infix. |

Both are functionally identical. Record the verbatim class name in `spring_config.factory_class` — do NOT normalize.

---

## BidderConfigurationProperties subclass detection (edge case #20)

When the adapter has YAML fields beyond the framework's default `BidderConfigurationProperties` (which covers `endpoint`, `enabled`, `geoscope`, etc.), the factory class declares an inner static class:

```java
@Validated
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
private static class KoblerConfigurationProperties extends BidderConfigurationProperties {

    @NotBlank
    private String devEndpoint;
}
```

### Detection rules

A class qualifies as a `BidderConfigurationProperties` subclass when ALL of these are true:

1. It is declared inside the factory class (typical) OR as a top-level class in the same package (rare).
2. It `extends BidderConfigurationProperties` (the framework's base class).
3. It is annotated `@Data` (Lombok) — required for Spring's setter-based property binding.
4. It declares at least ONE field beyond what the parent provides.

### Extraction rules

| Spec field | Source |
|---|---|
| `configuration_properties_class.name` | The subclass identifier (e.g., `KoblerConfigurationProperties`). |
| `configuration_properties_class.extends` | Typically `BidderConfigurationProperties`. Verify this is exactly that value; deviations (rare) flag a quirk. |
| `configuration_properties_class.extra_fields[]` | Each declared field as `{ name, type, validations[] }`. |
| `configuration_properties_class.nested_classes[]` | Inner static classes inside the subclass (e.g., Huaweiads `ExtraInfo`). |
| `configuration_properties_class.lombok_annotations[]` | Class-level Lombok annotations: `Data`, `EqualsAndHashCode`, `NoArgsConstructor`. List the annotation NAMES (not the full annotation expression). |

### Extra-fields validation patterns

Bean Validation annotations recognized:

- `@NotBlank` — string must be non-null and not just whitespace.
- `@NotNull` — non-null but may be empty.
- `@NotEmpty` — non-null and not empty (collections/strings).
- `@Size(min, max)` — length constraint.
- `@Min`, `@Max` — numeric bounds.
- `@Pattern(regexp)` — regex constraint.
- `@Email` — email format.

Record each annotation as a string in the `validations[]` list including the leading `@` (e.g., `["@NotBlank"]` or `["@Size(min=1, max=10)"]`).

### Worked examples

#### Kobler — `devEndpoint` only

```java
@Validated @Data @EqualsAndHashCode(callSuper = true) @NoArgsConstructor
private static class KoblerConfigurationProperties extends BidderConfigurationProperties {
    @NotBlank
    private String devEndpoint;
}
```

Spec emits:

```yaml
configuration_properties_class:
  name: KoblerConfigurationProperties
  extends: BidderConfigurationProperties
  extra_fields:
    - name: devEndpoint
      type: String
      validations: ["@NotBlank"]
  nested_classes: []
  lombok_annotations: [Data, EqualsAndHashCode, NoArgsConstructor]
```

#### Appnexus — `platformId` + inlined IAB-categories map

```java
@Validated @Data @EqualsAndHashCode(callSuper = true) @NoArgsConstructor
public static class AppnexusConfigurationProperties extends BidderConfigurationProperties {
    private Integer platformId;
    private Map<String, Long> iabCategories;     // inlined ~120 entries in YAML
}
```

Spec emits:

```yaml
configuration_properties_class:
  name: AppnexusConfigurationProperties
  extends: BidderConfigurationProperties
  extra_fields:
    - name: platformId
      type: Integer
      validations: []
    - name: iabCategories
      type: "Map<String, Long>"
      validations: []
  nested_classes: []
  lombok_annotations: [Data, EqualsAndHashCode, NoArgsConstructor]
```

The inlined `iabCategories` map carries 120-ish entries directly in `bidder-config/appnexus.yaml`. Read-bidder-class does NOT inventory the map's contents (that is `read-bidder-config`'s job), but it DOES set `iab_category_storage.storage_kind: yaml-inlined` + `yaml_field: iab-categories` + `table_size: ~120` + `delivery_mechanism: constructor-arg` (because the lambda passes `cfg.getIabCategories()` to the bidder constructor).

#### Huaweiads / NextMillennium — nested ExtraInfo

```java
@Validated @Data @EqualsAndHashCode(callSuper = true) @NoArgsConstructor
public static class HuaweiAdsConfigurationProperties extends BidderConfigurationProperties {
    private ExtraInfo extraInfo;

    @Data @NoArgsConstructor
    public static class ExtraInfo {
        private String pkgNameConvert;
        private String closeSiteSelectionByCountry;
    }
}
```

Spec emits:

```yaml
configuration_properties_class:
  name: HuaweiAdsConfigurationProperties
  extends: BidderConfigurationProperties
  extra_fields:
    - name: extraInfo
      type: ExtraInfo
      validations: []
  nested_classes:
    - name: ExtraInfo
      fields:
        - { name: pkgNameConvert, type: String }
        - { name: closeSiteSelectionByCountry, type: String }
  lombok_annotations: [Data, EqualsAndHashCode, NoArgsConstructor]
```

### When NO subclass exists

Many adapters (e.g., Optidigital, Generic, AAX) are happy with the default `BidderConfigurationProperties` and declare no subclass. Set `configuration_properties_class: null` in the spec. The factory `@Bean` method then directly takes `BidderConfigurationProperties` as a parameter (no explicit subclass type).

---

## Bean dependencies extraction

The factory `@Bean` method's parameter list is the canonical source for `bean_dependencies[]`. Each parameter has:

- A type (e.g., `KoblerConfigurationProperties`, `CurrencyConversionService`, `String`, `JacksonMapper`).
- A name (the parameter name).
- An optional Spring annotation (`@Value(${...})`, `@Qualifier(...)`).

### Source classification

| Source value | When | Example |
|---|---|---|
| `framework-injected` | The parameter has no explicit annotation; Spring resolves it by type from the application context (autowired bean). | `CurrencyConversionService currencyConversionService`, `JacksonMapper mapper`, `KoblerConfigurationProperties configurationProperties` |
| `@Value(${...})` | The parameter is annotated `@Value("${...}")` and gets a config-property value. | `@Value("${external-url}") String externalUrl` |

The `source` field on each `bean_dependencies[]` entry uses the verbatim annotation expression for `@Value` cases — preserves operator-substituted defaults like `@Value("${external-url:}")`.

### Standard collaborators

The framework provides a fixed catalog of injectable collaborators. Recognize these by type:

| Type | Role |
|---|---|
| `JacksonMapper` | JSON marshal/unmarshal (`mapper.encodeToBytes`, `mapper.mapper().convertValue`). |
| `CurrencyConversionService` | Currency conversion (`convertCurrency(value, bidRequest, from, to) BigDecimal`). |
| `IdGenerator` | UUID generation (used by some bidders for request IDs). |
| `Clock` | Time-of-bid context (used for HMAC timestamps and currency rate selection). |
| `BidderUtil` | Static helper for `defaultRequest(...)` — not always autowired but referenced by name. |

When a constructor parameter on the BIDDER class (Step 2 in SKILL.md) has any of these types AND comes from `framework-injected` source, set `bidder_class.constructor.parameters[].role: helper-collaborator`.

### Worked example — Kobler bean dependencies

The Kobler factory `@Bean` method (verbatim from `prebid/prebid-server-java@69b1993c` upstream):

```java
@Bean
BidderDeps koblerBidderDeps(KoblerConfigurationProperties config,
                            CurrencyConversionService currencyConversionService,
                            @NotBlank @Value("${external-url}") String externalUrl,
                            JacksonMapper mapper) {
```

Spec emits (parameter order matches upstream — emit verbatim, do NOT reorder):

```yaml
bean_dependencies:
  - name: config
    type: KoblerConfigurationProperties
    source: framework-injected         # The bean is provided by the @Bean above.
  - name: currencyConversionService
    type: CurrencyConversionService
    source: framework-injected
  - name: externalUrl
    type: String
    source: "@Value(${external-url})"
  - name: mapper
    type: JacksonMapper
    source: framework-injected
```

Note: the `configurationProperties` bean is technically defined by the same factory class via the `@Bean("koblerConfigurationProperties")` method, but from the factory `@Bean` method's perspective, it is autowired by type — so `source: framework-injected`.

---

## Constructor parameter classification on the BIDDER class

The bidder-class constructor (Step 2 in SKILL.md) parameters get TWO classification fields: `source` and `role`. The factory's `bidder_creator_lambda` is the source of truth for how each parameter gets its value.

### Decision tree

For each bidder-class constructor parameter, look up the corresponding lambda argument:

1. If the lambda argument is `cfg.getX()` (a getter on the configuration-properties class):
   - `source: config-field`
   - `role: properties` (the parameter is a config-derived String/primitive)
2. If the lambda argument is a captured outer variable that is a known framework collaborator (`currencyConversionService`, `mapper`, `idGenerator`, `clock`):
   - `source: framework-injected`
   - `role: helper-collaborator`
3. If the lambda argument is `externalUrl` or another `@Value`-injected string:
   - `source: framework-injected`
   - `role: properties` (or `helper-collaborator` if it is a URL the bidder uses for callbacks)
4. Anything else:
   - `source: framework-injected`
   - `role: framework-injected`

### Worked example — Kobler bidder constructor

The Kobler bidder constructor:

```java
public KoblerBidder(String endpointUrl,
                    String devEndpoint,
                    CurrencyConversionService currencyConversionService,
                    JacksonMapper mapper) {
    HttpUtil.validateUrl(endpointUrl);
    this.endpointUrl = endpointUrl;
    this.devEndpoint = devEndpoint;
    this.currencyConversionService = currencyConversionService;
    this.mapper = mapper;
}
```

Paired with the factory lambda:

```java
.bidderCreator(cfg -> new KoblerBidder(
        cfg.getEndpoint(),                  // → endpointUrl: source=config-field, role=properties
        cfg.getDevEndpoint(),               // → devEndpoint: source=config-field, role=properties
        currencyConversionService,          // → source=framework-injected, role=helper-collaborator
        mapper))                            // → source=framework-injected, role=helper-collaborator
```

Spec emits (matches Kobler golden lines 286-304):

```yaml
constructor:
  arity: 4
  parameters:
    - name: endpointUrl
      type: String
      source: config.endpoint
      role: properties
    - name: devEndpoint
      type: String
      source: config.devEndpoint
      role: properties
    - name: currencyConversionService
      type: CurrencyConversionService
      source: framework-injected
      role: helper-collaborator
    - name: mapper
      type: JacksonMapper
      source: framework-injected
      role: helper-collaborator
```

For the standard collaborator types listed above (`CurrencyConversionService`, `JacksonMapper`, `IdGenerator`, `Clock`, `BidderUtil`, `HttpUtil`), `role: helper-collaborator` is canonical. The `role: framework-injected` value is reserved for parameters that are framework-supplied but do NOT fit the standard-collaborator catalog (catch-all from rule 4 below).

---

## Lombok annotations to recognize

Class-level annotations on the configuration-properties class:

| Annotation | Role |
|---|---|
| `@Data` | Generates getters, setters, `equals`, `hashCode`, `toString`. Required for Spring property binding. |
| `@EqualsAndHashCode(callSuper = true)` | Includes the parent class's fields in `equals`/`hashCode`. Standard for subclasses of `BidderConfigurationProperties`. |
| `@NoArgsConstructor` | Generates the no-arg constructor Spring needs. |
| `@Validated` | Spring annotation (not Lombok) marking the class for validation. |

On the bidder class itself, Lombok is rarely used (the class is hand-written). On `proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java`, Lombok is heavily used — see [proto-pojo-patterns.md](proto-pojo-patterns.md).

### When to flag deviations

If the configuration-properties subclass omits `@Data` or uses `@Value` instead, this is a structural deviation that breaks Spring property binding. Flag with quirk `edge_case_taxon: incomplete-classification` and a free-text summary describing the missing annotation. Reviewers typically catch this in code review, but PRs can land if the validation happens to pass.

---

## When `factory_class != <Name>Configuration` AND `factory_class != <Name>BidderConfiguration`

Edge case #19 covers the two known patterns. Anything else (e.g., `KoblerConfig`, `KoblerSpringConfig`) is a deviation. Record the verbatim class name and emit a quirk `edge_case_taxon: incomplete-classification`.

---

## Sources

- Plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md`.
- Schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md).
- Java reference PR list: [../../../../references/new-bid-adapter-prs.md](../../../../references/new-bid-adapter-prs.md) — see Pattern Index tags `configuration-properties-subclass`, `dev-prod-endpoint-toggle`.
- Golden spec: [../../../test-fixtures/kobler.golden.spec.yaml](../../../test-fixtures/kobler.golden.spec.yaml) — `spring_config:` block (lines 245–277), `bidder_class.constructor` (lines 286–304).
- Phase 2 reconnaissance findings (in plan): `BidderConfigurationProperties` subclass observed in Kobler (`devEndpoint`), Appnexus (`platformId` + `iabCategories`), Huaweiads / NextMillennium (`ExtraInfo` nested class).
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
