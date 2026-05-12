# Bidder-Config Field Index — Java

Complete YAML schema mapping for `src/main/resources/bidder-config/{x}.yaml` PLUS the canonical Spring `@Configuration` Java surface that wraps it. Use this to trace any changed YAML field to its base-class POJO + jakarta validation constraint, and any changed Java line to its Spring DI semantic. The Go-side analog is `prebid-server-go/review/skills/bidder-info-pr-review/references/field-index.md` (YAML side only — Go has no per-bidder factory class).

**Upstream sources (canonical):**
- Base POJO: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/spring/config/bidder/model/BidderConfigurationProperties.java
- MetaInfo POJO: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/spring/config/bidder/model/MetaInfo.java
- Usersync POJO: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/spring/config/bidder/model/usersync/UsersyncConfigurationProperties.java
- Canonical Spring config: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java

> **Sync policy:** Local snapshot. `pr-triage-java`'s Step 2 runs centralized drift checks against `bidder-config` (the base POJO) and `framework-spring-di` (`BidderDepsAssembler` + `UsersyncerCreator`); SKILL.md Step 1b reads those results. If the base class gains fields, update Part A; if assembler signatures change, update Part B.

For framework-wide concerns (Spring DI conventions in detail, Lombok semantics, mvn-checkstyle ruleset, F-new trap catalog) see [../../shared/framework-utilities-java.md](../../shared/framework-utilities-java.md) — do NOT duplicate.

---

## Part A — `bidder-config/{x}.yaml` field index

Java's `bidder-config/{x}.yaml` is the **unified** Spring property-source file. It carries everything that lives in Go's `static/bidder-info/{x}.yaml` PLUS the operator-supplied endpoint URL, the usersync URL block, and the `aliases:` map (Java aliases are NESTED under the parent — Port Translation Rule 33). Every field below maps to a typed POJO field via Spring `@ConfigurationProperties` relaxed-binding (kebab-case YAML ↔ camelCase Java).

### A.1 Root wrapper

```yaml
adapters:
  {x}:               # MUST equal BIDDER_NAME constant in {X}Configuration.java (lowercase)
    endpoint: ...
    enabled: ...
    ...
```

The `adapters` root is the Spring property prefix for the `BidderCatalog`. The `{x}` sub-key is the canonical bidder name; collision with another `bidder-config/*.yaml` adapter key is a **FAIL** (pr-triage-java surfaces collisions in the manifest's `New aliases:` / `New bidders:` cross-check).

### A.2 Top-level adapter fields (under `adapters.{x}`)

These bind to `BidderConfigurationProperties` (the base class — **13 YAML-bindable fields** verified at SHA `a1fe64e123d6`) via Spring relaxed-binding. The base class also declares 2 non-binding internal fields (`defaultProperties` autowired, `selfClass` runtime-class reference) that are not part of the YAML surface.

| YAML Path | Java Field (base class) | Type | Required | Validation / Constraint | Reviewer Concerns |
|-----------|-------------------------|------|----------|-------------------------|-------------------|
| `endpoint` | `endpoint` | `String` | **Yes** | `@NotBlank` | URL well-formed; HTTPS preferred (HTTP permitted, INFO); macros `{{PREBID_SERVER_ENDPOINT}}` (framework-resolved via `resolveEndpoint` helper) or per-bidder tokens `{{adUnitId}}` (resolved in `{X}Bidder`). Non-template placeholders (`#{REGION}#`, `${X}`) require `enabled: false` + comment block (Rule 11 LANDED). See SKILL.md "Workflow: Endpoint Changed". |
| `enabled` | `enabled` | `Boolean` | No | — | Defaults to value in `DefaultBidderConfigurationProperties.enabled` (typically `true`). **Rule 45**: new bidder ships with `enabled: false` when region placeholders exist; aliases routinely ship with `enabled: false` (canonical Adverxo pattern). See SKILL.md "Workflow: Bidder Disabled". |
| `ortb-version` | `ortbVersion` | `OrtbVersion` (enum) | No | — | Enum values: `ORTB_2_5`, `ORTB_2_6`. YAML accepts string `"2.6"` per Java edge case #29 quoting rule. Defaults to `DefaultBidderConfigurationProperties.ortbVersion`. |
| `pbs-enforces-ccpa` | `pbsEnforcesCcpa` | `Boolean` | No | — | Rarely set per-bidder; framework default `true`. |
| `modifying-vast-xml-allowed` | `modifyingVastXmlAllowed` | `Boolean` | No | — | Video adapters that opt out of VAST-XML mutation. Defaults to framework default. See SKILL.md "Workflow: Modifying VAST XML Changed". |
| `deprecated-names` | `deprecatedNames` | `List<String>` | No | — | List of pre-rename adapter names; Spring routes deprecated names to current bidder for compatibility windows. |
| `aliases` | `aliases` | `Map<String, Object>` | No | — | Java aliases are NESTED under parent (Port Translation Rule 33 inversion vs. Go). Each entry is either tilde-inherit (`adport: ~` — value is YAML null) or full-block (`adport: { endpoint: ..., usersync: { ... } }`). See SKILL.md "Workflow: Aliases Block Changed". |
| `debug` | `debug` | `Debug` (POJO) | No | `@NotNull Boolean allow` when present | Per-bidder debug toggle. |
| `meta-info` | `metaInfo` | `MetaInfo` (POJO) | **Yes** | `@NotNull` (base class) + see A.3 below | Holds maintainer-email, media-types, vendor-id, supported-vendors, currency-accepted. |
| `usersync` | `usersync` | `UsersyncConfigurationProperties` (POJO) | No | see A.5 below | Holds cookie-family-name + iframe/redirect blocks. |
| `endpoint-compression` | `endpointCompression` | `CompressionType` (enum) | No | — | Enum values: `NONE`, `GZIP`. Spring relaxed-binding accepts lowercase `gzip` (Java edge case: this is the camelCase↔kebab-case enum match, distinct from Go's case-sensitive `"GZIP"`-only comparison). See SKILL.md "Workflow: Endpoint Compression Changed". |
| `ortb` | `ortb` | `Ortb` (POJO) | No | see A.4 below | F-new-44 zone. Java's key is `ortb` (Go's is `openrtb`). |
| `tmax-deduction-ms` | `tmaxDeductionMs` | `long` | No | — | Per-bidder timeout buffer subtracted from tmax. Operator-controlled. |
| `geoscope` | `geoscope` | (NOT bound in current upstream — silently dropped by Spring relaxed-binding) | No | — | List of ISO 3166-1 alpha-3 country codes, `GLOBAL`, `EEA`, or `!`-prefix exclusions. **Verified at SHA `a1fe64e123d6`: `BidderConfigurationProperties` has NO `geoscope` field and `BidderInfoCreator` has NO `getGeoscope()` reference** — the key parses as YAML but Spring relaxed-binding finds no target setter, so it is silently discarded. Operators should treat the field as documentation-only until upstream binds it. The bare empty `geoscope:` line is the F-new-67/69/72 trap — **INFO**; omit the field entirely or supply a list. Reviewers flagging "geoscope changes" should note that the field is currently unbound. See SKILL.md "Workflow: Geoscope Changed". |
| `white-label-only` | (custom property — consumed downstream) | `Boolean` | No | — | Marks the bidder as available only as a white-label parent (aliases reference it). Does NOT preclude Java adapter code on the parent. See SKILL.md "Workflow: White-Label Policy" + framework-utilities-java.md §1. |
| `extra-info` | (custom property) | `String` (JSON) | No | Must be valid JSON if present | Rarely used in Java; legacy of Go-side `extra_info`. |
| custom keys, e.g. `dev-endpoint` | (declared on Rule 35 typed-subclass) | varies | No | typed-subclass `@NotBlank` etc. | Rule 35 typed-config — operator-defined fields that extend `BidderConfigurationProperties`. Canonical: Kobler's `dev-endpoint: ...` → `private String devEndpoint` in `KoblerConfigurationProperties extends BidderConfigurationProperties`. See SKILL.md "Workflow: Typed-Config Subclass" + Part C.5 below. |

### A.3 `meta-info` block (binds to `MetaInfo` POJO)

```yaml
adapters:
  {x}:
    meta-info:
      maintainer-email: ...
      app-media-types: [...]
      site-media-types: [...]
      dooh-media-types: [...]
      supported-vendors: [...]
      currency-accepted: [...]
      vendor-id: N
```

| YAML Path | Java Field | Type | Required | Validation | Reviewer Concerns |
|-----------|-----------|------|----------|------------|-------------------|
| `meta-info.maintainer-email` | `maintainerEmail` | `String` | **Yes** | `@NotBlank` | Manual "received" gate per SKILL.md Workflow: Maintainer Email Changed. Generic-domain (`gmail.com`, etc.) → INFO; personal-name pattern → WARN. Cross-language: Go's `maintainer.email`. |
| `meta-info.app-media-types` | `appMediaTypes` | `List<MediaType>` | No | enum-constrained | Values: `banner`, `video`, `native`, `audio` (the `MediaType` enum). At least one platform must be declared (across app/site/dooh) for the bidder to be useful. Cross-language: Go's `capabilities.app.mediaTypes` (Port Translation Rule 34 flattening). |
| `meta-info.site-media-types` | `siteMediaTypes` | `List<MediaType>` | No | enum-constrained | Same. |
| `meta-info.dooh-media-types` | `doohMediaTypes` | `List<MediaType>` | No | enum-constrained | DOOH is uncommon; flag if declared without IT fixture coverage. |
| `meta-info.supported-vendors` | `supportedVendors` | `List<String>` | No | — | Often present as bare `supported-vendors:` (YAML null) — harmless. |
| `meta-info.currency-accepted` | `currencyAccepted` | `List<String>` | No | — | ISO 4217 codes. |
| `meta-info.vendor-id` | `vendorId` | `Integer` | **Yes** | `@NotNull` | Integer. `0` means "not IAB registered" and is the default. GVL lookup via `https://vendor-list.consensu.org/v3/vendor-list.json`. Cross-language: Go's `gvlVendorID` (camelCase) ↔ Java's `vendor-id` (kebab-case). See SKILL.md "Workflow: GVL Vendor ID Changed". |

### A.4 `ortb` block (binds to `Ortb` POJO)

```yaml
adapters:
  {x}:
    ortb:
      multiformat-supported: true     # bound via @JsonProperty("multiformat-supported")
```

| YAML Path | Java Field | Type | Required | Validation | Reviewer Concerns |
|-----------|-----------|------|----------|------------|-------------------|
| `ortb.multiformat-supported` | `multiFormatSupported` | `Boolean` | **Yes** when `ortb:` block present | `@NotNull` + `@JsonProperty("multiformat-supported")` | The `@JsonProperty` rename is required because relaxed-binding would otherwise map to `multiformatSupported` (one word). F-new-44 trap zone. Cross-language: Go's `openrtb.multiformat-supported`. |

**Note**: `ortb.version` and `ortb.gpp-supported` are **NOT** in the Java `Ortb` POJO. The `ortb-version` field lives at adapter top-level (`adapters.{x}.ortb-version`, binding to `BidderConfigurationProperties.ortbVersion`). GPP support is signaled implicitly via the presence of `{{gpp}}` / `{{gpp_sid}}` macros in usersync URLs — there is no `gpp-supported` boolean in Java. SKILL.md cross-field rule #10 covers the macro-presence check.

### A.5 `usersync` block (binds to `UsersyncConfigurationProperties` POJO)

```yaml
adapters:
  {x}:
    usersync:
      enabled: true
      cookie-family-name: {x}
      iframe:
        url: https://{host}/sync?gdpr={{gdpr}}&consent={{gdpr_consent}}&us_privacy={{us_privacy}}&redirect={{redirect_url}}
        uid-macro: '$UID'
        support-cors: false
      redirect:
        url: ...
        uid-macro: ...
        support-cors: ...
      skipwhen:
        ...
```

| YAML Path | Java Field | Type | Required | Validation | Reviewer Concerns |
|-----------|-----------|------|----------|------------|-------------------|
| `usersync.enabled` | `enabled` | `Boolean` | No | — | Defaults to `true` (set in `BidderConfigurationProperties.init()` `@PostConstruct`). |
| `usersync.cookie-family-name` | `cookieFamilyName` | `String` | **Yes** when `usersync:` present | `@NotBlank` | MUST be unique across all bidders (Spring fails fast at startup on collision). For aliases declaring per-alias usersync, MUST equal the alias name (canonical Adverxo: `adport`'s cookie-family-name is `adport`). |
| `usersync.iframe` | `iframe` | `UsersyncMethodConfigurationProperties` | No | — | iframe sync block. |
| `usersync.redirect` | `redirect` | `UsersyncMethodConfigurationProperties` | No | — | redirect (image) sync block. |
| `usersync.skipwhen` | `skipwhen` | `UsersyncBidderRegulationScopeProperties` | No | — | GDPR / GPP-SID skip conditions. |

#### `UsersyncMethodConfigurationProperties` (per-iframe / per-redirect)

| YAML Suffix | Java Field | Type | Required | Validation | Notes |
|-------------|-----------|------|----------|------------|-------|
| `.url` | `url` | `String` | **Yes** | `@NotBlank` | Required macros: `{{gdpr}}`, `{{gdpr_consent}}`, `{{us_privacy}}`, `{{redirect_url}}`. Optional: `{{gpp}}`, `{{gpp_sid}}`. **Java uses lowercase + underscore** (Port Translation Rule 12; Go uses `{{.GDPR}}`, `{{.GDPRConsent}}`). HTTPS required — HTTP usersync URLs are **FAIL**. |
| `.uid-macro` | `uidMacro` | `String` | No | — | Bidder-specific token, e.g., `$UID`, `<vsid>`, `[USER_ID]`. |
| `.support-cors` | `supportCors` | `Boolean` | **Yes** when method block present | `@NotNull` | Boolean. |
| `.format-override` | `formatOverride` | `UsersyncFormat` (enum) | No | — | Enum: `BLANK`, `IMAGE`. |

### A.6 Alias nesting forms (within `adapters.{x}.aliases`)

```yaml
# Tilde-inherit (full inheritance of parent fields):
aliases:
  adport: ~

# Full-block (selective override):
aliases:
  adport:
    enabled: false
    endpoint: https://adport.pbsadverxo.com/auction?id={{adUnitId}}&auth={{auth}}
    usersync:
      enabled: false
      cookie-family-name: adport
      iframe: { url: ..., uid-macro: '$UID', support-cors: false }
      redirect: { url: ..., uid-macro: '$UID', support-cors: false }
```

| Form | Reviewer Concerns |
|------|-------------------|
| Tilde-inherit (`adport: ~`) | Fully valid — do NOT flag as "missing fields". Per-alias usersync inherits parent's verbatim. Bidder-rename three-step refactor often produces tilde-inherit (Java edge case #33). |
| Full-block | Each override field validated against its base-class constraint. Per-alias `cookie-family-name` MUST equal alias name. Per-alias endpoint macros MUST be resolvable by parent's `resolveEndpoint` OR consumed by parent's `{X}Bidder` (cross-skill concern 5a). |

Aliases do NOT have an alias-side `meta-info` override — capabilities, vendor-id, maintainer-email inherit verbatim from parent.

### A.7 Custom properties — Rule 35 typed-config

When a bidder requires operator-supplied configuration beyond the 14 base fields (canonical: Kobler's `dev-endpoint` for the dev-mode endpoint), the YAML declares the field at adapter top-level and the Configuration class extends `BidderConfigurationProperties` with a typed subclass declaring the matching field. See Part C.5 below and SKILL.md "Workflow: Typed-Config Subclass".

```yaml
adapters:
  kobler:
    endpoint: "https://bid.essrtb.com/bid/prebid_server_rtb_call"
    dev-endpoint: "https://bid-service.dev.essrtb.com/bid/prebid_server_rtb_call"  # Rule 35 typed-config
```

---

## Part B — Spring `@Configuration` Java field index

The `{X}Configuration.java` / `{X}BidderConfiguration.java` file (filename variation is historical — see SKILL.md "Filename convention guidance") is the per-bidder Spring DI factory. There is **no Go analog** — Go uses a single `exchange/adapter_builders.go` map. Each Java config file has the same canonical shape; reviewers triage diffs against this shape.

### B.1 Class-level annotations

| Annotation | Required | Purpose | Reviewer Concerns |
|------------|----------|---------|-------------------|
| `@Configuration` | **Yes** | Marks class as a Spring singleton bean factory | Missing is **FAIL** — Spring will not instantiate. |
| `@PropertySource(value = "classpath:/bidder-config/{x}.yaml", factory = YamlPropertySourceFactory.class)` | **Yes** | Wires the per-bidder YAML into Spring's property environment | The `value` path MUST match the actual YAML filename; the `factory` MUST be `YamlPropertySourceFactory.class` (Spring's default factory is .properties-only). See SKILL.md "Workflow: PropertySource Wiring". |
| `@ConditionalOnProperty(prefix = "adapters.{x}", name = "enabled", havingValue = "true")` | No | Conditional activation; skips bean instantiation when `adapters.{x}.enabled=false` | Used by some bidders for env-toggled activation; not part of the canonical Kobler template. When present, must reference the same `adapters.{x}` prefix as `@ConfigurationProperties`. |

### B.2 Method-level annotations + signatures

#### B.2.1 The `configurationProperties()` bean factory

```java
@Bean("{x}ConfigurationProperties")
@ConfigurationProperties("adapters.{x}")
{X}ConfigurationProperties configurationProperties() {
    return new {X}ConfigurationProperties();
}
```

| Element | Required | Constraint | Reviewer Concerns |
|---------|----------|------------|-------------------|
| `@Bean("{x}ConfigurationProperties")` | **Yes** | Bean name MUST match Spring autowire-by-name pattern (lowercase + suffix `ConfigurationProperties`) | Mismatch with the `bidderDeps` parameter name breaks autowiring → **FAIL**. SKILL.md cross-field rule #3. |
| `@ConfigurationProperties("adapters.{x}")` | **Yes** | Prefix MUST equal the YAML wrapper key (`adapters.{x}`) | Mismatch produces silent zero-field binding → **FAIL**. SKILL.md cross-field rule #4. |
| Return type | **Yes** | When no Rule 35 subclass: `BidderConfigurationProperties`. When Rule 35: `{X}ConfigurationProperties extends BidderConfigurationProperties` | If a Rule 35 subclass is declared but the bean returns the base class, the typed fields are unreachable → **FAIL**. SKILL.md cross-field rule #6. |
| `@Validated` (on subclass) | When Rule 35 | Triggers jakarta validation at startup | Without `@Validated`, `@NotBlank`/`@NotNull` on subclass fields are inert. See framework-utilities-java.md §1.7. |

#### B.2.2 The `BidderDeps` bean factory (canonical Kobler signature)

```java
@Bean
BidderDeps {x}BidderDeps({X}ConfigurationProperties config,
                          CurrencyConversionService currencyConversionService,   // bidder-specific dependencies
                          @NotBlank @Value("${external-url}") String externalUrl,
                          JacksonMapper mapper) {
    return BidderDepsAssembler.<{X}ConfigurationProperties>forBidder(BIDDER_NAME)
            .withConfig(config)
            .usersyncerCreator(UsersyncerCreator.create(externalUrl))
            .bidderCreator(cfg -> new {X}Bidder(
                    cfg.getEndpoint(),
                    // ... other constructor args from cfg + injected deps
                    mapper))
            .assemble();
}
```

| Element | Required | Reviewer Concerns |
|---------|----------|-------------------|
| `@Bean` | **Yes** | Missing is **FAIL** — `BidderDeps` not registered, `BidderCatalog` cannot find bidder at startup. |
| Method name `{x}BidderDeps` | **Yes** | Spring autowire-by-name. Bean parameter name MUST match the `@Bean("{x}ConfigurationProperties")` name. SKILL.md cross-field rule #3. |
| Return type `BidderDeps` | **Yes** | The terminal type returned by `BidderDepsAssembler.assemble()`. |
| Parameter `{X}ConfigurationProperties config` | **Yes** | Type must match the Rule 35 subclass (when declared) — NOT the base class. SKILL.md cross-field rule #6. |
| `@NotBlank @Value("${external-url}") String externalUrl` | **Yes** when usersync present | Spring property; the `external-url` is the prebid-server's externally-reachable host. Used by `UsersyncerCreator`. |
| `JacksonMapper mapper` | Common | Inject when `{X}Bidder` does any JSON serialization (almost all do). |
| Bidder-specific deps (e.g., `CurrencyConversionService`, `BidderAliases`, `Clock`) | varies | Injected based on `{X}Bidder` constructor needs. Order doesn't matter (Spring resolves by type). Each must be a real Spring bean — pr-triage-java's framework-spring-di drift check guards the well-known deps. |

#### B.2.3 The `BidderDepsAssembler` fluent chain

| Method | Required | Reviewer Concerns |
|--------|----------|-------------------|
| `BidderDepsAssembler.<{X}ConfigurationProperties>forBidder(BIDDER_NAME)` | **Yes** | Static factory. **The generic type parameter MUST match the `@Bean` return type** (the Rule 35 subclass, or base class). Missing the generic causes raw-type warnings; mismatched generic is a compile error. SKILL.md "Workflow: BidderDepsAssembler Generic". |
| `.withConfig(config)` | **Yes** | Binds the `@ConfigurationProperties` instance into the assembler. SKILL.md "Workflow: withConfig Binding". |
| `.usersyncerCreator(UsersyncerCreator.create(externalUrl))` | When usersync declared | If YAML declares `usersync:` block, this line MUST appear; otherwise omit. Inconsistency: **FAIL**. SKILL.md "Workflow: UsersyncerCreator URL". |
| `.bidderCreator(cfg -> new {X}Bidder(...))` | **Yes** | The lambda constructs the bidder. **HIGH PRIORITY F-new-57 trap zone**: each constructor arg must match `{X}Bidder.java`'s declared constructor signature (arg count, order, type). Cross-skill READ verifies against `{X}Bidder.java`. SKILL.md "Workflow: bidderCreator Lambda". |
| `.bidderInfo(...)` | **NEVER** | **F-new-57b trap (HIGH BLOCKING FAIL — compile error)**: spurious `.bidderInfo(...)` call inserted by port-go2java template. Verified against `BidderDepsAssembler.java` at SHA `a1fe64e123d6`: there is NO public `.bidderInfo(...)` method on the assembler — the public surface is `forBidder`, `withConfig`, `usersyncerCreator`, `bidderCreator`, `assemble`. The assembler auto-creates `BidderInfo` internally inside `coreDeps()` from the `@ConfigurationProperties`'d YAML. Any `.bidderInfo(...)` call will NOT COMPILE. **FAIL** when present. Provenance: NEW finding from the F4 review-skill-suite framework-doc audit (not in the D2.8 cross-canary catalog; surfaced when grep-verifying upstream confirmed the method is absent). See framework-utilities-java.md §1.5. |
| `.assemble()` | **Yes** | Terminal call returning `BidderDeps`. Missing is a compile error. |

#### B.2.4 The `resolveEndpoint(...)` helper (when present)

```java
private static String resolveEndpoint(String externalUrl) {
    return "https://prebid.aaxads.com/rtb/pb/aax-prebid?src=" + externalUrl;
}
```

Used by bidders whose endpoint embeds the framework-level macro `{{PREBID_SERVER_ENDPOINT}}` (canonical: AAX). The helper resolves the macro at bean-construction time using the injected `external-url` Spring property. SKILL.md "Workflow: resolveEndpoint Helper".

- When the YAML endpoint contains `{{PREBID_SERVER_ENDPOINT}}`, this helper MUST exist AND be called from the `bidderCreator` lambda (`cfg -> new {X}Bidder(resolveEndpoint(cfg.getEndpoint()), ...)`). SKILL.md cross-field rule #5.
- Per-bidder template tokens (`{{adUnitId}}`) are NOT resolved here — they pass through to `{X}Bidder`'s `makeHttpRequests(...)`.

### B.3 Rule 35 typed-config subclass

#### B.3.1 Inner-class form (canonical Kobler — most common)

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

Located at the bottom of `{X}Configuration.java`. Canonical: Kobler, Rubicon, Appnexus, Adnuntius.

#### B.3.2 Separate-file form

Same class shape but lives at `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java`. **No upstream example exists at SHA `a1fe64e123d6`** — all currently-shipped Rule 35 subclasses are inner classes (Kobler, TheTradeDesk, Adnuntius). The separate-file form remains design-permitted and reviewer-accepted (the activation table in SKILL.md routes it to this skill), but reviewers should NOT cite a non-existent upstream example. When a PR introduces the separate-file form, the typed-subclass workflow applies verbatim.

#### B.3.3 Required annotations (subclass)

| Annotation | Required | Purpose | Reviewer Concerns |
|------------|----------|---------|-------------------|
| `@Validated` | **Yes** | Triggers jakarta validation on the subclass fields | Without it, `@NotBlank`/`@NotNull` are inert. See framework-utilities-java.md §1.7 + §2.5. |
| `@Data` | **Yes** | Lombok-generates getters + setters + toString + equals + hashCode | Required because Spring relaxed-binding uses setters. |
| `@EqualsAndHashCode(callSuper = true)` | **Yes** | Lombok delegates to base class's equals/hashCode | `callSuper = true` is mandatory; without it, two instances with different parent-field values compare equal. See framework-utilities-java.md §2.5. (F-new-59 is specifically the `lombok.Data` *import-ordering* trap — see §B.4 / framework-utilities-java.md §6.3 — not this annotation's `callSuper` parameter.) |
| `@NoArgsConstructor` | **Yes** | Lombok-generates no-arg constructor | Spring requires no-arg constructor for `@ConfigurationProperties` instantiation. |
| `extends BidderConfigurationProperties` | **Yes** | Subclass inherits all 14 base fields | NOT `extends Object` or other base — those would lose endpoint binding etc. |

#### B.3.4 Per-field jakarta constraints (subclass)

| jakarta.validation.constraints | Use Case |
|--------------------------------|----------|
| `@NotBlank` | String fields that must be non-null + non-empty (canonical Kobler `devEndpoint`) |
| `@NotNull` | Object/Boolean/Integer fields that must be non-null |
| `@Min(N)` / `@Max(N)` | Numeric range constraints |
| `@Pattern(regexp = ...)` | Regex-constrained strings |

Each YAML field that maps to a `@NotBlank` subclass field MUST be present + non-empty in the YAML; missing/empty value causes Spring `BeanCreationException` at startup. SKILL.md cross-field rule #7.

### B.4 Import block (F-new-58 / F-new-59 trap zone)

The mvn-checkstyle `ImportOrder` rule enforces 3-group order. See framework-utilities-java.md §6.3 for the full enumeration. Imports for the canonical Kobler config (representative):

```java
package org.prebid.server.spring.config.bidder;

// Group 1: third-party (lombok, apache.commons, org.springframework, etc.) + project imports
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import org.prebid.server.bidder.BidderDeps;
import org.prebid.server.bidder.kobler.KoblerBidder;
import org.prebid.server.currency.CurrencyConversionService;
import org.prebid.server.json.JacksonMapper;
import org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties;
import org.prebid.server.spring.config.bidder.util.BidderDepsAssembler;
import org.prebid.server.spring.config.bidder.util.UsersyncerCreator;
import org.prebid.server.spring.env.YamlPropertySourceFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;
import org.springframework.validation.annotation.Validated;

// Group 2: jakarta.*
import jakarta.validation.constraints.NotBlank;

// Group 3: java.*  (absent in Kobler; appears when java.util etc. is used)
```

Out-of-order imports are CI-blocked. SKILL.md "Workflow: Import Order Pre-Check".

### B.5 Class-filename match (F-new-79 trap)

```java
// File: KoblerConfiguration.java
public class KoblerConfiguration {       // class name MUST equal filename root
```

Mismatch is checkstyle `OuterTypeFilename` violation → **FAIL**. SKILL.md "Workflow: Class-Filename Match".

---

## Part C — Common cross-field validation rules

Apply ONLY when both sides are touched in the same PR OR when one side is being added/changed and depends on an existing unchanged field. Mirrors SKILL.md §"Cross-Field Validation Rules" — referenced here for quick lookup during field-level task generation.

| # | Rule | Sides | Severity on Mismatch |
|---|------|-------|---------------------|
| C.1 | YAML `adapters.{x}` key ↔ `BIDDER_NAME` constant in `{X}Configuration.java` (case-sensitive lowercase) | YAML ↔ Java | **FAIL** |
| C.2 | YAML `endpoint:` framework macro `{{PREBID_SERVER_ENDPOINT}}` ↔ `resolveEndpoint(...)` helper presence | YAML ↔ Java | **FAIL** when macro present and helper missing |
| C.3 | `@Bean("{x}ConfigurationProperties")` bean name ↔ `bidderDeps(...)` first-parameter name | Java ↔ Java | **FAIL** |
| C.4 | `@ConfigurationProperties("adapters.{x}")` prefix ↔ YAML wrapper key | YAML ↔ Java | **FAIL** (silent zero-field binding) |
| C.5 | Rule 35 subclass declared ↔ `@Bean` return type ↔ `.withConfig(...)` arg type ↔ `BidderDepsAssembler.<T>` generic | Java ↔ Java | **FAIL** |
| C.6 | Rule 35 subclass `@NotBlank` field ↔ YAML field present + non-empty | YAML ↔ Java | **FAIL** (startup `BeanCreationException`) |
| C.7 | YAML `aliases.{alias}.endpoint` macros ↔ parent's `resolveEndpoint` + parent's `{X}Bidder` macro consumers (cross-skill 5a) | YAML ↔ Java/cross-skill | **FAIL** when literal `{{TOKEN}}` would leak at runtime |
| C.8 | YAML `usersync:` block declared ↔ `.usersyncerCreator(...)` line present in `bidderDeps(...)` | YAML ↔ Java | **FAIL** |
| C.9 | YAML usersync URL contains `{{gpp}}` / `{{gpp_sid}}` ↔ implicit GPP support claim | YAML internal | **WARN** when macros absent but bidder claims GPP elsewhere |
| C.10 | YAML `meta-info.{app,site,dooh}-media-types` ↔ `{X}Bidder.java` `makeHttpRequests(...)` handles each declared type | YAML ↔ Java/cross-skill | **WARN** (deferred to bidder-class-pr-review for definitive code-side check) |
| C.11 | YAML `aliases.{alias}.cookie-family-name` (when full-block) ↔ alias name | YAML internal | **FAIL** |
| C.12 | YAML `aliases:` non-empty ↔ `white-label-only: true` (when claimed) | YAML internal | **WARN** on empty aliases for whitelabel parent |
| C.13 | `bidderCreator` lambda arg list (count + order + types) ↔ `{X}Bidder.java` constructor signature | Java ↔ cross-skill | **FAIL** — the F-new-57 trap |
| C.14 | Java-side `.bidderInfo(...)` call presence on `BidderDepsAssembler` | Java internal | **FAIL — HIGH BLOCKING** (F-new-57b: method does not exist on the assembler at SHA `a1fe64e123d6`; will not compile) |
| C.15 | Imports in canonical 3-group order | Java internal | **FAIL** — F-new-58/59 + CI annotation |
| C.16 | `public class {Name}` matches filename root | Java internal | **FAIL** — F-new-79 OuterTypeFilename |
| C.17 | YAML alias added ↔ `test-application.properties` registry entry (cross-skill 5i) | YAML ↔ cross-skill | **FAIL** when registry entry absent |

---

## Part D — Reviewer checklist

Quick-reference triage flow. Use this when picking up a `bidder-config-pr-review` task to ensure no surface is missed.

### D.1 Triage (before per-field workflows)

1. Read the routing manifest: identify which of the three owned file types are in scope (`bidder-config/{x}.yaml`, `{X}Configuration.java`, `{X}BidderConfigurationProperties.java`).
2. Note PR type (`new-adapter`, `alias-only`, `adapter-modification`, `bidder-removal`, `bidder-rename`, `mixed`).
3. Check the drift block for `bidder-config` (base POJO changes) and `framework-spring-di` (assembler API changes). Any drift = recheck Part A.2 / Part B.2.3.
4. Check the CI status. ImportOrder / OuterTypeFilename / LineLength annotations directly map to F-new-58/59/79.
5. Check the prior-source-spec block (port-fidelity). Any `bidder_info` divergence → fail per R5-strict.

### D.2 Per-field triage (YAML side)

For each `+` / `-` line in `bidder-config/{x}.yaml`:

1. Map to field path (use Part A.2 ↔ A.5 tables).
2. Identify the target POJO field + jakarta constraint.
3. Run the matching SKILL.md workflow.
4. Cross-check Part C rules where applicable.

### D.3 Per-section triage (Java side)

For each `+` / `-` line in `{X}Configuration.java`:

1. Classify the line (Part B.1 / B.2.1–B.2.4 / B.3 / B.4 / B.5).
2. Run the matching SKILL.md workflow.
3. Cross-check Part C rules (especially C.1–C.6, C.13–C.16).

### D.4 Bulk-mode (alias-only PR with N aliases of same parent)

Skip per-field tasks. Create exactly 2 tasks:

1. Bulk pattern consistency (Part A.6 + SKILL.md "Workflow: Aliases Block Changed").
2. Parent endpoint + `resolveEndpoint` verification (Part B.2.4 + cross-field rule C.7).

### D.5 Summary handoff

- Files changed (added/modified/removed/renamed).
- Per-file changed-section count.
- Findings split critical/warning/info with `file:line` refs.
- Cross-skill concerns resolved or referenced (5a, 5c, 5d, 5g, 5i, 5k).
- Port-fidelity findings when `prior_source_spec` was present.
- Recommendation (approve / request changes / comment).

---

## Cross-References

- [`../SKILL.md`](../SKILL.md) — consumer skill; this file is referenced from Step 3 (build verification task list) for field→workflow mapping.
- [`../../shared/framework-utilities-java.md`](../../shared/framework-utilities-java.md) — Spring DI conventions (§1), Lombok semantics (§2), mvn-checkstyle ruleset (§6), F-new trap catalog (§8). Do NOT duplicate here.
- [`../../../../../prebid-server-go/review/skills/bidder-info-pr-review/references/field-index.md`](../../../../../prebid-server-go/review/skills/bidder-info-pr-review/references/field-index.md) — Go-side analog (YAML side only). Cross-language mapping table lives there + in SKILL.md Step 1g.
