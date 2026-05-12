# Routing Rules (Java)

File-to-skill mapping rules, unowned file patterns, PR type heuristics, bidder-name extraction, and shared file resolution logic for `prebid-server-java`.

**Upstream source (canonical):** Derived from the activation patterns of:
- `bidder-class-pr-review/SKILL.md`
- `bidder-config-pr-review/SKILL.md`
- `bidder-params-java-pr-review/SKILL.md`

The Java-side analog of `prebid-server-go/review/skills/pr-triage/references/routing-rules.md`. Java's hierarchy is deeper than Go's because Spring DI separates configuration from implementation and IT tests are a first-class surface (per [java-review-skill-design.md §3.2](../../../../../docs/methodology/java-review-skill-design.md)).

> **Sync policy:** When a downstream skill's activation patterns change, this file must be updated to match. The active subset embedded in `pr-triage-java/SKILL.md` Step 3 must stay byte-aligned with this reference.

---

## Module reference & framework anchor

**Current major:** `prebid-server` Maven `<artifactId>` at `3.x` (baseline pinned in `prebid-server-java/read/skills/shared/framework-utilities-java.md`).

For framework-wide concerns (Lombok annotation conventions, Spring DI quartet, JacksonMapper, Vert.x ban-list, checkstyle ruleset, Jacoco coverage gates, JUnit5 + AssertJ conventions, alias inversion semantics, IT test harness contract), see [../../shared/framework-utilities-java.md](../../shared/framework-utilities-java.md). The pr-triage-java drift checks reference this file; downstream reviewer skills read it for anti-pattern catalogs and verbatim policy quotes.

---

## File-to-Skill Routing Table

### bidder-class-pr-review

| Pattern | Example | Notes |
|---------|---------|-------|
| `src/main/java/org/prebid/server/bidder/{x}/*.java` | `…/bidder/aax/AaxBidder.java` | Adapter implementation + helpers (request/response models, custom mappers) co-located in the bidder's package |
| `src/test/java/org/prebid/server/bidder/{x}/*.java` | `…/bidder/aax/AaxBidderTest.java` | Unit tests (JUnit5 + AssertJ; feed Jacoco ≥90% line gate) |
| `src/test/java/org/prebid/server/it/{X}Test.java` | `…/it/AaxTest.java` | The IT test class (`extends IntegrationTest`, WireMock-driven). Per-alias IT classes also land here — Adverxo aliases ship `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java` as TitleCase classroots of the alias name |

### bidder-config-pr-review

| Pattern | Example | Notes |
|---------|---------|-------|
| `src/main/resources/bidder-config/{x}.yaml` | `bidder-config/aax.yaml` | UNIFIED bidder-info + endpoint + aliases + usersync. Aliases live INSIDE the parent (`aliases: { adport: ~ }`), inverted from Go's per-alias `aliasOf:` (port-translation Rule 33) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` | `…/config/bidder/AaxConfiguration.java` | Spring `@Configuration` factory: `@Bean` declaring `BidderConfigurationProperties` + `BidderDeps` via `BidderDepsAssembler` |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` | `…/config/bidder/AdverxoBidderConfiguration.java` | Filename naming is BIMODAL upstream — both `{X}Configuration.java` and `{X}BidderConfiguration.java` are accepted. Reviewers do NOT flag the choice; the `OuterTypeFilename` checkstyle rule enforces internal class name matches filename root |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` | (design-permitted; no upstream example at SHA `a1fe64e123d6`) | The Rule 35 typed-config subclass when shipped as a separate file. Present ONLY when the bidder needs extra YAML fields beyond the framework default (e.g., `dev-endpoint`, `pixel-url`, `region-prefix`). Lombok `@Data`, extends `BidderConfigurationProperties`. In current upstream practice this subclass is always an inner `private static class` declared inside `{X}Configuration.java` (canonical: Kobler, TheTradeDesk, Adnuntius). The separate-file form is reviewer-accepted but unused upstream |

### bidder-params-java-pr-review

| Pattern | Example | Notes |
|---------|---------|-------|
| `src/main/resources/static/bidder-params/{x}.json` | `…/static/bidder-params/aax.json` | The draft-04 JSON Schema for imp.ext params. **Byte-identical to the Go-side `static/bidder-params/{x}.json`** for paired bidders per Rule 38; divergence is a `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` finding |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/ExtImp{X}.java` | `…/ext/request/aax/ExtImpAax.java` | The Lombok `@Value @Builder` POJO matching the JSON schema |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java` (sibling protos) | `…/ext/request/aax/ExtImpAaxBidExt.java` | Helper protos in the same package when the schema has nested objects |
| `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` | `…/it/openrtb2/aax/test-aax-bid-request.json` | The 4-file Rule 36 fixture set per scenario: `test-{name}-{bid-request,bid-response,auction-request,auction-response}.json`. The IT class references these by filename pattern |

### pr-triage-java (shared / multi-bidder files)

| Pattern | Example | Notes |
|---------|---------|-------|
| `src/test/resources/org/prebid/server/it/test-application.properties` | (single file) | The central IT registry. Every new-adapter / new-alias PR appends to it. Java's equivalent of Go's `exchange/adapter_builders.go` + `openrtb_ext/bidders.go` combined. pr-triage-java owns the file because per-bidder line-pair additions span any/all downstream skills |
| `pom.xml` | (single file) | Root project POM; framework-impact (Jacoco config, dependency tree). Drift-tracked |
| `extra/pom.xml` | (single file) | Optional bidder-specific Maven dependencies. Touched on new-adapter PRs that pull non-default JARs |
| `checkstyle.xml` | (single file) | The lint ruleset all bidder Java files cascade through. Drift-tracked; framework-impact file (modifications trigger Step 5h IMPACT warning) |
| `src/main/java/org/prebid/server/bidder/BidderCatalog.java` | (single file) | The Spring DI bidder registry. Drift-tracked |
| `src/main/java/org/prebid/server/spring/config/bidder/util/BidderDepsAssembler.java` | (single file) | The shared DI builder every `{X}Configuration.java` consumes. Drift-tracked |
| `src/main/java/org/prebid/server/spring/config/bidder/model/BidderConfigurationProperties.java` | (single file) | The base class every `{X}BidderConfigurationProperties` subclass extends. Drift-tracked; subclass-compatibility surface |

---

## IT Fixture Directory Conventions

Java's IT test framework (`it/{X}Test.java extends IntegrationTest`) references fixtures from `src/test/resources/org/prebid/server/it/openrtb2/{x}/`. The Rule 36 4-file split per scenario:

| File | Role | Owner |
|------|------|-------|
| `test-{name}-bid-request.json` | Outbound bid-request body sent to the bidder's mocked endpoint | bidder-params-java-pr-review |
| `test-{name}-bid-response.json` | Mocked bidder response (WireMock returns this) | bidder-params-java-pr-review |
| `test-{name}-auction-request.json` | Inbound auction request from upstream client (the PBS entry point) | bidder-params-java-pr-review |
| `test-{name}-auction-response.json` | Final auction response the IT asserts against | bidder-params-java-pr-review |

Some bidders ship multiple scenarios (e.g., `simple-banner`, `simple-video`); each scenario uses the same 4-file shape. The IT class' `@Test` method names typically follow `scenarioFor{Source}{Name}` camelCase (the F-new-60 trap — snake_case test method names violate Java convention).

---

## Shared File Resolution

### `src/test/resources/org/prebid/server/it/test-application.properties`

This file is multi-bidder. Every new-adapter PR and every new-alias PR adds a 2-line pair (or 2-line pair per alias). **pr-triage-java OWNS the file** for routing purposes (categorization bucket `shared:test-application-properties`) and performs the IT-Registry cross-skill check (Step 5i) that validates each added line against a corresponding YAML change. Downstream reviewer skills do NOT create review tasks for lines in this file.

**Per-line context** (informational — pr-triage-java performs the verification; downstream skills consume the IT-Registry findings):

| Diff Content | Associated bidder context |
|-------------|--------------------------|
| `adapters.{x}.enabled=true` (new top-level adapter) | Pairs with `bidder-config/{x}.yaml` addition |
| `adapters.{x}.endpoint=http://localhost:8090/{x}-exchange` | Pairs with adapter implementation; pr-triage verifies the WireMock localhost convention |
| `adapters.{parent}.aliases.{alias}.enabled=true` | Pairs with a parent YAML's `aliases:` block addition and (typically) a new `it/{Alias}Test.java` |
| `adapters.{parent}.aliases.{alias}.endpoint=...` | Same as above |

Mismatches surface as `IT-REGISTRY:` findings in the manifest's cross-skill concerns block. Per-alias IT class additions remain in `bidder-class-pr-review`'s scope (the Java class file is in the bidder-class bucket); the `test-application.properties` line itself is verified by pr-triage-java.

### Framework files (BidderCatalog, BidderDepsAssembler, base BidderConfigurationProperties)

| Diff Content | Owner |
|-------------|-------|
| Changes to `BidderCatalog.java` public API (`bidders()`, `bidderInfoByName(...)`, `nameByAlias(...)`) | `unowned:framework`; pr-triage drift `framework-spring-di` |
| Changes to `BidderDepsAssembler.<T>forBidder(...)` (typed form) or its builder methods (`withConfig`, `usersyncerCreator`, `bidderCreator`, `assemble`) | `unowned:framework`; pr-triage drift `framework-spring-di` |
| Changes to `BidderConfigurationProperties` base class fields | `unowned:framework`; pr-triage drift `bidder-config`; **TRIGGERS schema-migration sub-label** |

Drift output is consumed by downstream skills, NOT routed as a file.

---

## Priority Rules for Overlapping Patterns

Java's deeper package hierarchy makes most patterns disjoint by path. The patterns below could theoretically overlap; the disambiguator is always the **package path**, not the filename.

| File | Winner | Reason |
|------|--------|--------|
| `…/proto/openrtb/ext/request/{x}/ExtImp{X}.java` | **bidder-params-java-pr-review** | Lives in `proto/openrtb/ext/request/{x}/`, NOT in `bidder/{x}/`. Package path is the disambiguator |
| `…/bidder/{x}/{X}Bidder.java` | **bidder-class-pr-review** | Lives in `bidder/{x}/`. Direct match |
| `…/spring/config/bidder/{X}Configuration.java` | **bidder-config-pr-review** | Lives in `spring/config/bidder/`. Direct match |
| `…/spring/config/bidder/{X}BidderConfigurationProperties.java` | **bidder-config-pr-review** | The Rule 35 typed-config subclass lives alongside `{X}Configuration.java`, NOT in `bidder/{x}/`. Per design-doc §8 Q2: bidder-config owns; bidder-class READS cross-skill |
| `src/test/java/org/prebid/server/it/{X}Test.java` | **bidder-class-pr-review** | The IT test class is a Java class with hand-written test logic — functional review territory. NOT bidder-params-java even though it exercises the schema |
| `src/test/resources/.../it/openrtb2/{x}/*.json` | **bidder-params-java-pr-review** | The 4-file fixtures are schema-exercising data payloads — data-shape review territory. NOT bidder-class even though the IT class references them |
| `src/test/java/org/prebid/server/bidder/{x}/{X}BidderTest.java` | **bidder-class-pr-review** | Unit-test source code; sits beside the production class |

The Go-side `params_test.go` exclusion has no Java analog — Java does not have a separate "param-validation test" file; param validation lives in `{X}BidderTest.java` (under bidder-class) and is exercised via JSON-schema-validator at framework load time.

---

## Unowned File Patterns

Files NOT matching any reviewer skill's activation patterns. Grouped by sub-category.

### Framework — Known Impact

| Pattern | Impact Scope | Recommendation |
|---------|-------------|----------------|
| `src/main/java/org/prebid/server/bidder/BidderCatalog.java` | All bidders (lookup, alias resolution) | **Drift-tracked**; framework-impact |
| `src/main/java/org/prebid/server/spring/config/bidder/util/BidderDepsAssembler.java` | All bidders' `@Bean BidderDeps` wiring | **Drift-tracked**; framework-impact |
| `src/main/java/org/prebid/server/spring/config/bidder/model/BidderConfigurationProperties.java` | Base class — every adapter's `@Bean` inherits | **Triggers bidder-config field index DRIFT**; schema-migration sub-label |
| `src/main/java/org/prebid/server/spring/config/bidder/model/*.java` (sibling base classes) | Per-feature base classes (usersync, info) | Schema-migration risk; cross-bidder cascade |
| `src/main/java/org/prebid/server/auction/**` | Auction service (request enrichment, response building) | General exchange logic review; human triage |
| `src/main/java/org/prebid/server/handler/**` | HTTP request handlers (`/openrtb2/auction`, `/cookie_sync`, `/setuid`) | Request-routing review; affects all bidders |
| `src/main/java/org/prebid/server/cache/**` | Prebid Cache integration | Affects all VAST/video bidders |
| `src/main/java/org/prebid/server/currency/**` | `CurrencyConversionService` | Affects bidders that inject this service |
| `src/main/java/org/prebid/server/json/**` | `JacksonMapper` + `ObjectMapperProvider` | All JSON marshal/unmarshal across adapters |
| `src/main/java/org/prebid/server/privacy/**` | GDPR / CCPA / TCF | Affects bidders with privacy concerns |
| `src/main/java/org/prebid/server/gdpr/**` | GDPR enforcement | Affects bidders with GVL IDs |
| `src/test/java/org/prebid/server/it/IntegrationTest.java` | All IT classes extend this | If signature changes, every `{X}Test.java` recompiles |
| `src/main/java/org/prebid/server/proto/openrtb/ext/response/*.java` | Bid-response ext POJOs (`ExtBidResponse`, etc.) | Affects all adapters that emit response ext |
| `checkstyle.xml` | All `*.java` files | **Drift-tracked**; cascading-impact label |
| `pom.xml` | Build, Jacoco gate, dependency tree | **Drift-tracked**; framework-only on major bumps |
| `extra/pom.xml` | Optional bidder dependencies | DEPENDENCY warning on modification |

### Framework — Unknown Impact

Any `.java` file under `src/main/java/org/prebid/server/` not matching the patterns above. Records as `unowned:framework` with `unknown impact` note; recommends human review.

### Documentation

| Pattern | Notes |
|---------|-------|
| `*.md` | README, CONTRIBUTING, etc. |
| `docs/**` | Documentation directory |
| `README*`, `LICENSE`, `NOTICE` | Repo metadata |

### CI/CD

| Pattern | Notes |
|---------|-------|
| `.github/**` | GitHub Actions, workflows |
| `Dockerfile*` | Container configuration |
| `mvnw`, `mvnw.cmd`, `.mvn/**` | Maven wrapper |
| `Jenkinsfile`, `.travis.yml` (legacy) | CI configuration |

### Build/Config

| Pattern | Notes |
|---------|-------|
| `pom.xml`, `extra/pom.xml` | Maven config (see framework-known-impact above) |
| `.gitignore`, `.gitattributes` | Git config |
| `.editorconfig`, `.tool-versions` | Editor / toolchain pins |

### Other

Any file not matching any of the above categories.

---

## PR Type Detection Heuristics

### New Adapter

A PR is classified as `new-adapter` if ALL FOUR of the following are true for at least one bidder (strict form — byte-aligned with `pr-triage-java/SKILL.md` Step 4 rule 2):
1. `src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java` has status `added`
2. `src/main/resources/bidder-config/{x}.yaml` has status `added`
3. `src/main/resources/static/bidder-params/{x}.json` has status `added`
4. `src/test/resources/org/prebid/server/it/test-application.properties` diff contains new top-level `adapters.{x}.enabled=true` and `adapters.{x}.endpoint=...` lines (NOT under an existing parent's `aliases:`)

Rationale (per design-doc §8 Q3 — Locked in this PR): the strict form eliminates false-positive new-adapter classifications when partial subsets land.

Completeness check (Step 5e) enumerates all **12 expected files** per new adapter (13 when Rule 35 typed-subclass ships as a separate file — the design-permitted but upstream-unused form); missing ones are reported as `COMPLETENESS: New adapter {x} missing {file_type}`.

### Alias-Only

A PR is classified as `alias-only` if ALL of the following are true:
1. No `{X}Bidder.java` / `{X}BidderTest.java` is added or modified (only `it/{Alias}Test.java` may be added — the per-alias IT class)
2. No `ExtImp{X}.java`, `bidder-params/{x}.json` is added or modified
3. Every `bidder-config/*.yaml` diff hunk is restricted to an `aliases:` subtree (no changes outside `aliases:`)
4. `test-application.properties` additions are all `adapters.{parent}.aliases.{alias}.*` (no new top-level `adapters.{x}.` entries)

Per design-doc §8 Q1: `bidder-class-pr-review` activates IFF a new `it/{Alias}Test.java` was added — the IT class has hand-written test scenarios that need review even on an alias-only PR.

### Bulk-Mode / Infrastructure

A PR is classified as `infrastructure` if ANY of the following are true:
1. **5+ distinct bidder directories** have files in any single skill's bucket AND the changes follow a repetitive pattern (same file types modified, similar diff hunks)
2. **Framework files constitute >50%** of the total changed files
3. **Total files >50** AND >80% match a single repeated pattern

When `infrastructure` is detected:
- Extract the bulk pattern; identify outliers
- Downstream skills activate in "bulk mode" — pattern consistency check, not per-bidder detailed review

**Sub-labels** (applied on top of `infrastructure`):
- `framework-debt`: triggered by changes to any of the 5 cascading-impact files: `checkstyle.xml`, `BidderCatalog.java`, `BidderDepsAssembler.java`, `BidderConfigurationProperties.java` (base class), or `src/test/java/org/prebid/server/it/IntegrationTest.java` (the IT-base class). Byte-aligned with `pr-triage-java/SKILL.md` Step 4 rule 1 + Step 5h.
- `schema-migration`: triggered when `BidderConfigurationProperties` or sibling base classes under `spring/config/bidder/model/` are modified — all adapters inherit silently; migration coverage check is required

### Adapter Modification

A PR is classified as `adapter-modification` if:
- Files in an existing `bidder/{x}/` directory are modified (not added), OR
- Existing `bidder-config/{x}.yaml` / `{X}Configuration.java` / `bidder-params/{x}.json` / `ExtImp{X}.java` are modified

Only the relevant skills activate based on which files changed.

### Bidder Removal/Disable

A PR is classified as `bidder-removal` if:
- Adapter files are removed, OR
- A `bidder-config/{x}.yaml` diff shows `enabled: false` being added at the top-level adapter key (not under aliases)

### Bidder Rename / Refactor

A PR is classified as `bidder-rename` if:
- Files are deleted from `bidder/{old_x}/` AND added to `bidder/{new_x}/` in the same PR
- AND/OR `bidder-config/{old_x}.yaml` deleted with `bidder-config/{new_x}.yaml` added
- AND/OR a YAML's top-level adapter key is renamed inside an existing file (rare; same-file rename)

Renames are breaking changes typically deferred to the next major release; pr-triage records `RENAME: {old} → {new}` and flags INFO. Mirror Go-side guidance (PR #4456 progx → programmaticX, PR #4639 adoppler → elementaltv).

### Framework-Only

A PR is classified as `framework-only` if:
- All changed files are in `unowned:*` categories
- No reviewer-skill-owned files exist

No downstream reviewer skills activate; pr-triage emits framework-change summary and recommends human review.

### Mixed

A PR is classified as `mixed` if multiple categories above apply (e.g., new adapter + framework change). Each sub-component is handled according to its own type.

### Cross-Cutting Framework Change

A PR is classified with the `framework-debt` sub-label when it modifies `checkstyle.xml`, `BidderCatalog.java`, `BidderDepsAssembler.java`, the IT base class `IntegrationTest.java`, or `BidderConfigurationProperties` base class — files that affect many existing adapters.

When detected:
- Expect wide blast radius (many existing adapters' files may need updating in the same PR)
- pr-triage drift output should be SPECIFIC about what changed (e.g., `DRIFT: checkstyle ruleset — rule property changed: LineLength.max (120 → 140)`), NOT generic `DRIFT: drift detected`
- Java analog of Go-side PR #4592 cascading test-harness change

### Whitelabel-Redirect-Mid-Review (sub-label on `alias-only`)

Applied when final state is `alias-only` AND PR comment history contains:
- Reviewer phrase matching "is this (a )?white.?label" or "looks (very )?similar to" or "this looks like a copy of"
- + author confirmation containing "white label" or "white-label"
- + commit count > 1 (indicates code was changed mid-review, suggesting redirection)

INFORMATIONAL only; pr-triage records `REDIRECT: PR was originally a full adapter, redirected to alias-only after reviewer flagged white-label policy.`

---

## Bidder Name Extraction Rules

| File Pattern | Bidder Name Source |
|-------------|-------------------|
| `src/main/resources/bidder-config/{x}.yaml` | Filename without `.yaml` (lowercase; may have digits like `152media`) |
| `src/main/resources/static/bidder-params/{x}.json` | Filename without `.json` |
| `src/main/java/org/prebid/server/bidder/{x}/...` | First path component after `bidder/` (lowercase) |
| `src/test/java/org/prebid/server/bidder/{x}/...` | First path component after `bidder/` (lowercase) |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/...` | First path component after `request/` (lowercase) |
| `src/test/resources/org/prebid/server/it/openrtb2/{x}/...` | First path component after `openrtb2/` (lowercase) |
| `src/test/java/org/prebid/server/it/{X}Test.java` | TitleCase `X` lowercased via the TitleCase-preservation map (e.g., `AaxTest` → `aax`, `OneFiveTwoMediaTest` → `152media`, `BidTheatreTest` → `bidtheatre`, `TheTradeDeskTest` → `thetradedesk`). When the lowercased form does not match an existing `bidder-config/*.yaml`, this is likely a per-alias IT class — check `aliases:` in candidate parent YAMLs |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` | The leading TitleCase component; strip `Configuration` suffix and lowercase first char (e.g., `AaxConfiguration` → `aax`) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` | Strip `BidderConfiguration` suffix and lowercase first char (e.g., `AdverxoBidderConfiguration` → `adverxo`) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` | Strip `BidderConfigurationProperties` suffix (e.g., `KoblerBidderConfigurationProperties` → `kobler`) |

**Special cases:**

- **camelCase Go yaml_name → Java directory.** Go's `static/bidder-info/adkernelAdn.yaml` ↔ Java's `bidder-config/adkerneladn.yaml` and `bidder/adkerneladn/` (Rule 46: Java lowercases the segment).
- **Multi-word PascalCase class names.** `TheTradeDeskBidder` → bidder = `thetradedesk`. The TitleCase-preservation map (in `prebid-server-java/read/skills/shared/framework-utilities-java.md`) holds the verified mapping for edge cases.
- **Digit-leading bidders.** `33across` → bidder = `33across`. Java class root spells out the digits: `ThreeThreeAcrossBidder.java` / `ThreeThreeAcrossConfiguration.java` may appear; reviewers must use the bidder-config YAML filename as the canonical bidder name.
- **Rebrand aliases.** `cadent_aperture_mx` ↔ `emxdigital` (Rule 43). Same canonical bidder; the YAML filename wins.
- **One-Five-Two style numeric words.** `OneFiveTwoMediaTest.java` → bidder = `152media` (Java IT class identifiers can't start with digits, so the upstream spells out digits in the class root).

---

## Bulk-Mode Exception for Multi-Adapter Alias Bundles

A PR may bundle multiple alias-only changes WITHOUT triggering `infrastructure` / bulk mode IF:

1. ALL changes are `aliases:`-block additions inside ONE `bidder-config/{parent}.yaml` (or aliases bundled across `bidder-config/{parent}.yaml` and a sibling parent's YAML when the bundle reviewer-permits it)
2. ALL alias YAML entries reference the SAME parent
3. Each alias adds only 1–3 lines (the `aliases.{alias}: ~` or `aliases.{alias}: { endpoint: ... }` entry)
4. `test-application.properties` additions are all `adapters.{parent}.aliases.{alias}.*` pairs (2 lines per alias)
5. The only Java files added are per-alias `it/{Alias}Test.java` IT classes (no new `{X}Bidder.java`, no new `ExtImp{X}.java`, no new `bidder-params/{x}.json` — aliases inherit the parent's adapter class)
6. Identical YAML key set across all aliases (no per-alias userSync, no per-alias capabilities overrides, no per-alias gvlVendorID divergence)

**Canonical Java case**: Adverxo with `adport`, `bidsmind`, `mobupps` per-alias IT classes shipped in `bidder-config/adverxo.yaml`'s `aliases:` block. The Java reviewer convention (per pr-triage-java's One-Alias-Per-PR Rule section) treats this as acceptable because Java's nested-alias model means N aliases for the same parent are a single-file YAML diff — low cognitive cost.

OUTSIDE this exception (e.g., aliases for DIFFERENT parents, or aliases bundled with adapter-modification work for the parent), the Go-side `pm-isha-bharti` one-alias-per-PR preference applies; pr-triage records `BULK-PR: {N} alias entries bundled across {N_parents} different parents — reviewer may request split for changelog clarity.` at WARN severity.

The Go-side analog is PR #4651 (5 Limelight aliases). The Java mechanics differ (nested-vs-per-file YAMLs) but the reviewer ergonomics are equivalent.

---

## Whitelabel Policy

`whiteLabelOnly: true` at the adapter top-level of `bidder-config/{parent}.yaml` marks the parent as available only as an alias-parent — but does NOT preclude an `{X}Bidder.java` on the parent. The Java analog of Go's TeqBlaze / SmartHub convention: parents with `whiteLabelOnly: true` AND Java adapter code (the code serves the aliases).

For NEW PRs: when a full adapter is being added that resembles an existing adapter (similar endpoint, comparable params, copy-paste-style `{X}Bidder.java`), reviewers redirect contributor to use `aliases: { newName: ... }` inside an existing parent's YAML. pr-triage's Step 5g flags PRs where:
- Type is `new-adapter`
- AND (PR description / commit messages / discussion mention "white label" / "white-label" / "whitelabel") OR (the new `{X}Bidder.java` is significantly smaller than typical, e.g., < 80 lines, AND closely resembles an existing adapter's structure) OR (the new YAML's `endpoint:` matches an existing adapter's endpoint domain)

Severity: **WARN** with note suggesting alias-only conversion. The white-label workflow lives in `bidder-config-pr-review` skill; this is the cross-skill detection trigger.

For verbatim reviewer quotes and the canonical white-label workflow, see [`../../shared/framework-utilities-java.md`](../../shared/framework-utilities-java.md) §1 (Spring DI conventions, which covers the alias-inversion and white-label inner-class-or-separate-file form), [`../../../../../docs/methodology/java-review-skill-design.md`](../../../../../docs/methodology/java-review-skill-design.md) §3.2 #6 (alias inversion via Rule 33), and [`../../bidder-config-pr-review/SKILL.md`](../../bidder-config-pr-review/SKILL.md) Workflow: White-Label Policy.

---

## Cross-References

- [`../SKILL.md`](../SKILL.md) — the consumer of this routing file (pr-triage-java orchestrator; the embedded routing-table subset in Step 3 must stay byte-aligned with this reference)
- [`../../../../../docs/methodology/java-review-skill-design.md`](../../../../../docs/methodology/java-review-skill-design.md) — design rationale, port-translation rule justifications, open design questions (§8 Q1–Q5)
- [`../../shared/framework-utilities-java.md`](../../shared/framework-utilities-java.md) — Java framework conventions (Lombok, Spring DI, JacksonMapper, checkstyle ruleset, JUnit5 + AssertJ), drift-check baselines, anti-pattern catalog, verbatim policy quotes
- [`../../../../../prebid-server-go/review/skills/pr-triage/references/routing-rules.md`](../../../../../prebid-server-go/review/skills/pr-triage/references/routing-rules.md) — Go-side analog (canonical structural template this file mirrors)
- Port-translation rules: `prebid-server-go/read/skills/shared/port-translation-rules.yaml` (Rule 33 alias inversion, Rule 35 typed-config subclass, Rule 36 4-file IT fixtures, Rule 38 byte-fidelity, Rule 43 rebrand-aliases, Rule 46 camelCase-to-lowercase)
