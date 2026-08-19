# Java artifact shapes (port-go2java emission contract)

Phase D1.3 deliverable — captures the exact shape Java artifacts must take so that `port-go2java`'s Step 5 emission produces files indistinguishable from upstream-merged hand-authored Java code, and so the emission passes upstream `prebid-server-java`'s CI gates without operator hand-edits.

## 1. Source-of-truth pinning

Templates in `../templates/*.j2` are derived from real merged PRs in `prebid/prebid-server-java`, NOT synthesized ideals. The pinned reference: upstream master at SHA `a1fe64e123d6` (verified 2026-05-04 per [`../../../docs/methodology/repo-rules.md`](../../../docs/methodology/repo-rules.md)).

When upstream conventions shift (e.g., a checkstyle rule changes), the templates regenerate AND `repo-rules.md`'s "Last verified" cell bumps in the same PR. Sync drift surfaces via [`scripts/sync-from-upstream.py`](../../../scripts/sync-from-upstream.py).

## 2. License headers

`prebid/prebid-server-java` does NOT use per-file license headers. Repository-level LICENSE.md (Apache 2.0) covers all files. Templates emit:

- NO `/* Copyright ... */` header at file top
- NO `/* SPDX-License-Identifier: ... */` directive
- The first non-blank line is the `package ...` declaration

If upstream begins requiring per-file headers, regenerate templates and bump the SHA pin.

## 3. Package declarations

Per the upstream-CI audit, every Java file under `src/main/java/org/prebid/server/bidder/{bidder}/` declares:

```java
package org.prebid.server.bidder.{bidder};
```

Where `{bidder}` is the lowercase Java YAML name (per `scripts/lib/port_engine.normalize_bidder_name`). NOT the brand-cased class name root.

Cross-package POJO files at `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/`:

```java
package org.prebid.server.proto.openrtb.ext.request.{bidder};
```

Spring-config files at `src/main/java/org/prebid/server/spring/config/bidder/`:

```java
package org.prebid.server.spring.config.bidder;
```

(NOT under a `{bidder}` sub-package — Spring config files live in a flat directory.)

## 4. Import order (checkstyle ImportOrder)

> **Corrected (F-new-111).** This section previously showed the groups INVERTED, with `java.*` first. `java.*` goes LAST. The templates already emitted the correct order, so an operator hand-filling from this doc would have produced a checkstyle failure the templates do not.

The enforcing configuration is `checkstyle.xml:77-85` in prebid-server-java:

```xml
<module name="ImportOrder">
    <property name="option" value="bottom"/>
    <property name="groups" value="*,/^java|^jakarta/"/>
    <property name="ordered" value="false"/>
    <property name="separated" value="true"/>
    <property name="caseSensitive" value="true"/>
</module>
```

Group 1: everything else — third-party and project-own (`com.*`, `io.*`, `lombok.*`, `org.*`), plus `javax.*`, which the group-2 regex does not match.
Group 2: `java.*` and `jakarta.*`, LAST.

```java
import com.fasterxml.jackson.core.JsonProcessingException;
import com.iab.openrtb.request.BidRequest;
import com.iab.openrtb.response.BidResponse;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Value;
import org.prebid.server.bidder.Bidder;
import org.prebid.server.bidder.model.BidderBid;

import java.util.List;
import java.util.Map;
import java.util.Objects;
```

`separated="true"` makes the single blank line between groups mandatory. `ordered="false"` means alphabetical order WITHIN a group is convention, not enforcement — the templates emit it anyway, and matching it keeps a diff against a sibling adapter readable.

`option="bottom"` places static imports below the regular groups, separated by one blank line. Most main-source adapters use none; test classes routinely do (`org.assertj.core.api.Assertions.*`, fixture helpers).

**Banned**: `io.vertx.core.json.Json` (per upstream checkstyle ban-list; use `org.prebid.server.json.JacksonMapper` instead). Templates MUST NOT emit this import.

## 5. EmptyLineSeparator (checkstyle)

Exactly one blank line between:

- Top of class body and first member declaration.
- Member declarations (field-to-field, field-to-method, method-to-method).
- Inner class definitions.
- Method body and the closing brace? — NO. Method body's last statement IS adjacent to the closing brace; no blank line.

Multi-line method signatures wrap at 120 chars. The continuation indent is **8 spaces**, NOT 4 (matches upstream convention).

## 6. LineLength ≤ 120

Hard cap. Long lines wrap at:

- Method-call chains: break before `.`
- Generic type parameters: break before the `<`
- Constructor parameter lists: break after the `(`, one parameter per line, closing `)` on its own line aligned with the opening line
- String concatenation: prefer `String.format(...)` over `+` chains for >2 components

## 7. Lombok annotation order

Class-level annotations stack in this order (top to bottom):

```java
@AllArgsConstructor
@Value(staticConstructor = "of")
@Builder(toBuilder = true)
public class {Name} {
    @JsonProperty("paramName")
    String fieldName;
    ...
}
```

Field-level: `@JsonProperty` precedes any visibility modifier. Most fields are package-private (no explicit modifier).

## 8. ExtImp{Bidder}.java POJO shape

Cross-package: lives in `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java` (NOT under the bidder package). Builder + Value + JsonProperty annotations. The Go-side `openrtb_ext/imp_{bidder}.go` is the source of truth; this template translates Go struct fields with `json:"X"` tags to Java fields with `@JsonProperty("X")` annotations.

## 9. {Bidder}Configuration.java shape

The Spring-config class lives at `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}Configuration.java`. Two accepted forms (per Java edge case #19 — both equally valid upstream):

- **Plain `Configuration` form** (Kobler-style): `public class {Bidder}Configuration` extending the standard pattern.
- **`BidderConfiguration` form** (Adverxo-style): `public class {Bidder}BidderConfiguration` — used when the bidder has typed configuration properties (Rule 35 subclass).

Templates emit the form that matches the source spec's `cross_language.java_artifacts.config_class` field (when present, populated by Phase E read skills).

## 10. test-application.properties insertion shape

The IT-test resource file at `src/test/resources/org/prebid/server/it/test-application.properties` carries two lines per bidder. The port skill INSERTS exactly two lines (per upstream convention):

```properties
adapters.{bidder}.enabled=true
adapters.{bidder}.endpoint=http://localhost:8090/{bidder}-exchange
```

Where `{bidder}` is the lowercase Java YAML name. The insertion point is the END OF THE CONTIGUOUS `adapters.*` BLOCK, not the end of the file (F-new-110). At `e3ffd57db` that block is lines 1-707 and the file's remaining 61 lines carry non-adapter settings (`http-client.*`, `auction.*`, … `ccpa.enforce`), so an EOF append lands the entry outside the block. No alphabetical sort within the block — entries land in the order they were added.

DO NOT rewrite the file or move existing entries; that conflicts with concurrent ports. See [`registration-rules.md`](registration-rules.md) for the full rule.

## 11. Bidder-config YAML emission rules

`src/main/resources/bidder-config/{bidder}.yaml` carries the unified shape (per ADR-001 Java edge case):

```yaml
adapters:
  {bidder}:
    endpoint: <URL>
    endpoint-compression: gzip           # when the source declares it
    ortb-version: "2.6"                  # when the source speaks anything but the adapter-default 2.5
    modifying-vast-xml-allowed: false    # Rule 49: ALWAYS declared, source-effective value, both polarities
    geoscope: [<region>, ...]
    aliases:
      {alias}: ~                         # or per-alias overrides per Rule 33 alias-graph-invert
    usersync:
      ...
    meta-info:
      maintainer-email: <email>
      site-media-types: [banner, video, native]
      app-media-types: [banner, video, native]
      vendor-id: <int>
```

> **Corrected (F-new-112).** This example previously showed three keys that do not exist in the live binding. Measured at `e3ffd57db` across the 255 files in `src/main/resources/bidder-config/`:
>
> | shown before | files carrying it | live key | files carrying that |
> |---|---|---|---|
> | `gvl-vendor-id:` | 0 | `vendor-id:` (under `meta-info`) | 255 |
> | `user-sync:` | 0 | `usersync:` (one word) | 162 |
> | `yaml-extra-fields:` | 0 | no such parent key — see below | — |
>
> Regenerate the figures with `git grep -l <key> -- src/main/resources/bidder-config | wc -l`; 162 carry `usersync:` at that pin, and the two spellings never coexist. A key that does not bind is silently ignored at startup, which is the same silent-binding-typo class the bidder-config review skill exists to catch. The templates already emitted `vendor-id` and `usersync` correctly, so the exposure was to an operator hand-filling from this doc.
>
> `yaml-extra-fields` was a spec field name (`bidder_info.yaml_extra_fields`) transcribed as if it were a YAML key. What the spec records there lands as an ordinary adapter-level key: kobler's `dev-endpoint` sits directly under `adapters.kobler`, sibling to `endpoint`, with no wrapper.

Key order is not fixed upstream — kobler puts `dev-endpoint` second and `geoscope` before `meta-info`, vungle puts `aliases` before `modifying-vast-xml-allowed`. Do not treat the order above as a constraint.

**Field-name convention**: kebab-case (NOT camelCase). The Go-side equivalent uses camelCase. The template MUST emit kebab-case regardless of what the source spec recorded. (Source of truth: `bidder_info.yaml_field_name_quirks[]` is informational, NOT the canonical naming for the target language.)

## 12. IT-fixture pair shape (test-resources)

Per Rule 36 reframing (semantic-coverage parity, NOT byte-translation):

`src/test/resources/org/prebid/server/it/openrtb2/{bidder}/`:

- `test-auction-{bidder}-request.json` — pre-bidder request payload
- `test-auction-{bidder}-response.json` — post-bidder response from the auction endpoint
- `test-{bidder}-bid-request.json` — request the Java adapter sends to the bidder
- `test-{bidder}-bid-response.json` — response the bidder returns

Re-authored from Go's flat `adapters/{bidder}/{bidder}test/exemplary/*.json` (one file per call) into Java's IT 4-file split. The port skill computes the structural mapping using the source spec's `tests.fixture_inventory.*` field.

## 13. Pre-emit checklist (D2 acceptance gates)

Before D2 considers an emission complete, every emitted file passes:

1. `mvn -B compile --file extra/pom.xml` exits 0
2. `mvn -B checkstyle:check` exits 0 (covers all rules in this doc)
3. `mvn -B test -Dtest={Bidder}BidderTest` exits 0
4. Jacoco line-coverage on `{Bidder}Bidder.java` ≥ 90% — a local measurement, not a CI verdict. Upstream asks contributors to self-certify this level (`docs/developers/contributing.md:17`; `.github/pull_request_template.md:34`) but wires Jacoco for `prepare-agent` + `report` only (`extra/pom.xml:325-344`), with no `check` goal and no coverage step in `pr-java-ci.yml`.
5. The emitted `bidder-params/{bidder}.json` byte-matches the Go-side source per Rule 38 — its sha256 equals `bidder_params_ref.sha256` and its length equals `bidder_params_ref.bytes` (`scripts/lib/port_engine.materialize_params` verifies both before returning the bytes; re-check the file after writing it)

The skill's Step 6 R5 check at port time runs after these gates pass.

## See also

- [`pr-template-mapping.md`](pr-template-mapping.md) — Java PR-template auto-population (D1.3 sibling).
- [`registration-rules.md`](registration-rules.md) — alphabetical insertion rules across `bidder-config/`, `pull_request_template.md`, etc.
- [`../../prebid-server-java/read/skills/shared/framework-utilities-java.md`](../../../prebid-server-java/read/skills/shared/framework-utilities-java.md) — `BidderUtil`, `BidderDeps`, `JacksonMapper`, `CurrencyConversionService`, `HttpUtil.headers()`. Templates call these utilities; this doc documents what they do.
- Upstream porting guide: [`prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md`](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md) — version-pinned via PR #3768.
