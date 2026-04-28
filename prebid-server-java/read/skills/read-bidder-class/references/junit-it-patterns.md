# JUnit + Integration-Test Patterns (Java)

Detail-heavy reference for Java-side test inventory. Consumed by [SKILL.md](../SKILL.md) Steps 10–12 (`tests:` block — unit tests, IT class, IT fixtures, per-alias IT classes, registry append count). Cross-language schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md#tests](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md#tests).

This file documents:

1. Unit-test class detection + `@Test` method counting.
2. The 4-file Wiremock IT fixture pattern + filename role classification.
3. The 6-file pattern (with cache flow) + multi-folder pattern.
4. Per-alias IT class detection (Adverxo's three-IT-class pattern).
5. Central `test-application.properties` registry append count.
6. Folder naming canonicalization (`canonical, suffix-augmented, multi-folder, custom`).

---

## Unit-test class

### File location

The bidder unit-test class lives at:

```
src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java
```

The folder mirrors the production folder (`src/main/java/org/prebid/server/bidder/{xyz}/`). The class name is always `<Name>BidderTest` matching the production class with a `Test` suffix.

### Class declaration

The canonical test class extends `VertxTest`:

```java
package org.prebid.server.bidder.kobler;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.prebid.server.VertxTest;

public class KoblerBidderTest extends VertxTest {

    private KoblerBidder target;

    @BeforeEach
    public void setUp() {
        target = new KoblerBidder("https://endpoint", "https://dev", currencyConversionService, jacksonMapper);
    }

    @Test
    public void creationShouldFailOnInvalidEndpointUrl() { /* ... */ }

    @Test
    public void makeHttpRequestsShouldConvertBidFloorCurrency() { /* ... */ }
}
```

### Detection rules

| Spec field | Source | Notes |
|---|---|---|
| `tests.test_root_directory` | The bidder unit-test directory: `src/test/java/org/prebid/server/bidder/{xyz}/`. | Always set this exact path on Java specs. |
| `tests.uses_canonical_harness` | `true` if the test class `extends VertxTest`. | `VertxTest` is the Java equivalent of Go's `RunJSONBidderTest` — it provides `jacksonMapper`, time/clock helpers, and the standard test fixtures. |
| `tests.unit_test_methods_count` | Count of `@Test`-annotated methods. | Use regex `^\s*@Test\b` on the file. Multiline `@Test` annotations (`@Test\n(timeout = ...)`) are rare; the regex still matches. |
| `tests.unit_test_loc` | Total line count of the test file. | Including blank lines and the final newline. |
| `tests.hand_written_test_methods[]` | List of method names in declaration order. | Extract the method name following each `@Test` annotation. |

### `@Test` method counting

Regex pattern (one per line):

```
^\s*@Test\b
```

This catches:

- `@Test` alone.
- `@Test(expected = ...)` (JUnit 4-style — rare on PBS-Java).
- `@Test\n(timeout = ...)` — JUnit 5-style multiline.

It deliberately misses any `@Test` that is COMMENTED OUT (the regex requires `@Test` at line start with optional indentation; comment-prefixed lines fail).

### Method-name extraction

For each matched `@Test` line, the next non-blank line is the method declaration. The method name is between `public void` (or `void`) and the opening paren `(`:

```java
@Test
public void makeHttpRequestsShouldConvertBidFloorCurrency() { ... }
```

Extracts: `makeHttpRequestsShouldConvertBidFloorCurrency`.

### Naming convention

Canonical method names follow the pattern: `<methodUnderTest>Should<ExpectedBehavior>WhenCondition`. Examples (from Kobler):

- `creationShouldFailOnInvalidEndpointUrl`
- `makeHttpRequestsShouldReturnErrorIfNoValidImps`
- `makeHttpRequestsShouldConvertBidFloorCurrency`
- `makeHttpRequestsShouldUseDevEndpointWhenTestModeEnabled`
- `makeBidsShouldReturnEmptyListWhenSeatbidIsEmpty`
- `makeBidsShouldDefaultToBannerWhenPrebidTypeIsMissing`

Record verbatim. Do NOT normalize. The Kobler golden lists 14 methods (see [../../../test-fixtures/kobler.golden.spec.yaml](../../../test-fixtures/kobler.golden.spec.yaml) lines 226–240).

### When the test class does NOT extend `VertxTest`

Set `tests.uses_canonical_harness: false` and emit a quirk:

```yaml
quirks:
  - id: legacy-test-helpers-imported
    file: src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java
    summary: "Test class does not extend VertxTest; uses bespoke setup. Should migrate to VertxTest pattern."
    edge_case_taxon: legacy-test-helpers-imported
```

Plus a `provenance.warnings` entry (Validation Rule R10).

---

## Integration-test class

### File location

```
src/test/java/org/prebid/server/it/{Xyz}Test.java
```

The IT class name is `<Name>Test` (NO `Bidder` suffix; the IT class lives in the framework's `it` package, not in the bidder's package).

### Class declaration

```java
package org.prebid.server.it;

import org.junit.jupiter.api.Test;
import org.springframework.test.context.TestPropertySource;

@TestPropertySource(locations = {"classpath:/test-application.properties"})
public class KoblerTest extends IntegrationTest {

    @Test
    public void openrtb2AuctionShouldRespondWithBidsFromKobler() throws IOException, JSONException {
        WIRE_MOCK_RULE.stubFor(post(urlPathEqualTo("/kobler-exchange"))
                .willReturn(aResponse().withBody(jsonFrom("openrtb2/kobler/test-kobler-bid-response.json"))));

        final Response response = responseFor("openrtb2/kobler/test-auction-kobler-request.json", Endpoint.openrtb2_auction);

        assertJsonEquals("openrtb2/kobler/test-auction-kobler-response.json", response, singletonList(KOBLER));
    }
}
```

### Detection rules

| Spec field | Source | Notes |
|---|---|---|
| `tests.integration_test_class` | The class identifier (e.g., `KoblerTest`). | Single class for non-aliased adapters; multiple per-alias classes for aliased adapters (see [Per-alias IT class set](#per-alias-it-class-set-edge-case-24)). |
| `tests.integration_test_pattern` | One of: `4-file-split, 6-file-with-cache, multi-folder, none`. | Determined by the fixture inventory under `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/`. |
| `tests.java_it_folder_naming` | One of: `canonical, suffix-augmented, multi-folder, custom`. | See [Folder naming canonicalization](#folder-naming-canonicalization). |

When the bidder ships NO integration test (rare; flagged as a gap), set `tests.integration_test_class: null` and `tests.integration_test_pattern: none`. Emit a quirk with `edge_case_taxon: incomplete-classification`.

---

## The 4-file Wiremock IT fixture pattern (edge case #23)

Each integration-test case emits exactly 4 JSON files under `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/`:

| Filename pattern | `role` | Purpose |
|---|---|---|
| `test-{xyz}-bid-request.json` | `bidder-bid-request` | Outbound: the bid request the adapter sends to the bidder's endpoint. The Wiremock stub matches against this. |
| `test-{xyz}-bid-response.json` | `bidder-bid-response` | Inbound: the mock response Wiremock returns to the adapter. |
| `test-auction-{name}-request.json` | `auction-request` | Inbound: the auction request the test client sends to PBS. |
| `test-auction-{name}-response.json` | `auction-response` | Outbound: the auction response PBS returns to the test client. |

`{xyz}` is the bidder name; `{name}` is the test scenario name (often equal to `{xyz}` for a single-scenario IT, but may differ for multi-scenario tests like `kobler` vs `kobler-banner`).

### Detection rules

For each fixture file in `inputs.files.integration_test_fixtures`:

1. Compute SHA-256 and byte length.
2. Match against the four filename patterns above.
3. Record `{ filename, sha256, bytes, role }` under `tests.fixture_inventory.integration[]`.

A complete 4-file set has exactly one of each role. When a set is incomplete (e.g., missing `auction-response`), set `tests.integration_test_pattern: custom` and emit a quirk.

### Worked example — Kobler 4-file set

The Kobler IT folder `src/test/resources/org/prebid/server/it/openrtb2/kobler/` contains:

```
test-kobler-bid-request.json     → role: bidder-bid-request
test-kobler-bid-response.json    → role: bidder-bid-response
test-auction-kobler-request.json → role: auction-request
test-auction-kobler-response.json → role: auction-response
```

Spec emits (matches Kobler golden lines 205–222):

```yaml
fixture_inventory:
  integration:
    - filename: test-kobler-bid-request.json
      sha256: 3a0362a7779539d2d9a3eddf7956e69a4d6a496f7d907b7bec723194a4f05dcb
      bytes: 879
      role: bidder-bid-request
    - filename: test-kobler-bid-response.json
      sha256: 9508a94e9a2286f4f11577436b9c4c28271670a87965a2dd034ab44f20463155
      bytes: 353
      role: bidder-bid-response
    - filename: test-auction-kobler-request.json
      sha256: ac6aadb9500f6e6b05d70dc1217c20c818d2ec5cebd8d644e4990833e4028fcf
      bytes: 282
      role: auction-request
    - filename: test-auction-kobler-response.json
      sha256: e55ff8dbde6b5d60a137b28c9b958ccfc280b6c469c724cc9f99835f56bc4e4f
      bytes: 821
      role: auction-response
```

---

## The 6-file pattern (with cache flow)

Some adapters add 2 additional fixture files for cache-flow testing:

```
test-cache-{xyz}-request.json    → role: cache-request
test-cache-{xyz}-response.json   → role: cache-response
```

When the IT folder has 6 files matching the 4 standard + 2 cache patterns, set `tests.integration_test_pattern: 6-file-with-cache`. Record all 6 in `fixture_inventory.integration[]`. The cache-* roles are extensions; record them with the appropriate `role` value.

---

## Multi-folder pattern (Rubicon)

Rubicon-style adapters split fixtures into multiple sibling folders for different test flows:

```
src/test/resources/org/prebid/server/it/openrtb2/rubicon/auction/
src/test/resources/org/prebid/server/it/openrtb2/rubicon/amp/
src/test/resources/org/prebid/server/it/openrtb2/rubicon/video/
```

Set `tests.integration_test_pattern: multi-folder` and `tests.java_it_folder_naming: multi-folder`. Record fixtures from all subfolders, each with its parent folder noted (e.g., `auction/test-rubicon-bid-request.json`).

---

## Per-alias IT class set (edge case #24)

When the parent's YAML declares aliases, EACH alias requires its own IT class + 4-file fixture set. The Adverxo adapter is the canonical multi-alias example:

```
src/test/java/org/prebid/server/it/AdverxoTest.java
src/test/java/org/prebid/server/it/AdportTest.java
src/test/java/org/prebid/server/it/BidsmindTest.java
src/test/java/org/prebid/server/it/MobuppsTest.java
```

Each alias has its own IT class AND its own fixture folder:

```
src/test/resources/org/prebid/server/it/openrtb2/adverxo/test-adverxo-bid-request.json (etc.)
src/test/resources/org/prebid/server/it/openrtb2/adport/test-adport-bid-request.json (etc.)
src/test/resources/org/prebid/server/it/openrtb2/bidsmind/test-bidsmind-bid-request.json (etc.)
src/test/resources/org/prebid/server/it/openrtb2/mobupps/test-mobupps-bid-request.json (etc.)
```

### Detection rules

When `inputs.parent_aliases` is non-empty:

1. For each alias name, locate `src/test/java/org/prebid/server/it/{Name}Test.java`.
2. For each alias, locate `src/test/resources/org/prebid/server/it/openrtb2/{name}/`.
3. Populate `aliases[].test_assets`:

```yaml
aliases:
  - name: adport
    test_assets:
      it_class: AdportTest
      fixture_dir: src/test/resources/org/prebid/server/it/openrtb2/adport/
      fixture_file_count: 4
  - name: bidsmind
    test_assets:
      it_class: BidsmindTest
      fixture_dir: src/test/resources/org/prebid/server/it/openrtb2/bidsmind/
      fixture_file_count: 4
  - name: mobupps
    test_assets:
      it_class: MobuppsTest
      fixture_dir: src/test/resources/org/prebid/server/it/openrtb2/mobupps/
      fixture_file_count: 4
```

When an alias is missing its IT class OR fixture folder, emit a quirk with `edge_case_taxon: incomplete-classification` and a free-text summary.

### Identifier-rule workaround (edge case #26)

For aliases with digit-leading or dot-containing names, the IT class name uses an identifier-rule workaround:

| YAML name | IT class name | Workaround |
|---|---|---|
| `152media` | `OneFiveTwoMediaTest` | Java identifiers cannot start with a digit; spell it out. |
| `360playvid` | `ThreeSixtyPlayvidTest` (if a Java class were needed; in practice 360playvid is YAML-only — see Pattern Index `digit-leading-bidder-name-as-yaml-only`) | Same. |
| `AdTarget.org` | `AdTargetOrgTest` (dot stripped) | Java identifiers cannot contain dots; strip them. |

Detection: when `aliases[].test_assets.it_class` does NOT match TitleCase(yaml_name), set (under top-level `code_naming:`):

- `code_naming.yaml_name: <verbatim>`
- `code_naming.class_name_root: <derived>`
- `code_naming.identifier_workaround: digit-leading-rename`

Plus a quirk with `edge_case_taxon: identifier-rule-workaround`.

### TitleCase brand-acronym preservation (edge case #27)

When the bidder's class name preserves brand acronym casing, set (under top-level `code_naming:`):

- `code_naming.preserves_acronym_case: true`

Examples:

| YAML name | Class name | Acronym preserved |
|---|---|---|
| `elementaltv` | `ElementalTV` (NOT `ElementalTv`) | TV |
| `feedad` | `FeedAd` (NOT `Feedad` or `FeedAD`) | Ad as a brand-suffix |
| `bidtheatre` | `BidTheatre` | n/a — example for naming convention |

Emit a quirk with `edge_case_taxon: acronym-case-preservation` only when the casing diverges from a strict TitleCase normalization.

---

## Folder naming canonicalization

`tests.java_it_folder_naming`:

| Value | Folder path | Example |
|---|---|---|
| `canonical` | `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/` with 4-file split. | Kobler, Optidigital, FeedAd, most Java adapters. |
| `suffix-augmented` | The folder has an extra suffix (rare; e.g., `{xyz}-cache/`). | n/a in current master. |
| `multi-folder` | Multiple sibling folders for different test flows. | Rubicon. |
| `custom` | Anything else. REQUIRES quirk. | rare. |

Detection: the folder path under `src/test/resources/org/prebid/server/it/openrtb2/` should equal `{xyz}/` exactly. Anything else flags non-canonical.

---

## Central `test-application.properties` registry append (edge case #25)

Every Java adapter PR adds 2-4 lines to `src/test/resources/test-application.properties`:

```properties
adapters.{xyz}.enabled=true
adapters.{xyz}.endpoint=http://localhost:8090/{xyz}-exchange
```

Plus per-alias entries when the bidder is a parent:

```properties
adapters.{xyz}.aliases.{name}.enabled=true
adapters.{xyz}.aliases.{name}.endpoint=http://localhost:8090/{name}-exchange
```

### Detection rules

1. Read `src/test/resources/test-application.properties`.
2. Count lines that begin with `adapters.{xyz}.` for THIS bidder (and any parent_aliases).
3. Emit:

```yaml
tests:
  test_application_properties_entries_added: <count>
```

The `tests.test_application_properties_entries_added` form is the canonical spec field used by downstream consumers. Per-alias detail (each appended line as `{ key, value, line }`) lives under `aliases[].test_application_properties_entries[]` and the orchestrator merges from the read-bidder-class fragment.

When the count is zero (gap — bidder added but no IT class), emit a quirk with `edge_case_taxon: incomplete-classification`.

### Worked example — Kobler

For Kobler (no aliases), the registry contains:

```properties
adapters.kobler.enabled=true
adapters.kobler.endpoint=http://localhost:8090/kobler-exchange
```

Count: 2 lines.

(The Kobler golden currently emits `0` because the registry append count is computed by the orchestrator after the read, not by the read-bidder-class skill itself. Skills downstream read this from the orchestrator. The skill SHOULD populate the field when the orchestrator's input includes the properties file content.)

For Adverxo (parent + 3 aliases), the registry contains:

```properties
adapters.adverxo.enabled=true
adapters.adverxo.endpoint=http://localhost:8090/adverxo-exchange
adapters.adverxo.aliases.adport.enabled=true
adapters.adverxo.aliases.adport.endpoint=http://localhost:8090/adport-exchange
adapters.adverxo.aliases.bidsmind.enabled=true
adapters.adverxo.aliases.bidsmind.endpoint=http://localhost:8090/bidsmind-exchange
adapters.adverxo.aliases.mobupps.enabled=true
adapters.adverxo.aliases.mobupps.endpoint=http://localhost:8090/mobupps-exchange
```

Count: 8 lines (2 for parent + 2 per alias × 3 aliases).

---

## Bidder-rename three-step refactor (edge case #33)

When a bidder is renamed (e.g., Adoppler → ElementalTV), the PR contains:

1. DELETE the old YAML: `bidder-config/adoppler.yaml`.
2. CREATE the new YAML: `bidder-config/elementaltv.yaml`.
3. Add `aliases: { adoppler: ~ }` under the new YAML for backward compat.

Plus cascading file moves:

- `src/main/java/org/prebid/server/bidder/adoppler/` → `src/main/java/org/prebid/server/bidder/elementaltv/`.
- `src/main/java/org/prebid/server/spring/config/bidder/AdopplerConfiguration.java` → `ElementalTvConfiguration.java`.
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/adoppler/` → `proto/openrtb/ext/request/elementaltv/`.
- `src/test/java/org/prebid/server/bidder/adoppler/` → `bidder/elementaltv/`.
- `src/test/java/org/prebid/server/it/AdopplerTest.java` → `ElementalTVTest.java`.
- `src/test/resources/org/prebid/server/it/openrtb2/adoppler/` → `openrtb2/elementaltv/`.
- `static/bidder-params/adoppler.json` → `bidder-params/elementaltv.json`.

This is captured at the orchestrator level under `lifecycle.rename.*`. Read-bidder-class detects the absence of the old folder + presence of the new folder + presence of the alias-back tilde syntax in the new YAML, but the synthesis happens in the orchestrator. The skill emits NO quirks for rename — only for genuine gaps (missing IT, missing fixture).

The Pattern Index tag is `bidder-rename-major-version` + `alias-back-via-tilde` + `package-rename-fixture-dir-rename`.

---

## Sources

- Plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md`.
- Schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md) — `tests:` block (lines covering `unit_test_methods_count`, `integration_test_pattern`, `aliases[].test_assets`, etc.).
- Java reference PR list: [../../../../references/new-bid-adapter-prs.md](../../../../references/new-bid-adapter-prs.md) — see Pattern Index tags `alias-coverage-it-classes` (#3705 Adverxo), `digit-leading-bidder-class-workaround-OneFiveTwoMedia` (#3829 152 Media), `bidder-rename-major-version` + `package-rename-fixture-dir-rename` + `acronym-case-preservation` (#4326 ElementalTV).
- Golden spec: [../../../test-fixtures/kobler.golden.spec.yaml](../../../test-fixtures/kobler.golden.spec.yaml) — `tests:` block (lines 195–243), particularly `unit_test_methods_count: 14`, `unit_test_loc: 320`, `hand_written_test_methods` (lines 226–240), `integration_test_class: KoblerTest`, `integration_test_pattern: 4-file-split`, the four `fixture_inventory.integration[]` entries.
- Phase 2 reconnaissance findings (in plan): per-alias IT class requirement observed on Adverxo (`AdportTest.java`+`BidsmindTest.java`+`MobuppsTest.java`); identifier-rule workaround observed on 152media (`OneFiveTwoMediaTest`); TitleCase preservation observed on ElementalTV, FeedAd, BidTheatre.
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
