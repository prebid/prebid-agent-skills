# Java review-skill suite — design doc (Phase F4)

Design for the four `prebid-server-java/review/skills/*` SKILLs and their shared framework reference. Phase F4 ships the suite that brings the Go-side review surface (3 reviewer skills + 1 orchestrator + 1 shared framework doc) over to the Java tree, mirroring the read/ suite's earlier Go ↔ Java symmetry effort.

Status: **complete, full F4 suite shipped.** This PR lands the design doc plus all four SKILL.md files at v1.0.0, all four `references/*.md` deep-dives, and the review-side `shared/framework-utilities-java.md` — the entire Phase F4 surface in one PR (3 sequential commits per the audit at [`../runs/post-d3.8-remaining-work.md`](../runs/post-d3.8-remaining-work.md) §F4).

This file is the design contract anchoring the four shipped skills.

---

## 1. Scope

### In scope (this phase, F4 — all shipped at v1.0.0)

| Skill | Owns | Status this session |
|---|---|---|
| `pr-triage-java` | Routing, drift checks, CI status, PR-type detection, manifest emission | v1.0.0 (commit `6f53c11`; references/routing-rules.md commit `c618fde`) |
| `bidder-class-pr-review` | `bidder/{x}/*.java` + `bidder/{x}/*Test.java` + the `it/{X}Test.java` IT class | v1.0.0 (commit `63be93d`; references/bidder-class-index.md commit `c618fde`) |
| `bidder-config-pr-review` | `bidder-config/{x}.yaml` + `{X}Configuration.java` + the Rule 35 typed-config subclass (in current upstream practice an inner `private static class` inside `{X}Configuration.java`; separate-file `{X}BidderConfigurationProperties.java` is absent from upstream master (checked at `e3ffd57`; the suffix names two framework classes)) | v1.0.0 (commit `63be93d`; references/field-index.md commit `c618fde`) |
| `bidder-params-java-pr-review` | `bidder-params/{x}.json` + `ExtImp{X}.java` + `it/openrtb2/{x}/*.json` IT fixtures | v1.0.0 (commit `63be93d`; references/params-type-index.md commit `c618fde`) |
| `shared/framework-utilities-java.md` (review-side) | Cross-cutting Java conventions reviewers must know | v1.0.0 (commit `63be93d`) — adds reviewer-specific anti-patterns + verbatim policy quotes on top of the read-side analog at `prebid-server-java/read/skills/shared/framework-utilities-java.md` |

### Out of scope (NOT this phase)

- **The Java upstream codebase itself** — F4 ships skills that REVIEW PRs against `prebid/prebid-server-java`. The upstream repo isn't modified.
- **The Java `read/` skill suite** — already shipped (Phase C, all 4 skills at v1.0.0+).
- **Cross-language review** — Java PRs that were ported from Go consume `prior_source_spec` (the SOURCE-language spec) via the SAME hook the Go side just shipped on `feat/f5-port-fidelity-hooks`. F4 authors the manifest BLOCK in `pr-triage-java` AND the three downstream reviewer skills CONSUME it in this same F4 PR (audit item 25 LANDED — see §4 below + Step 1g in each downstream SKILL.md).
- **`write/` skills** — Phase G (not started).
- **`diff-spec` skills** — design-only at audit time.

---

## 2. File ownership map

Mirror of the Go-side routing rules at `prebid-server-go/review/skills/pr-triage/references/routing-rules.md`. Java's hierarchy is deeper than Go's because Spring DI separates configuration from implementation.

### bidder-class-pr-review

| Pattern | Example | Notes |
|---|---|---|
| `src/main/java/org/prebid/server/bidder/{x}/*.java` | `…/bidder/aax/AaxBidder.java` | Adapter implementation + helpers (request/response models, custom mappers) co-located with the class |
| `src/test/java/org/prebid/server/bidder/{x}/*.java` | `…/bidder/aax/AaxBidderTest.java` | Unit tests (JUnit5 + AssertJ; what these cover drives the Jacoco report — see §5.5, which is a review expectation, not a build gate) |
| `src/test/java/org/prebid/server/it/{X}Test.java` | `…/it/AaxTest.java` | The IT test class. Per-alias IT classes also land here (Adverxo aliases ship `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`) — each lives at `it/{X}Test.java` where `X` is the TitleCase classroot of the alias name |

### bidder-config-pr-review

| Pattern | Example | Notes |
|---|---|---|
| `src/main/resources/bidder-config/{x}.yaml` | `bidder-config/aax.yaml` | UNIFIED bidder-info + endpoint + aliases + usersync. Note: Java's YAML is one file per parent; aliases are nested under the parent (`aliases: { adport: ~ }`), inverted from Go's per-alias `aliasOf:` pattern (port-translation Rule 33) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` | `…/config/bidder/AaxConfiguration.java` | Spring `@Configuration` factory: `@Bean` declaring `BidderConfigurationProperties` + `BidderDeps` via `BidderDepsAssembler` |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` | `…/config/bidder/AdverxoBidderConfiguration.java` | Same role as above; upstream uses BOTH `{X}Configuration.java` AND `{X}BidderConfiguration.java` naming forms (see §5 conventions; the bidder-config skill must accept either) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` | (design-permitted; no upstream example at SHA `a1fe64e123d6`) | The Rule 35 typed-config subclass when shipped as a SEPARATE file — present ONLY when the bidder needs extra config fields beyond the framework default (e.g., `dev-endpoint`, `pixel-url`, `region-prefix`). Subclasses `BidderConfigurationProperties`. Lombok `@Data`. In current upstream practice ALL Rule 35 subclasses are inner `private static class` declarations inside `{X}Configuration.java` (canonical: Kobler, TheTradeDesk, Adnuntius). The separate-file form has no upstream instance — when a PR ships it, this skill's activation table covers it |

### bidder-params-java-pr-review

| Pattern | Example | Notes |
|---|---|---|
| `src/main/resources/static/bidder-params/{x}.json` | `…/static/bidder-params/aax.json` | The draft-04 JSON Schema for the bidder's imp.ext params. **Byte-identical to the Go-side `static/bidder-params/{x}.json`** for paired bidders per Rule 38 — divergence (e.g., missing `minLength: 1`) is a `cross-language-pairs/*.dual-spec-assertions.yaml` finding |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/ExtImp{X}.java` | `…/ext/request/aax/ExtImpAax.java` | The Lombok `@Value @Builder` POJO matching the JSON schema. May have helper protos in the same package (e.g., `ExtImpAaxBidExt.java`, `ExtImpAaxParams.java`) when the schema has nested objects |
| `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` | `…/it/openrtb2/aax/test-aax-bid-request.json` | The 4-file split fixture set per port-translation Rule 36 per scenario: `test-auction-{x}-{request,response}.json` (inbound publisher request + expected PBS response) + `test-{x}-bid-{request,response}.json` (outbound to bidder + mock bidder response). Some bidders ship multiple scenarios; each scenario is 4 files. The IT class' `@Test` methods reference these by filename pattern |

### pr-triage-java (shared / multi-bidder files)

| Pattern | Example | Notes |
|---|---|---|
| `src/test/resources/org/prebid/server/it/test-application.properties` | (single file) | The central registry that every bidder appends to. The Java equivalent of Go's `exchange/adapter_builders.go` + `openrtb_ext/bidders.go` shared registration files. pr-triage-java owns it because every new-adapter PR touches it |
| `extra/pom.xml` | (single file) | Hosts the bidder module's optional Maven dependencies. Touched on new-adapter PRs that pull in non-default JARs |
| `pom.xml` | (single file) | Root project POM; framework-impact file. Drift check (see §5.3 below) |

### Unowned by reviewer skills

- `checkstyle.xml` — framework-impact file; pr-triage emits drift warning when modified
- `src/main/java/org/prebid/server/auction/**` — exchange/auction framework; framework-only label
- `src/main/java/org/prebid/server/spring/config/**` (excluding `config/bidder/`) — non-bidder Spring infrastructure
- `*.md`, `docs/**`, `.github/**`, `Dockerfile*`, `mvnw*` — docs/CI/build

---

## 3. Symmetric / asymmetric structure vs Go

The Java review suite is **3 reviewer skills + 1 orchestrator** like the Go side, BUT the per-skill ownership is asymmetric because Java's framework has structural features Go does not.

### 3.1 Symmetric (1:1 mapping)

| Concern | Go skill | Java skill | Notes |
|---|---|---|---|
| Routing + manifest | `pr-triage` | `pr-triage-java` | Same orchestrator pattern, Java-specific drift checks |
| Adapter implementation review | `adapter-code-pr-review` | `bidder-class-pr-review` | Java reviewer owns IT class + unit tests in addition |
| JSON schema + Go-side imp-ext POJO review | `bidder-params-pr-review` | `bidder-params-java-pr-review` | Java reviewer also owns IT fixtures (Rule 36 4-file set) |
| Bidder-info YAML review | `bidder-info-pr-review` | (subsumed by `bidder-config-pr-review`) | Java's YAML is unified (bidder-info + endpoint + aliases together); the YAML reviewer is folded into the config reviewer |

### 3.2 Asymmetric (Java-only concerns)

The following Java framework features have **no Go analog** and demand reviewer attention the Go side doesn't need:

1. **Spring DI configuration files (`{X}Configuration.java`).** Each Java bidder has a `@Configuration` class wiring its `BidderDeps`. Go has no analog — Go's `exchange/adapter_builders.go` is a single 600-line `map[string]builderConstructor` keyed by BidderName. The Java reviewer must check:
   - `@PropertySource(value = "classpath:/bidder-config/{x}.yaml", factory = YamlPropertySourceFactory.class)` — wired to the correct YAML
   - `@Bean("xConfigurationProperties") @ConfigurationProperties("adapters.x")` — bean name + properties prefix match the bidder
   - `BidderDepsAssembler.forBidder(BIDDER_NAME)` — constant matches the YAML's adapter key
   - The `bidderCreator` lambda's constructor args match `{X}Bidder`'s signature
   - When Rule 35 applies: `withConfig({x}ConfigurationProperties)` references the typed subclass, not the base class
   - **Class-name-vs-filename match** (the F-new-79 trap): the public class declared inside MUST match the filename; `Adverxo.java` cannot contain `public class AdverxoBidderConfiguration` and vice versa. checkstyle's `OuterTypeFilename` catches this, but reviewers should flag it pre-CI.
   - This is `bidder-config-pr-review`'s primary surface.

2. **Java has Lombok annotations** (`@Value`, `@Builder`, `@Data`, `@Slf4j`). Reviewers must verify:
   - `ExtImp{X}.java` declares `@Value @Builder` (Java's immutable-by-default idiom); deviations like raw POJOs or `@Data` (which generates setters) are anti-patterns.
   - `{X}BidderConfigurationProperties.java` uses `@Data` (Spring's bean form needs setters); deviations like `@Value` would break Spring property injection.
   - `bidder-params-java-pr-review` and `bidder-config-pr-review` share this concern; both should reference the same shared anti-pattern list.

3. **Maven + Checkstyle ruleset.** Java's analog of `gofmt + go vet` is `mvn -B checkstyle:check` against `checkstyle.xml` at the repo root. The ruleset (verified at upstream SHA `a1fe64e123d6` per `prebid-server-java/read/skills/shared/framework-utilities-java.md`):
   - `LineLength` max=120 (vs Go's no enforced line limit)
   - `EmptyLineSeparator` between fields/methods (loose for fields, strict for methods)
   - `ImportOrder` 3-group: `*`, then blank, then `java|jakarta`; sortStaticImports alphabetically — strict (catches F-new-58/59)
   - `FinalLocalVariable` on `VARIABLE_DEF` — Java's analog of "prefer immutability"; locals must be `final` unless reassigned
   - `IllegalImport` BANS `io.vertx.core.json.Json` everywhere except `ObjectMapperProvider.java` — only `JacksonMapper` is acceptable for JSON
   - `AvoidStarImport`, `RedundantImport`, `UnusedImports(processJavadoc=true)` — strict
   - `FileLength` max=2024 (5x Go's typical adapter, but bidders should still fit comfortably)
   - `MultipleVariableDeclarations`, `SimplifyBooleanExpression`, `SimplifyBooleanReturn`, `EqualsHashCode`, `MissingOverride`, `StringLiteralEquality` (`==` on strings)
   - Suppressions for `*Test.java`: `AvoidStaticImport` and `FileLength` off (AssertJ uses static imports heavily; test files can be long)
   - (Coverage is NOT part of this checkstyle list, and not a build gate at all — see §5.5.)

4. **IT tests as a separate concept.** Go has unit tests (`{bidder}_test.go`) + JSON fixtures under `{bidder}test/exemplary/` and `supplemental/` — one test runner, multiple fixtures. Java has TWO test surfaces:
   - **Unit tests**: `src/test/java/org/prebid/server/bidder/{x}/{X}BidderTest.java` — hand-written `@Test` methods (10–50 typically), AssertJ assertions, Mockito for `JacksonMapper`/`CurrencyConversionService`. Owned by `bidder-class-pr-review`.
   - **Integration tests**: `src/test/java/org/prebid/server/it/{X}Test.java` — extends `IntegrationTest`, uses WireMock stubs, drives the FULL Vert.x server. Each scenario references a 4-file fixture set under `src/test/resources/org/prebid/server/it/openrtb2/{x}/`. The IT class is owned by `bidder-class-pr-review` (it's a Java class with test logic); the 4-file fixtures are owned by `bidder-params-java-pr-review` (they're the schema-exercising payloads). This split forces a **cross-skill concern** when one moves without the other (§7 cross-skill references below).

5. **Rule 35 typed-config subclass.** When a Java bidder needs extra config fields beyond the framework default (the canonical example is Kobler's `dev-endpoint`), upstream creates a subclass `extends BidderConfigurationProperties`. In current upstream practice (SHA `a1fe64e123d6`) the subclass is always an inner `private static class` inside `{X}Configuration.java` (Kobler, TheTradeDesk, Adnuntius); the separate-file `{X}BidderConfigurationProperties.java` form has no upstream instance. Go has no equivalent — Go adapters access extras via the `cfg config.Adapter` map directly or a per-adapter extra struct. Reviewers must check:
   - The subclass extends `BidderConfigurationProperties` (not `Object`)
   - Lombok `@Data` (not `@Value`) — Spring needs setters
   - Field names match the YAML's snake-case → Spring relaxed-binding (e.g., YAML `dev-endpoint` ↔ Java `devEndpoint`)
   - The `{X}Configuration.java` references the typed subclass in `@Bean` and `withConfig(...)` calls
   - Owned by `bidder-config-pr-review`.

6. **Alias inversion (port-translation Rule 33).** Go alias YAMLs are PER ALIAS (`static/bidder-info/adport.yaml` declares `aliasOf: adverxo`). Java aliases are NESTED under the parent (`bidder-config/adverxo.yaml` declares `adapters.adverxo.aliases.adport: {...}`). A new Java alias does NOT add a new YAML file; it modifies the parent's YAML. This means:
   - Java's "alias-only" PR type is detected by a diff hunk inside the `aliases:` block of an existing YAML, NOT by a new file.
   - Per-alias IT class addition (e.g., new `AdportTest.java`) is normal for new aliases — owned by `bidder-class-pr-review`.
   - Per-alias entry in `test-application.properties` is mandatory — owned by `pr-triage-java`.

---

## 4. Cross-language hook symmetry (`prior_source_spec`)

The Go-side `pr-triage` skill exposes two prior-spec slots:

- `prior_spec` — same-language Go-prior-spec ↔ Go-PR regression detection
- `prior_source_spec` — cross-language source-language spec ↔ destination-language PR port-fidelity detection (just landed for Go PRs in sibling branch `feat/f5-port-fidelity-hooks`, 1 commit, unpushed at design time)

`pr-triage-java` mirrors this contract symmetrically:

| Slot | Purpose | Path (when persisted) |
|---|---|---|
| `prior_spec` | Same-language Java-prior-spec ↔ Java-PR regression detection | `prebid-server-java/read/specs/{bidder}/latest.yaml` (gitignored; user opts in via `read-bidder-orchestrator --persist`) |
| `prior_source_spec` | Cross-language Go SOURCE spec ↔ Java PR port-fidelity detection | `prebid-server-go/read/specs/{bidder}/latest.yaml` (mirror image: when reviewing a Java PR ported from Go, the SOURCE language is Go) |

Discovery resolution order (first match wins) — identical to the Go side's contract per `prebid-server-go/review/skills/pr-triage/SKILL.md:613-619`:

1. `--prior-spec=` / `--prior-source-spec=` CLI overrides
2. `${PRIOR_SPEC_PATH}` / `${PRIOR_SOURCE_SPEC_PATH}` env vars
3. `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` when `${FULL_LOOP_RUN_ID}` is set (Teal flow hand-off, lang=java for prior_spec, lang=go for prior_source_spec)
4. `prebid-server-{lang}/read/specs/{bidder}/latest.yaml` (persisted user-opt-in location)

Manifest block: `--- PRIOR SOURCE SPEC COMPARISON ---` (emitted only when the source spec resolves). Severity policy mirrors the Go side:

- `info` by default — most port asymmetries are legitimate per Rules 5/9/11/35/38/etc.
- `warn` when the divergence touches a Rule 38 byte-fidelity assertion (e.g., bidder-params JSON formatting) or an R5-strict cross-language equivalence
- `fail` when a dual-spec assertion under `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` declares the divergence as `severity: fail` (the canonical case is aax: Java's bidder-params.json omits `minLength: 1` on `cid`/`crid`)

**Important:** `pr-triage-java` AUTHORS the `--- PRIOR SOURCE SPEC COMPARISON ---` manifest block AND the three downstream reviewer skills CONSUME it in this F4 PR (audit item 25 LANDED — see Step 1g in each downstream SKILL.md). Each skill cross-references prior_source_spec findings against its own PR-derived findings and surfaces port-fidelity divergences at `info` / `warn` / `fail` severity per the shared policy. The Go-side downstream consumption is still pending as of audit time (zero downstream consumers exist per `docs/runs/post-d3.8-remaining-work.md:36`); Java has landed it first via this F4 PR, with the Go side scheduled to follow symmetrically.

---

## 5. Java framework conventions reviewer skills must know

This section enumerates the conventions reviewers need to recognize. The shared `review/skills/shared/framework-utilities-java.md` (LANDED in this PR, step 2, commit `63be93d`) holds the verbatim canonical references; this section is the design-level summary.

### 5.1 Lombok

| Annotation | Usage | Reviewer concern |
|---|---|---|
| `@Value` | Immutable POJOs (ExtImp{X}.java, response DTOs) | DEFAULT for ext-request POJOs; deviation is anti-pattern |
| `@Builder` | Companion to @Value; generates fluent builders | Almost always paired with @Value; helps with Jackson deserialization when default constructor is needed |
| `@Data` | Mutable beans with getters/setters | For Spring `@ConfigurationProperties` classes ONLY (e.g., `{X}BidderConfigurationProperties.java`). Anti-pattern on ext-request POJOs |
| `@Slf4j` | Logger field injection | Adapter classes use this; reviewers verify usage matches log-level conventions |
| `@RequiredArgsConstructor` | Generates constructor from `final` fields | Common in adapter classes — `{X}Bidder` typically declares `@RequiredArgsConstructor` so Spring DI works through final-field injection |
| `@AllArgsConstructor` | Generates constructor from ALL fields | Rare in adapters; more common in DTOs |
| `@NoArgsConstructor` | Generates default constructor | Anti-pattern on adapter classes (breaks immutability); acceptable on DTOs that need Jackson deserialization without `@Builder` |
| `@JsonProperty("name")` | Jackson rename on fields | Common on ExtImp{X} fields when the YAML param name differs from the Java field name (e.g., `param-name` → `paramName`) |

### 5.2 Spring DI

`@Configuration` + `@Bean` + `@ConfigurationProperties` + `@PropertySource` form the bidder's wiring quartet:

```java
@Configuration
@PropertySource(value = "classpath:/bidder-config/{x}.yaml", factory = YamlPropertySourceFactory.class)
public class {X}Configuration {

    private static final String BIDDER_NAME = "{x}";

    @Bean("{x}ConfigurationProperties")
    @ConfigurationProperties("adapters.{x}")
    BidderConfigurationProperties configurationProperties() {
        return new BidderConfigurationProperties();
    }

    @Bean
    BidderDeps {x}BidderDeps(BidderConfigurationProperties {x}ConfigurationProperties,
                             JacksonMapper mapper) {

        return BidderDepsAssembler.forBidder(BIDDER_NAME)
                .withConfig({x}ConfigurationProperties)
                .bidderCreator(config -> new {X}Bidder(config.getEndpoint(), mapper))
                .assemble();
    }
}
```

`forBidder` / `withConfig` / `bidderCreator` / `assemble` is the assembler's complete public surface (`BidderDepsAssembler.java:59,65,70,75` at `e3ffd57`). Earlier revisions of this document showed a `.usersyncerCreator(UsersyncerCreator.create(externalUrl))` link and the `@NotBlank @Value("${external-url}") String externalUrl` parameter that feeds it; `UsersyncerCreator` was deleted upstream in `2880782f` (#4464), and the assembler now derives the `Usersyncer` from the bidder's own YAML `usersync` block (`BidderDepsAssembler.java:127,132-136`). A review skill must flag that chain link as a compile error, not accept it.

Variations:
- **Filename naming.** Upstream uses BOTH `{X}Configuration.java` (e.g., `AaxConfiguration`, `KoblerConfiguration`) AND `{X}BidderConfiguration.java` (e.g., `AdverxoBidderConfiguration`). The bidder-config skill must accept either form; reviewers should NOT flag the choice but MUST flag when the internal `public class` name does not match the filename (checkstyle `OuterTypeFilename` enforces this, but reviewers should pre-flag because the F-new-79 trap shows port-go2java emits this wrong).
- **Constructor argument list of `bidderCreator`.** Varies by adapter — typical args: `config.getEndpoint()` + `mapper`. With currency conversion: `+ currencyConversionService`. With external URL: `+ externalUrl`. With Rule 35 typed config: `config.getEndpoint() + config.getDevEndpoint() + mapper`.
- **`@PropertySource` factory class.** Always `YamlPropertySourceFactory.class`. Hardcoded — checkstyle does not enforce this but a deviation is a YAML-binding bug.

### 5.3 Vert.x (the HTTP layer)

`io.vertx.core.MultiMap` for headers, `io.vertx.core.json.Json` BANNED (checkstyle `BanVertxJsonImport`). The adapter Bidder interface uses `org.prebid.server.bidder.Bidder<BidRequest>` with `makeHttpRequests` / `makeBids`. Reviewers should:
- Flag any `io.vertx.core.json.Json` import — must use `JacksonMapper` (mapper.encodeToBytes / mapper.decodeValue)
- Flag direct `HttpClient` use in adapter code — adapters return `HttpRequest<BidRequest>` builders; the framework executes them

### 5.4 JUnit5 + AssertJ + Mockito

- `org.junit.jupiter.api.Test` (checkstyle BANS the older `org.junit.Test`)
- `org.assertj.core.api.Assertions.assertThat(...)` — chained assertion API
- `org.mockito.Mockito.{when, verify, mock, spy}` — for `JacksonMapper` and `CurrencyConversionService` mocks
- Test method names: camelCase per Java convention (the F-new-60 trap — port-go2java was emitting `scenarioFor_app_simple_banner` snake_case; correct is `scenarioForAppSimpleBanner`)

### 5.5 Jacoco

Upstream asks for **90% coverage on the changed code**, and says so twice: `docs/developers/contributing.md:17` ("All pull requests must have 90% coverage in the changed code. Check the code coverage with your IDE or external tools.") and the PR-template checkbox `.github/pull_request_template.md:34` ("Does your test coverage exceed 90%?").

It is a **human requirement, not a build gate.** Jacoco is wired for measurement only: the parent pom declares exactly two executions, `prepare-agent` and `report` (`extra/pom.xml:325-344`), and the root `pom.xml:516-531` adds only `<configuration>` (a `skip` flag plus package excludes). There is no `check` goal and no `<rules>`/`<limit>` block anywhere, and `.github/workflows/pr-java-ci.yml` runs no coverage step — so coverage cannot fail CI. The contrast is deliberate and visible in the same file: checkstyle DOES bind `<goal>check</goal>` (`extra/pom.xml:302`), which is what a real hard gate looks like in this pom.

Consequences for a review skill: never report coverage as "CI will catch it". The reviewer IS the enforcement — flag a PR that adds a method without a corresponding test, and read the coverage number from a local `mvn` run or an IDE rather than expecting a red check. Per-method coverage is not measured at all (`MethodLength` checkstyle is a separate, unrelated rule).

### 5.6 mvn-checkstyle (canonical ruleset, summarized)

Sourced from upstream `checkstyle.xml` at SHA `a1fe64e123d6` (verified per `prebid-server-java/read/skills/shared/framework-utilities-java.md` §1):

- `LineLength` max=120 (ignores: `package`, `import`, URLs, `@see`, `//`-only comments)
- `FileLength` max=2024 (test files exempt)
- `EmptyLineSeparator` strict on classes/methods, loose between fields
- `ImportOrder`: groups `*` then `java|jakarta`, not ordered within group, separated (blank line between groups), case-sensitive, sortStaticImportsAlphabetically=true, useContainerOrderingForStatic=false
- `IllegalImport`: BANS `autovalue.shaded.com.google`, `org.inferred.freebuilder.shaded.com.google`, `org.apache.commons.lang` (only lang3), `org.junit.Test`
- `IllegalImport id="BanVertxJsonImport"`: BANS `io.vertx.core.json.Json` everywhere except `ObjectMapperProvider.java`
- `UnusedImports processJavadoc=true`
- `AvoidStarImport`, `AvoidStaticImport` (test files exempt)
- `FinalLocalVariable` tokens=VARIABLE_DEF
- `RedundantModifier`, `ModifierOrder`, `NeedBraces`, `LeftCurly`, `RightCurly` (alone for METHOD_DEF)
- `EqualsHashCode`, `MissingOverride`, `StringLiteralEquality`, `SimplifyBooleanExpression`, `SimplifyBooleanReturn`
- `OneStatementPerLine`, `MultipleVariableDeclarations`
- `OuterTypeFilename` — class name must match file name (the F-new-79 trap)
- `OverloadMethodsDeclarationOrder` — grouped overloads
- `RegexpSingleline` no trailing whitespace
- `RegexpMultiline` empty row after class/interface/enum definition required

Reviewers don't need to enforce every rule line-by-line (CI handles that), but they should recognize the common-trap rules (ImportOrder, FinalLocalVariable, BanVertxJson, OuterTypeFilename, LineLength≤120) so they can pre-flag pre-CI.

---

## 6. Activation patterns

Each skill activates when the routing manifest (emitted by `pr-triage-java`) routes ≥1 file to it. Specifically:

- `bidder-class-pr-review` activates when ANY of:
  - `src/main/java/org/prebid/server/bidder/{x}/*.java` is added/modified/removed
  - `src/test/java/org/prebid/server/bidder/{x}/*.java` is added/modified/removed
  - `src/test/java/org/prebid/server/it/{X}Test.java` is added/modified/removed (note: filename is TitleCase per Java identifier rules; per-alias IT classes look like `AdportTest.java` not `adport_test.java`)

- `bidder-config-pr-review` activates when ANY of:
  - `src/main/resources/bidder-config/{x}.yaml` is added/modified/removed
  - `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` is added/modified/removed
  - `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` is added/modified/removed
  - `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` is added/modified/removed

- `bidder-params-java-pr-review` activates when ANY of:
  - `src/main/resources/static/bidder-params/{x}.json` is added/modified/removed
  - `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java` is added/modified/removed (the imp-ext POJO + any helper protos in the same package)
  - `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` is added/modified/removed (the 4-file Rule 36 fixture set)

- `pr-triage-java` always runs first; it is not optional.

The manifest's `--- SKILL ACTIVATION ---` block lists each skill with `yes`/`no` and a 1-line reason, identical in shape to the Go side.

---

## 7. Cross-skill references

When a reviewer skill needs context from a file owned by ANOTHER skill, it READS the file but does NOT create review tasks for it. Mirrors the Go side's "Cross-Skill References (Read-Only)" section in each SKILL.md.

### bidder-class-pr-review reads:
- `bidder-config/{x}.yaml` — to check declared capabilities (banner / video / native — drives test-data expectations); to check `endpoint:` (the adapter's `{x}Bidder.java` constructor receives this resolved); to check aliases (per-alias IT class addition signals new alias)
- `static/bidder-params/{x}.json` — to verify the adapter code references all declared params correctly (the imp-ext mapping in `makeHttpRequests` must align with the schema)
- `proto/openrtb/ext/request/{x}/ExtImp{X}.java` — to verify adapter code uses the correct POJO type and field names
- `it/openrtb2/{x}/test-*.json` — to verify IT class' `@Test` methods reference the fixtures by the canonical 4-file pattern

### bidder-config-pr-review reads:
- `bidder/{x}/{X}Bidder.java` — to verify the `bidderCreator` lambda's constructor arg list matches `{X}Bidder`'s actual constructor signature (the F-new-57 trap: `mapper` vs `BidderConfigurationProperties` mismatch)
- `static/bidder-params/{x}.json` — to verify `bidder-config/{x}.yaml` `meta-info.app-media-types` / `site-media-types` align with what the schema allows
- `test-application.properties` — to verify a new alias has a corresponding `adapters.{parent}.aliases.{alias}.enabled=true` + `.endpoint=...` line

### bidder-params-java-pr-review reads:
- `bidder/{x}/{X}Bidder.java` — to verify the adapter code reads every field declared in `ExtImp{X}.java` (orphaned fields are dead code)
- `bidder/{x}/{X}BidderTest.java` — to verify unit tests cover the param parsing (catches missing test coverage for new schema fields)
- `bidder-config/{x}.yaml` — to verify `endpoint:` template macros (e.g., `{{adUnitId}}`) align with declared params

### pr-triage-java reads (drift comparison):
- `pom.xml` (upstream) — for module version drift
- `checkstyle.xml` (upstream) — for ruleset drift (new rules added → reviewer skills' anti-pattern lists need updating)
- `static/bidder-info-schema.json` (if present in upstream) — for schema drift; otherwise reads the canonical schema from `read-bidder-config/references/schema-fields.md`
- `bidder-config/{x}.yaml` (upstream, when reviewing a PR that doesn't touch it) — for capabilities + alias metadata extraction
- `read/specs/{bidder}/latest.yaml` (both Java and Go locations) — for `prior_spec` + `prior_source_spec` slots

---

## 8. Design questions — resolutions

The following design choices were OPEN at design-doc author time and are RESOLVED in this F4 PR by the shipping SKILL prose:

### Q1: Per-alias IT class ownership when a PR adds an alias

When a new alias lands, the PR typically modifies the parent's `bidder-config/{x}.yaml` (adding under `aliases:`), modifies `test-application.properties` (adding the alias's enabled/endpoint lines), AND adds a new `it/{Alias}Test.java`. Three skills are touched. **Question:** should the alias-only PR type activate ALL THREE skills, or just `bidder-config-pr-review` with the IT class added as a cross-skill cosmetic check? Recommendation (provisional): all three activate, because the IT class has hand-written test scenarios that need review. Go side parallel: alias-only PRs activate only `bidder-info-pr-review` because Go has no per-alias test class to add. Java's structural difference (per-alias IT class is mandatory) demands activating `bidder-class-pr-review` even when only an alias was added.

### Q2: Rule 35 typed-config subclass — which skill owns it?

`{X}BidderConfigurationProperties.java` is a Spring `@ConfigurationProperties`-bound class living in the same package as `{X}Configuration.java`. It's NOT in the bidder package (`bidder/{x}/`), and it IS in the Spring config package (`spring/config/bidder/`). **Locked in this PR**: assigned to **`bidder-config-pr-review`**, because the file's purpose is Spring DI binding, not adapter logic. The bidder-class skill READS it (cross-skill reference) to verify the `{X}Bidder.java` constructor accepts the typed-subclass fields. In current upstream practice (SHA `a1fe64e123d6`) all Rule 35 subclasses are inner `private static class` declarations inside `{X}Configuration.java`; the separate-file form is design-permitted but absent from master.

### Q3: How does pr-triage-java detect "new-adapter" PRs?

In Go, the trigger is `adapters/{bidder}/{bidder}.go` status=added. In Java, the analog is `bidder/{x}/{X}Bidder.java` status=added. Java has multiple "completeness" signals: the unified YAML being added, the Spring `@Configuration` being added, the ExtImp{X}.java being added, the IT class being added, the 4-file fixture set being added, and the `test-application.properties` having a new `adapters.{x}.enabled=true` line. **Locked in this PR** — the strict-form trigger requires ALL FOUR of: `{X}Bidder.java` status=added AND `bidder-config/{x}.yaml` status=added AND `bidder-params/{x}.json` status=added AND `test-application.properties` having a new top-level `adapters.{x}.` entry. This eliminates false-positive new-adapter classifications when an incomplete subset lands. The completeness check (Step 5e) enumerates all 12 expected files (13 when Rule 35 typed-subclass applies); missing ones are reported as `COMPLETENESS: New adapter {x} missing {file_type}`. Confirmed via shipping heuristics in `pr-triage-java/SKILL.md` Step 4 + `references/routing-rules.md` §"New Adapter"; future canary validation may refine.

### Q4: How does pr-triage-java detect "alias-only" PRs?

Go: only `static/bidder-info/{name}.yaml` file(s) changed, AND every changed file's diff contains `aliasOf` on an added (`+`) line. Java: the analog is harder because aliases live INSIDE the parent YAML, so the diff is a hunk addition under `aliases:` inside an existing file. **Locked in this PR** — an "alias-only" PR is one where every changed file is either (a) a `bidder-config/{x}.yaml` whose diff is restricted to an `aliases:`-rooted hunk, (b) `test-application.properties` with only new `adapters.{parent}.aliases.{alias}.*` lines, or (c) a new `it/{Alias}Test.java`. Negative tests: any change in `{X}Bidder.java`, `ExtImp{X}.java`, or the parent's non-alias YAML fields disqualifies the PR from alias-only. Confirmed via shipping heuristics in `pr-triage-java/SKILL.md` Step 4 + `references/routing-rules.md` §"Alias-Only"; future canary validation may refine.

### Q5: Drift checks for the BidderName-equivalent registry

Go has `openrtb_ext/bidders.go` as the canonical BidderName enum + `coreBidderNames` slice — pr-triage checks for drift there. **Java's equivalent location is unclear.** Java's `BidderCatalog` (`src/main/java/org/prebid/server/bidder/BidderCatalog.java`) registers bidders via Spring `@Autowired Map<String, BidderDeps>`, so each `{X}Configuration.java`'s `@Bean BidderDeps {x}BidderDeps(...)` IS the registration. There's no single enum file. The drift check should instead verify:
- `BidderCatalog.java` API surface unchanged (the `bidders()` / `bidderInfoByName(...)` methods that the framework calls)
- `BidderDepsAssembler.java` API unchanged
- The `BidderConfigurationProperties` base class unchanged (subclass-compatibility)

This is more diffuse than Go's single-enum drift. **Open question:** should pr-triage-java enumerate these 3 framework files as one drift check, or treat each as independent? Tentative answer in this session: ONE drift check named `framework-spring-di-drift` covering all 3. Revisit if false-positives.

---

## 9. Sources

- Go-side review skills as reference: `prebid-server-go/review/skills/{pr-triage,adapter-code-pr-review,bidder-info-pr-review,bidder-params-pr-review}/SKILL.md`
- Java read skills (vocabulary + file layout): `prebid-server-java/read/skills/{read-bidder-orchestrator,read-bidder-class,read-bidder-config,read-bidder-params-java}/SKILL.md`
- Java framework utilities (read-side companion): `prebid-server-java/read/skills/shared/framework-utilities-java.md`
- Java upstream codebase (verified at SHA `a1fe64e123d6`): `prebid/prebid-server-java`
- D2.8 cross-canary findings (template defects the Java review skills should detect): `docs/runs/d2.8-cross-canary-summary.md` (F-new-50 family, F-new-56/57/58/59/60/61/79/86/90/96)
- Audit doc: `docs/runs/post-d3.8-remaining-work.md` § Phase F4
- Port-translation rules (Rule 33 alias inversion, Rule 35 typed-config subclass, Rule 36 4-file IT fixtures, Rule 38 byte-fidelity): `prebid-server-go/read/skills/shared/port-translation-rules.yaml`
