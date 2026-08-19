# Provenance Warnings (Java)

Schema for `provenance.warnings[]` entries the Java orchestrator emits during read. Each warning is non-blocking (does NOT abort the read) but surfaces in the Markdown summary's "## Provenance" section so reviewers and porters see it.

## Warning entry shape

Every warning is a YAML object with these fields:

```yaml
- type: <warning-type>
  file: <repo-relative-path-or-empty>
  line: <int-or-null>
  summary: <one-line-description>
```

`type` is from the closed registry below. New types REQUIRE a Phase 2 sample (a real prebid-server-java PR demonstrating the issue) and an atomic update to this file plus the canonical schema.

## Common warnings (shared with Go)

These warnings are language-neutral and emitted by both orchestrators:

| Type | When emitted | Example |
|---|---|---|
| `module-major-drift` | Step 3 detects the project version major doesn't match the orchestrator's tested baseline. For Go this checks `go.mod`'s `module github.com/prebid/prebid-server/v4` major. For Java this checks `pom.xml`'s `<version>` major (3.x at v3.41.0). | `pom.xml: <version>4.0.0-SNAPSHOT</version>` against tested baseline `3.x` |
| `alias-resolution-circular` | Step 4 detects an inconsistency: the bidder has its own `bidder/{xyz}/` directory AND a parent declares it as an alias. The standalone implementation wins; the alias entry is dead config. | `kobler` exists at `bidder/kobler/` AND `bidder-config/foo.yaml` declares `aliases: { kobler: ~ }` |
| `bidder-params-sha-conflict` | Step 6 detects that the orchestrator-computed sha256 doesn't match what the reader produced. Indicates a reader bug. | `reader produced 125fef34...; orchestrator computed abc123...` |
| `ref-resolution-failure` | Step 1 cannot resolve `--ref` to a SHA. The read aborts. | `pr=99999 returned 404` |
| `missing-expected-file` | Step 2 cannot find a required file. Severity depends on file: `Bidder.java` missing aborts; `BidderTest.java` missing is just a warning. | `src/test/java/org/prebid/server/it/KoblerTest.java not found` |
| `incomplete-classification` | A reader could not classify a behavioral field with affirmative evidence. Surfaces also as a `quirks` entry. | `make_requests.batching.rules[]` left empty because the reader saw bespoke logic it couldn't categorize |
| `cross-language-byte-divergence` | Step 6 R5 cross-check detects a `bidder_params_ref.sha256` / `bidder_params_ref.bytes` mismatch with the sibling Go-side spec, each side's digest measured by its own reader. Bytes must be byte-identical to satisfy Rule 1 of `port-translation-rules.md`. Paired with quirks taxon of the same name. | `bidder-params/{bidder}.json` differs by whitespace ordering between Go and Java |

## Java-specific warnings

These warnings are specific to the Java suite. They have no Go-side analogs (or the Go analog is a different warning type).

### `pom-version-mismatch`

**When emitted**: Step 3 reads `pom.xml` at the repo root and the project version doesn't match the orchestrator's expected pattern. Specifically:

1. The `<artifactId>prebid-server</artifactId>` parent POM artifact is checked first.
2. Its `<version>` is parsed as `<major>.<minor>.<patch>[-SNAPSHOT]`.
3. Orchestrator's tested baseline is `3.x`. Major drift (`4.x`, `2.x`) emits this warning.

**Example**:
```yaml
- type: pom-version-mismatch
  file: pom.xml
  line: 14
  summary: "Project version 4.0.0-SNAPSHOT differs from orchestrator's tested baseline 3.x. Spec may not capture v4-specific behaviors."
```

**Action for reviewers**: verify the spec format still applies; the orchestrator may need a baseline bump.

### `disabled-bidder-read`

**When emitted**: Step 6 detects `bidder_info.default_enabled == false` (the YAML's `enabled: false` opt-in default — Optidigital, Adverxo aliases, deploy-time-token bidders) AND the user did NOT pass `--allow-disabled`.

**Example**:
```yaml
- type: disabled-bidder-read
  file: src/main/resources/bidder-config/optidigital.yaml
  line: 4
  summary: "Bidder is enabled: false by default. Spec is being produced but the bidder is non-functional in default deployments. Pass --allow-disabled to suppress this warning."
```

**Action for reviewers**: confirm the read was intentional (porters often DO want to read disabled bidders to understand their structure for porting).

### `class-yaml-name-mismatch`

**When emitted**: Step 6 cross-validates class-to-YAML alignment and finds:

1. `XyzConfiguration.java`'s `@PropertySource` path doesn't reference `classpath:/bidder-config/{xyz}.yaml`.
2. `XyzConfiguration.java`'s factory method name doesn't follow the `xyzBidderDeps` convention.
3. `XyzBidder.java`'s class name doesn't match the expected TitleCase derivation from `{xyz}`, AND the discovered name isn't on the acronym-preservation or identifier-rule-workaround allow-lists in `discovery-rules.md`.

**Example (TitleCase preservation, NOT a warning)**:
```yaml
# FeedAd is on the acronym-preservation allow-list — no warning.
```

**Example (actual mismatch, warning emitted)**:
```yaml
- type: class-yaml-name-mismatch
  file: src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java
  line: 28
  summary: "@PropertySource(\"classpath:/bidder-config/koblar.yaml\") does not match expected path classpath:/bidder-config/kobler.yaml. Likely copy-paste artifact (Java analog of Go bidder-constant-mismatch)."
```

**Action for reviewers**: verify the classpath actually resolves; if not, the bidder is silently broken (PBS will fail to bind the configuration).

This is the Java-side analog of Go's `bidder-constant-mismatch` warning. Phase 2 found two real Go-side instances (kobler_test.go BidderKargo, params_test.go BidderKrushmedia); the Java analog catches similar copy-paste artifacts in `@PropertySource` paths and factory method names.

### `yaml-field-name-typo`

**When emitted**: Step 6 detects YAML field names that should follow Java's kebab-case style but use Go's camelCase style instead. The canonical example is the Ogury PR #3788 regression where `endpointCompression` (camelCase, the Go style) was used instead of `endpoint-compression` (kebab-case, the Java style). PBS silently ignores the typo'd field — the gzip compression is NOT applied at runtime, but tests pass.

**Detected fields** (camelCase form → kebab-case form):

| Wrong (camelCase) | Right (kebab-case) | Affects |
|---|---|---|
| `endpointCompression` | `endpoint-compression` | gzip compression of outbound bid requests |
| `modifyingVastXmlAllowed` | `modifying-vast-xml-allowed` | VAST XML modification permission |
| `metaInfo` | `meta-info` | the entire maintainer/capabilities block (severe — breaks the bidder entirely) |
| `mediaTypes` | `media-types` (under `meta-info`) | site/app media type lists |
| `vendorId` | `vendor-id` | GVL vendor ID |
| `geoScope` | `geoscope` | geographic scope (note: NOT kebab-cased, single word) |

**Example**:
```yaml
- type: yaml-field-name-typo
  file: src/main/resources/bidder-config/ogury.yaml
  line: 9
  summary: "YAML field 'endpointCompression' is camelCase (Go style); Java expects kebab-case 'endpoint-compression'. Field is silently ignored by Spring binding — gzip compression NOT applied at runtime. Reference: PR #3788 regression."
```

**Action for reviewers**: this is a SHIPPED-BUT-BROKEN bug indicator. The bidder appears to work but a critical behavior is silently disabled.

### `bidder-constant-mismatch` analog

**When emitted**: Java has no `openrtb_ext.Bidder{Xyz}` constants like Go does. The analog check in Java is whether the configuration class's factory method name matches the bidder name. Specifically:

1. `KoblerConfiguration.java` should declare `@Bean` methods named `koblerBidderDeps`, `koblerConfigurationProperties`.
2. If the method names reference a different bidder (e.g., `koblerBidderDeps()` returns a `KargoBidder` because of copy-paste), it's a copy-paste artifact analogous to Go's `bidder-constant-mismatch`.

**Example**:
```yaml
- type: class-yaml-name-mismatch
  file: src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java
  line: 38
  summary: "Factory method koblerBidderDeps returns new KargoBidder(...) — copy-paste artifact. Bidder will be misregistered."
```

This shares the `class-yaml-name-mismatch` warning type (no separate type — Java's class-naming and YAML-naming are tightly coupled, so any misalignment is the same class of bug).

### `test-application-properties-missing-entries`

**When emitted**: Step 6 reads `src/test/resources/test-application.properties` and counts entries matching `adapters.{xyz}.*`. Every Java adapter PR adds 2-4 lines (typical: `adapters.{xyz}.enabled=true`, `adapters.{xyz}.endpoint=http://localhost:...`, optionally `adapters.{xyz}.modifying-vast-xml-allowed=true`). Zero entries means the registry was not updated, which means integration tests cannot bind the bidder at test time.

**Example**:
```yaml
- type: test-application-properties-missing-entries
  file: src/test/resources/test-application.properties
  line: null
  summary: "No entries matching adapters.kobler.* found in test-application.properties. Expected 2-4 entries (enabled, endpoint, optionally modifying-vast-xml-allowed). Integration tests will not bind the bidder."
```

**Action for reviewers**: verify the PR appended the entries. The orchestrator records `tests.test_application_properties_entries_added: 0` when this fires.

For aliases, the same warning fires when the alias has its own IT class but no alias-specific entries in `test-application.properties` (the IT class will fail to bind).

## Warning emission order

Warnings are emitted in the order Step 6 encounters them:

1. `pom-version-mismatch` (Step 3 detection, recorded but emitted with rest)
2. `missing-expected-file` (Step 2 detections)
3. `disabled-bidder-read` (Step 6, before validation rules)
4. `class-yaml-name-mismatch` (Step 6, R6 + Java extras)
5. `yaml-field-name-typo` (Step 6, R6 extension)
6. `endpoint-placeholder-unresolved` (R8)
7. `legacy-encoding-json-direct-usage` (R9 Java analog — rare)
8. `legacy-test-helpers-imported` (R10 Java analog — when test class doesn't extend `VertxTest`)
9. `test-application-properties-missing-entries` (Step 6, after R-rules)
10. `incomplete-classification` (any reader's classification gap)
11. `bidder-params-sha-conflict` (Step 6 final cross-check)

## Severity (informational, no enforcement)

The orchestrator does NOT classify warnings as error/warn/info levels — every entry in `provenance.warnings[]` is non-blocking. Reviewer skills and humans are responsible for prioritizing. The Markdown summary's "## Provenance" section sorts warnings by emission order so the chronologically-first issue (typically the most foundational) leads.

Hard errors (R1, R2, R3) abort the read and never reach `provenance.warnings`. They surface as a top-level error message and the orchestrator exits with a non-zero status.

## Sources

- Canonical schema: `../../../../../prebid-server-go/read/skills/shared/adapter-spec.md` (Warnings schema section under provenance).
- Behavior taxonomy: `../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md` (`bidder-constant-mismatch`, `yaml-field-name-typo`, `endpoint-compression-typo` taxa).
- Port translation rules: `../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md` (Rule 33 alias inversion, Rule 34 YAML unification, Rule 35 config subclass).
- Java reference list: `../../../references/new-bid-adapter-prs.md` (Ogury PR #3788 endpoint-compression typo regression).
- Sibling Go warnings reference: `../../../../../prebid-server-go/read/skills/read-adapter-orchestrator/references/provenance-warnings.md` (when authored — Go-specific extras: `bidder-constant-mismatch`, `legacy-test-helpers-imported`, etc.).
