---
name: bidder-class-pr-review
description: Reviews changes to Java bidder class code (src/main/java/org/prebid/server/bidder/{x}/*.java), unit tests (src/test/java/org/prebid/server/bidder/{x}/*.java), and IT test classes (src/test/java/org/prebid/server/it/{X}Test.java). USE WHEN a PR touches any of these files. Do NOT use for bidder-config/{x}.yaml, bidder-params/{x}.json, ExtImp{X}.java, Configuration.java, or BidderConfigurationProperties.java — those are owned by sibling skills.
version: 1.0.0
---

# Bidder Class PR Review (Java)

Review pull requests that touch the Java adapter implementation class, its co-located helpers, the bidder-package unit tests, and the IT test class. For every changed method, helper, test, or fixture-wiring line, apply the matching verification workflow to produce actionable review findings.

## Core Principle: Review Only What Changed

**You are a PR reviewer, not a full-file auditor.** The PR diff is your single source of truth. Only create verification tasks for code, tests, or wiring that actually changed in the diff. Code that already exists unchanged in the file was approved in a prior PR and is out of scope.

- **NEVER** review unchanged methods, `@Test` methods, or IT scenarios just because they exist in a file
- **NEVER** audit the entire adapter implementation when only one method changed
- **DO** verify every line that appears as added (`+`) or modified in the diff
- The number of verification tasks should correspond to changed items, not total items in the file

## Activation

This skill activates when a PR adds, modifies, or removes any file matching:

- `src/main/java/org/prebid/server/bidder/{x}/*.java` — adapter implementation + co-located helpers (custom request/response DTOs that live inside the bidder package, util classes like `MediasquareUtil.java`, `KueezExtractor.java`)
- `src/test/java/org/prebid/server/bidder/{x}/*.java` — unit tests (`{X}BidderTest.java` plus any helper test fixtures in the same package)
- `src/test/java/org/prebid/server/it/{X}Test.java` — the IT test class (per-alias IT classes too: `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`)

This skill does **NOT** activate on its own — `pr-triage-java` runs first and routes files via the manifest defined in [`../pr-triage-java/SKILL.md`](../pr-triage-java/SKILL.md) Step 6.

This skill does **NOT** activate for files owned by other skills:

- `src/main/resources/bidder-config/{x}.yaml` — owned by `bidder-config-pr-review`
- `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` (and `{X}BidderConfiguration.java`, `{X}BidderConfigurationProperties.java`) — owned by `bidder-config-pr-review`
- `src/main/resources/static/bidder-params/{x}.json` — owned by `bidder-params-java-pr-review`
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java` (including `ExtImp{X}.java`) — owned by `bidder-params-java-pr-review`
- `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` — owned by `bidder-params-java-pr-review`
- `src/test/resources/org/prebid/server/it/test-application.properties` — owned by `pr-triage-java` (the multi-bidder registry)

**Alias-only PR exception (per design-doc §8 Q1):** When PR type is `alias-only` AND only a per-alias IT class (`it/{Alias}Test.java`) was added — no `bidder/{x}/` files touched — this skill activates **for the IT class only**. The bidder-config sibling owns the parent YAML's `aliases:` block edit.

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model, which can paraphrase source code and lose raw Java syntax. `curl` returns exact, deterministic content. Parse the raw output directly.

### Step 1: Receive Triage Data

This skill receives pre-fetched PR data from the **pr-triage-java** skill. Do NOT re-fetch PR files, drift checks, or CI status.

**1a. Accept the routing manifest.**

The pr-triage-java skill provides:
- The complete file list filtered to files owned by this skill (bidder-package Java files, bidder-package test files, IT class files)
- Each file's `filename`, `status` (added/modified/removed/renamed), and `patch` (diff hunks)
- Drift check results — relevant to this skill: `checkstyle.xml` ruleset drift and `framework-spring-di` API surface drift
- CI status summary (overall + per-check-run conclusions and annotations)
- PR type classification (`new-adapter` / `alias-only` / `adapter-modification` / `bidder-removal` / `bidder-rename` / `infrastructure` / `mixed`)
- Bulk change flag (if applicable)
- PR description analysis (docs PR link, template completeness, feature rationale)
- Commit history (count, messages, head SHA)
- PR comments (reviewer feedback, CI bot reports, author responses) — categorized and summarized
- Duplicate PR search results
- Bidder metadata per bidder: `parent`, `aliases[]`, `whitelabelOnly`, `capabilities` (extracted from PR or `not in PR — downstream must fetch from master`), `endpoint`, `rule_35_typed_config`
- `--- PRIOR AGENT FINDINGS ---` block (when `agent_review: yes` was recorded)
- `--- PRIOR SPEC COMPARISON ---` block (same-language regression detection; opt-in)
- `--- PRIOR SOURCE SPEC COMPARISON ---` block (cross-language port-fidelity detection; opt-in)

**1b. Handle drift warnings.**

If the manifest reports `checkstyle.xml` drift, factor the new/changed rule into the Step 4 verification — specifically the [Checkstyle Pre-Flag](#workflow-checkstyle-pre-flag) workflow. If `framework-spring-di` drift is reported (`BidderCatalog` or `BidderDepsAssembler` API surface changed), include the warning in the Step 5 summary — adapter `bidder.Bidder<T>` constructor signatures may need to align even though the cross-skill concern is in `bidder-config-pr-review`.

**1c. Handle CI status.**

If CI status is `blocked`, acknowledge in the summary and note that review findings are preliminary until CI passes. For a `checkstyle` job failure, harvest the `output.annotations` (`file`:`line` + `message`) — these become high-confidence findings that supplement diff-derived ones. If the failure is in `Build / Test` (the JUnit + Jacoco gate), the affected unit-test or IT changes need extra scrutiny in Step 4.

**1d. Incorporate reviewer feedback.**

Cross-reference reviewer comments from the manifest against your review findings:

- If a reviewer has already flagged an issue you also find, surface it as `Previously flagged by {reviewer}` and reference the comment URL
- If a CI bot report indicates a failure relevant to your scope (`checkstyle`, `Build / Test`), use it as additional evidence for your verification steps
- If the author has responded to reviewer feedback with fixes, check whether the current diff reflects those fixes

**1e. Fetch full file content when verification requires context beyond the diff.**

For files with status `added`, full content is in the patch (every line prefixed with `+`) — do NOT re-fetch. For files with status `modified`, the patch contains only changed regions; fetch the full file only when verification requires it (Java's `OuterTypeFilename` checkstyle rule, full constructor inspection for Lombok-annotation review, or full IT class read-through):

```bash
# Full file for modified bidder code
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/{head_sha}/{filename}"
# Capabilities from master when not in PR (drives test-data and bid-type expectations)
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/main/resources/bidder-config/{x}.yaml"
```

Cache fetched content — do not re-fetch the same file multiple times within a single review.

**1f. Handle bulk change mode.**

If the manifest indicates PR type `infrastructure` and this skill's files are part of the bulk pattern:

- Do NOT create per-bidder item-level tasks
- Instead, create a single "bulk pattern consistency" task:
  - Verify the same change was applied consistently across all affected bidders
  - Flag any bidders that deviate from the pattern (outliers)
  - Focus detailed review only on net-new bidder code that is NOT part of the bulk pattern

Examples that route through bulk mode: a framework-wide `BidderUtil.defaultRequest` signature change cascading into every `{X}Bidder.java`; a checkstyle rule tightening (e.g., `LineLength` 120 → 100) producing identical line-break edits across many adapters.

**1g. Consume `--- PRIOR SOURCE SPEC COMPARISON ---` (cross-language ports).**

When the manifest carries a `--- PRIOR SOURCE SPEC COMPARISON ---` block, this PR is a cross-language port — typically a Go → Java port via `port-go2java`. Each entry is tagged with `info` / `warn` / `fail` severity per pr-triage-java's documented severity policy. Bidder-class-specific worked examples:

| Source spec key | Java emit expectation | Severity if mismatched |
|---|---|---|
| `code.make_requests.endpoint_resolution.kind = template-macro` | Java uses `String.format` / `String.replace` / `URIBuilder` (NOT `text/template`) | `info` — language-idiomatic asymmetry; flag only if neither pattern is present |
| `code.make_requests.mutation.entity_strategies.{Imp,Device,User,Site,App,Cur} ∈ {immutable-rebuild, mutate-in-place}` | Java uses Lombok `toBuilder().build()` for non-passthrough/non-none strategies (Rule 5) | `warn` when an entity flagged `immutable-rebuild` in Go appears mutated via raw setter or copy-and-replace in Java |
| `code.make_bids.http_status_handling.kind = canonical-go-helpers` | Java emits NO explicit status check; framework default handles it (Rule 30) | `warn` when Java declares an explicit `httpCall.getResponse().getStatusCode() == 204` short-circuit beyond `framework-default-plus-empty-seatbid-shortcircuit` |
| `quirks[].id = bid-post-processing-macro` (ADR-007 F4, canonical `thetradedesk`) | Java has an `applyBidPostProcessingMacros(Bid)`-equivalent helper substituting `${AUCTION_PRICE}` into `bid.nurl` / `adm` / `burl` | `warn` when source-spec carries the quirk but Java emit omits the helper |
| `bidder_class.constructor.parameters[].role = helper-collaborator` (`CurrencyConversionService`) | Java constructor accepts `CurrencyConversionService` arg; cross-skill: `bidder-config-pr-review` verifies factory wiring | `info` when Go uses `requestInfo.ConvertCurrency` (function-arg) — legitimate asymmetry per Rule 22 |
| `code.make_bids.bid_type_resolution.method_chain[].method = bid.ext.prebid.type` | Java emit walks `bid.ext → "prebid" → ObjectNode → ExtBidPrebid.type` (canonical Kobler pattern) | `warn` when Java uses a different resolution chain than Go for the same bidder |
| `headers_constructed.language_stamped: true` (ADR-007 F2) | Java emits header with `java_value` (e.g., `freewheelssp` `Componentid: prebid-java`); NOT `prebid-go` | `fail` when Java emits `prebid-go` or omits the header entirely |

Dedupe semantics:

- Surface `warn` / `fail` flags in the Step 5 summary
- Suppress `info` unless the PR diff elevates severity (e.g., introduces NEW divergence not previously captured)
- Net-new findings whose pattern matches an entry in `--- PRIOR SOURCE SPEC COMPARISON ---` are deduped as `Previously flagged by prior_source_spec — confirm with reviewer if intentional` (analogous to the `Previously flagged by {reviewer}` / `Previously flagged by prior agent` patterns)

Downstream consumption mechanics here are symmetric with the Go-side F5 hook at [`prebid-server-go/review/skills/adapter-code-pr-review/SKILL.md` §Step 1g](../../../../prebid-server-go/review/skills/adapter-code-pr-review/SKILL.md). Both sides LANDED — Java in F4 PR #10, Go in F5. The 4-tier severity matrix (info/warn/fail/urgent) + dedup phrase + Step 5 emission template are all canonicalized at [`prebid-server-go/review/skills/shared/framework-utilities.md` §Cross-Language Port-Fidelity Hook Contract](../../../../prebid-server-go/review/skills/shared/framework-utilities.md#cross-language-port-fidelity-hook-contract).

### Step 2: Extract Changes From the Diff

Group changed files by bidder name (extracted from path components per the bidder-name rules in `pr-triage-java` Step 3). For each bidder, identify which file types changed:

- `src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java` — adapter implementation
- `src/main/java/org/prebid/server/bidder/{x}/*.java` (other than `{X}Bidder.java`) — co-located helpers / custom DTOs
- `src/test/java/org/prebid/server/bidder/{x}/{X}BidderTest.java` — unit tests
- `src/test/java/org/prebid/server/bidder/{x}/*.java` (other than `{X}BidderTest.java`) — helper test fixtures
- `src/test/java/org/prebid/server/it/{X}Test.java` — IT test class (parent or per-alias)

For each changed file, parse the diff:

- **Added file** (status `added`) — every method, `@Test`, or wiring line is new and needs review
- **Modified file** (status `modified`) — **ONLY** review the specific methods / `@Test` methods / lines that changed
- **Removed file** (status `removed`) — create a single task to validate the removal is intentional and that consumers (IT class, sibling helpers) are also removed/updated

**Comment-only changes:** If all changed lines are Java comments (`//`, `/* */`) or whitespace with no functional code changes, the file has **zero changed items**. Skip to Step 5 and recommend fast-track approval.

**Rename detection:** When a file has status `renamed`, treat both endpoints — the deleted bidder package and the added bidder package — as one task ("verify rename was consistent: directory, package statement, public class declaration, all callers updated"). Cross-skill: `bidder-config-pr-review` is responsible for the YAML key rename; this skill verifies code-side consistency.

### Step 3: Build Verification Task List

There are two categories of tasks:

**1. PR-level tasks (zero or more):** PR-wide checks that don't map to a specific changed item.

- **Completeness for new adapters**: For PR type `new-adapter`, verify the bidder-class slice of the expected file set is present — `{X}Bidder.java`, `{X}BidderTest.java`, and `{X}Test.java`. The full 10-file completeness check (which spans all 3 reviewer skills) lives in `pr-triage-java` Step 5e; this skill confirms only its own files.
- **Naming consistency**: Bidder slug consistency between directory name (`bidder/{x}/`), `package` statement (`package org.prebid.server.bidder.{x};`), public class declaration (`public class {X}Bidder implements Bidder<...>`), and the IT class' package + `extends IntegrationTest` location. Mismatches are a checkstyle `OuterTypeFilename` failure (the F-new-79 trap) and a cross-skill concern with `bidder-config-pr-review` (the Spring `@PropertySource` path must match the YAML filename).
- **Checkstyle pre-flag**: Mechanical pre-checks per the [Checkstyle Pre-Flag](#workflow-checkstyle-pre-flag) workflow. Pre-CI surfacing reduces reviewer round-trips on the most-common cascade triggers (F-new-58/59 imports, F-new-60 snake_case test names, F-new-79 OuterTypeFilename, `LineLength` > 120, banned `io.vertx.core.json.Json`).
- **Capabilities ↔ MakeBids drift**: Cross-read `bidder-config/{x}.yaml` `meta-info.{app,site,dooh}-media-types` and the adapter's `makeBids` bid-type resolution. Every YAML-declared media type must have a Java return path. The Go-side rule (`YAML capabilities ↔ Go MType drift`) applies symmetrically here.

**2. Item-level tasks (one per changed item):** For each changed method, helper, `@Test`, or IT scenario, look up the matching verification workflow:

For **adapter code changes** (`bidder/{x}/{X}Bidder.java`):
1. Constructor / `Builder` static method changed — use [Constructor / Builder Changed](#workflow-constructor--builder-changed)
2. `makeHttpRequests` changed — use [makeHttpRequests Changed](#workflow-makehttprequests-changed)
3. `makeBids` changed — use [makeBids Changed](#workflow-makebids-changed)
4. Private helper changed (`parseImpExt`, `resolveBidType`, `resolveEndpoint`, `modifyImp`, `bidsFromResponse`, etc.) — use [Private Helper Changed](#workflow-private-helper-changed)
5. Class-level field / `static final` constant changed — use [Adapter Field Changed](#workflow-adapter-field-changed)
6. Lombok annotation added/removed on the class — use [Lombok Annotation Changed](#workflow-lombok-annotation-changed)

For **co-located helper Java files** (`bidder/{x}/*.java` other than `{X}Bidder.java`):
7. Co-located helper file changed — use [Co-Located Helper Changed](#workflow-co-located-helper-changed)

For **unit test changes** (`bidder/{x}/{X}BidderTest.java`):
8. `@Test` method added/modified — use [Unit Test Changed](#workflow-unit-test-changed)
9. `@BeforeEach` / class-level fixture setup changed — use [Unit Test Setup Changed](#workflow-unit-test-setup-changed)

For **IT test class changes** (`it/{X}Test.java`):
10. IT class added or modified — use [IT Class Changed](#workflow-it-class-changed)
11. Per-alias IT class added (empire-parent bidders) — use [Per-Alias IT Class Added](#workflow-per-alias-it-class-added)

**Sanity check:** The number of item-level tasks should correspond to the number of distinct changed items across all files this skill owns. If you have significantly more tasks than changed items, you may be reviewing out-of-scope content. The PR-level tasks do not count toward this check.

### Step 4: Execute Verification Tasks

Work through tasks, parallelizing where possible. For each task:

1. Mark the task `in_progress`
2. Execute every verification step from the matching workflow
3. Record each step's result as PASS, FAIL, or WARN with evidence (file:line and exact snippet)
4. Mark the task `completed` with findings

When a finding overlaps with `--- PRIOR AGENT FINDINGS ---`, `--- PRIOR SPEC COMPARISON ---`, or `--- PRIOR SOURCE SPEC COMPARISON ---` from the manifest, surface it with the appropriate dedup phrase (`Previously flagged by prior agent` / `Previously captured in prior_spec — confirm with reviewer if intentional` / `Previously flagged by prior_source_spec — confirm with reviewer if intentional`). Net-new findings are emitted normally.

### Step 5: Summary

After all tasks are complete, produce a review summary:

- Files changed (with category: added/modified/removed)
- Items changed per file
- Verification steps executed
- Issues found (critical / warning / info)
- Cross-skill concerns surfaced (forwarded to `bidder-config-pr-review` or `bidder-params-java-pr-review` as appropriate)
- Cross-language port-fidelity findings (when `prior_source_spec` was loaded)
- Recommendation: **approve** / **request changes** / **comment**

---

## Verification Workflows

### Workflow: Constructor / Builder Changed

**Triggers when:** The public constructor of `{X}Bidder` is added or modified; OR a `Builder` static method on the class is added or modified.

Java's analog of Go's `Builder` function is the public constructor — Spring DI invokes it through the `bidderCreator` lambda in `{X}Configuration.java`. Reviewer verifications:

1. **Class declaration**: `public class {X}Bidder implements Bidder<BidRequest>` (default) or `Bidder<{CustomRequestType}>` (rare — Mediasquare's `MediasquareRequest`, Huaweiads's `HuaweiAdsRequest`). The custom-type case requires a corresponding `parameterized_request_type` in the read-spec; flag uncommon types as **INFO** for reviewer attention.
2. **Constructor parameter list — cross-skill alignment**: The constructor's parameter order, types, and count MUST match the `bidderCreator(config -> new {X}Bidder(...))` lambda's arg list in `{X}Configuration.java`. Mismatch is the F-new-57 trap (canonical: `mapper` vs `BidderConfigurationProperties` reorder). This is a **cross-skill concern** with `bidder-config-pr-review` — surface as: `CROSS-SKILL: {X}Bidder constructor signature does not match bidderCreator lambda in {X}Configuration.java. F-new-57 trap.`
3. **Endpoint validation**: When a `String endpointUrl` parameter is present, the constructor should call `HttpUtil.validateUrl(endpointUrl)` (the canonical pattern across Kobler, Adverxo, AdkernelAdn). Direct assignment without validation is a **WARN** — fail-fast on bad config is the framework convention. Some adapters wrap with `Objects.requireNonNull(...)` first; both forms are acceptable.
4. **No hardcoded credentials**: Constructor must not embed API keys, passwords, or secrets. Configuration arrives via `String`-typed Spring properties or the typed-config subclass (Rule 35).
5. **`Objects.requireNonNull` on helper collaborators**: Constructor should null-check `JacksonMapper`, `CurrencyConversionService`, `IdGenerator`, `Clock`, and other framework-injected helpers. The Adverxo pattern (raw `this.mapper = mapper;` without null-check) is acceptable in practice but **INFO** — Kobler / AdkernelAdn use `Objects.requireNonNull(mapper)`.
6. **No request-scoped state**: The adapter class instance is a singleton (Spring `@Bean`). Constructor must not store request-specific state. Acceptable fields: `endpointUrl` (String), `devEndpoint` (String, Rule 35), `mapper` (JacksonMapper), `currencyConversionService` (CurrencyConversionService), `templateProcessor`-like immutable helpers. Mutable state (Maps, ArrayLists holding request data, mutable counters) is a **FAIL**.
7. **Field declarations**: All fields backing constructor params should be `private final`. Non-final fields are an immutability anti-pattern and a checkstyle `FinalLocalVariable`-adjacent smell — **WARN**.
8. **Template macros declared as constants**: When the adapter uses endpoint templates (`{{adUnitId}}`, `{{auth}}`, `{{PublisherID}}`), they should be declared as `private static final String` constants (canonical: Adverxo's `ADUNIT_MACROS_ENDPOINT`, AdkernelAdn's `URL_PUBLISHER_ID_MACRO`). Inline string literals in `String.replace(...)` calls are a **WARN**.
9. **Rule 35 typed-config constructor**: When the bidder uses a typed-config subclass (`{X}BidderConfigurationProperties.java` exists), the constructor accepts additional String / primitive args derived from the subclass getters (canonical: Kobler's `String devEndpoint`). Verify these are properly stored as `private final` and used in `makeHttpRequests`. Cross-skill: `bidder-config-pr-review` verifies the YAML binding and `{X}Configuration.java` wires the subclass.
10. **No exported types**: The bidder class itself is the only `public` type in the bidder package. Co-located helpers should be package-private unless they're DTOs the framework reflects on (Jackson can reflect on package-private classes; default to package-private). **WARN** on unjustified public.

### Workflow: makeHttpRequests Changed

**Triggers when:** The `makeHttpRequests` method is added or modified.

1. **Correct signature**: Must be `public Result<List<HttpRequest<BidRequest>>> makeHttpRequests(BidRequest bidRequest)` (or `Result<List<HttpRequest<{CustomType}>>>` matching the class's `Bidder<T>` parameterization). Method MUST be annotated `@Override`.
2. **Imp ext unmarshaling**: Each imp's `imp.ext` is unmarshaled via the canonical two-step:
   - `mapper.mapper().convertValue(imp.getExt(), {X}_EXT_TYPE_REFERENCE).getBidder()` — using a class-level `TypeReference<ExtPrebid<?, ExtImp{X}>>` constant
   - Wrapped in try/catch for `IllegalArgumentException`, re-thrown as `PreBidException`
   - The shared `ExtImp{X}` POJO MUST come from `proto/openrtb/ext/request/{x}/` (owned by `bidder-params-java-pr-review`). Inline imp-ext POJOs defined in the bidder package are a **WARN**.
3. **No `io.vertx.core.json.Json` usage**: Banned by checkstyle `BanVertxJsonImport`. Must use `JacksonMapper` (`mapper.encodeToBytes(...)`, `mapper.decodeValue(...)`, `mapper.mapper().convertValue(...)`). Flag any `io.vertx.core.json.Json` import or call as **FAIL**.
4. **HttpRequest construction**: Each returned `HttpRequest<BidRequest>` must include:
   - `method(HttpMethod.POST)` — typically POST (use the `io.vertx.core.http.HttpMethod` enum, NOT a string literal). When the adapter uses `BidderUtil.defaultRequest(...)`, method/headers/payload are framework-defaulted.
   - `uri(...)` — the resolved endpoint URL (from `this.endpointUrl` after macro substitution, not hardcoded)
   - `body(mapper.encodeToBytes(outgoingRequest))` — marshaled JSON via JacksonMapper, NOT `io.vertx.core.json.Json` and NOT `request.toString()`
   - `headers(headers())` — minimum `HttpUtil.headers()` (which preloads `Content-Type: application/json` + `Accept: application/json`). Adapters that fully replace headers (e.g., custom `MultiMap headers = MultiMap.caseInsensitiveMultiMap();`) MUST add `Content-Type` explicitly; flag omission as **WARN**.
   - `payload(outgoingRequest)` — the canonical pattern when downstream `makeBids` reads `httpCall.getRequest().getPayload()` for context (AdkernelAdn's `extractBids(bidRequest, bidResponse)` relies on this).
5. **Result construction**: Must be `Result.of(httpRequests, errors)` (returning both lists), `Result.withValues(...)` (no errors), or `Result.withErrors(...)` (no values). NEVER `new Result(...)` directly.
6. **Mutation idiom: Lombok `toBuilder()` rebuild**: Mutations to `BidRequest`, `Imp`, `Device`, `User`, `Site`, `App` use the Lombok-generated `toBuilder()` pattern: `imp.toBuilder().bidfloor(x).build()`. NEVER mutate via direct setter — OpenRTB entities from `com.iab.openrtb` are immutable, so this is enforced at compile time; flag any pattern that bypasses immutability as **FAIL**. This is the Java analog of Go's `mutation.entity_strategies.immutable-rebuild` (Rule 5).
7. **Error types**: Use `BidderError.badInput(msg)` for invalid request data (publisher's fault). Use `BidderError.badServerResponse(msg)` ONLY in `makeBids`. `BidderError.generic(msg)` for unknown errors. Errors generated within an impression loop should include the impression ID for log diagnosability — e.g., `"Invalid imp with id=%s. Expected imp.banner or imp.video".formatted(imp.getId())` (canonical AdkernelAdn pattern).
8. **Currency conversion**: When the adapter converts bid floors, use `currencyConversionService.convertCurrency(value, bidRequest, fromCur, toCur)` — Java's 4-arg form (the `bidRequest` arg carries time-context for currency-rate lookup, the canonical cross-language asymmetry vs Go's 3-arg `reqInfo.ConvertCurrency`). Wrap in `BidderUtil.shouldConvertBidFloor(price, DEFAULT_BID_CURRENCY)` to guard against the no-op case (canonical Kobler / Adverxo pattern). Set `DEFAULT_BID_CURRENCY = "USD"` as a class-level constant.
9. **Multi-impression handling**: If the adapter sends one request per impression, verify each request has a correct single-impression slice. If batching (canonical AdkernelAdn `dispatchImpressions` grouping by `pubId`), verify the grouping logic AND that bidder-info `meta-info.app-media-types` / `site-media-types` aligns with what the grouping retains.
10. **Endpoint resolution**: Java's analog of Go's `text/template` is `String.replace(...)` or `String.format(...)` for simple substitutions; `URIBuilder` for query-param construction; a custom resolver class only when complexity demands it. Verify every `{{TOKEN}}` macro in the endpoint URL has a corresponding `.replace("{{TOKEN}}", ...)` call. Unresolved macros leave the literal in the URL at runtime — common port-go2java trap.
11. **No redundant PBS-core checks**: The framework already filters:
    - Empty `imp` list (filtered upstream by `org.prebid.server.auction.requestfactory`)
    - Endpoint emptiness (Spring `@PropertySource` + `@NotBlank` validation at startup)
    - Media-type capability filtering (PBS routes imps to adapters per `bidder-config/{x}.yaml` capabilities; imp.banner/video/native null-checks in the adapter are defensive)
    - Site/App presence filtering (capability-driven)
    Flag re-implementations as **WARN**. Specific-field defensive checks (e.g., requiring `imp.banner.format[0]` for an adapter that needs explicit format dimensions per AdkernelAdn) are valid.
12. **No `System.out.print` / `System.err.print`**: Banned by checkstyle's `RegexpMultiline` rule. Use the framework's `@Slf4j` logger (`log.info(...)`, `log.warn(...)`, `log.error(...)`) if logging is needed at all — but `makeHttpRequests` should rarely log; errors return via `BidderError`.

### Workflow: makeBids Changed

**Triggers when:** The `makeBids` method is added or modified.

1. **Correct signature**: Must be `public Result<List<BidderBid>> makeBids(BidderCall<BidRequest> httpCall, BidRequest bidRequest)`. Method MUST be annotated `@Override`. Note `makeBids` does NOT receive a `requestInfo` arg — currency conversion is available ONLY in `makeHttpRequests` (Java symmetric with Go on this point).
2. **HTTP status handling**: Java's framework default (`framework-default`) handles 204 / 4xx / 5xx upstream — the adapter's `makeBids` is invoked only for successful responses. Custom status checks (`framework-default-plus-empty-seatbid-shortcircuit` or `custom-status-checks`) are legitimate when the upstream returns 200-but-empty-body. Flag `custom-status-checks` as **WARN** — usually the framework default suffices. When `prior_source_spec` declares Go uses `canonical-go-helpers` (e.g., `adapters.IsResponseStatusCodeNoContent`), Java should rely on framework default (Rule 30); explicit Java status checks for that case are a `warn` cross-language finding.
3. **Response unmarshaling**: Use `mapper.decodeValue(httpCall.getResponse().getBody(), BidResponse.class)` — wrapped in try/catch for `DecodeException`, re-thrown as `Result.withError(BidderError.badServerResponse(e.getMessage()))`. NEVER use `io.vertx.core.json.Json.decodeValue(...)` (banned).
4. **Empty-seatbid short-circuit**: Acceptable guard pattern: `if (bidResponse == null || CollectionUtils.isEmpty(bidResponse.getSeatbid())) { return Collections.emptyList(); }` (canonical Kobler). Maps to read-spec `http_status_handling.kind: framework-default-plus-empty-seatbid-shortcircuit`.
5. **Bid type resolution**: Must determine bid type for each bid. Preferred chains (in order):
   - From `bid.MType` (OpenRTB 2.6 markup type field) — `1 → banner`, `2 → video`, `3 → audio`, `4 → native`
   - From `bid.ext → "prebid" → ObjectNode → ExtBidPrebid.type` (canonical Kobler pattern: `Optional.ofNullable(bid.getExt()).map(ext -> ext.get(EXT_PREBID)).filter(JsonNode::isObject)...`)
   - From impression lookup (match `bid.getImpid()` to the original imp and check which media type is non-null, canonical AdkernelAdn `getType(impId, imps)`)
   - Fallback to `BidType.banner` is acceptable when there's no signal; FAIL when there's no fallback and unknown types would propagate
6. **Coverage of declared media types**: Cross-reference the bid type resolution against `bidder-config/{x}.yaml` `meta-info.{app,site,dooh}-media-types`. Every YAML-declared media type must have a Java return path; flag missing as **FAIL** (PBS routes that media type here and the adapter can't handle it). Java code returning a media type not in YAML is dead branch — **WARN**.
7. **BidderBid construction**: `BidderBid.of(bid, bidType, currency)` — preserves `bidResponse.getCur()` per spec, the `passthrough-from-response` pattern. NEVER overwrite `bidResponse.getCur()` with a hardcoded value (would mask the bidder's price reporting); when the response carries no currency, leave it null — framework handles the default upstream.
8. **Stream-pipeline `Objects::nonNull` filters**: Acceptable defensive pattern (canonical Kobler `bidResponse.getSeatbid().stream().filter(Objects::nonNull).map(SeatBid::getBid).filter(Objects::nonNull).flatMap(Collection::stream).filter(Objects::nonNull)`). The triple-filter is verbose but legitimate — Java's nullable collection elements force this. No finding unless filters are missing.
9. **Bid post-processing macros (ADR-007 F4)**: For canonical bidders (e.g., `thetradedesk`) that need `${AUCTION_PRICE}` substitution in `bid.nurl` / `adm` / `burl`, verify an `applyBidPostProcessingMacros(Bid)`-equivalent helper. When `prior_source_spec` carries a `bid-post-processing-macro` quirk for the bidder but the Java PR omits the helper, flag as `warn` cross-language finding.
10. **BidderResponse capacity allocation**: Java's analog of Go's `NewBidderResponseWithBidsCapacity(len(request.Imp))` is implicit via stream `.toList()` allocation — no explicit reviewer task unless the code returns a `BidderResponse` directly (rare).
11. **Error wrapping**: When wrapping a downstream exception, include `bid.getImpid()` for log diagnosability — e.g., `"unsupported bid mtype " + bid.getMtype() + " for impID " + bid.getImpid()`.

### Workflow: Private Helper Changed

**Triggers when:** A `private` (or package-private) method on the bidder class is added or modified — `parseImpExt`, `resolveBidType`, `resolveEndpoint`, `modifyImp`, `bidsFromResponse`, `getBidType`, etc.

1. **Necessity**: Helper should serve a clear purpose (ext parsing, endpoint resolution, bid-type lookup, currency conversion, imp/request rebuild). Flag unnecessary wrappers that just call a single framework method without transformation.
2. **No JSON injection via string concatenation**: NEVER build JSON by `String.format(...)` or `+` concatenation with raw values. Always use `mapper.encodeToBytes(...)` to re-serialize, or build via `ObjectNode` / `mapper.createObjectNode()`. Flag as **FAIL** (security).
3. **Error handling**: Helpers that can fail should throw `PreBidException` (the framework's canonical adapter-side checked exception), NOT panic / throw raw `RuntimeException`. The Bidder's public methods catch `PreBidException` and translate to `BidderError`.
4. **No side effects**: Helpers should not modify class-level fields or external state. Pure functions are the default; mutation lives only in the rebuild paths via `toBuilder()`.
5. **Package-private visibility**: Private helpers should be `private` unless tests need access. Package-private is acceptable for test-targeted helpers; `protected` / `public` on a helper is a **WARN** unless justified.
6. **Static when possible**: Helpers that don't reference `this` (instance fields) should be `static` (canonical AdkernelAdn: `validateImp`, `dispatchImpressions`, `compatImpression`, `createBidRequest`). Non-static helpers that don't reference `this` are a **WARN** — minor but consistent reviewer feedback.
7. **No dead or commented-out code**: Blocks of commented-out Java code are a **WARN** — should be deleted, not commented. Debug-print remnants (`System.out.println`, `log.debug` with local variables) are banned in production paths.

### Workflow: Adapter Field Changed

**Triggers when:** A class-level field declaration in `{X}Bidder.java` is added or modified.

1. **Visibility**: Fields should be `private`. `package-private` is acceptable for test access but **INFO**. Public fields are a **FAIL**.
2. **Finality**: All fields backing constructor parameters should be `final`. Non-final fields without a clear mutation path are a **WARN**.
3. **Static constants**: `static final` for class-level constants (TypeReferences, default-currency strings, ext-key strings, template-macro constants). Naming: SCREAMING_SNAKE_CASE per checkstyle `ConstantName` (`^([A-Z][A-Z0-9]*(_[A-Z0-9]+)*|(.*?)[l,L]ogger)$`).
4. **TypeReference declaration**: `private static final TypeReference<ExtPrebid<?, ExtImp{X}>> {X}_EXT_TYPE_REFERENCE = new TypeReference<>() { };` — the canonical Java-21 diamond syntax. Older `new TypeReference<ExtPrebid<?, ExtImp{X}>>() { }` is tolerated but newer pattern is preferred.
5. **No request-scoped fields**: Adapter is a singleton. Fields holding `BidRequest`, `Imp`, or mutable collections of request data are a **FAIL**.

### Workflow: Lombok Annotation Changed

**Triggers when:** A Lombok annotation (`@Value`, `@Data`, `@Builder`, `@Slf4j`, `@RequiredArgsConstructor`, `@AllArgsConstructor`, `@NoArgsConstructor`) is added/removed on a class in the bidder package.

The bidder class itself (`{X}Bidder`) almost never carries Lombok annotations — it has a custom validating constructor (`HttpUtil.validateUrl`, `Objects.requireNonNull`) that conflicts with `@RequiredArgsConstructor` generation. Flag `@RequiredArgsConstructor` / `@AllArgsConstructor` on `{X}Bidder` as **WARN** unless validation is genuinely absent.

Co-located helper DTOs (request/response models living inside the bidder package) follow the Java convention:

- `@Value @Builder @Jacksonized` for immutable POJOs — the default
- `@Data` is ONLY acceptable on classes that need Spring property injection (which is a `bidder-config-pr-review` concern, not this skill's surface). Flag `@Data` on bidder-package DTOs as **WARN** — they should be immutable.
- `@Slf4j` is acceptable on the bidder class when logging is genuinely needed; rare.

When the diff toggles `@Value` ↔ `@Data`, this changes the bean's mutability contract. **FAIL** if `@Data` replaces `@Value` on an OpenRTB-payload DTO; **INFO** the other direction.

### Workflow: Co-Located Helper Changed

**Triggers when:** A non-Bidder Java file in `bidder/{x}/` is added or modified — typical examples: `{X}Util.java`, `MediasquareUtil.java`, `KueezExtractor.java`, custom request/response DTOs.

1. **Necessity**: Co-located helpers must serve a clear purpose (multi-call adapter coordination, complex DTO that doesn't belong in `proto/openrtb/ext/request/{x}/`, response-parsing util). Flag duplication of logic already in `BidderUtil` / `HttpUtil` / `JacksonMapper` as **WARN**.
2. **Package statement**: Must match `package org.prebid.server.bidder.{x};` (lowercase, no underscores). Mismatch is a `PackageName` checkstyle violation — pre-flag here. (Distinct from the F-new-50 family, which covers `resolveEndpoint()` placeholder traps; see [Workflow: Private Helper Changed](#workflow-private-helper-changed) for that scope.)
3. **Visibility**: Default to package-private (Java idiom for "internal to this package"). `public` requires justification.
4. **No mutable static state**: Static fields holding mutable collections / counters are a **FAIL**.
5. **Test colocation**: A `{X}Util.java` typically has a `{X}UtilTest.java` sibling in the test tree. When the helper has non-trivial logic, flag missing test coverage as **WARN** — Jacoco enforces 90% line coverage, so untested helpers tank coverage.

### Workflow: Unit Test Changed

**Triggers when:** A `@Test` method in `{X}BidderTest.java` is added or modified.

1. **JUnit5 import**: `import org.junit.jupiter.api.Test;` — NOT `org.junit.Test` (banned by checkstyle `IllegalImport`). Catches the legacy-JUnit-import port-go2java mistake.
2. **Class extends `VertxTest`**: The canonical test base class — provides `jacksonMapper` field, `ObjectMapper`, common test helpers. When the test class does NOT extend `VertxTest`, flag as **WARN** — legacy adapters may import test helpers directly, but new code should follow the canonical pattern. The read-side `read-bidder-class` skill emits a `legacy-test-helpers-imported` quirk for this case.
3. **Mockito wiring**: For mocked dependencies (`CurrencyConversionService`, `JacksonMapper` is rarely mocked — `VertxTest` provides a real one), the class should use:
   - `@ExtendWith(MockitoExtension.class)` on the class
   - `@Mock private CurrencyConversionService currencyConversionService;` on the field
   - `@BeforeEach public void setUp() { ... }` for instantiation
4. **Test method naming — camelCase**: `void makeHttpRequestsShouldReturnErrorIfNoValidImps()` — JUnit convention. Snake_case (e.g., `scenario_for_app_simple_banner`) is the F-new-60 trap — port-go2java was emitting these incorrectly. Flag any `@Test` method with `_` in the name as **FAIL**.
5. **AssertJ patterns**: `assertThat(...)` from `org.assertj.core.api.Assertions` — chained API. Forbidden: `org.junit.Assert.*` (the JUnit4-style asserts), `org.junit.jupiter.api.Assertions.*` (JUnit5 native, but the project prefers AssertJ). Flag deviations as **WARN**.
6. **Static imports**: AssertJ uses static imports heavily (`import static org.assertj.core.api.Assertions.assertThat;`); checkstyle's `AvoidStaticImport` is suppressed on `*Test.java`. No finding.
7. **`given` / `when` / `then` block comments**: The project convention (canonical Kobler test): `// given`, `// when`, `// then` comments delimiting test phases. Strongly encouraged but not a hard rule — INFO if missing.
8. **Test data builders**: Reuse the `givenBidRequest(...)` / `givenImp(...)` helper pattern from the canonical adapter tests rather than inlining `BidRequest.builder()...build()` in every test. Inline construction is acceptable for one-off tests but **INFO** when repeated.
9. **No live HTTP calls**: Unit tests must NOT call real HTTP endpoints. The adapter's contract is "return `HttpRequest<BidRequest>` builder; framework executes." Mock at the `CurrencyConversionService` level, not at the network level.
10. **Coverage of changed adapter code**: For each `@Test` added in this PR, verify it exercises code added in the same PR (or net-new coverage of existing code). A `@Test` that only re-asserts pre-existing behavior may indicate Jacoco-padding — **INFO**.

### Workflow: Unit Test Setup Changed

**Triggers when:** `@BeforeEach`, class-level fields, or constructor wiring in `{X}BidderTest.java` is added or modified.

1. **Setup pattern**: `@BeforeEach public void setUp() { target = new {X}Bidder(...); }` — the canonical instantiation point. Tests should reference `target`, not re-instantiate the adapter per-method (except for negative-tests like `creationShouldFailOnInvalidEndpointUrl`).
2. **Constructor arg drift**: When `{X}Bidder`'s constructor signature changed (in the same PR), verify `@BeforeEach` updates accordingly. Stale `@BeforeEach` is a compile failure caught by CI but worth pre-flagging.
3. **Mock injection consistency**: If `@BeforeEach` adds a new `@Mock` field, verify all `@Test` methods that need it use `when(...)` / `verify(...)` correctly.

### Workflow: IT Class Changed

**Triggers when:** `src/test/java/org/prebid/server/it/{X}Test.java` is added or modified.

1. **Package and extends**: `package org.prebid.server.it;` + `public class {X}Test extends IntegrationTest`. The base class wires WireMock, the test server, fixture loading. Deviation from `extends IntegrationTest` is a **FAIL**.
2. **`@Test` method conventions**: Canonical pattern (per Kobler): one or more `@Test public void openrtb2AuctionShouldRespondWithBidsFromThe{X}Bidder() throws IOException, JSONException`. The method name encodes the test's intent — `openrtb2AuctionShouldRespondWith*` is the prefix for happy-path; other prefixes for error paths.
3. **WireMock stub pattern**: Canonical pattern:

   ```java
   WIRE_MOCK_RULE.stubFor(post(urlPathEqualTo("/{x}-exchange"))
           .withRequestBody(equalToJson(
                   jsonFrom("openrtb2/{x}/test-{x}-bid-request.json")))
           .willReturn(aResponse().withBody(
                   jsonFrom("openrtb2/{x}/test-{x}-bid-response.json"))));
   ```

   - `urlPathEqualTo` matches the `/{x}-exchange` path (must match the YAML `endpoint:` + `test-application.properties` `adapters.{x}.endpoint=http://localhost:8090/{x}-exchange` value). Mismatch is the F-new-96 trap.
   - `equalToJson(...)` does strict JSON equality against the bidder-bid-request fixture
   - The response body comes from the bidder-bid-response fixture

   Deviations (`urlEqualTo` instead of `urlPathEqualTo`, `containing` instead of `equalToJson`) are tolerated for special cases but **WARN** otherwise.

4. **`responseFor` + `assertJsonEquals` pattern**: Canonical close:

   ```java
   final Response response = responseFor("openrtb2/{x}/test-auction-{x}-request.json", Endpoint.openrtb2_auction);
   assertJsonEquals("openrtb2/{x}/test-auction-{x}-response.json", response, singletonList("{x}"));
   ```

   The `singletonList("{x}")` is the bidder name for ID-stripping in the comparison. For per-alias IT classes, this is the alias name, not the parent.

5. **Fixture path references — 4-file Rule 36**: Each `@Test` references EXACTLY these 4 fixture files (cross-skill with `bidder-params-java-pr-review` which owns them):
   - `openrtb2/{x}/test-{x}-bid-request.json` (the bidder-bound request)
   - `openrtb2/{x}/test-{x}-bid-response.json` (the bidder's mock response)
   - `openrtb2/{x}/test-auction-{x}-request.json` (the inbound auction request)
   - `openrtb2/{x}/test-auction-{x}-response.json` (the outbound auction response)
   - Missing fixtures are a **FAIL** — IT class will fail to load. Pre-flag against the PR's fixture additions; cross-skill: this is a `bidder-params-java-pr-review` owner concern, but flag here too so the reviewer sees the dependency.

6. **Scenario count**: One scenario is sufficient for basic coverage. Multi-scenario IT classes (e.g., Rubicon's multi-folder pattern) are acceptable when the bidder genuinely needs multiple end-to-end paths. Adding many scenarios in a new-adapter PR without justification is **WARN**.

7. **No imports of internal test helpers**: IT classes should NOT import from `src/test/java/org/prebid/server/bidder/`. The IT surface is separate from unit tests by design.

### Workflow: Per-Alias IT Class Added

**Triggers when:** A new `it/{Alias}Test.java` is added for an alias of an existing parent bidder (canonical: Adverxo's empire — `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`).

All [IT Class Changed](#workflow-it-class-changed) checks apply. Additional per-alias verifications:

1. **Class name matches alias slug**: `{Alias}Test` where `Alias` is TitleCase of the alias slug (e.g., `Adport` for alias `adport`). Mismatch is a **FAIL** (checkstyle `OuterTypeFilename`).
2. **WireMock URL path matches alias endpoint**: When the parent YAML's `aliases.{alias}.endpoint` declares a distinct endpoint (or inherits the parent), the IT class' `urlPathEqualTo(...)` must match the corresponding `test-application.properties` `adapters.{parent}.aliases.{alias}.endpoint=...` entry. Cross-skill with `bidder-config-pr-review` and `pr-triage-java`.
3. **Fixture directory**: Per-alias fixtures live at `src/test/resources/org/prebid/server/it/openrtb2/{alias}/` — separate from the parent's directory. The 4-file Rule 36 set applies per alias. Cross-skill: `bidder-params-java-pr-review` owns the fixtures.
4. **`assertJsonEquals` bidder name**: `singletonList("{alias}")` — the alias name, NOT the parent. Common port-go2java trap: emitting the parent name and silently breaking ID-stripping. Pre-flag as **FAIL**.
5. **Parent YAML consistency**: Cross-skill with `bidder-config-pr-review` — the parent YAML's `aliases:` block MUST declare this alias. Flag in Step 5 summary as a forwarded concern when the parent YAML is in the PR but doesn't carry the new alias entry.
6. **`test-application.properties` consistency**: Cross-skill with `pr-triage-java` — must have `adapters.{parent}.aliases.{alias}.enabled=true` and `.endpoint=http://localhost:8090/{alias}-exchange` (or shared with parent). Pre-flag in Step 5 summary.

### Workflow: Checkstyle Pre-Flag

**Triggers as a PR-level check on any added Java file in scope.**

Without simulating checkstyle, pre-flag these patterns from the diff. These are the most-common port-go2java emit traps from D2.8 cross-canary findings (F-new-50, F-new-56/57/58/59/60, F-new-79, F-new-96):

1. **`ImportOrder` violation (F-new-58 / F-new-59)**: Imports must be in 3 groups: `*` (everything else) then a blank line then `java|jakarta`. Within each group, alphabetical not enforced; case-sensitive ordering. Specifically: `org.prebid.server.*`, `com.iab.*`, `com.fasterxml.*`, `org.apache.*`, `io.vertx.*` all live in the first `*` group. `java.util.*`, `java.io.*`, `java.math.*`, `jakarta.validation.*` live in the second group. Wrong-group imports (e.g., `java.util.List` placed before `org.prebid.server.bidder.Bidder`) fail checkstyle `ImportOrder`. Pre-flag added imports that violate.
2. **Banned `io.vertx.core.json.Json` (F-new-56)**: Pre-flag any added `import io.vertx.core.json.Json;` — checkstyle `BanVertxJsonImport` will fail CI. Use `JacksonMapper` instead.
3. **`OuterTypeFilename` mismatch (F-new-79)**: Extract `public class Xxx` declaration from each added `*.java` file and verify it matches the filename root. `AdverxoBidder.java` must declare `public class AdverxoBidder`; `KoblerTest.java` must declare `public class KoblerTest`. Mismatch fails CI.
4. **`LineLength` > 120 (F-new-61)**: Any added line exceeding 120 chars (excluding URLs in `@see`, `//` comments, `package`, `import`). Use the checkstyle `ignorePattern` from `checkstyle.xml` (verbatim: `^package.*|^import.*|a href|href|http://|https://|@see|//`) to determine what's exempt. Canonical D2.8 emit defect: long IT-test fixture-path string literals and scenario method invocations exceeding 120 chars.
5. **`MethodName` snake_case (F-new-60)**: In added `*Test.java` files, flag `@Test` methods with `_` in the name. checkstyle's `MethodName` is `^[a-z][a-zA-Z0-9]*$` by default.
6. **`FinalLocalVariable`**: Any local variable declaration (`String x = ...;` without `final`) that's never reassigned fails checkstyle. Most-common emit error from port-go2java when translating Go's `:=` short declarations. Pre-flag missing `final` on local declarations.
7. **`UnusedImports processJavadoc=true`**: Imports that aren't referenced (including in `{@link X}` javadoc tags) fail. Pre-flag added imports that don't appear in the file body.
8. **`EmptyLineSeparator`**: Methods MUST have a blank line between them; fields MAY share without blank lines (per `allowNoEmptyLineBetweenFields=true`). Multiple consecutive blank lines fail (`allowMultipleEmptyLines=false`). Pre-flag any added 3+ consecutive blank lines.
9. **`NewlineAtEndOfFile`**: Every added Java file MUST end with a newline. Pre-flag trailing-newline omission.
10. **`RegexpSingleline` trailing whitespace**: Trailing spaces on any line fail. Pre-flag.
11. **`RegexpMultiline` `System.out.print` / `System.err.print`**: Banned anywhere. Pre-flag.
12. **`RegexpMultiline` empty row after class/interface/enum definition**: After `public class X {` there must be a blank line before the first member. Pre-flag.

When the manifest's `--- DRIFT CHECKS ---` reports `checkstyle.xml: DRIFT: ...`, factor the new/changed rule into pre-flag scope.

---

## Cross-Skill References (Read-Only)

This skill reads files owned by other skills for context, but does NOT create review tasks for them:

- `src/main/resources/bidder-config/{x}.yaml` — read to check declared capabilities (drives `makeBids` bid-type coverage); to check `endpoint:` (the adapter's constructor receives this resolved); to check `aliases:` (per-alias IT class addition signals new alias). Owned by `bidder-config-pr-review`.
- `src/main/resources/static/bidder-params/{x}.json` — read to verify adapter code references all declared params correctly. Owned by `bidder-params-java-pr-review`.
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/ExtImp{X}.java` — read to verify adapter code uses the correct POJO type and field names. Owned by `bidder-params-java-pr-review`.
- `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` — read to verify IT class' `@Test` methods reference fixtures by the canonical 4-file pattern. Owned by `bidder-params-java-pr-review`.
- `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` — read to cross-check the `bidderCreator` lambda's constructor args against the `{X}Bidder` constructor signature (F-new-57 trap). Owned by `bidder-config-pr-review`.
- `src/test/resources/org/prebid/server/it/test-application.properties` — read to verify `adapters.{x}.endpoint=http://localhost:8090/{x}-exchange` matches the IT class' `WireMock` stub. Owned by `pr-triage-java`.

When a cross-skill issue is detected, surface it as `CROSS-SKILL: {description}` in the Step 5 summary so the parent reviewer can route it appropriately.

---

## References

- [`../pr-triage-java/SKILL.md`](../pr-triage-java/SKILL.md) — the orchestrator that emits the routing manifest this skill consumes (Step 6 manifest contract)
- [`../bidder-config-pr-review/SKILL.md`](../bidder-config-pr-review/SKILL.md) — sibling skill; cross-skill concern: constructor parameters ↔ Spring `bidderCreator` lambda wiring
- [`../bidder-params-java-pr-review/SKILL.md`](../bidder-params-java-pr-review/SKILL.md) — sibling skill; cross-skill concern: `ExtImp{X}` POJO shape ↔ `{X}Bidder.parseImpExt` ext-parsing logic; 4-file Rule 36 IT fixture ownership
- [`../shared/framework-utilities-java.md`](../shared/framework-utilities-java.md) — review-side shared Java framework conventions (Lombok annotation catalog, JacksonMapper conventions, error-type taxonomy, endpoint-template-macro list, anti-pattern register, Vert.x ban-list, JUnit5 + AssertJ + Mockito conventions, IT test harness contract). Authored in parallel with this skill.
- [`../../../read/skills/read-bidder-class/SKILL.md`](../../../read/skills/read-bidder-class/SKILL.md) — read-side companion. Reviewers should know what fields the read side already extracts (`bidder_class.*`, `code.make_requests.*`, `code.make_bids.*`, `currency_conversion.*`, `headers_constructed.*`, `tests.*`); when reviewing a PR with an attached `prior_spec` or `prior_source_spec`, those fields are the basis for regression / port-fidelity findings.
- [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) — F4 design doc (file ownership map, Java-only concerns, open design questions). §3.2 enumerates Lombok / Spring DI / mvn-checkstyle / Jacoco / IT-tests / Rule 35 / alias-inversion concerns this skill must understand.
- D2.8 cross-canary findings (template-defect patterns this skill detects): `docs/runs/d2.8-cross-canary-summary.md` (F-new-50 / 56 / 57 / 58 / 59 / 60 / 79 / 96 trap families)
- Port-translation rules (Rule 5 mutation idiom, Rule 22 currency-conversion injection, Rule 30 framework-default HTTP status handling, Rule 33 alias inversion, Rule 35 typed-config subclass, Rule 36 4-file IT fixture, Rule 38 byte-fidelity): [`../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml)
