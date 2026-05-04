# Java framework utilities (read-side companion + port-side reference)

Phase D1.3 deliverable — documents the prebid-server-java framework utilities that adapters call. Read-side: the read skills surface usages of these utilities in `code.*` fields. Port-side: `port-go2java`'s emission templates call these utilities — emitting an adapter that reinvents them is a code-review decline trigger.

This file mirrors the Go-side read skill's `read-adapter-code/references/framework-utilities-go.md` (its Java companion). It lives at the Java tree's shared directory because it's referenced by both the Java read skills and the port-go2java SKILL templates.

## 1. Source-of-truth pinning

Sourced from upstream `prebid/prebid-server-java` master at SHA `a1fe64e123d6` (verified 2026-05-04 per [`../../../../docs/methodology/repo-rules.md`](../../../../docs/methodology/repo-rules.md)).

When upstream amends a utility's signature, regenerate the relevant template AND bump the SHA pin in the same PR.

## 2. Utility catalog

### 2.1 `BidderUtil` (`org.prebid.server.bidder.BidderUtil`)

Static helpers for common adapter operations:

| Method | Purpose | Port-skill usage |
|---|---|---|
| `defaultRequest(BidRequest, URL, byte[], Map<String,String>)` | Construct an `HttpRequest<BidRequest>` with default `Content-Type: application/json` + `Accept: application/json` headers. | The most common call from `makeHttpRequests` — emit this when source spec's `code.make_requests.batching.rules` is `single-batched` and headers are standard. |
| `headers(MultiMap)` | Convert Vert.x `MultiMap` to a flat `Map<String,String>`. | Rare; emitted when source spec's `headers_constructed.collapse_helper` is true. |

### 2.2 `BidderDeps` + `BidderDepsAssembler`

Spring-DI container for per-bidder dependencies. Generated via `BidderDepsAssembler` in the `{Bidder}Configuration` class:

```java
@Bean
public BidderDeps {bidder}BidderDeps(...) {
    return BidderDepsAssembler.<{Bidder}BidderConfigurationProperties>forBidder(BIDDER_NAME)
        .withConfig(configurationProperties)
        .bidderInfo(bidderInfoCreator()::create)
        .usersyncerCreator(...)
        .bidderCreator(config -> new {Bidder}Bidder(config.getEndpoint(), mapper))
        .assemble();
}
```

The `{Bidder}Configuration` template emits this assembly idiom. Variations the template handles:

- **Plain config form**: `withConfig(configurationProperties)` references the standard Java map of properties.
- **Typed-subclass form** (Rule 35 applied, e.g., Adverxo): `withConfig(typedConfigurationProperties)` with a `BidderConfigurationProperties` subclass declared in the same file.

### 2.3 `JacksonMapper` (`org.prebid.server.json.JacksonMapper`)

The framework's canonical JSON serializer. Wraps a configured `ObjectMapper`. **The only acceptable JSON serializer in adapter code** — `io.vertx.core.json.Json` is banned by checkstyle.

Usage in adapter code:

```java
private final JacksonMapper mapper;

// ... in MakeRequests:
final byte[] body = mapper.encodeToBytes(outgoingRequest);

// ... in MakeBids:
final BidResponse bidResponse = mapper.decodeValue(httpCall.getResponse().getBody(), BidResponse.class);
```

Templates emit `mapper.encodeToBytes(...)` / `mapper.decodeValue(...)`. NEVER emit `Json.encode(...)` or `Json.decodeValue(...)` (the banned Vert.x API).

### 2.4 `CurrencyConversionService` (`org.prebid.server.currency.CurrencyConversionService`)

Constructor-injected via the `{Bidder}Configuration` `BidderDepsAssembler`. Used when source spec's `currency_conversion.used == true`:

```java
@Component
public class {Bidder}Bidder implements Bidder<BidRequest> {
    private final CurrencyConversionService currencyConversionService;

    public {Bidder}Bidder(String endpoint, JacksonMapper mapper, CurrencyConversionService currencyConversionService) {
        this.currencyConversionService = currencyConversionService;
        ...
    }

    // ... in MakeBids:
    final BigDecimal converted = currencyConversionService.convertCurrency(bid.getPrice(), bidRequest, fromCur, toCur);
}
```

The Go side handles currency conversion via `reqInfo.ConvertCurrency` (function-arg injection). Cross-language: same algorithm, different injection idiom.

### 2.5 `HttpUtil` (`org.prebid.server.util.HttpUtil`)

Static URL/header helpers:

| Method | Purpose |
|---|---|
| `addHeaderIfValueIsNotEmpty(MultiMap, String name, String value)` | Conditional header (skips empty values). Used for `User-Agent`, `X-Forwarded-For` propagation. |
| `addHeaderIfValueIsNotBlank(MultiMap, String name, String value)` | Same but trims whitespace before checking. |
| `headers()` | Returns a `MultiMap` pre-populated with `Content-Type: application/json;charset=utf-8` + `Accept: application/json`. The Rule 19 collapse helper. |

The Rule 19 prose calls out `HttpUtil.headers()` collapsing — emit it when the adapter's headers are exactly the two defaults. Otherwise emit explicit `MultiMap.caseInsensitiveMultiMap().add(...)` calls.

### 2.6 `BidderInfoCreator` (`org.prebid.server.spring.config.bidder.BidderInfoCreator`)

Per-bidder factory that consumes the `bidder-config/{bidder}.yaml` and produces a `BidderInfo` POJO. Used inside `{Bidder}Configuration`:

```java
@Bean
public BidderInfoCreator {bidder}BidderInfoCreator() {
    return new BidderInfoCreator(yamlMapper);
}
```

Templates emit this factory bean. The `BidderInfoCreator` reads the YAML file at startup; the YAML is the source of truth for endpoint, geoscope, capabilities, etc.

### 2.7 `ImpUtil` (`org.prebid.server.bidder.ImpUtil`)

Common imp-walking helpers:

| Method | Purpose |
|---|---|
| `parseImpExt(Imp, JacksonMapper, Class<T>)` | Parse `imp.ext.bidder` into a typed POJO; throws `PreBidException` on malformed JSON. |
| `getImpIds(BidRequest)` | Extract distinct imp IDs (string list). |

The `parseImpExt` is the standard idiom for getting the bidder-extension struct out of an Imp. Templates use it with `ExtImp{Bidder}.class` as the target type.

## 3. Cross-language analog table

For cross-language readability (port-go2java and port-java2go can both reference this):

| Java helper | Go analog | Rule |
|---|---|---|
| `BidderUtil.defaultRequest(...)` | inline `&adapters.RequestData{Method: "POST", Uri: ..., Body: ..., Headers: ...}` | Rule 19 (helpers collapse Java; expand Go) |
| `JacksonMapper.encodeToBytes(...)` | `json.Marshal(...)` from `encoding/json` | Standard |
| `JacksonMapper.decodeValue(bytes, Class)` | `json.Unmarshal(bytes, &target)` | Standard |
| `CurrencyConversionService.convertCurrency(...)` | `reqInfo.ConvertCurrency(price, from, to)` | Rule 28 (currency injection idiom differs by language) |
| `HttpUtil.headers()` | `http.Header{}` + `Add("Content-Type", ...)` + `Add("Accept", ...)` | Rule 19 |
| `HttpUtil.addHeaderIfValueIsNotEmpty(...)` | `if value != "" { headers.Add(name, value) }` | Trivial inversion |
| `BidderInfoCreator + bidder-config/{bidder}.yaml` | `static/bidder-info/{bidder}.yaml` (loaded via `config.Adapter`) | Rule 1 (YAML topology) |
| `ImpUtil.parseImpExt(Imp, ...)` | `json.Unmarshal(imp.Ext, &target)` plus manual error wrapping | Java helper saves boilerplate |

## 4. Forbidden imports / patterns

The Java emission MUST NOT use:

- `io.vertx.core.json.Json` — banned by checkstyle (use `JacksonMapper`).
- `org.json.*` — not on the dependency list (use `JacksonMapper`).
- `org.apache.commons.io.*` — not on the dependency list except where pre-imported by another upstream class.
- `lombok.experimental.*` — keep to the stable Lombok subset (`@Builder`, `@Value`, `@AllArgsConstructor`, `@JsonProperty`).
- Static logging via `LoggerFactory.getLogger(...)` — adapter code is not expected to log; if logging is essential, use `org.prebid.server.log.ConditionalLogger` per upstream framework convention.

## 5. Provenance + maintenance

This doc was authored by Phase D1.3 from:

- Direct inspection of upstream merged adapters: `kobler`, `adverxo`, `aax`, `33across`, `vungle`, `thetradedesk`.
- The upstream porting guide at `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` (PR #3768).
- Cross-references to the Go-side read skill's `read-adapter-code/references/file-role-heuristics.md` to ensure the cross-language analog table is symmetric.

Refresh cadence: when an upstream PR amends a utility's signature or introduces a new utility relevant to adapter authoring. Surface changes via `scripts/sync-from-upstream.py` (which fingerprints utility-class file SHAs) and `scripts/audit-pr.py`.

## See also

- [`../../../../docs/methodology/port-skills-design.md`](../../../../docs/methodology/port-skills-design.md) — port-go2java SKILL design contract.
- [`../../port-go2java/references/java-artifact-shapes.md`](../../../port-go2java/references/java-artifact-shapes.md) — checkstyle + import-order + emission templates that call the utilities catalogued here.
- [`../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) Rules 19, 28, 30, 35 — the rules that drive emission of these utilities.
