# Framework Utilities — Java (Shared Reference)

Cross-cutting Java framework reference shared by all 4 prebid-server-java review skills (`pr-triage-java`, `bidder-class-pr-review`, `bidder-config-pr-review`, `bidder-params-java-pr-review`). Skills' `references/` files link here instead of duplicating content.

This is the Java analog of `prebid-server-go/review/skills/shared/framework-utilities.md`. It mirrors that file's structure for cross-cutting concerns but covers Java-specific surface: Spring DI, Lombok, Vert.x, JUnit5+AssertJ, Jacoco, mvn-checkstyle, and Java idioms.

**Upstream pin:** `prebid/prebid-server-java` master at SHA `e3ffd57` (verified 2026-08-18). Aggregator artifact `prebid-server-aggregator` version `4.1.0-SNAPSHOT` per `extra/pom.xml:7`. Java toolchain: **Java 25** (`extra/pom.xml` `<java.version>`). Maven plugins: checkstyle `10.17.0`, checkstyle-plugin `3.6.0`, jacoco `0.8.13`. Spring Boot `4.0.6`, Vert.x `5.0.12`, Lombok (managed by Spring Boot BOM).

**Version-extraction note:** the root `pom.xml` `prebid-server` artifact declares **no** `<version>` element — it inherits from `<parent><artifactId>prebid-server-aggregator</artifactId><version>…</version></parent>` (`pom.xml:5-10`). Read the version from `<parent>` in `pom.xml`, or from the project coordinates in `extra/pom.xml:5-7`.

**Drift policy:** `pr-triage-java` Step 2 fetches `pom.xml`, `extra/pom.xml`, `checkstyle.xml`, and the framework Spring DI files. Any change to a pinned version, ruleset entry, or framework API surface triggers `DRIFT:` entries in the routing manifest and an atomic update to this file in the same migration.

---

## Review disposition system (severity · action · fidelity↔conformance tie-breaker)

> **Governs how every finding across the four Java review skills is rated and acted on.** This is the canonical disposition reference; per-skill checks and the F-new trap table (§8) cite it instead of re-deriving severity. Established by [ADR-009 — lean-conformance doctrine](../../../../docs/decisions/009-lean-conformance-doctrine.md). The detailed severity-vocabulary mapping (skill-finding severity ↔ F-new-trap catalog severity) lives in §8.1; this section adds the **disposition (action)** dimension and the **fidelity↔conformance tie-breaker**.

### Severity → disposition ladder

| Severity (per §8.1) | Disposition | Meaning |
|---|---|---|
| **FAIL** (HIGH BLOCKING / most HIGH) | **BLOCK** merge | Won't compile / pass build (checkstyle, unit tests, IT — all inside the `build (25)` check-run, §8.2), a correctness bug, or a violation of a hard upstream-java merge norm. Note: coverage is **not** in this list — jacoco has no gate (§5.1). |
| **WARN** (MEDIUM) | **ASK** the author | Likely a problem but context-dependent. Raise as a change request; the author fixes or vouches acceptably. |
| **INFO** (LOW / WARN) | **NOTE** (non-blocking) | Style/process heads-up. Mention once; never blocks. |

Severity is set by the **target repo's merge bar** (prebid-server-java), not by how the Go source adapter behaves. The two historical miscalibrations — "the Go source does it this way" and "more coverage/artifacts can't hurt" — are corrected by the tie-breaker and the more-artifacts corollary below.

### Tie-breaker: target-conformance beats source-fidelity

When a finding is defended by source-fidelity — *"the Go source adapter does exactly this, so the Java port should too"* — do NOT dismiss it. Re-rate against the **target (Java)** norm:

- If upstream-java would reject the pattern, **the finding stands at its target-norm severity**, regardless of faithful reproduction. Fidelity is the means; a merge-ready Java PR is the end (ADR-009).
- Record the divergence in the port's `port-report.json` `quirks[]`; for a genuine source-side defect, recommend an upstream issue against prebid-server (Go) so both sides re-align.
- Java-specific sharp edge: the Go→Java direction frequently transliterates Go-canonical helper *names* that do not exist in Java (F-new-90 `BidderUtil.isResponseStatusCodeNoContent`; F-new-57b `.bidderInfo(...)`). That is fidelity-to-Go the Java compiler rejects outright — **FAIL / BLOCK** regardless of the Go original.

This is the core calibration fix from the Teal review: reviews must resolve toward target-conformance, not source-fidelity.

### Guard: the tie-breaker does NOT auto-promote WARN-by-design findings

The tie-breaker resolves *fidelity-vs-conformance* conflicts; it is not license to escalate every strict-reading divergence to FAIL. **WARN/INFO by design** (keep unless an independent target-norm violation applies):

- **Specific-ID defensive checks the framework does NOT enforce** (`site.id`, `app.id`, `publisher.id` null guards) — legitimately KEEP/WARN.
- **Forward-compat branches** for not-yet-schematized fields/values.
- **Constant bid-type fallbacks that match the bidder's real default.** ASYMMETRY WITH GO: Java has **no operator-vouching surface** (Go vouches via `port-report.json` `quirks[]`). A silent constant `resolveBidType` fallback in Java is therefore more likely a latent bug (F-new-64) and should be flagged at HIGH absent a clear, code-evident reason — but a fallback that demonstrably matches the bidder's sole declared media type remains legitimate. Flag *silent / unvouched / mis-typing*, not the mere existence of a default.

Default to WARN (ASK) when uncertain between WARN and FAIL on a defensive check; let the author vouch.

### Corollary: more artifacts ≠ higher quality

A port PR that ships *more than the canonical Java corpus* is off-spec, not premium. Emit exactly what upstream-java merges — `{X}Bidder.java`, the Spring `{X}Configuration.java`, `ExtImp{X}.java`, `bidder-config/{x}.yaml`, `bidder-params/{x}.json`, `{X}BidderTest.java`, the per-scenario IT class + 4-file fixtures (Rule 36), registry lines — and nothing carried over from the Go side's dev aids (the Go port's `doc.go` / `*_fuzz_test.go` / `*_bench_test.go` have no Java equivalent and no place in a Java PR). Speculative scaffolding or gratuitous standalone helper tests are **findings to flag, not merits** (ADR-009). Coverage is demonstrated through the unit + IT corpus against the merge bar (§5.2) — there is no jacoco gate to satisfy, so "more tests" is never self-justifying.

---

## 1. Spring DI conventions

Every bidder in the Java codebase is wired into the Spring `ApplicationContext` via a `@Configuration` class under `org.prebid.server.spring.config.bidder`. The wiring quartet is `@Configuration` + `@PropertySource` (binds the bidder's YAML) + `@Bean` (factory method) + `@ConfigurationProperties` (typed properties binding). Skills MUST recognize this canonical pattern AND the few legitimate variations.

### 1.1 Canonical singleton form (no Rule 35 typed-config subclass)

Verified canonical at `src/main/java/org/prebid/server/spring/config/bidder/AaxConfiguration.java` (verbatim at `e3ffd57`):

```java
package org.prebid.server.spring.config.bidder;

import org.prebid.server.bidder.BidderDeps;
import org.prebid.server.bidder.aax.AaxBidder;
import org.prebid.server.json.JacksonMapper;
import org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties;
import org.prebid.server.spring.config.bidder.util.BidderDepsAssembler;
import org.prebid.server.spring.env.YamlPropertySourceFactory;
import org.prebid.server.util.Uri;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.PropertySource;

import jakarta.validation.constraints.NotBlank;

@Configuration
@PropertySource(value = "classpath:/bidder-config/aax.yaml", factory = YamlPropertySourceFactory.class)
public class AaxConfiguration {

    private static final String BIDDER_NAME = "aax";
    private static final String EXTERNAL_URL_MACRO = "PREBID_SERVER_ENDPOINT";

    @Bean("aaxConfigurationProperties")
    @ConfigurationProperties("adapters.aax")
    BidderConfigurationProperties configurationProperties() {
        return new BidderConfigurationProperties();
    }

    @Bean
    BidderDeps aaxBidderDeps(BidderConfigurationProperties aaxConfigurationProperties,
                             @NotBlank @Value("${external-url}") String externalUrl,
                             JacksonMapper mapper) {

        return BidderDepsAssembler.forBidder(BIDDER_NAME)
                .withConfig(aaxConfigurationProperties)
                .bidderCreator(config -> new AaxBidder(resolveEndpoint(config.getEndpoint(), externalUrl), mapper))
                .assemble();
    }

    private String resolveEndpoint(String configEndpoint, String externalUrl) {
        return Uri.of(configEndpoint).replaceMacro(EXTERNAL_URL_MACRO, externalUrl).expand();
    }
}
```

Reviewer checklist for canonical form:
- `@Configuration` on class
- `@PropertySource(value = "classpath:/bidder-config/{x}.yaml", factory = YamlPropertySourceFactory.class)` — factory MUST be `YamlPropertySourceFactory.class`; deviation is a YAML-binding bug
- `private static final String BIDDER_NAME = "{x}"` — string literal MUST match the YAML adapter key + the directory `bidder/{x}/`
- `@Bean("{x}ConfigurationProperties") @ConfigurationProperties("adapters.{x}")` — both names MUST be the bidder name (camelCase identifier suffix; `adapters.` prefix)
- `BidderDepsAssembler.forBidder(BIDDER_NAME)` — uses the constant, not a string literal
- `bidderCreator(config -> new {X}Bidder(...))` — lambda invokes the `{X}Bidder` constructor with the resolved endpoint + mapper (+ optional services)
- **No usersync line in the chain.** `BidderDepsAssembler` has no usersync-related builder method. The assembler derives the `Usersyncer` internally in its private `usersyncer(CFG)` method, from `configProperties.getUsersync()`, via `UsersyncerUtil.create(usersync)` — see `BidderDepsAssembler.java` `usersyncer(CFG)` and `spring/config/bidder/util/UsersyncerUtil.java`. A bidder with a full `usersync:` YAML block therefore ships a Configuration class with **no** usersync call at all: `AdprimeConfiguration.java` (whose `bidder-config/adprime.yaml` declares `usersync.iframe` + `usersync.redirect`) is the canonical anchor.

### 1.1a `BidderDepsAssembler` public builder surface (verified at `e3ffd57`)

`src/main/java/org/prebid/server/spring/config/bidder/util/BidderDepsAssembler.java` declares exactly four public members on the fluent chain:

| Member | Signature | Notes |
|---|---|---|
| `forBidder` | `static <CFG extends BidderConfigurationProperties> BidderDepsAssembler<CFG> forBidder(String bidderName)` | Entry point; the `<CFG>` witness is supplied explicitly when Rule 35 applies. |
| `withConfig` | `BidderDepsAssembler<CFG> withConfig(CFG configProperties)` | |
| `bidderCreator` | `BidderDepsAssembler<CFG> bidderCreator(Function<CFG, Bidder<?>> bidderCreator)` | |
| `assemble` | `BidderDeps assemble()` | Terminal. |

Anything else chained on the assembler — `.usersyncerCreator(...)`, `.bidderInfo(...)`, `.deprecatedNames(...)` — does **not** exist and will not compile. `BidderInfo` and `Usersyncer` are both derived internally inside `deps(...)`, from the `@ConfigurationProperties`-bound YAML.

**Historical note for reviewers reading older adapters or older port templates:** upstream deleted `UsersyncerCreator` and the `.usersyncerCreator(...)` chain link in commit `2880782f` (PR #4464, merged 2026-07-09). A PR that reintroduces either is **FAIL / BLOCK** (compile error), not a style preference.

### 1.2 Typed-config subclass form (Rule 35 applied)

Verified canonical at `src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java`:

```java
@Configuration
@PropertySource(value = "classpath:/bidder-config/kobler.yaml", factory = YamlPropertySourceFactory.class)
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
                                JacksonMapper mapper) {

        return BidderDepsAssembler.<KoblerConfigurationProperties>forBidder(BIDDER_NAME)
                .withConfig(config)
                .bidderCreator(cfg -> new KoblerBidder(
                        cfg.getEndpoint(),
                        cfg.getDevEndpoint(),
                        currencyConversionService,
                        mapper))
                .assemble();
    }

    @Validated
    @Data
    @EqualsAndHashCode(callSuper = true)
    @NoArgsConstructor
    private static class KoblerConfigurationProperties extends BidderConfigurationProperties {

        @NotBlank
        private String devEndpoint;
    }
}
```

Reviewer checklist for typed-config form:
- `BidderDepsAssembler.<{X}ConfigurationProperties>forBidder(BIDDER_NAME)` — type parameter is the typed subclass
- `withConfig({x}ConfigurationProperties)` references the typed subclass (NOT the base `BidderConfigurationProperties`)
- The subclass `extends BidderConfigurationProperties` (not `Object`)
- Subclass annotated `@Data` + `@EqualsAndHashCode(callSuper = true)` + `@NoArgsConstructor` (and typically `@Validated`)
- Field names use Spring's relaxed-binding (YAML `dev-endpoint` ↔ Java `devEndpoint`)
- The subclass MAY be nested inside the `{X}Configuration.java` (Kobler form) OR live in its own `{X}BidderConfigurationProperties.java` file under the same package (Adnuntius/Adverxo/Thetradedesk form) — both are acceptable
- The `bidderCreator` lambda passes the typed-subclass getters (e.g., `cfg.getDevEndpoint()`) into the `{X}Bidder` constructor

### 1.3 Filename naming variations

Upstream uses BOTH naming conventions for the Spring DI factory:
- `{X}Configuration.java` — e.g., `AaxConfiguration.java`, `KoblerConfiguration.java`. Most common.
- `{X}BidderConfiguration.java` — e.g., `AdverxoBidderConfiguration.java`, `AdnuntiusBidderConfiguration.java`. Used by newer adapters.

Both are acceptable. Reviewers MUST NOT flag the choice between these two forms. BUT reviewers MUST flag when the public class name inside the file does not match the filename root (the **F-new-79 trap** below).

### 1.4 F-new-57 anti-pattern: Spring factory passes wrong arg type

The `port-go2java` D2.8 template emitted bugs where the `bidderCreator` lambda received `mapper` (the `JacksonMapper` bean) as the `withConfig(...)` argument — instead of the bidder's `BidderConfigurationProperties` instance. Severity: **HIGH BLOCKING** (won't compile / won't wire). Anti-pattern surface:

```java
// WRONG — F-new-57 trap:
.withConfig(mapper)                                  // BidderConfigurationProperties expected
.bidderCreator(config -> new {X}Bidder(mapper))      // config.getEndpoint() ignored

// CORRECT:
.withConfig({x}ConfigurationProperties)
.bidderCreator(config -> new {X}Bidder(config.getEndpoint(), mapper))
```

Only emits on Rule-35-applying canaries (kobler, thetradedesk in D2.8). Owning skill: `bidder-config-pr-review`.

### 1.5 F-new-57b: spurious `.bidderInfo(...)` line — HIGH BLOCKING (compile error)

A related template defect adds an unnecessary line such as `.bidderInfo(BidderInfoCreator.create(mapper)::create)` to the `BidderDepsAssembler` chain. **Verified at SHA `e3ffd57`: `BidderDepsAssembler` has NO public `.bidderInfo(...)` method.** The complete public builder surface is `forBidder`, `withConfig`, `bidderCreator`, `assemble` (§1.1a) — adding `.bidderInfo(...)` will NOT COMPILE. The framework auto-creates the `BidderInfo` internally: `BidderDepsAssembler.coreDeps()` calls `BidderInfoCreator.create(configProperties)` and passes the result into the private `deps(...)` builder, sourced from the `@ConfigurationProperties`'d YAML. Reviewers MUST block merge — flag as **FAIL / HIGH BLOCKING** when seen on `{X}Configuration.java` PRs.

The same reasoning covers the sibling trap `.usersyncerCreator(UsersyncerCreator.create(externalUrl))`: `UsersyncerCreator` no longer exists (deleted in `2880782f`, PR #4464), the assembler has no `usersyncerCreator` method, and the `Usersyncer` is derived internally via `UsersyncerUtil.create(usersync)`. Also **FAIL / HIGH BLOCKING**.

Provenance: NEW finding from the F4 review-skill-suite framework-doc audit (not in the D2.8 cross-canary catalog; the grep-verified absence of the method on `BidderDepsAssembler` is what elevated this from "ASK to remove" to "block merge").

### 1.6 F-new-79 anti-pattern: `OuterTypeFilename` mismatch

The checkstyle rule `OuterTypeFilename` requires the public class declared in a `.java` file to match the filename root. The D2.8 canary 4 (Adverxo) exposed a template defect where the filename was emitted as `AdverxoBidderConfiguration.java` but the internal class was declared as `public class AdverxoConfiguration`. javac error + checkstyle violation. Severity: **HIGH** (won't compile).

Reviewer pre-flag (mirrors `pr-triage-java` Step 5k): for every added Java file in the diff, extract the `public class Xxx` declaration and verify it matches the filename root. Pre-CI catch prevents reviewer round-trips.

### 1.7 `@Validated` annotation usage

`@Validated` on a `@ConfigurationProperties` subclass enables runtime validation of `jakarta.validation.constraints.*` (`@NotBlank`, `@NotNull`, etc.) during Spring binding. Common on Rule 35 typed-config subclasses to enforce that mandatory YAML fields (e.g., Kobler's `dev-endpoint`) are populated. Absence is tolerated for optional fields; presence + `@NotBlank` on a field is the canonical pair.

---

## 2. Lombok annotation semantics

Lombok is provided via the `org.projectlombok:lombok` dependency in `extra/pom.xml` (scope `provided`). Skills MUST recognize and verify the annotation conventions below.

### 2.0 Census — what upstream actually uses on `ExtImp{X}` POJOs

Measured over `src/main/java/org/prebid/server/proto/openrtb/ext/request/**/ExtImp*.java` at `e3ffd57` (226 files). Regenerate with:

```bash
D=src/main/java/org/prebid/server/proto/openrtb/ext/request
find $D -name 'ExtImp*.java' | wc -l                              # 226
grep -rl 'staticConstructor = "of"' --include='ExtImp*.java' $D | wc -l   # 197
grep -rl '@Builder'   --include='ExtImp*.java' $D | wc -l          # 28
grep -rl '@Data'      --include='ExtImp*.java' $D | wc -l          # 0
```

| Construct | Files | Share | Reviewer label |
|---|---|---|---|
| `@Value` | 226 | 100% | **Mandatory** — every ExtImp carries it. |
| `@Value(staticConstructor = "of")` | 197 | 87% | **Canonical.** The default shape a new adapter should emit. |
| `@Builder` (paired with `@Value`) | 28 | 12% | **Accepted variant.** Reserved for wide POJOs with many optional fields (canonical: `ExtImpAppnexus`, `@Builder(toBuilder = true) @Value`). |
| `@Data` | 0 | — | **FAIL** on an ExtImp — see §2.3. |
| `@Jacksonized` | 0 | — | Not used on ExtImp POJOs; do not require it. See §2.2. |
| `@Singular` | 0 | — | Not used on ExtImp POJOs; do not require it. |

The plain-`@Value` and `@Value(staticConstructor = "of")` forms are both correct; the static-factory form is the majority and the one to prefer when suggesting a shape. Reviewers MUST NOT flag the choice between them.

### 2.1 `@Value` — immutable POJO

Generates `private final` fields, getters (no setters), `equals` + `hashCode` + `toString`, and a `@AllArgsConstructor` for all fields. **The default for ext-request POJOs** (`ExtImp{X}.java`) and response DTOs (`{X}Response.java`, etc.). Reviewer concern: any `@Data` on an ext-request POJO is an anti-pattern (mutable POJOs allow accidental mutation; ExtImp objects should be immutable from JSON-deserialize through to HTTP-write).

Canonical pair: `@Value(staticConstructor = "of")` — see §2.7 below. Minority pair: `@Value @Builder` — see §2.2.

### 2.2 `@Builder` — fluent builder generator

Generates a static `{X}.builder()` returning a `{X}Builder` with one fluent setter per field, plus `.build()` returning the immutable instance. A **minority companion** to `@Value` on ExtImp POJOs (28 of 226; §2.0) and the standard shape on the OpenRTB entity types the adapter rebuilds. Critical companion: `.toBuilder()` (when `@Builder(toBuilder = true)` or when paired with `@Value`'s implicit support) — produces a new builder pre-populated from an existing instance, the **Rule 5 entity-mutation idiom**:

```java
final BidRequest modifiedRequest = bidRequest.toBuilder()
        .site(bidRequest.getSite() != null
                ? bidRequest.getSite().toBuilder()
                        .publisher(Publisher.builder().id(pubID).build())
                        .build()
                : null)
        .build();
```

`toBuilder()` is the Java idiom for what Go does with shallow-copy + pointer mutation. Reviewers MUST recognize the `toBuilder()...build()` chain pattern when reviewing adapter `makeHttpRequests` logic; absence (i.e., direct setter calls on a `@Value` POJO) won't compile.

### 2.3 `@Data` — mutable POJO with getters + setters

Generates `private` fields (not final), getters + setters, `equals` + `hashCode` + `toString`, and `@RequiredArgsConstructor` for all final fields. **Banned on ext-request POJOs**; mandatory on Spring `@ConfigurationProperties` classes (Spring needs setters for property injection via `BeanWrapper`).

Reviewer concern in `{X}Configuration.java` PRs: the Rule 35 typed-config subclass uses `@Data`; the ext-request POJO uses `@Value`. Swapping them is a serialization bug.

### 2.4 `@NoArgsConstructor` / `@AllArgsConstructor` / `@RequiredArgsConstructor`

- `@NoArgsConstructor` — empty constructor. Required on Spring `@ConfigurationProperties` subclasses (Spring instantiates via reflection then calls setters).
- `@AllArgsConstructor` — constructor with all fields. Implicit when `@Value` is used.
- `@RequiredArgsConstructor` — constructor for `final` fields only. Common on adapter `{X}Bidder` classes via final-field DI:

```java
@RequiredArgsConstructor  // NOT typically used — adapters declare an explicit constructor instead
public class {X}Bidder implements Bidder<BidRequest> {
    private final String endpoint;
    private final JacksonMapper mapper;
}
```

In practice, upstream `{X}Bidder` classes prefer an **explicit constructor** (not the Lombok-generated form) because they typically validate the endpoint URL inside the constructor (see §3.4 below):

```java
public {X}Bidder(String endpointUrl, JacksonMapper mapper) {
    this.endpointUrl = HttpUtil.validateUrl(Objects.requireNonNull(endpointUrl));
    this.mapper = Objects.requireNonNull(mapper);
}
```

### 2.5 `@EqualsAndHashCode(callSuper = true)` — F-new-59 trap context

Mandatory on Rule 35 typed-config subclasses (`extends BidderConfigurationProperties`). Forgetting `callSuper = true` means equals/hashCode ignore inherited fields — silent semantic bug. The pair `@Data @EqualsAndHashCode(callSuper = true) @NoArgsConstructor` is canonical for typed-config subclasses.

The **F-new-59 trap** is specifically about `lombok.Data` *import ordering* (not the annotation itself) — see §6.3 checkstyle `ImportOrder`.

### 2.6 `@JsonProperty` — Jackson rename

Renames a field for Jackson serialization when the YAML/JSON wire format differs from the Java camelCase identifier:

```java
@Value(staticConstructor = "of")
public class ExtImp{X} {
    @JsonProperty("param-name")
    String paramName;  // YAML: "param-name", Java: paramName
}
```

Common on ExtImp{X} when the bidder-params JSON schema uses kebab-case or snake_case. Reviewer concern: a missing `@JsonProperty` on a field whose schema name differs from the Java identifier produces a null field on deserialization (no error, silent failure).

### 2.7 `@Value(staticConstructor = "of")` — canonical static-factory form

A variant of `@Value` that generates a static factory method `{Class}.of(arg1, arg2, ...)` in addition to the all-args constructor. This is the **canonical `ExtImp{X}` shape** — 197 of 226 ExtImp POJOs at `e3ffd57` (§2.0). Anchors: `ExtImpKobler.java` (`ExtImpKobler.of(test)`), `ExtImpAdverxo.java` (`ExtImpAdverxo.of(adUnitId, auth)`), `ExtImpIx.java`, `ExtImpTheTradeDesk.java`. Plain `@Value` without the static constructor is an accepted variant; reviewers do NOT flag the choice in either direction. The `bidder-params-java-pr-review` skill's [params-type-index.md](../bidder-params-java-pr-review/references/params-type-index.md) Part B.1 documents this in the Lombok matrix.

### 2.8 Constructs with no upstream ExtImp instances

`@Jacksonized` and `@Singular` have **zero** occurrences across the 226 ExtImp POJOs at `e3ffd57`, and one occurrence each across all of `src/main/java`. Reviewers MUST NOT require either, and MUST NOT emit a WARN for their absence:

- **`@Jacksonized`** — Lombok's `@Builder` ↔ Jackson glue (`@JsonDeserialize(builder = …)`). Upstream does not use it on ExtImp POJOs; the canonical `@Builder` ExtImp, `ExtImpAppnexus.java` (`@Builder(toBuilder = true) @Value`), deserializes fine without it because Jackson binds through the all-args constructor Lombok generates for `@Value`. A rule that WARNs on "`@Builder` without `@Jacksonized`" fires on **every** `@Builder` ExtImp upstream ships, including the one this suite cites as canonical — which is why it is not a rule here.
- **`@Singular`** — per-element fluent setter for `@Builder` collection fields. Absence on a `List<T>` field is not a finding.

### 2.9 `@JsonAlias` — accept multiple JSON keys for one field

```java
@JsonAlias({"siteid", "siteID"})
@JsonProperty("siteId")
String siteId;
```

Maps multiple JSON keys (`siteid`, `siteID`, plus the canonical `siteId` from `@JsonProperty`) onto the SAME Java field — the Java-side answer to schema-level `oneOf` over alternate spellings (canonical: Ix's 3-spelling alias support; Appnexus's `placementId`/`placement_id`). Distinct from `@JsonProperty` (single key rename). Reviewers MUST verify the alias list matches the schema's deprecated-name entries on `bidder-params/{x}.json`.

### 2.10 `@JsonDeserialize(using = {X}Deserializer.class)` — custom deserializer hook

Wires Jackson to use a custom `StdDeserializer<T>` subclass (located in the same package) for the annotated field or class. Reviewers verify the referenced deserializer class exists and `extends StdDeserializer<{T}>` (or implements `JsonDeserializer<{T}>`). Anti-pattern: `@JsonDeserialize` referencing a non-existent class is **FAIL** (compile error). Common when the field's accepted shapes exceed `@JsonAlias` capability. The `bidder-params-java-pr-review` skill's params-type-index Part B.5 documents the flexible-type idiom matrix this annotation belongs to.

---

## 3. Vert.x HTTP layer

`io.vertx.core:vertx-core` 5.0.12 (`<vertx.version>` in `extra/pom.xml`). Adapter code never directly drives Vert.x — the framework executes the `HttpRequest<BidRequest>` builders adapters return. Reviewers verify adapters use only the canonical Vert.x types.

### 3.0 URL macros — single-brace RFC 6570, expanded through `Uri`

**This is the highest-frequency stale-knowledge trap in the Java tree.** Upstream migrated endpoint and usersync URL templating to Vert.x `UriTemplate` (RFC 6570) in commit `bc0409271` (PR #4444, "Add Vert.x `UriTemplate`", merged 2026-07-20). Two consequences reviewers MUST apply:

**(a) Framework macros in YAML are SINGLE-brace.** In `src/main/resources/bidder-config/*.yaml` and endpoint templates, the framework-substituted names are written `{gdpr}`, `{gdpr_consent}`, `{us_privacy}`, `{gpp}`, `{gpp_sid}`, `{redirect_url}`. There are **zero** double-brace occurrences of any of those names anywhere under `src/`. A PR that writes `{{gdpr}}` is emitting a token `UriTemplate` will not expand — **FAIL / BLOCK**.

```bash
# regenerate the counts (run from an upstream checkout)
for m in gdpr gdpr_consent us_privacy redirect_url gpp; do
  printf '{%s}=%s  {{%s}}=%s\n' "$m" "$(grep -rlF "{$m}" src | wc -l)" "$m" "$(grep -rlF "{{$m}}" src | wc -l)"
done
# at e3ffd57: {gdpr}=144/0  {gdpr_consent}=144/0  {us_privacy}=132/0  {redirect_url}=164/0  {gpp}=62/0
```

**(b) Double braces are NOT extinct — they are bidder-owned `uid-macro` VALUES.** `{{…}}` still appears in `bidder-config/*.yaml`, but only as the literal cookie-sync placeholder a *bidder* substitutes on its own side, never as a framework macro. At `e3ffd57` there are 7 such lines:

| File | Value |
|---|---|
| `bidder-config/tappx.yaml:18` | `uid-macro: '{{TPPXUID}}'` |
| `bidder-config/frvradn.yaml:18` | `uid-macro: '{{UID}}'` |
| `bidder-config/lockerdome.yaml:19` | `uid-macro: '{{uid}}'` |
| `bidder-config/vidoomy.yaml:18` | `uid-macro: '{{VID}}'` |
| `bidder-config/ogury.yaml:18,21` | `uid-macro: "{{OGURY_UID}}"` |
| `bidder-config/avocet.yaml:18` | `uid-macro: '{{UUID}}'` |

So the rule is **not** "no double braces in YAML". It is: **framework macro names are single-brace; `uid-macro` values are opaque bidder strings and may be any shape** (`$UID`, `[UID]`, `<vsid>`, `{{UUID}}`, …). Flagging a `uid-macro: '{{X}}'` value as a brace error is a false positive.

**(c) Java-side substitution uses `Uri` + BARE constant names.** The macro constant holds the variable name with **no braces at all**, and substitution goes through `org.prebid.server.util.Uri`:

```java
// AceexBidder.java:36, :68 — canonical
private static final String ACCOUNT_ID_MACRO = "AccountId";
private final Uri endpointUrl;                        // constructor: this.endpointUrl = Uri.of(endpointUrl);

private String resolveEndpoint(String accountId) {
    return endpointUrl.replaceMacro(ACCOUNT_ID_MACRO, accountId).expand();
}
```

`Uri.of(String)` validates the template and returns a `Uri`; `replaceMacro(String key, String value)` (also `replaceMacro(String, List<String>)`, `replaceMacros(Map<String,String>)`, `addQueryParam(...)`) returns a `Uri.ParameterizedUri`; `expand()` produces the final `String`. At `e3ffd57`, `Uri.of(` appears in 125 files under `src/main/java` and `replaceMacro` in 94 — while `String.replace("{{…}}", …)` appears in **zero**.

Reviewer rules:
- A macro constant declared with braces — `= "{{PREBID_SERVER_ENDPOINT}}"` or `= "{AccountId}"` — is **FAIL**: `replaceMacro` keys on the bare variable name, so a braced key never matches and `expand()` throws `NoSuchElementException` on the unfilled variable.
- Hand-rolled `configEndpoint.replace("{{TOKEN}}", value)` in place of `Uri.of(...).replaceMacro(...).expand()` is **FAIL** — no upstream file does this, and it bypasses `Uri`'s template validation.
- `HttpUtil.encodeUrl(externalUrl)` is **not** part of endpoint resolution. `UriTemplate` expansion handles escaping. Zero files under `src/main/java/org/prebid/server/spring/config/bidder/` call `encodeUrl`; requiring it is a stale rule.

### 3.1 HTTP status handling — framework default (Rule 30)

**The Java framework's most important convention for adapter authors:** Java's HTTP layer auto-handles 204 No Content + non-2xx status codes BEFORE `bidder.makeBidderResponse(...)` (the adapter's `makeBids`) is invoked. Verified mechanism in `HttpBidderRequester.java` at SHA `e3ffd57`:

1. After the HTTP call completes, the response is wrapped via `BidderCall.succeededHttp(httpRequest, httpResponse, errorOrNull(statusCode))` (line 268); the private static helper `errorOrNull(int statusCode)` (line 274) returns a `BidderError` when status ≠ 200 AND ≠ 204 (line 275).
2. The private static `makeBids(...)` dispatcher (line 294) then:
   - Returns `null` if `httpCall.getError() != null` (the badInput/badServerResponse error was attached above).
   - Short-circuits when `statusCode == HttpResponseStatus.NO_CONTENT.code()` (line 303) — the adapter's `makeBids` is NEVER called for 204.
   - Returns `null` when `statusCode != HttpResponseStatus.OK.code()` (line 306) — the adapter's `makeBids` is NEVER called for 4xx/5xx.
   - Only on `statusCode == OK` does the adapter's `bidder.makeBidderResponse(...)` (i.e., the `makeBids` method we review) execute.

The factual core stands: **zero status-check code is canonical in adapter `makeBids` implementations**. The 204/4xx/5xx triage is the private static `errorOrNull` + the dispatcher's switches above — there is NO method called `validateResponse` on `HttpBidderRequester`.

**Translation rule (Rule 30, `http_status_handling.kind`):**
- Go: `canonical-go-helpers` — adapter explicitly checks `adapters.IsResponseStatusCodeNoContent` and `adapters.CheckResponseStatusCodeForErrors` in `MakeBids`.
- Java: `framework-default` — adapter `makeBids` does NOT include status checks. The body parsing happens directly.

Optional empty-seatbid short-circuit (canonical pattern):
```java
if (CollectionUtils.isEmpty(bidResponse.getSeatbid())) {
    return Collections.emptyList();
}
```

### 3.2 F-new-90 trap: non-existent BidderUtil methods

The D2.8 vungle canary exposed a template defect that emitted Go-canonical helper names (transliterated to Java):

```java
// WRONG — F-new-90 trap (these methods DO NOT EXIST in upstream Java):
if (BidderUtil.isResponseStatusCodeNoContent(httpCall)) { return Collections.emptyList(); }
BidderUtil.checkResponseStatusCode(httpCall);
```

Verified against `src/main/java/org/prebid/server/util/BidderUtil.java` at SHA `e3ffd57`: the public static methods that exist are `defaultRequest` (2 overloads), `impIds`, `isValidPrice` (2 overloads), `shouldConvertBidFloor`, `resolvePriceFloor`, `roundFloor`, `isNullOrZero`, `getBidType` — NONE match the Go helper naming.

Reviewer pre-flag: any `BidderUtil.isResponseStatusCodeNoContent` / `BidderUtil.checkResponseStatusCode` / `BidderUtil.checkResponseStatusCodeForErrors` reference in adapter code is an F-new-90 defect. Severity: **HIGH BLOCKING** (won't compile). Owning skill: `bidder-class-pr-review`.

The CORRECT pattern is **no explicit status check** (framework handles 204+4xx upstream of makeBids). When a 204 needs to short-circuit cleanly, the canonical Java idiom is the `CollectionUtils.isEmpty(bidResponse.getSeatbid())` early-return shown in §3.1.

### 3.3 HTTP request building — `HttpRequest<BidRequest>` builder

Canonical pattern (verified at `BidderUtil.defaultRequest(...)` source):

```java
return HttpRequest.<BidRequest>builder()
        .method(HttpMethod.POST)
        .uri(endpointUrl)
        .headers(HttpUtil.headers())
        .impIds(BidderUtil.impIds(bidRequest))
        .body(mapper.encodeToBytes(bidRequest))
        .payload(bidRequest)
        .build();
```

Or, the shortcut form when headers and impIds are default:

```java
final HttpRequest<BidRequest> request = BidderUtil.defaultRequest(bidRequest, endpointUrl, mapper);
```

Reviewer concern: any `new HttpRequest(...)` direct constructor call (instead of the builder) is an anti-pattern. Direct Vert.x `HttpClient.request(...)` use in adapter code is forbidden — the framework owns HTTP execution.

### 3.4 URL validation in constructor — `HttpUtil.validateUrl`

Canonical adapter constructor pattern (validates URL parses at startup; rejects malformed config):

```java
public {X}Bidder(String endpointUrl, JacksonMapper mapper) {
    this.endpointUrl = HttpUtil.validateUrl(Objects.requireNonNull(endpointUrl));
    this.mapper = Objects.requireNonNull(mapper);
}
```

`HttpUtil.validateUrl(String)` (`org.prebid.server.util.HttpUtil:94-96`) delegates to `HttpUtil.parseUrl(String)` (line 86) and returns `parseUrl(url).toString()`; `parseUrl` throws `IllegalArgumentException("URL supplied is not valid: …")` when the string does not parse. It is **not** deprecated at `e3ffd57`, and there is no `validateUrlSyntax` method.

**Preferred form for macro-carrying endpoints:** adapters whose endpoint contains RFC 6570 variables store a `Uri` instead of a `String` and let `Uri.of(...)` do the validating — `Uri.of` calls `HttpUtil.validateUrl` internally after stripping `{`/`}` (see `Uri.validateTemplate`). Canonical: `AceexBidder.java` `this.endpointUrl = Uri.of(endpointUrl);`. Both constructor shapes are accepted; see §3.0(c).

### 3.5 Standard headers — `HttpUtil.headers()` (Rule 19)

Returns a `MultiMap` pre-populated with `Content-Type: application/json;charset=utf-8` + `Accept: application/json`. The canonical shortcut for the 2-header case. Adapters needing additional headers compose via `.add(...)`:

```java
final MultiMap headers = HttpUtil.headers()
        .add("X-OpenRTB-Version", "2.5")
        .add(HttpUtil.X_FORWARDED_FOR_HEADER, ip);
```

Reviewer concern: hand-rolled `MultiMap.caseInsensitiveMultiMap().add("Content-Type", ...)` boilerplate where `HttpUtil.headers()` would suffice — request `HttpUtil.headers()` (Rule 19 collapse).

### 3.6 Banned Vert.x JSON import

`io.vertx.core.json.Json` is BANNED everywhere except `ObjectMapperProvider.java` (the single source-of-truth for the configured ObjectMapper). Enforced by checkstyle `IllegalImport id="BanVertxJsonImport"` (see §6.5). Use `JacksonMapper.encodeToBytes(...)` / `mapper.decodeValue(...)` exclusively.

---

## 4. JUnit5 + AssertJ + Vert.x test infrastructure

Test surface uses JUnit Jupiter (`org.junit.jupiter`), AssertJ (`org.assertj.core.api.Assertions`), Mockito (`org.mockito.Mockito`), and the prebid-server-java-specific `VertxTest` + `IntegrationTest` base classes.

### 4.1 Unit tests — `extends VertxTest`

Canonical unit test class skeleton:

```java
package org.prebid.server.bidder.{x};

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.prebid.server.VertxTest;
// ...

public class {X}BidderTest extends VertxTest {

    private {X}Bidder target;

    @BeforeEach
    public void setUp() {
        target = new {X}Bidder("https://test.endpoint", jacksonMapper);
    }

    @Test
    public void makeHttpRequestsShouldReturnExpectedRequest() {
        // given
        final BidRequest bidRequest = givenBidRequest(...);

        // when
        final Result<List<HttpRequest<BidRequest>>> result = target.makeHttpRequests(bidRequest);

        // then
        assertThat(result.getErrors()).isEmpty();
        assertThat(result.getValue()).hasSize(1);
    }
}
```

Reviewer checklist:
- `extends VertxTest` (provides `jacksonMapper` + `mapper` field for use)
- `@org.junit.jupiter.api.Test` (NOT `org.junit.Test` — the older `org.junit.Test` is BANNED by checkstyle `IllegalImport`)
- `@BeforeEach` (NOT `@Before` from JUnit 4)
- `org.assertj.core.api.Assertions.assertThat(...)` (NOT `org.junit.Assert.assertEquals(...)`)
- Mocks via `org.mockito.Mockito.mock(Class.class)` + `when(...).thenReturn(...)` + `verify(...)`
- Method names: **camelCase** (the F-new-60 trap — see §4.4)

### 4.2 Integration tests — `extends IntegrationTest`

IT tests live under `src/test/java/org/prebid/server/it/{X}Test.java` and drive the full Vert.x server with WireMock stubs:

```java
package org.prebid.server.it;

import io.restassured.response.Response;
import org.junit.jupiter.api.Test;
import org.springframework.test.context.TestPropertySource;

@TestPropertySource(locations = "test-application.properties", properties = {
        "auction.host.skip-validation=true"
})
public class {X}Test extends IntegrationTest {

    @Test
    public void openrtb2AuctionShouldRespondWithBidsForKnownPublisher() throws IOException, JSONException {
        // given
        WIRE_MOCK_RULE.stubFor(post(urlPathEqualTo("/{x}-exchange"))
                .withRequestBody(equalToJson(jsonFrom("openrtb2/{x}/test-{x}-bid-request.json")))
                .willReturn(aResponse().withBody(jsonFrom("openrtb2/{x}/test-{x}-bid-response.json"))));

        // when
        final Response response = responseFor(...);

        // then
        assertJsonEquals("openrtb2/{x}/test-auction-{x}-response.json", response, singletonList({X}));
    }
}
```

Reviewer checklist:
- `extends IntegrationTest` (provides `WIRE_MOCK_RULE`, `responseFor`, `assertJsonEquals` helpers)
- Per-alias IT classes (e.g., `AdportTest.java`) are mandatory when a new alias lands — Java has no per-alias YAML, so this is the alias's test surface
- 4-file fixture set per scenario per **Rule 36**. Note the two *different* shapes — the auction pair puts `auction` BEFORE the bidder name, the bid pair puts it after:
  - `test-auction-{name}-request.json` — inbound publisher auction request
  - `test-auction-{name}-response.json` — expected outbound PBS auction response
  - `test-{name}-bid-request.json` — what the adapter sends to the bidder (WireMock `equalToJson`)
  - `test-{name}-bid-response.json` — what WireMock returns as the bidder

  Verified at `e3ffd57` against `src/test/resources/org/prebid/server/it/openrtb2/kobler/` and `…/adprime/`. `test-{name}-auction-request.json` (auction after the name) is NOT the upstream shape — a fixture written that way is loaded by no `@Test` and the IT fails on a missing resource.

### 4.3 Mocking conventions

- `JacksonMapper` is provided by `VertxTest` — DON'T mock it
- `CurrencyConversionService` is typically mocked via `mock(CurrencyConversionService.class)` + `when(svc.convertCurrency(...)).thenReturn(BigDecimal.ONE)`
- Clock injection (when used) via `mock(Clock.class)` + `when(clock.instant()).thenReturn(Instant.now())`

### 4.4 F-new-60 trap: snake_case test method names

The D2.8 template emitted test method names like `scenarioFor_app_simple_banner`. Java's checkstyle `MethodName` rule enforces `^[a-z][a-zA-Z0-9]*$` (camelCase only). Underscores fail. Correct emission: `scenarioForAppSimpleBanner`. Severity: **MEDIUM** (compiles but breaks CI). Owning skill: `bidder-class-pr-review`. Hits 6/6 D2.8 canaries.

---

## 5. Jacoco coverage gates

Jacoco plugin version `0.8.13` (`<jacoco-maven-plugin.version>`, `extra/pom.xml:30`).

### 5.1 Jacoco is a REPORT, not a gate

**Verified at `e3ffd57`. There is no coverage threshold enforced anywhere in this build.**

- `extra/pom.xml:327-344` declares the plugin with exactly two executions: `before-unit-test-execution` → goal `prepare-agent`, and `after-unit-test-execution` (phase `prepare-package`) → goal `report`. **No `check` goal. No `<rules>` / `<limit>` block.**
- The root `pom.xml:517-531` adds only `<skip>${skipUnitTests}</skip>` plus an `<excludes>` list. Still no `check`, still no `<rules>`.
- No workflow under `.github/workflows/` runs a coverage step, uploads a coverage report, or gates on one (`grep -rn 'jacoco\|coverage\|codecov' .github/workflows/` → empty).

Consequence: **a coverage shortfall cannot fail CI, and reviewers MUST NOT write "the Jacoco gate will fail" in a finding.** Nothing in the build reads the number.

### 5.2 Where the 90% figure actually comes from

Upstream states it normatively, in `docs/developers/contributing.md:17`:

> All pull requests must have **90% coverage in the changed code**. Check the code coverage with your IDE or external tools.

`.github/pull_request_template.md:34` is the author's attestation of that rule, not the rule itself:

> - [ ] Does your test coverage exceed 90%?

So there are two true statements and they must be given together. The requirement is real and normative — "self-certify with your IDE" is exactly what the contributing guide asks for, because nothing computes it in CI. And nothing enforces it: jacoco is report-only (§5.1) and no workflow runs a coverage step. Describing the 90% as merely a checkbox understates a genuine merge-bar requirement; describing it as a gate overstates a control that does not exist.

The practical consequence for a reviewer: coverage is **yours to judge**, precisely because CI will not do it for you. Reviewer disposition when a PR ships an obviously untested code path:

- **INFO / NOTE** by default — cite the PR-template checkbox, ask the author to confirm it.
- **WARN / ASK** when a *specific* changed branch in `{X}Bidder.java` has no corresponding `@Test` — name the branch, not a percentage.
- Never **FAIL / BLOCK** on coverage alone. There is no build gate to point at.

### 5.3 Per-file expectations

- `{X}Bidder.java` — primary test target. Unit tests in `{X}BidderTest.java` exercise `makeHttpRequests` + `makeBids` directly.
- Helper classes (`{X}Utils.java`, custom DTOs) — covered indirectly via main-class tests. Standalone tests are unusual; reviewers should not require them.
- `ExtImp{X}.java` — Lombok boilerplate; standalone tests are not required.
- IT tests — DO NOT contribute to Jacoco unit-test coverage. Jacoco's `prepare-agent` is wired to the unit-test phase (`maven-surefire-plugin`), which runs before IT (`maven-failsafe-plugin`).
- **Spring config classes are not measured at all.** The root `pom.xml` jacoco `<excludes>` (line 528) contains `org/prebid/server/spring/config/**`. Every `{X}Configuration.java` and every Rule 35 typed-config subclass nested inside one is therefore outside the report entirely — a coverage argument about them is meaningless in both directions. (This is why the former F-new-52 trap has been removed from §8: it asserted a 0%-coverage consequence for a file class jacoco never instruments.)

---

## 6. mvn-checkstyle ruleset (full enumeration)

Sourced verbatim from `prebid/prebid-server-java/checkstyle.xml` at SHA `e3ffd57`. Plugin: `maven-checkstyle-plugin` 3.6.0 (`<checkstyle-plugin.version>`); Checkstyle engine: `10.17.0` (`<checkstyle.version>`), both in `extra/pom.xml`.

**Checkstyle IS a real gate — keep every pre-flag in this section.** `extra/pom.xml:285-313` binds the plugin's `check` goal to the `validate` phase with `<failsOnError>true</failsOnError>` and `<includeTestSourceDirectory>true</includeTestSourceDirectory>`. `validate` is the first phase of `mvn package`, so a checkstyle violation fails the build **before compilation** and surfaces as a failure of the `build (25)` check-run (§8.2) — there is no separate `checkstyle` check-run to look for.

`<failsOnError>true</failsOnError>` — any violation fails the build. `<includeTestSourceDirectory>true</includeTestSourceDirectory>` — test files are checked too (with limited suppressions, see §6.10).

### 6.1 File-level rules

| Rule | Settings | Common review-time mistake |
|---|---|---|
| `NewlineAtEndOfFile` | (defaults) | Missing trailing newline — IDE-default issue |
| `Translation` | (defaults) | i18n properties bundles must be complete |
| `FileLength` | max=2024 | Bidder classes > 2024 lines — split into helpers |
| `FileTabCharacter` | (defaults) | Tabs disallowed; spaces only |
| `RegexpSingleline` | `\s+$` | Trailing whitespace |
| `RegexpMultiline` | `^.*(class\|interface\|enum) [^{]*\{\n[^\n}]` | Missing blank line after `class X {` declaration |
| `RegexpMultiline` | `System\.(out\|err)\.print` | `System.out.println` in adapter code (banned — use SLF4J) |
| `LineLength` | max=120; ignores package/import/URLs/`@see`/`//`-only | **F-new-61 trap** — lines > 120 chars in template-emitted IT fixtures |

### 6.2 Naming + structural rules (TreeWalker)

| Rule | Settings | Common review-time mistake |
|---|---|---|
| `Indentation` | lineWrappingIndentation=8; arrayInitIndent=8 | Tabs vs spaces; off-by-4 indentation |
| `EmptyLineSeparator` | allowNoEmptyLineBetweenFields=true; allowMultipleEmptyLines=false | Multiple blank lines between methods |
| `NoLineWrap` | (defaults) | (class declarations) |
| `NeedBraces` | (defaults) | `if (x) y();` without braces |
| `ConstantName` | `^([A-Z][A-Z0-9]*(_[A-Z0-9]+)*\|(.*?)[l,L]ogger)$` | non-UPPER_SNAKE constants |
| `FinalLocalVariable` | tokens=VARIABLE_DEF | Local variables must be `final` unless reassigned |
| `LocalFinalVariableName` | (defaults) | |
| `LocalVariableName` | (defaults) | camelCase only |
| `MemberName` | (defaults) | camelCase only |
| `MethodName` | (defaults: `^[a-z][a-zA-Z0-9]*$`) | **F-new-60 trap** — snake_case method names |
| `MultipleVariableDeclarations` | (defaults) | `int a, b;` — one per line |
| `PackageName` | (defaults) | |
| `ParameterName` | (defaults) | |
| `StaticVariableName` | (defaults) | |
| `TypeName` | (defaults) | UpperCamelCase only |

### 6.3 Import rules — F-new-58 / F-new-59 trap

| Rule | Settings | Common review-time mistake |
|---|---|---|
| `AvoidStarImport` | (defaults) | `import java.util.*;` banned |
| `AvoidStaticImport` | (defaults) | `import static Foo.bar;` banned in non-test files (test files exempt — see §6.10) |
| `IllegalImport` | `illegalPkgs=autovalue.shaded.com.google,org.inferred.freebuilder.shaded.com.google,org.apache.commons.lang`; `illegalClasses=org.junit.Test` | Using `org.apache.commons.lang` (must be `lang3`); using `org.junit.Test` (must be `org.junit.jupiter.api.Test`) |
| `IllegalImport id="BanVertxJsonImport"` | `illegalClasses=io.vertx.core.json.Json` (suppressed only for `ObjectMapperProvider.java`) | Importing `io.vertx.core.json.Json` — use `JacksonMapper` instead |
| `RedundantImport` | (defaults) | `import java.lang.String;` |
| `UnusedImports` | processJavadoc=true | **F-new-96 trap** — unused `JsonNode` / unused `JsonProcessingException` imports |
| `ImportOrder` | **option=bottom; groups=`*,/^java|^jakarta/`; ordered=false; separated=true; caseSensitive=true; sortStaticImportsAlphabetically=true; useContainerOrderingForStatic=false** | **F-new-58/59 trap** — see breakdown below |

**Import order semantics — INVERTED from typical Java conventions:**

The `groups="*,/^java|^jakarta/"` + `option="bottom"` settings mean:
1. **TOP group**: ALL non-`java`/non-`jakarta` imports (third-party libs + project classes mixed), in source order (NOT alphabetical — `ordered=false`).
2. **Blank separator line**.
3. **BOTTOM group**: `java.*` AND `jakarta.*` imports, in source order.
4. Static imports sorted alphabetically across groups.

This is INVERTED from the common Eclipse/IntelliJ default (`java/javax` at top, third-party below). PRs imported via IDE auto-format almost always violate this. The **F-new-58 trap** is `BidderDeps` import out of group order (hits 6/6 D2.8 canaries); the **F-new-59 trap** is `lombok.Data` import out of order on Rule-35-applying canaries.

Verified pattern from `AaxConfiguration.java`:
```java
import org.prebid.server.bidder.BidderDeps;        // TOP group (third-party + project)
import org.prebid.server.bidder.aax.AaxBidder;
// ... more non-java imports ...
import org.springframework.context.annotation.PropertySource;

import jakarta.validation.constraints.NotBlank;    // BOTTOM group (java + jakarta), blank separator above
```

### 6.4 Whitespace + brace rules

| Rule | Common review-time mistake |
|---|---|
| `MethodLength` | (defaults — typically 150 lines) — bidder methods exceeding limit |
| `EmptyForIteratorPad` (option=space) | `for (;;)` formatting |
| `GenericWhitespace` | `Map<String,String>` (missing space) |
| `MethodParamPad` (allowLineBreaks=false) | `foo (x)` (extra space) |
| `NoWhitespaceAfter` (tokens: INC,DEC,UNARY_*,BNOT,LNOT,DOT,...) | `obj . method()` |
| `NoWhitespaceBefore` | `obj .method()` |
| `OperatorWrap` | binary operator at end of wrapped line |
| `ParenPad` / `TypecastParenPad` | `foo( x )` (extra space) |
| `WhitespaceAfter` / `WhitespaceAround` | `if(x)` (missing space) |

### 6.5 Annotation + modifier rules

| Rule | Common review-time mistake |
|---|---|
| `AnnotationLocation` | `@Test public void foo()` (annotation must be on previous line) |
| `ModifierOrder` | `static public final` (must be `public static final`) |
| `RedundantModifier` | `public abstract` on interface method |
| `MissingOverride` | Missing `@Override` annotation on inherited method |

### 6.6 Block + statement rules

| Rule | Common review-time mistake |
|---|---|
| `AvoidNestedBlocks` | Bare `{ ... }` block inside method |
| `EmptyBlock` | `if (x) {}` |
| `LeftCurly` | `{` placement |
| `RightCurly` (default) | `}` placement |
| `RightCurly id=METHOD_DEF` (option=alone) | Method-closing `}` must be alone on its line |
| `EmptyStatement` | Stray `;` |
| `OneStatementPerLine` | `int a = 1; int b = 2;` |

### 6.7 Code-quality rules

| Rule | Common review-time mistake |
|---|---|
| `EqualsHashCode` | Overriding only `equals` without `hashCode` |
| `IllegalInstantiation` | Direct `new Boolean(...)` (use `Boolean.valueOf`) |
| `InnerAssignment` | `if ((x = foo()) != null)` |
| `SimplifyBooleanExpression` | `if (a == true)` |
| `SimplifyBooleanReturn` | `if (x) return true; else return false;` |
| `HideUtilityClassConstructor` | Utility class without private constructor (e.g., `HttpUtil`, `BidderUtil` declare `private HttpUtil() {}`) |
| `ArrayTypeStyle` | `int x[]` (must be `int[] x`) |
| `CommentsIndentation` | Misaligned comments |
| `UpperEll` | `long x = 1l;` (must be `1L`) |
| `IllegalThrows` | Throwing generic `Throwable` |
| `OuterTypeFilename` | **F-new-79 trap** — public class name must match filename root |
| `OverloadMethodsDeclarationOrder` | Overloads must be grouped |
| `SeparatorWrap` (DOT=nl, COMMA=eol) | `foo,\n bar` wrap direction |
| `SingleSpaceSeparator` | `int  x` (double space) |
| `StringLiteralEquality` | `s == "literal"` (must be `.equals`) |
| `UnnecessaryParentheses` | Redundant parens in expressions (extensive token list — see source) |

### 6.8 Suppression filter

```xml
<module name="SuppressWarningsFilter"/>
<module name="SuppressWarningsHolder"/>
```

Enables `@SuppressWarnings("checkstyle:ruleName")` to suppress specific rules at method/class level. Use sparingly; reviewers should challenge any new suppression.

### 6.9 Indentation policy

`Indentation` rule: `lineWrappingIndentation=8`, `arrayInitIndent=8`, `forceStrictCondition=false`. **8-space indentation on continuation lines** is the upstream convention — not 4. PRs that wrap with 4-space continuation violate this.

### 6.10 Suppression filters (test files)

```xml
<SuppressionSingleFilter checks="AvoidStaticImport" files=".*Test\.java"/>
<SuppressionSingleFilter checks="FileLength"        files=".*Test\.java"/>
<SuppressionSingleFilter id="BanVertxJsonImport"    files="src/main/java/org/prebid/server/json/ObjectMapperProvider\.java"/>
```

Test files MAY use static imports (AssertJ's `assertThat` is typically imported statically) AND MAY exceed 2024 lines. `ObjectMapperProvider.java` is the single allowed import site for `io.vertx.core.json.Json`.

---

## 7. Java idioms reviewers should expect

The Java codebase is idiomatic modern Java (Java 25 — `<java.version>` in `extra/pom.xml`, and the sole entry in the `build` job's matrix in `.github/workflows/pr-java-ci.yml`). Reviewers MUST recognize these patterns; failure to use them indicates either Go-port residue or pre-Java-8 style.

| Idiom | Pattern | Notes |
|---|---|---|
| `Optional<T>` for nullable returns | `Optional<Bid> resolveBid(...)` | Preferred over returning `null`. Use `.map`, `.orElse`, `.orElseGet`, `.ifPresent`. Don't `.get()` without `.isPresent()` check (or use `.orElseThrow`). |
| Stream API chains | `bids.stream().filter(...).map(...).collect(Collectors.toList())` | Preferred over manual for-loops for transformation/filter pipelines. `.toList()` (Java 16+) is preferred over `.collect(Collectors.toList())` in new code. |
| `toBuilder()` rebuild (Rule 5) | `bidRequest.toBuilder().site(...).build()` | The Java mutation idiom — see §2.2. Direct setter calls on `@Value` POJOs won't compile. |
| `CollectionUtils.isEmpty()` | `org.apache.commons.collections4.CollectionUtils.isEmpty(coll)` | Null-safe empty check. Preferred over `coll == null || coll.isEmpty()`. Note `collections4` (`org.apache.commons.collections4`) — NOT `collections` or `commons.collections`. |
| `StringUtils.*` (commons-lang3) | `StringUtils.isBlank(s)`, `StringUtils.isNotEmpty(s)`, `StringUtils.equalsIgnoreCase(a, b)` | From `org.apache.commons.lang3.StringUtils`. NOTE: `org.apache.commons.lang` (without `lang3`) is BANNED by checkstyle. |
| `BigDecimal.toPlainString()` | `bid.getPrice().toPlainString()` | For currency / numeric serialization without scientific notation. The Java analog of Go's `strconv.FormatFloat`. |
| `Objects.requireNonNull(x)` | Constructor null-checks | Throws `NullPointerException` with a meaningful message. Common in `{X}Bidder` constructors. |
| `Objects.equals(a, b)` | Null-safe equality | Preferred over `a.equals(b)` when `a` may be null. |
| `final` everywhere | All locals + params | Enforced by checkstyle `FinalLocalVariable` (locals must be `final` unless reassigned). |
| `Result<T>` for adapter returns | `Result.of(List<HttpRequest>, List<BidderError>)` | The `Bidder<T>` interface return type for `makeHttpRequests` / `makeBids`. Carries both successful output and per-imp errors. |
| `BidderError.badInput / badServerResponse` | Error taxonomy | Use `BidderError.badInput(msg)` for client (publisher) errors; `BidderError.badServerResponse(msg)` for upstream-bidder errors. Java analog of Go's `errortypes.BadInput` / `BadServerResponse`. |

---

## 8. Cross-skill F-new trap reference table

Brief tabular reference linking each F-new finding from D2.8 cross-canary to the SKILL that should flag it. Severity column follows the design doc / cross-canary summary semantics: **HIGH BLOCKING** = won't compile or won't pass build; **HIGH** = correctness bug surface; **MEDIUM** = checkstyle/style violation; **WARN** = process / informational.

| F-new | Symptom | Owning skill | Severity |
|---|---|---|---|
| F-new-50 family | `resolveEndpoint()` placeholder body for non-trivial endpoint kinds (`dev-prod-toggle`, `template-macro`, `multi-token-substitution`, `query-parameter-augmentation`) — returns `endpointUrl` unchanged | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-56 | Unreachable `JsonProcessingException` in `makeBids` multi-catch on `mapper.decodeValue()` (Jackson's `decodeValue` doesn't throw the checked exception) | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-57 | Spring DI factory passes `mapper` where `BidderConfigurationProperties` expected in `.withConfig(...)` | `bidder-config-pr-review` | HIGH BLOCKING |
| F-new-57b | Spurious method on the `BidderDepsAssembler` chain — `.bidderInfo(...)` or `.usersyncerCreator(...)`. Verified at SHA `e3ffd57`: the complete public surface is `forBidder`, `withConfig`, `bidderCreator`, `assemble` (§1.1a). `BidderInfo` and `Usersyncer` are both derived internally from the `@ConfigurationProperties`-bound YAML. `UsersyncerCreator` itself was deleted in `2880782f` (PR #4464). Any extra chain link is a compile error. | `bidder-config-pr-review` | HIGH BLOCKING |
| F-new-58 | `BidderDeps` (or other project-import) out of canonical 3-group order — non-java/jakarta imports at top, java/jakarta at bottom with blank separator | `bidder-config-pr-review` | MEDIUM |
| F-new-59 | `lombok.Data` import out of order in `{X}BidderConfigurationProperties.java` (or in `{X}Configuration.java` when subclass is nested) | `bidder-config-pr-review` | MEDIUM |
| F-new-60 | Test method names use `scenarioFor_app_simple_banner` snake_case — Java convention is camelCase per `MethodName` checkstyle | `bidder-class-pr-review` | MEDIUM |
| F-new-61 | LineLength > 120 chars in IT test fixture paths + scenario method invocations | `bidder-class-pr-review` | MEDIUM |
| F-new-64 | `resolveBidType` hardcodes `bid.ext.prebid.type` lookup, drops alternative paths like aax's `bid.ext.adCodeType` | `bidder-class-pr-review` | HIGH |
| F-new-66 | `bidder-config.yaml.j2` emits `usersync` dict as `tojson`-flow-style instead of block YAML | `bidder-config-pr-review` | MEDIUM-HIGH |
| F-new-67/69/72 | Empty `geoscope:` bare line on `geoscope: []` (YAML cosmetic) | `bidder-config-pr-review` | LOW |
| F-new-78 | Entity-mutation chains (Imp/Site/App/Banner/Video `toBuilder()` rebuild) not emitted — `makeHttpRequests` body is just passthrough | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-79 | `OuterTypeFilename` mismatch — `{X}BidderConfiguration.java` contains `public class {X}Configuration` (or vice versa) | `bidder-config-pr-review` | HIGH |
| F-new-86 | ADR-007 F3 Site→App synthesis not preserved — `makeHttpRequests` dispatches original `bidRequest` with Site, not synthesized App | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-90 | `BidderUtil.isResponseStatusCodeNoContent` / `BidderUtil.checkResponseStatusCode` — these methods DO NOT EXIST in upstream Java; Go-canonical names transliterated incorrectly | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-91 | imp.ext three-key wrapper repack path (`{prebid, bidder, vungle}` shape) missing in `makeHttpRequests` | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-92 | Buyer-UID promotion hook (`imp.ext.{bidder}.bid_token` → `user.buyeruid`) missing | `bidder-class-pr-review` | HIGH BLOCKING |
| F-new-93 | Custom HTTP header (e.g., `X-OpenRTB-Version: 2.5`) not emitted; `ctx.headers_collapse` ignored | `bidder-class-pr-review` | MEDIUM |
| F-new-96 | `UnusedImports` of `com.fasterxml.jackson.databind.JsonNode` (or `JsonProcessingException`) — checkstyle `UnusedImports` rule | `bidder-class-pr-review` | MEDIUM |
| F-new-100 | ADR-007 F4 bid-post-processing macros (`${AUCTION_PRICE}`) not preserved — `extractBids` is generic stream, never substitutes macros into nurl/adm/burl | `bidder-class-pr-review` | HIGH BLOCKING |

Reviewers cross-reference findings against this table when surfacing per-PR concerns. The cross-canary catalog at `docs/runs/d2.8-cross-canary-summary.md` holds the authoritative per-canary breakdown.

### 8.1 Severity glossary — FAIL ↔ HIGH BLOCKING alignment

The skills use two interlocking severity vocabularies. They map 1:1:

| Skill-finding severity (per-PR review) | F-new-trap catalog severity (this table) | Meaning |
|---|---|---|
| **FAIL** | **HIGH BLOCKING** | Build / compile / CI-blocking defect. Examples: F-new-79 (OuterTypeFilename), F-new-57 (`.withConfig(mapper)`), F-new-57b (non-existent assembler chain method), F-new-90 (non-existent `BidderUtil.*` method), F-new-56 (unreachable checked exception), F-new-78 / F-new-86 / F-new-91 / F-new-92 / F-new-100 (missing canonical emit paths — will not pass IT). |
| **FAIL** | **HIGH** | Correctness bug surface, but not necessarily build-blocking. Examples: F-new-64 (`resolveBidType` drops alternative chains — silently mis-types bids). When a HIGH F-new trap surfaces in a per-PR review, emit at **FAIL** severity unless the reviewer can confirm the affected code path is not exercised by tests. |
| **WARN** | **MEDIUM** | Checkstyle / style violation. Checkstyle runs inside the `build (25)` job (§6, §8.2), so these DO fail CI — but they fail at the `validate` phase rather than at compile or test. Examples: F-new-58 / F-new-59 (import order), F-new-60 (snake_case test names), F-new-61 (LineLength), F-new-66 (YAML flow-style usersync), F-new-93 (custom header), F-new-96 (UnusedImports). |
| **WARN** / **INFO** | **WARN** / **LOW** | Process/informational. F-new-67/69/72 (cosmetic YAML). |

This alignment is what each reviewer skill's "Severity" notation references when a finding cites a specific F-new trap. The skills emit **FAIL** for everything tagged HIGH BLOCKING and most HIGH; emit **WARN** for MEDIUM; emit **INFO** for LOW.

**Retired:** F-new-52 ("Rule 35 typed-config subclass has 0% Jacoco coverage") has been removed from this catalog. Its premise was false in two independent ways at `e3ffd57`: jacoco declares no `check` goal or `<rules>` anywhere, so there is no coverage gate to fail (§5.1); and `org/prebid/server/spring/config/**` is in jacoco's `<excludes>` (`pom.xml:528`), so a typed-config subclass is never instrumented in the first place. Do not re-derive it from either the number or the file.

### 8.2 CI check-run model — what actually runs on a PR

Reviewer skills classify CI as `blocked` / `passing` / `pending` from the GitHub Checks API. **The names matter, and the historical names in this suite were wrong.** There is no `Build / Test` check-run, no `checkstyle` check-run, and no `JaCoCo Coverage` check-run on this repo.

```bash
gh api "repos/prebid/prebid-server-java/commits/{head_sha}/check-runs" \
  --jq '"\(.total_count)|" + ([.check_runs[].name] | sort | join(", "))'
```

Observed on recent PR heads (2026-08-18):

| Check-run name | Source workflow | Meaning for a bidder PR |
|---|---|---|
| `build (25)` | `pr-java-ci.yml`, job `build`, matrix `java: [25]` | **The one that matters.** Runs `mvn -B package --file extra/pom.xml`, which executes checkstyle (`validate`), compile, unit tests (surefire), and jacoco `report`. A checkstyle violation, a compile error, and a failing unit test all surface here. Appears more than once per SHA when a workflow is re-run. |
| `Analyze (actions)` | `codeql-analysis.yml` | Workflow-definition scanning. Not adapter-relevant. |
| `Analyze (java-kotlin)` | `codeql-analysis.yml` | CodeQL source analysis. |
| `CodeQL` | `codeql-analysis.yml` | Aggregate CodeQL status. |
| `Trivy` | `trivy-security-check.yml` | Dependency/vuln scan. |
| `Trivy security check` | `trivy-security-check.yml` | Aggregate Trivy status. |
| `cross-repo` | `cross-repo-issue.yml` | Seen on merged/closed PRs; not part of the pre-merge gate. |

Classification rules:

1. **Map `blocked` to a failing `build (25)`**, not to a name that does not exist. When `build (25)` fails, the cause is checkstyle, javac, or surefire — the job log distinguishes them; there is no per-concern check-run to read a conclusion from.
2. **An empty check-run list is a FINDING, not a pass.** `total_count == 0` means the workflows never ran for that SHA — most often a fork PR from a first-time contributor awaiting a maintainer's "Approve and run workflows". Four of twelve recent PR heads sampled on 2026-08-18 (`#4601`, `#4597`, `#4589`, `#4582`) returned zero check-runs. Report it as **INFO / NOTE**: `CI: no check-runs for {head_sha} — workflows have not been authorized to run; CI state is unknown, not green.` Never report "CI passing" or "no failures" off an empty list.
3. Assert the list is non-empty for the **exact head SHA** before drawing any conclusion from it. A check-run list fetched for the base branch or a stale head proves nothing about the PR.

---

## 9. Cross-references

This file is consumed by all 4 Java review skills:

- [`../pr-triage-java/SKILL.md`](../pr-triage-java/SKILL.md) — Step 2 drift checks (compares live `pom.xml` / `checkstyle.xml` / `BidderConfigurationProperties.java` against the baselines pinned here). Step 5k pre-checkstyle pre-flags reference §6 rule semantics directly.
- [`../bidder-class-pr-review/SKILL.md`](../bidder-class-pr-review/SKILL.md) — adapter-implementation reviewer; consumes §1 Spring DI conventions (for the `{X}Bidder` constructor signature), §2 Lombok semantics (`toBuilder()` rebuild patterns), §3 Vert.x HTTP layer (§3.0 `Uri` macros, F-new-90 trap), §4 JUnit5+AssertJ (F-new-60 trap), §5 coverage expectations, §6 checkstyle (F-new-56/58/60/61/96 traps), §7 Java idioms, §8.2 CI check-run model.
- [`../bidder-config-pr-review/SKILL.md`](../bidder-config-pr-review/SKILL.md) — Spring configuration reviewer; consumes §1 Spring DI + §1.1a assembler surface (F-new-57/57b/79 traps), §2 Lombok (Rule 35 typed-config subclass conventions), §3.0 macro semantics, §6 checkstyle (F-new-58/59 import order traps).
- [`../bidder-params-java-pr-review/SKILL.md`](../bidder-params-java-pr-review/SKILL.md) — JSON schema + ExtImp{X} POJO reviewer; consumes §2 Lombok (`@Value @Builder` + `@JsonProperty`), §6 checkstyle (basic rules).

Upstream + cross-language sources:

- [`../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) — Rule 5 entity-mutation `toBuilder()`, Rule 19 standard headers via `HttpUtil.headers()`, Rule 30 framework-default HTTP status handling, Rule 35 typed-config subclass, Rule 36 4-file IT fixture set, Rule 38 byte-fidelity (bidder-params JSON).
- [`../../../../docs/runs/d2.8-cross-canary-summary.md`](../../../../docs/runs/d2.8-cross-canary-summary.md) — Authoritative F-new findings catalog (D2.8 cross-canary corpus). Per-canary traces preserve subagent-local F-new numbering.
- [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) — Phase F4 design doc; covers skill ownership boundaries, asymmetric Go↔Java concerns, cross-skill manifest contract.
- [`../../../read/skills/shared/framework-utilities-java.md`](../../../read/skills/shared/framework-utilities-java.md) — Read-side companion (Phase D1.3 deliverable). Covers utility catalog (`BidderUtil`, `BidderDepsAssembler`, `JacksonMapper`, `CurrencyConversionService`, `HttpUtil`, `BidderInfoCreator`) from the read-side perspective. This review-side file adds reviewer-specific anti-patterns + verbatim policy quotes.
- `prebid/prebid-server-java` master at SHA `e3ffd57` — `checkstyle.xml`, `pom.xml`, `extra/pom.xml`, `.github/workflows/pr-java-ci.yml`, `.github/pull_request_template.md`, `src/main/java/org/prebid/server/util/{HttpUtil,BidderUtil,Uri}.java`, `src/main/java/org/prebid/server/spring/config/bidder/util/{BidderDepsAssembler,UsersyncerUtil,BidderInfoCreator}.java`, `src/main/java/org/prebid/server/spring/config/bidder/{AaxConfiguration,AdprimeConfiguration,KoblerConfiguration,MagniteConfiguration,AdnuntiusBidderConfiguration}.java`.

---

## 10. Sources

- `prebid/prebid-server-java` master @ SHA `e3ffd57` (verified 2026-08-18)
- `checkstyle.xml` (verbatim rule enumeration in §6)
- `pom.xml` (parent-inherited version `4.1.0-SNAPSHOT`; jacoco `<excludes>` at line 528)
- `extra/pom.xml` (`4.1.0-SNAPSHOT`, Java 25, jacoco 0.8.13 report-only, checkstyle 10.17.0 + plugin 3.6.0 on `validate`, Spring Boot 4.0.6, Vert.x 5.0.12)
- `.github/workflows/pr-java-ci.yml` (job `build`, matrix `java: [25]` → check-run `build (25)`)
- `.github/pull_request_template.md:34` (the 90%-coverage checkbox — the only place the figure appears)
- `src/main/java/org/prebid/server/util/HttpUtil.java` (parseUrl, validateUrl, encodeUrl, headers)
- `src/main/java/org/prebid/server/util/Uri.java` (`of`, `replaceMacro`, `replaceMacros`, `addQueryParam`, `expand`; RFC 6570 via `io.vertx.uritemplate.UriTemplate`)
- `src/main/java/org/prebid/server/util/BidderUtil.java` (defaultRequest, impIds, isValidPrice, getBidType at 112-129)
- `src/main/java/org/prebid/server/spring/config/bidder/util/BidderDepsAssembler.java` (public surface `forBidder`, `withConfig`, `bidderCreator`, `assemble`)
- `src/main/java/org/prebid/server/spring/config/bidder/AaxConfiguration.java` (canonical singleton form, `Uri`-based `resolveEndpoint`)
- `src/main/java/org/prebid/server/spring/config/bidder/AdprimeConfiguration.java` (canonical: full `usersync:` YAML, no usersync call in the assembler chain)
- `src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java` (canonical Rule 35 nested subclass form)
- `src/main/java/org/prebid/server/spring/config/bidder/MagniteConfiguration.java` (nested subclass with `@Valid @NotNull XAPI xapi`; renamed from Rubicon in PR #4573)
- `src/main/java/org/prebid/server/spring/config/bidder/AdnuntiusBidderConfiguration.java` (canonical `{X}BidderConfiguration` naming variant)
- `src/main/java/org/prebid/server/bidder/aceex/AceexBidder.java:36,68` (canonical bare-name macro constant + `Uri.replaceMacro(...).expand()`)
- `prebid-server-go/read/skills/shared/port-translation-rules.yaml` (Rules 5, 19, 30, 35, 36, 38)
- `docs/runs/d2.8-cross-canary-summary.md` (F-new findings catalog)
- `docs/methodology/java-review-skill-design.md` (Phase F4 design)
