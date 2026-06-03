# Bidder Class Index — Java

Deep-dive lookup index for `bidder-class-pr-review` covering the per-bidder Java surface: the `{X}Bidder.java` implementation class, its co-located helpers, the `{X}BidderTest.java` unit test, and the `it/{X}Test.java` integration test class. This file is the analog of the Go-side `adapter-code-index.md` but targets Java's narrower, more uniform surface.

**Upstream pin:** `prebid/prebid-server-java` master at SHA `a1fe64e123d6` (verified 2026-05-04). Java toolchain: **Java 21**. Vert.x `4.5.20`, Spring Boot `3.5.10`, checkstyle `10.17.0`, Jacoco `0.8.13`.

**Canonical reference adapter** (referenced throughout): `src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java` (Rule 35 typed-config + currency conversion + bid-type-via-ext.prebid + dev/prod endpoint toggle — the most representative single-adapter example).

For cross-cutting framework surface (Spring DI, Lombok, Vert.x ban-list, JUnit5+AssertJ+Mockito, checkstyle rules, Jacoco, F-new trap table), see [`../../shared/framework-utilities-java.md`](../../shared/framework-utilities-java.md). This file does NOT duplicate that content; it links to it.

**Upstream sources (canonical):**
- Bidder interface: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/bidder/Bidder.java
- BidderUtil: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/util/BidderUtil.java
- HttpUtil: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/util/HttpUtil.java
- Canonical adapter: https://github.com/prebid/prebid-server-java/blob/master/src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java
- Canonical IT test base: https://github.com/prebid/prebid-server-java/blob/master/src/test/java/org/prebid/server/it/IntegrationTest.java

> **Sync policy:** This file is a local snapshot. The `pr-triage-java` skill's Step 2 runs centralized drift checks against the live source on every review run; this skill's Step 1b reads those drift results from the manifest. If the `Bidder<T>` interface signature, `BidderUtil` helper API surface, or `HttpUtil.validateUrl` semantics change upstream, update this file to match.

---

## 1. Bidder class anatomy (canonical Kobler reference)

The canonical `{X}Bidder.java` shape, line-by-line per Kobler. Every reviewer task in this skill grounds back into this template.

### 1.1 Package + imports

```java
package org.prebid.server.bidder.{x};
```

Canonical 27-import set per `KoblerBidder.java:3-39`. Reviewer-relevant import-source families (`com.fasterxml.jackson.*`, `com.iab.openrtb.{request,response}`, `org.apache.commons.{collections4,lang3}`, `org.prebid.server.bidder.{model,Bidder}`, `org.prebid.server.{currency,exception,json}`, `org.prebid.server.proto.openrtb.ext.{request,response}.*`, `org.prebid.server.util.{BidderUtil,HttpUtil}`) live in the **TOP** `ImportOrder` group; `java.*` and `jakarta.*` live in the **BOTTOM** group with a blank-line separator. See `framework-utilities-java.md` §6.3 for the full `ImportOrder` rule.

Banned import surface (each triggers checkstyle `IllegalImport`):
- `io.vertx.core.json.Json` — use `JacksonMapper` (F-new-56). Suppressed only for `ObjectMapperProvider.java`.
- `org.apache.commons.lang` (without `lang3`) — use `org.apache.commons.lang3.*`.
- `org.junit.Test` (JUnit 4) — use `org.junit.jupiter.api.Test`.
- `autovalue.shaded.com.google.*`, `org.inferred.freebuilder.shaded.com.google.*` — shadowed deps.

### 1.2 Class declaration

```java
public class {X}Bidder implements Bidder<BidRequest> {
```

- **Class modifier**: `public` (only `public` type in the bidder package — co-located helpers default to package-private)
- **Class name**: `{X}Bidder` (UpperCamelCase, matches filename root per `OuterTypeFilename` — F-new-79 trap)
- **Type parameter `T`**: `BidRequest` is canonical. Custom request types (`MediasquareRequest`, `HuaweiAdsRequest`) are rare; see §2.5.
- **No Lombok annotations on the class** — see §1.6.

### 1.3 Static final constants

Canonical Kobler constants:

```java
private static final TypeReference<ExtPrebid<?, ExtImpKobler>> KOBLER_EXT_TYPE_REFERENCE =
        new TypeReference<>() { };
private static final String DEFAULT_BID_CURRENCY = "USD";
private static final String EXT_PREBID = "prebid";
```

Reviewer rules:
- **`TypeReference` constant** — class-level, `private static final`, name `{X}_EXT_TYPE_REFERENCE`. Diamond `new TypeReference<>() { }` (Java 21 anonymous-class diamond) preferred over the explicit-generic form.
- **SCREAMING_SNAKE_CASE** per `ConstantName` rule. `DEFAULT_BID_CURRENCY = "USD"` is conventional for currency-conversion guards.
- **Template-macro constants** (when applicable): `URL_PUBLISHER_ID_MACRO = "{{PublisherID}}"` (AdkernelAdn), `ADUNIT_MACROS_ENDPOINT = "{{adUnitId}}"` (Adverxo), `EXT_PREBID = "prebid"` (Kobler). Inline string literals in `String.replace(...)` are **WARN** — extract to a named constant.

### 1.4 Adapter fields

`private final` for every constructor-backed field. Visibility: `private` (package-private acceptable for test access but **INFO**; public is **FAIL**). Finality: `final` always — non-final is **WARN**. No request-scoped state: adapter is a Spring singleton; fields holding `BidRequest`, `Imp`, or mutable collections of request data are **FAIL**. Instance fields are non-`static`; constants are `static final` (see §1.3).

### 1.5 Constructor

Canonical Kobler form:

```java
public KoblerBidder(String endpointUrl, String devEndpoint,
                    CurrencyConversionService currencyConversionService, JacksonMapper mapper) {
    this.endpointUrl = HttpUtil.validateUrl(endpointUrl);
    this.devEndpoint = Objects.requireNonNull(devEndpoint);
    this.currencyConversionService = Objects.requireNonNull(currencyConversionService);
    this.mapper = Objects.requireNonNull(mapper);
}
```

Reviewer invariants:
- **Visibility**: `public` (Spring DI invokes via the `bidderCreator` lambda in `{X}Configuration.java`).
- **`HttpUtil.validateUrl(endpointUrl)`** — fail-fast on malformed endpoint at startup. Skipping is **WARN**. Some adapters wrap with `Objects.requireNonNull(endpointUrl)` first; both forms acceptable.
- **`Objects.requireNonNull(...)`** on every helper collaborator. Raw assignment without null-check is **INFO** (Adverxo pattern is tolerated; Kobler / AdkernelAdn use `requireNonNull`).
- **Parameter order MUST match the `bidderCreator(cfg -> new {X}Bidder(...))` lambda** — F-new-57 trap. **Cross-skill with `bidder-config-pr-review`**.
- **No hardcoded credentials** — secrets arrive via Spring properties.
- **No request-scoped state** stored — see §1.4.

### 1.6 Lombok annotations on `{X}Bidder` — almost never

The adapter class itself almost never carries Lombok annotations. Adapters declare an **explicit validating constructor** (`HttpUtil.validateUrl`, `Objects.requireNonNull`) that conflicts with `@RequiredArgsConstructor` generation.

- **`@RequiredArgsConstructor` / `@AllArgsConstructor`** on `{X}Bidder` is **WARN** unless validation is genuinely absent.
- **`@Slf4j`** is acceptable when logging is genuinely needed (rare — `makeHttpRequests` should return errors via `BidderError`, not log).
- **`@Value` / `@Data` / `@Builder`** never appear on the adapter class itself; only on co-located DTOs (see §10).

See `framework-utilities-java.md` §2 for the full Lombok semantics catalog.

### 1.7 `@Override` method signatures

```java
@Override
public Result<List<HttpRequest<BidRequest>>> makeHttpRequests(BidRequest bidRequest) { ... }

@Override
public Result<List<BidderBid>> makeBids(BidderCall<BidRequest> httpCall, BidRequest bidRequest) { ... }
```

Both methods MUST be annotated `@Override` (enforced by checkstyle `MissingOverride`). Signature deviations fail compilation.

### 1.8 Private helpers

Canonical Kobler helpers (in declaration order):

| Helper | Purpose | Static-eligible? |
|---|---|---|
| `modifyImp(BidRequest, Imp)` | Rebuilds the `Imp` with resolved bid floor | No (uses `this.currencyConversionService`) |
| `resolveBidFloor(Imp, BidRequest)` | Calls `BidderUtil.shouldConvertBidFloor` + delegates | No |
| `convertBidFloor(Price, BidRequest)` | Invokes `currencyConversionService.convertCurrency` | No |
| `normalizeCurrencies(BidRequest)` | Adds USD to `bidRequest.cur` if absent | Yes (no `this` deps) — flag as **WARN** if non-static |
| `isTest(Imp, List<BidderError>)` | Reads `imp.ext.bidder.test` flag for dev/prod toggle | No |
| `parseImpExt(Imp)` | Two-step ext unmarshaling | No (uses `this.mapper`) |
| `extractBids(BidResponse)` | Top-level null-guard + delegation | Yes — flag as **WARN** if non-static |
| `bidsFromResponse(BidResponse)` | Stream pipeline of `SeatBid → Bid → BidderBid` | No (uses `this.getBidType`) |
| `getBidType(Bid)` | Bid-type resolution per §5 | No (uses `this.parseExtBidPrebid`) |
| `parseExtBidPrebid(ObjectNode)` | Jackson `treeToValue` for `ExtBidPrebid` | No (uses `this.mapper`) |

See `Workflow: Private Helper Changed` in [`../SKILL.md`](../SKILL.md) for the verification checklist applied per-helper-change.

---

## 2. Constructor signatures by adapter shape

The constructor's parameter list is determined by the adapter's helper-collaborator needs. Six canonical shapes:

### 2.1 Bare (no helper collaborators)

`public {X}Bidder(String endpointUrl, JacksonMapper mapper)`. Canonical: `AdkernelAdnBidder.java:48`. Spring lambda: `new {X}Bidder(config.getEndpoint(), mapper)`.

### 2.2 Currency-converting

`public {X}Bidder(String endpointUrl, CurrencyConversionService currencyConversionService, JacksonMapper mapper)`. Canonical: `AdverxoBidder.java:50`. Adds `CurrencyConversionService` for `convertCurrency(value, bidRequest, fromCur, toCur)` calls in `resolveBidFloor`. Spring lambda: `new {X}Bidder(config.getEndpoint(), currencyConversionService, mapper)`.

### 2.3 Rule 35 typed-config (dev/prod toggle, Kobler-shape)

`public KoblerBidder(String endpointUrl, String devEndpoint, CurrencyConversionService currencyConversionService, JacksonMapper mapper)`. Canonical: `KoblerBidder.java:55-58`. The extra `String devEndpoint` parameter comes from `KoblerConfigurationProperties.getDevEndpoint()` (Rule 35 typed-config subclass — see `framework-utilities-java.md` §1.2). Spring lambda:

```java
.bidderCreator(cfg -> new KoblerBidder(
        cfg.getEndpoint(), cfg.getDevEndpoint(), currencyConversionService, mapper))
```

**Cross-skill concern**: `bidder-config-pr-review` owns `KoblerConfigurationProperties`. The constructor's typed-config arg names + order MUST match the typed subclass's getters AND the lambda's invocation order (F-new-57).

### 2.4 Rule 35 typed-config (separate-file subclass form)

When the typed-config subclass lives in `{X}BidderConfigurationProperties.java` (separate file in `org.prebid.server.spring.config.bidder`) rather than nested in `{X}Configuration.java`, the constructor receives the typed instance directly OR receives the extracted strings (same as §2.3). Both forms are acceptable; the lambda decides which.

### 2.5 Custom request type (Mediasquare / Huaweiads)

`public class {X}Bidder implements Bidder<{CustomType}>` — `implements` line parameterized with a co-located DTO (`bidder/{x}/request/{X}Request.java` or `bidder/{x}/{X}Request.java`) that the adapter constructs in `makeHttpRequests` and the framework round-trips back to `makeBids`. Canonical: `MediasquareBidder implements Bidder<MediasquareRequest>` (`MediasquareBidder.java:55`), `HuaweiAdsBidder implements Bidder<HuaweiAdsRequest>` (`HuaweiAdsBidder.java:54`). Rule 9 of the port-translation rules covers `parameterized_request_type`. Flag uncommon types as **INFO**.

### 2.6 Multi-token / `EndpointTemplate` (F-new-2 LANDED)

When the endpoint URL contains MULTIPLE `{{TOKEN}}` macros with non-trivial substitution (per-imp lookups, side-channel data flows), the adapter holds a parsed `EndpointTemplate`-like helper built once in the constructor (`this.template = EndpointTemplate.parse(HttpUtil.validateUrl(endpointUrl));`). Simple single-token substitutions use inline `String.replace("{{TOKEN}}", value)`. Java's analog of Go's `text/template`: `String.replace(...)` / `String.format(...)` / `URIBuilder`. Custom resolver classes (e.g., `HuaweiEndpointResolver` in the huaweiads package) appear only when complexity demands it.

---

## 3. `makeHttpRequests` dispatching modes

`makeHttpRequests` is one of nine canonical shapes per the cross-language behavior taxonomy at [`../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml) (`code.make_requests.batching.rules[]`): `single-batched`, `per-imp`, `max-imps-per-request`, `format-split`, `deals-split`, `pod-grouping`, `imp-flatten-aggregate`, `filtered-subset`, `grouped-by-key`. The read-side `read-bidder-class` skill emits `code.make_requests.batching.rules[]` for each adapter — reviewers should expect the Java emit to match. The five most-common shapes have detailed code skeletons below (§3.1–§3.5); the remaining four (`deals-split`, `pod-grouping`, `imp-flatten-aggregate`, `filtered-subset`) are documented terse in §3.6.

### 3.1 `single-batched` — one request per `BidRequest`

The default. Canonical example: Kobler (`KoblerBidder.java:67-93`). Skeleton:

```java
@Override
public Result<List<HttpRequest<BidRequest>>> makeHttpRequests(BidRequest bidRequest) {
    final List<BidderError> errors = new ArrayList<>();
    final List<Imp> modifiedImps = new ArrayList<>();

    for (Imp imp : bidRequest.getImp()) {
        try {
            modifiedImps.add(modifyImp(bidRequest, imp));
        } catch (PreBidException e) {
            errors.add(BidderError.badInput(e.getMessage()));
            return Result.withErrors(errors);                    // hard fail-fast (Kobler-style)
        }
    }

    final BidRequest modifiedRequest = bidRequest.toBuilder().imp(modifiedImps).build();
    return Result.of(Collections.singletonList(
            BidderUtil.defaultRequest(modifiedRequest, endpointUrl, mapper)),
            errors);
}
```

### 3.2 `per-imp` — one request per `Imp`

Loop accumulating `Result.of(requests, errors)` where each iteration's `bidRequest.toBuilder().imp(Collections.singletonList(imp)).build()` produces a single-imp `HttpRequest`. Errors are **accumulated** (not fail-fast) so partial success is preserved across imps.

### 3.3 `per-key` (F-new-7 EXT-A) — group by extracted key

`bidRequest.getImp().stream().collect(Collectors.groupingBy(this::extractKey))` — extract publisher-id / zone-id / network-id from `imp.ext`, then dispatch one request per group via `bidRequest.toBuilder().imp(entry.getValue()).build()`. Canonical example: AdkernelAdn's `dispatchImpressions` grouping by `pubId`. Verify grouping logic + alignment with `meta-info.{app,site}-media-types` capability.

### 3.4 `max-imps-per-request` — fixed-size batches

`Lists.partition(bidRequest.getImp(), MAX_IMPS_PER_REQUEST)` with `MAX_IMPS_PER_REQUEST` as class-level `static final`. Rare.

### 3.5 `format-split` — banner / video / native partitioned

`bidRequest.getImp().stream().filter(imp -> imp.getBanner() != null).toList()` for each format, dispatched to a distinct format-specific endpoint (class-level constant OR separate constructor arg).

### 3.6 Remaining canonical modes — terse

The four remaining batching rules per the canonical 9-mode taxonomy. Reviewers recognize the shape; full skeletons are not duplicated here when the read-side spec emits them.

- **`deals-split`** — separate request batches for deal-imps vs non-deal-imps (`imp.pmp.private_auction == 1`). Canonical: Rubicon's deal-split pattern. Used composably with `format-split` (Rubicon emits `[format-split, deals-split]`).
- **`pod-grouping`** — long-form video / OTT imps grouped by `imp.video.podid`. Canonical: Appnexus (composed with `max-imps-per-request: 10` → `[max-imps-per-request: 10, pod-grouping]`).
- **`imp-flatten-aggregate`** — multi-imp request flattened into a single request body where each imp's params are aggregated into top-level keys. Rare; specific to bidders whose upstream API does not accept OpenRTB-2.x imp arrays directly.
- **`filtered-subset`** — only a subset of imps (matching adapter-side eligibility criteria — currency, format, capability) are dispatched; the rest are dropped with `BidderError.badInput(...)` per imp.

Each of these has the same cross-cutting rules as §3.1–§3.5 (`toBuilder()` mutation, Vert.x JSON ban, `Result.of(...)`, headers via `HttpUtil.headers()`, payload, endpoint resolution, no redundant PBS-core filtering). When `read-bidder-class` emits any of these in `batching.rules[]`, reviewers verify the dispatch logic matches the rule's semantics.

### 3.7 Cross-cutting reviewer rules for all modes

- **Mutation via `toBuilder()`**: `BidRequest`, `Imp`, `Device`, `User`, `Site`, `App` mutations use the Lombok-generated `toBuilder()...build()` chain (Rule 5). Direct setters don't compile on `@Value` POJOs — see `framework-utilities-java.md` §2.2.
- **No `io.vertx.core.json.Json` usage**: Banned by checkstyle `BanVertxJsonImport` (F-new-56). Use `mapper.encodeToBytes(...)`.
- **`Result.of(values, errors)`** for mixed; `Result.withValues(...)` for no errors; `Result.withErrors(...)` for no values. NEVER `new Result(...)`.
- **Headers**: `HttpUtil.headers()` for the default 2-header set (`Content-Type: application/json;charset=utf-8` + `Accept: application/json`). Compose additional headers via `.add(...)`. When using `BidderUtil.defaultRequest`, headers are framework-defaulted.
- **`payload(outgoingRequest)`**: include the `BidRequest` payload when downstream `makeBids` reads `httpCall.getRequest().getPayload()` (canonical AdkernelAdn pattern).
- **Endpoint resolution**: Java's analog of Go's `text/template` is `String.replace(...)` / `String.format(...)` / `URIBuilder`. Verify every `{{TOKEN}}` macro in the URL has a corresponding `.replace("{{TOKEN}}", ...)` call. Unresolved macros leave the literal in the URL at runtime — a common `port-go2java` trap (F-new-50 family).
- **No redundant PBS-core filtering**: The framework filters empty imp lists, endpoint emptiness (Spring `@NotBlank`), media-type capability routing, site/app presence. Re-implementing those checks is **WARN**. Specific-field defensive checks (e.g., `imp.banner.format[0]` for an adapter requiring explicit dimensions) are valid.

---

## 4. `makeBids` response-handling modes

`makeBids` is one of three canonical shapes, distinguished by `http_status_handling.kind` in the read-spec:

### 4.1 `framework-default` (the default — Rule 30)

The Java framework's `HttpBidderRequester` handles 204 / 4xx / 5xx BEFORE invoking the adapter's `makeBids`. The actual upstream mechanism (verified at SHA `a1fe64e123d6`): `errorOrNull(int statusCode)` (line 279) attaches a `BidderError` when status ≠ 200 ∧ ≠ 204, and the private static `makeBids(...)` dispatcher (line 302) short-circuits on 204 → `CompositeBidderResponse.empty()`, returns null on 4xx/5xx, and only on 200 invokes the adapter's `bidder.makeBidderResponse(...)`. There is no method named `validateResponse` on `HttpBidderRequester`. The adapter's `makeBids` is invoked only for successful responses. **No explicit status checks in adapter code.** This is the Java analog of Go's `canonical-go-helpers` (`adapters.IsResponseStatusCodeNoContent` / `adapters.CheckResponseStatusCodeForErrors`).

Canonical Kobler pattern (`KoblerBidder.java:149-157`):

```java
@Override
public Result<List<BidderBid>> makeBids(BidderCall<BidRequest> httpCall, BidRequest bidRequest) {
    try {
        final BidResponse bidResponse =
                mapper.decodeValue(httpCall.getResponse().getBody(), BidResponse.class);
        return Result.withValues(extractBids(bidResponse));
    } catch (DecodeException e) {
        return Result.withError(BidderError.badServerResponse(e.getMessage()));
    }
}
```

### 4.2 `framework-default-plus-empty-seatbid-shortcircuit`

Same as §4.1 but with an early-return when `bidResponse.seatbid` is empty (Kobler-style):

```java
private List<BidderBid> extractBids(BidResponse bidResponse) {
    if (bidResponse == null || CollectionUtils.isEmpty(bidResponse.getSeatbid())) {
        return Collections.emptyList();
    }
    return bidsFromResponse(bidResponse);
}
```

This is the canonical pattern. The early-return is the Java equivalent of Go's 204 short-circuit (the framework strips actual 204s upstream; this guard handles the 200-but-empty-body case).

### 4.3 `custom-status-checks` (WARN by default)

When the adapter explicitly reads `httpCall.getResponse().getStatusCode()` and short-circuits:

```java
if (httpCall.getResponse().getStatusCode() == HttpResponseStatus.NO_CONTENT.code()) {
    return Result.empty();
}
```

Flag as **WARN** — usually the framework default suffices. When `prior_source_spec` declares Go uses `canonical-go-helpers`, Java should rely on framework default; explicit Java status checks for that case are a `warn` cross-language finding.

**F-new-90 trap (HIGH BLOCKING)**: Any reference to `BidderUtil.isResponseStatusCodeNoContent(...)` / `BidderUtil.checkResponseStatusCode(...)` / `BidderUtil.checkResponseStatusCodeForErrors(...)` is a port-go2java defect — **these methods do not exist in upstream Java**. The Go-canonical helper names were transliterated incorrectly. See `framework-utilities-java.md` §3.2.

### 4.4 Stream-pipeline `extractBids` body

The canonical post-decode stream pipeline (Kobler `bidsFromResponse`):

```java
private List<BidderBid> bidsFromResponse(BidResponse bidResponse) {
    return bidResponse.getSeatbid().stream()
            .filter(Objects::nonNull)
            .map(SeatBid::getBid)
            .filter(Objects::nonNull)
            .flatMap(Collection::stream)
            .filter(Objects::nonNull)
            .map(bid -> BidderBid.of(bid, getBidType(bid), bidResponse.getCur()))
            .toList();
}
```

The **triple `Objects::nonNull` filter** is verbose but legitimate — Java's nullable collection elements force it. No finding unless filters are missing.

### 4.5 F-new-100 / ADR-007 F4 post-processing macro hook

For canonical bidders (e.g., `thetradedesk`) needing `${AUCTION_PRICE}` substitution in `bid.nurl` / `bid.adm` / `bid.burl`, the stream maps through an additional helper:

```java
.map(bid -> BidderBid.of(applyBidPostProcessingMacros(bid), getBidType(bid), bidResponse.getCur()))
```

Where `applyBidPostProcessingMacros(Bid)` rebuilds the bid via `bid.toBuilder().nurl(substituted).adm(substituted).burl(substituted).build()`. When `prior_source_spec` carries a `bid-post-processing-macro` quirk for the bidder but the Java PR omits the helper, flag as `warn` cross-language finding (F-new-100, HIGH BLOCKING per `framework-utilities-java.md` §8).

### 4.6 Cross-cutting reviewer rules

- **`BidderBid.of(bid, bidType, currency)`** — the canonical constructor. `currency` is `bidResponse.getCur()` (passthrough; null when bidder returned no currency — the framework defaults upstream). NEVER overwrite with a hardcoded value.
- **No `requestInfo` arg**: `makeBids` does NOT receive a `requestInfo` parameter (Java symmetric with Go). Currency conversion is available ONLY in `makeHttpRequests`.
- **Error wrapping with impId for diagnosability**: `"unsupported bid mtype " + bid.getMtype() + " for impID " + bid.getImpid()`.
- **`BidderError.badServerResponse(...)` for upstream-bidder errors only** (the response body was unparseable / unexpected). `BidderError.badInput` is reserved for request-side errors in `makeHttpRequests`.

---

## 5. Bid type resolution kinds

The bid-type resolution chain in `getBidType(Bid)` / `resolveBidType(Bid, BidRequest)` follows the canonical cross-language taxonomy at [`../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml) (`code.make_bids.bid_type_resolution.method_chain[].method`): `by-imp-mediatype`, `by-bid-mtype`, `by-bid-ext-typed-field`, `by-imp-id-suffix`, `imp-prefix-lookup`, `by-response-payload-shape`, `hardcoded`, `custom`. Reviewers cross-reference against `bidder-config/{x}.yaml` `meta-info.{app,site,dooh}-media-types` — every declared media type MUST have a Java return path.

### 5.1 `hardcoded` — single-type adapter

`return BidType.banner;` when YAML declares only `banner`. Also serves as the canonical fallback in deeper resolution chains (`.orElse(BidType.banner)`). The method-chain step has `method: hardcoded`, `hardcoded_value: <BidType>`, `fallback_action: return-default`. Hardcoding a type NOT in YAML capabilities is dead branch — **WARN**.

### 5.2 `by-imp-mediatype` — match `bid.impid` → `imp.{banner,video,native,audio}`

Loop over `bidRequest.getImp()`, find the imp where `imp.getId().equals(bid.getImpid())`, return whichever media-type field is non-null (priority: banner, video, native, audio).

Available as a framework helper: `BidderUtil.getBidType(bid, impIdToImpMap)` (`BidderUtil.java:112-129`) — same logic with `BidType.banner` fallback for missing imps. Prefer the framework helper for new adapters; flag manual reimplementation as **WARN**.

### 5.3 `by-bid-mtype` — OpenRTB 2.6 markup-type switch

`switch (bid.getMtype()) { case 1 -> banner; case 2 -> video; case 3 -> audio; case 4 -> xNative; default -> throw new PreBidException("Unknown mtype " + ... + " for impID " + bid.getImpid()); }`. Preferred for OpenRTB 2.6 — adapters whose upstream populates `bid.mtype`. Fallback to `by-imp-mediatype` introspection (§5.2) when `mtype` is missing.

### 5.4 `by-bid-ext-typed-field` — `bid.ext.{vendor-specific-field}`

`mapper.mapper().convertValue(bid.getExt(), {X}BidExt.class)` → switch on a custom field. `{X}BidExt` is a co-located DTO. Used when the bidder embeds the type in their own ext namespace (aax's `bid.ext.adCodeType`, etc.). The method-chain step's `field` is the path within `bid.ext` (e.g., `"bid.ext.adCodeType"`, `"bid.ext.prebid.type"`). **F-new-64 trap** when this path is missed in favor of a generic `bid.ext.prebid.type` chain.

### 5.5 `by-bid-ext-typed-field` with `field: bid.ext.prebid.type` — canonical Kobler chain

The canonical Kobler pattern (`KoblerBidder.java:177-194`):

```java
private BidType getBidType(Bid bid) {
    return Optional.ofNullable(bid.getExt())
            .map(ext -> ext.get(EXT_PREBID))
            .filter(JsonNode::isObject)
            .map(ObjectNode.class::cast)
            .filter(JsonNode::isObject)
            .map(this::parseExtBidPrebid)
            .map(ExtBidPrebid::getType)
            .orElse(BidType.banner);
}
```

Walks `bid.ext → "prebid" → ObjectNode → ExtBidPrebid.type`, falling back to `BidType.banner`. The `parseExtBidPrebid` helper wraps `mapper.mapper().treeToValue(prebid, ExtBidPrebid.class)` in a try/catch returning `null` on `JsonProcessingException`. Broadest-coverage pattern — most empire bidders use it.

**Caveat (F-new-64 / disposition system):** the `.orElse(BidType.banner)` silently mis-types any bid the chain fails to classify. **Acceptable** only when `banner` is the bidder's *sole* declared media type; a likely-unreachable safety net on a fully-covered chain is **WARN** (prefer erroring on the unreachable branch); a default that can mislabel a declared video/native/audio bid as banner is **FAIL** (the Teal #4765 latent-bug class). See [SKILL.md](../SKILL.md) makeBids step 5.

**Cross-language asymmetry note**: When `prior_source_spec` declares the Go side uses `bid.ext.prebid.type`, the Java emit MUST walk the same chain. Different resolution chains for the same bidder is a `warn` cross-language finding.

### 5.6 `by-imp-id-suffix` / `imp-prefix-lookup` — side-channel correlation

Variant where `bid.impid` correlates to a side-channel map built during `makeHttpRequests`. **FAIL** if implemented via class fields (`private final Map<...>` / `ThreadLocal`) — adapter is a singleton. The correct pattern packs the map into a custom request type (§2.5) and reads it back via `httpCall.getRequest().getPayload()`.

### 5.7 Coverage of declared media types (cross-skill concern)

Cross-reference the bid-type resolution against `bidder-config/{x}.yaml` `meta-info.{app,site,dooh}-media-types`:

- Every YAML-declared media type MUST have a Java return path; missing is **FAIL** (PBS routes that media type here and the adapter can't handle it).
- Java code returning a media type NOT in YAML is dead branch — **WARN**.
- The fallback `.orElse(BidType.banner)` is **acceptable** only when `banner` is the bidder's *sole* declared media type; a never-hit safety net on a fully-covered chain is **WARN** (prefer erroring on the unreachable branch); a default that can mislabel a declared video/native/audio bid as banner is **FAIL** (F-new-64 / Teal #4765). See SKILL.md makeBids step 5.

---

## 6. Unit test (`{X}BidderTest`) anatomy

### 6.1 Canonical skeleton

```java
package org.prebid.server.bidder.{x};
// ... AssertJ static imports + JUnit5 + Mockito + VertxTest + bidder DTOs ...

@ExtendWith(MockitoExtension.class)
public class {X}BidderTest extends VertxTest {

    private static final String ENDPOINT_URL = "https://test.endpoint";

    @Mock private CurrencyConversionService currencyConversionService;
    private {X}Bidder target;

    @BeforeEach
    public void setUp() {
        target = new {X}Bidder(ENDPOINT_URL, currencyConversionService, jacksonMapper);
    }

    @Test
    public void creationShouldFailOnInvalidEndpointUrl() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new {X}Bidder("invalid-url", currencyConversionService, jacksonMapper));
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

    private static BidRequest givenBidRequest(UnaryOperator<BidRequest.BidRequestBuilder>... customizers) { ... }
    private static Imp givenImp(UnaryOperator<Imp.ImpBuilder> impCustomizer) { ... }
    private static BidderCall<BidRequest> givenHttpCall(String body) { ... }
}
```

### 6.2 Reviewer checklist

- **`extends VertxTest`** — provides `jacksonMapper` field (real `JacksonMapper`, do NOT mock) + `mapper` (`ObjectMapper`). Missing inheritance is **WARN** (legacy adapters may bypass; new code follows canonical pattern). Read-side emits a `legacy-test-helpers-imported` quirk for this case.
- **`@org.junit.jupiter.api.Test`** — NOT `org.junit.Test` (BANNED by checkstyle `IllegalImport`).
- **`@BeforeEach`** — NOT `@Before` (JUnit 4 — banned via `org.junit.Test` ban).
- **`@ExtendWith(MockitoExtension.class)`** when `@Mock` fields are used.
- **AssertJ `assertThat(...)` from `org.assertj.core.api.Assertions`** — chained API. Forbidden: `org.junit.Assert.*` (JUnit 4 asserts), `org.junit.jupiter.api.Assertions.*` (project prefers AssertJ).
- **Static imports** — AssertJ's `assertThat` is typically imported statically; `AvoidStaticImport` is suppressed on `*Test.java` (see `framework-utilities-java.md` §6.10). No finding.
- **`given` / `when` / `then` block comments** — strongly encouraged but not enforced. INFO if missing.
- **Test data builders** — `givenBidRequest(...)` / `givenImp(...)` / `givenHttpCall(...)` helper pattern. Inline `BidRequest.builder()...build()` is acceptable for one-off tests but **INFO** when repeated.

### 6.3 Baseline canonical test methods (every new adapter)

Reviewers expect the following canonical `@Test` methods in a new `{X}BidderTest.java`. Missing any is **WARN** (not **FAIL** — coverage is enforced by Jacoco):

| Method | Purpose |
|---|---|
| `creationShouldFailOnInvalidEndpointUrl` | Constructor validation negative-path (the `HttpUtil.validateUrl` invariant) |
| `makeHttpRequestsShouldReturnErrorIfImpExtCouldNotBeParsed` | `parseImpExt` error path |
| `makeHttpRequestsShouldReturnExpectedRequest` (or `...Request[s]`) | Happy path — request construction |
| `makeBidsShouldReturnEmptyListIfResponseBodyHasNoBids` | Empty-seatbid short-circuit |
| `makeBidsShouldReturnBannerBid` (× media types declared in YAML) | Bid-type resolution per format |
| `makeBidsShouldReturnErrorOnInvalidResponseBody` | `DecodeException → BidderError.badServerResponse` path |

### 6.4 F-new-60 trap reminder

Test method names MUST be camelCase (`^[a-z][a-zA-Z0-9]*$`). Snake_case (e.g., `scenario_for_app_simple_banner`) is the `port-go2java` D2.8 emit defect. Flag any `@Test` method with `_` in the name as **FAIL** (caught by checkstyle `MethodName` — see `framework-utilities-java.md` §4.4 + §6.2).

### 6.5 No live HTTP calls

Unit tests must NOT call real HTTP endpoints. The adapter's contract is "return `HttpRequest<BidRequest>` builder; framework executes." Mock at the `CurrencyConversionService` level, not at the network level.

---

## 7. IT test class (`it/{X}Test.java`) anatomy

### 7.1 Canonical skeleton (per Kobler — `KoblerTest.java`)

```java
package org.prebid.server.it;
// ... WireMock static imports + io.restassured.Response + JSONException + JUnit5 ...

public class {X}Test extends IntegrationTest {

    @Test
    public void openrtb2AuctionShouldRespondWithBidsFromThe{X}Bidder() throws IOException, JSONException {
        // given
        WIRE_MOCK_RULE.stubFor(post(urlPathEqualTo("/{x}-exchange"))
                .withRequestBody(equalToJson(
                        jsonFrom("openrtb2/{x}/test-{x}-bid-request.json")))
                .willReturn(aResponse().withBody(
                        jsonFrom("openrtb2/{x}/test-{x}-bid-response.json"))));

        // when
        final Response response = responseFor("openrtb2/{x}/test-auction-{x}-request.json",
                Endpoint.openrtb2_auction);
        // then
        assertJsonEquals("openrtb2/{x}/test-auction-{x}-response.json", response, singletonList("{x}"));
    }
}
```

### 7.2 Reviewer checklist

- **`package org.prebid.server.it;`** — IT classes live in their own package (NOT `org.prebid.server.bidder.{x}`).
- **`extends IntegrationTest`** — base class provides `WIRE_MOCK_RULE`, `responseFor`, `assertJsonEquals`, `jsonFrom` helpers. Deviation is **FAIL**.
- **`@TestPropertySource` URL override** — when the IT class needs to override defaults beyond `test-application.properties`, add: `@TestPropertySource(locations = "test-application.properties", properties = { "auction.host.skip-validation=true" })`. Most adapters don't need this; presence is **INFO** unless justified.
- **`@Test public void openrtb2AuctionShouldRespondWithBidsFromThe{X}Bidder() throws IOException, JSONException`** — canonical method name + signature. The `openrtb2AuctionShouldRespondWith*` prefix is for happy-path; other prefixes for error paths.
- **`urlPathEqualTo("/{x}-exchange")`** — MUST match the `test-application.properties` `adapters.{x}.endpoint=http://localhost:8090/{x}-exchange` value. Mismatch is the F-new-96 trap. **Cross-skill with `pr-triage-java`** (owns the properties file).
- **`equalToJson(...)`** for strict JSON equality. Deviations (`urlEqualTo` instead of `urlPathEqualTo`, `containing` instead of `equalToJson`) are **WARN** unless special-cased.
- **`responseFor(...)` + `assertJsonEquals(...)`** — canonical close. The `singletonList("{x}")` is the bidder name for ID-stripping in the comparison. For per-alias IT classes, this is the alias name, NOT the parent.

### 7.3 4-file fixture set (Rule 36)

Each `@Test` method references EXACTLY these 4 fixture files. The fixtures are **owned by `bidder-params-java-pr-review`** but this skill verifies referential integrity:

| Fixture path | Purpose |
|---|---|
| `openrtb2/{x}/test-{x}-bid-request.json` | The bidder-bound request (what we send to upstream) |
| `openrtb2/{x}/test-{x}-bid-response.json` | The bidder's mock response (what WireMock returns) |
| `openrtb2/{x}/test-auction-{x}-request.json` | The inbound auction request (what PBS receives) |
| `openrtb2/{x}/test-auction-{x}-response.json` | The outbound auction response (what PBS returns) |

Missing fixtures are **FAIL** — IT class will fail to load. Pre-flag against the PR's fixture additions; cross-skill: this is a `bidder-params-java-pr-review` owner concern, but flag here too so the reviewer sees the dependency.

### 7.4 Multi-scenario IT classes

One scenario is sufficient for basic coverage. Multi-scenario IT classes (e.g., Rubicon's multi-folder pattern, multi-format adapters that need separate banner/video/native scenarios) are acceptable when the bidder genuinely needs multiple end-to-end paths. Adding many scenarios in a new-adapter PR without justification is **WARN**.

### 7.5 Per-alias IT classes (empire-parents)

When the parent bidder has aliases (canonical: Adverxo's empire — `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`), each alias gets its own per-alias IT class. Per-alias verifications layered on top of §7.2-7.3:

1. **Class name matches alias slug**: `{Alias}Test` where `Alias` is TitleCase of the alias slug. Mismatch is **FAIL** (checkstyle `OuterTypeFilename`).
2. **WireMock URL matches alias endpoint**: When the parent YAML's `aliases.{alias}.endpoint` declares a distinct endpoint, `urlPathEqualTo(...)` must match the corresponding `test-application.properties` `adapters.{parent}.aliases.{alias}.endpoint=...` entry.
3. **Per-alias fixture directory**: Per-alias fixtures live at `src/test/resources/org/prebid/server/it/openrtb2/{alias}/` — separate from the parent's directory. The 4-file Rule 36 set applies per alias.
4. **`assertJsonEquals` bidder name**: `singletonList("{alias}")` — the alias name, NOT the parent. Common `port-go2java` trap: emitting the parent name and silently breaking ID-stripping. Pre-flag as **FAIL**.
5. **Parent YAML / test-application.properties consistency**: Cross-skill with `bidder-config-pr-review` (parent YAML's `aliases:` block) and `pr-triage-java` (multi-bidder properties registry).

### 7.6 `singletonList("{x}")` vs `asList(seats)`

When multiple bidder names need ID-stripping (rare — typically a parent + alias both bid on the same auction), use `asList("{parent}", "{alias}")`. Single-bidder scenarios use `singletonList("{x}")` (the default Kobler pattern).

### 7.7 No imports of internal test helpers

IT classes should NOT import from `src/test/java/org/prebid/server/bidder/`. The IT surface is separate from unit tests by design.

---

## 8. Common F-new traps reviewer should pre-flag

The D2.8 cross-canary F-new findings catalog (21-row table mapping each F-new to symptom, owning skill, severity) lives in [`../../shared/framework-utilities-java.md`](../../shared/framework-utilities-java.md) §8. Reviewers cross-reference findings against that table — DO NOT duplicate here.

Quick filter: traps owned by **this skill** (`bidder-class-pr-review`) are F-new-50, 56, 60, 61, 64, 78, 86, 90, 91, 92, 93, 96, 100. Traps owned by **sibling skills** (forward as CROSS-SKILL findings per §9) are F-new-52, 57/57b/58/59/79 (`bidder-config-pr-review`) and F-new-66/67/69/72 (`bidder-config-pr-review` YAML).

When a finding overlaps with `--- PRIOR AGENT FINDINGS ---` or `--- PRIOR SOURCE SPEC COMPARISON ---` in the manifest, surface with the appropriate dedup phrase per SKILL Step 4.

---

## 9. Cross-skill concerns

When `bidder-class-pr-review` findings imply work for sibling skills, surface as `CROSS-SKILL: {description}` in the Step 5 summary:

| # | Trigger in this skill | Sibling skill / file | Surface phrase |
|---|---|---|---|
| 9.1 | Constructor signature changed | `bidder-config-pr-review` / `{X}Configuration.java` | `{X}Bidder constructor signature changed — verify bidderCreator lambda in {X}Configuration.java matches (F-new-57 trap)` |
| 9.2 | `parseImpExt` or any `imp.ext` access changed | `bidder-params-java-pr-review` / `ExtImp{X}.java` | `parseImpExt reads {field} — verify ExtImp{X}.java declares this field with matching @JsonProperty alias` |
| 9.3 | IT class references a new fixture path | `bidder-params-java-pr-review` / `it/openrtb2/{x}/*.json` | `IT class references {fixture-path} — verify bidder-params-java-pr-review includes the fixture file (Rule 36 4-file set)` |
| 9.4 | `makeBids` bid-type coverage gap | `bidder-config-pr-review` / `bidder-config/{x}.yaml` | `makeBids cannot return BidType.{type} but YAML declares it in meta-info — fix one side` |
| 9.5 | New per-alias IT class (`{Alias}Test.java`) | `bidder-config-pr-review` / parent YAML `aliases:` block | `New per-alias IT class {Alias}Test.java added — verify parent YAML's aliases.{alias} entry exists` |
| 9.6 | IT class `urlPathEqualTo(...)` value | `pr-triage-java` / `test-application.properties` | `IT class stubs urlPathEqualTo({path}) — verify test-application.properties adapters.{x}.endpoint matches` |

Rationale for each: F-new-57 (9.1) blocks compilation; ExtImp field-drift (9.2) silently nulls fields on deserialize; IT fixture absence (9.3) fails IT load; YAML/MakeBids drift (9.4) misroutes traffic; alias-YAML drift (9.5) blocks alias bidding; properties drift (9.6) makes WireMock stub miss real bidder traffic.

---

## 10. Co-located helper files

When `bidder/{x}/` contains additional `.java` files beyond `{X}Bidder.java`, this skill activates for them per its [activation](../SKILL.md#activation) section.

### 10.1 Naming conventions

| File pattern | Purpose | Examples |
|---|---|---|
| `{X}Util.java` | Static utility class scoped to the bidder package | `MediasquareUtil.java`, `HuaweiUtils.java` |
| `{X}Extractor.java` | Specialized extraction helper | `KueezExtractor.java` |
| `{X}ImpModifier.java`, `{X}Helper.java` | Descriptive helper | `KoblerImpModifier.java` (hypothetical) |
| `{X}Request.java`, `{X}Response.java` | Custom request/response DTOs (when `Bidder<{CustomType}>` is used per §2.5) | `MediasquareRequest.java`, `HuaweiAdsRequest.java` |
| `{X}AdmBuilder.java`, `{X}DeviceBuilder.java` | Builder-pattern helpers for complex field synthesis | `HuaweiAdmBuilder.java`, `HuaweiDeviceBuilder.java` |
| `{X}EndpointResolver.java` | Custom endpoint resolution class (rare — most adapters inline) | `HuaweiEndpointResolver.java` |
| `request/`, `response/` sub-packages | Sub-organized DTO packages for very large adapters | `bidder/mediasquare/request/`, `bidder/mediasquare/response/` |

### 10.2 Reviewer rules per [Workflow: Co-Located Helper Changed](../SKILL.md#workflow-co-located-helper-changed)

- **Necessity**: Helper must serve a clear purpose. Flag duplication of `BidderUtil` / `HttpUtil` / `JacksonMapper` logic as **WARN**.
- **Package statement**: MUST be `package org.prebid.server.bidder.{x};` (lowercase, no underscores). The F-new-50-adjacent trap caught by checkstyle `PackageName`.
- **Visibility**: Default to package-private (Java idiom for "internal to this package"). `public` requires justification.
- **Lombok on DTOs**: `@Value @Builder @Jacksonized` for immutable POJOs (the default). `@Data` on bidder-package DTOs is **WARN** — they should be immutable. See `framework-utilities-java.md` §2.
- **No mutable static state**: Static fields holding mutable collections / counters are **FAIL**.
- **Filename ↔ class name match**: `OuterTypeFilename` checkstyle rule (F-new-79).

### 10.3 Test colocation

A `{X}Util.java` typically has a `{X}UtilTest.java` sibling in the test tree (`bidder/{x}/{X}UtilTest.java`). When the helper has non-trivial logic, flag missing test coverage as **WARN** — Jacoco enforces 90% line coverage, so untested helpers tank coverage. See `framework-utilities-java.md` §5.

### 10.4 Activation scope

This skill activates for ANY `*.java` file under `src/main/java/org/prebid/server/bidder/{x}/` or `src/test/java/org/prebid/server/bidder/{x}/` — including helper Java files beyond `{X}Bidder.java` / `{X}BidderTest.java`. Sibling skills do NOT touch these files. See SKILL.md [Activation](../SKILL.md#activation).

---

## References

- [`../SKILL.md`](../SKILL.md) — the consumer of this file (Step 3 looks up workflows; Step 4 grounds verifications against §1-7 here)
- [`../../shared/framework-utilities-java.md`](../../shared/framework-utilities-java.md) — Spring DI, Lombok, Vert.x, JUnit5+AssertJ, Jacoco, checkstyle (CROSS-CUTTING — do not duplicate)
- [`../../pr-triage-java/SKILL.md`](../../pr-triage-java/SKILL.md) — the orchestrator emitting the routing manifest this skill consumes
- [`../../bidder-config-pr-review/SKILL.md`](../../bidder-config-pr-review/SKILL.md) — sibling skill; cross-skill concerns: constructor↔lambda (§9.1), YAML capabilities (§9.4), alias declarations (§9.5)
- [`../../bidder-params-java-pr-review/SKILL.md`](../../bidder-params-java-pr-review/SKILL.md) — sibling skill; cross-skill concerns: ExtImp{X} POJO (§9.2), IT fixtures (§9.3)
- [`../../../../read/skills/read-bidder-class/SKILL.md`](../../../../read/skills/read-bidder-class/SKILL.md) — read-side companion; emits `bidder_class.*`, `code.make_requests.*`, `code.make_bids.*` fields this skill verifies
- [`../../../../../prebid-server-go/review/skills/adapter-code-pr-review/references/adapter-code-index.md`](../../../../../prebid-server-go/review/skills/adapter-code-pr-review/references/adapter-code-index.md) — Go-side analog
- [`../../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) — Rules 5, 9, 19, 22, 30, 35, 36
- D2.8 cross-canary findings: `docs/runs/d2.8-cross-canary-summary.md`
- F4 design doc: `docs/methodology/java-review-skill-design.md`

---

## Sources

- `prebid/prebid-server-java` master @ SHA `a1fe64e123d6` (verified 2026-05-04)
- `src/main/java/org/prebid/server/bidder/Bidder.java` (the interface)
- `src/main/java/org/prebid/server/bidder/kobler/KoblerBidder.java` (canonical reference adapter — Rule 35 + currency + ext-prebid bid-type)
- `src/main/java/org/prebid/server/bidder/adkerneladn/AdkernelAdnBidder.java` (bare constructor + per-key dispatch)
- `src/main/java/org/prebid/server/bidder/adverxo/AdverxoBidder.java` (currency-converting constructor)
- `src/main/java/org/prebid/server/bidder/mediasquare/MediasquareBidder.java` (custom request type — `Bidder<MediasquareRequest>`)
- `src/main/java/org/prebid/server/bidder/huaweiads/HuaweiAdsBidder.java` (custom request type + co-located helper package)
- `src/main/java/org/prebid/server/util/BidderUtil.java` (`defaultRequest`, `impIds`, `shouldConvertBidFloor`, `getBidType`)
- `src/main/java/org/prebid/server/util/HttpUtil.java` (`validateUrl`, `headers`)
- `src/test/java/org/prebid/server/it/KoblerTest.java` (canonical IT test class shape)
