# Port Translation Rules (Go ↔ Java)

37 explicit translation rules between Go and Java prebid-server adapter patterns, each anchored to an Adapter Specification field driver. Used by the future `port-go2java` and `port-java2go` skills as their translation contract. Two specs for the same bidder produced from each language MUST be consistent with these rules — a port that violates a rule surfaces as a port-fidelity warning.

---

## Table of Contents

| Section | Rules | Topic |
|---|---|---|
| [Imp.ext unmarshaling](#impext-unmarshaling-rules-3) | 1–3 | TypeReference / two-phase / free-form |
| [Mutation](#mutation-rules-4) | 4–7 | toBuilder / shallow-copy / schain / banner |
| [HTTP request construction](#http-request-construction-rules-3) | 8–10 | defaultRequest / Bidder<T> / per-imp |
| [Endpoint resolution](#endpoint-resolution-rules-5) | 11–15 | tokens / query / dev-prod / region / deploy-time |
| [Multi-imp grouping](#multi-imp-grouping-rules-3) | 16–18 | max-imps / pod / format-split |
| [Header construction](#header-construction-rules-3) | 19–21 | HttpUtil / basic-auth / HMAC |
| [Bid type resolution](#bid-type-resolution-rules-5) | 22–26 | by-mediatype / by-mtype / chain / by-shape / hardcoded |
| [Error emission](#error-emission-rules-3) | 27–29 | BadInput / BadServerResponse / FailedToMarshal |
| [Status code handling](#status-code-handling-rules-2) | 30–31 | canonical helpers / retcode-field |
| [Currency conversion](#currency-conversion-rules-1) | 32 | reqInfo vs CurrencyConversionService |
| [YAML and config](#yaml-and-config-rules-3) | 33–35 | aliases / unification / config-subclass |
| [Test fixture](#test-fixture-rules-2) | 36–37 | httpCalls vs 4-file split / per-alias IT |

---

## How to use this reference

Each rule names a Pattern, identifies the Adapter Specification field that drives the translation, shows a concrete master Go and Java code snippet pair, and notes edge cases. Rules are grouped by spec section. A porter consumes the spec, looks up each rule by its field driver, and applies the corresponding translation.

The rule numbers (1-31) are stable identifiers — port skills cite them by number in their output (e.g., "applied Rule 7: Multi-imp grouping per pod prefix").

---

## Imp.ext unmarshaling rules (3)

Driven by `code.make_requests.imp_ext_unmarshal.kind` and `mechanism_*`.

### Rule 1: Standard ExtPrebid two-phase wrapper

**Pattern**: Two-phase unmarshal — first to framework wrapper, then to bidder-specific params type.
**Spec field driver**: `code.make_requests.imp_ext_unmarshal.kind: standard-two-phase`

**Go code**:
```go
var bidderExt adapters.ExtImpBidder
if err := jsonutil.Unmarshal(imp.Ext, &bidderExt); err != nil {
    return nil, &errortypes.BadInput{Message: "Error parsing bidderExt object"}
}
var impExt openrtb_ext.ExtImpKobler
if err := jsonutil.Unmarshal(bidderExt.Bidder, &impExt); err != nil {
    return nil, &errortypes.BadInput{Message: "Error parsing impExt object"}
}
```

**Java code**:
```java
private static final TypeReference<ExtPrebid<?, ExtImpKobler>> KOBLER_EXT_TYPE_REFERENCE =
        new TypeReference<>() {};

private ExtImpKobler parseImpExt(Imp imp) {
    try {
        return mapper.mapper().convertValue(imp.getExt(), KOBLER_EXT_TYPE_REFERENCE).getBidder();
    } catch (IllegalArgumentException e) {
        throw new PreBidException(e.getMessage());
    }
}
```

**Notes**: This is the canonical path. The framework wrapper is `adapters.ExtImpBidder` (Go) or `ExtPrebid<?, T>` (Java). The bidder-specific type is byte-equal across languages by class/struct shape (json tags ↔ jackson annotations on the same field set). When a Go spec has `mechanism_go: jsonutil-two-phase`, the Java port emits `mechanism_java: typeref-extprebid`.

### Rule 2: Direct unmarshal to custom wrapper

**Pattern**: Skip the framework wrapper; unmarshal `imp.Ext` directly into a custom wrapper class.
**Spec field driver**: `code.make_requests.imp_ext_unmarshal.kind: direct` + `wrapper_type: <name>`

**Go code**:
```go
// Appnexus uses appnexusExtImp directly.
var appnexusExt appnexusExtImp
if err := jsonutil.Unmarshal(imp.Ext, &appnexusExt); err != nil {
    return nil, &errortypes.BadInput{Message: err.Error()}
}
```

**Java code**:
```java
private static final TypeReference<AppnexusExtImp> APPNEXUS_EXT_TYPE_REFERENCE =
        new TypeReference<>() {};

private AppnexusExtImp parseImpExt(Imp imp) {
    return mapper.mapper().convertValue(imp.getExt(), APPNEXUS_EXT_TYPE_REFERENCE);
}
```

**Notes**: Used when the bidder cannot fit the standard `bidder.{...}` shape inside `imp.ext.bidder` — typically because of a legacy field layout. The wrapper class is co-located in the proto/ directory (Java) or `openrtb_ext/` (Go). When porting, the wrapper type's field set must be byte-compatible across languages.

### Rule 3: Free-form (no proto)

**Pattern**: Adapter has no bidder-specific params — `imp.ext` is not unmarshaled.
**Spec field driver**: `code.make_requests.imp_ext_unmarshal.kind: none`

**Go code**:
```go
// Ogury — no imp.ext unmarshal; imps are filtered by presence of imp.ext.bidder.
for _, imp := range request.Imp {
    if imp.Ext == nil { continue }
    // ... pass through unchanged
}
```

**Java code**:
```java
// Ogury (Java) — no proto, no parseImpExt.
final List<Imp> filteredImps = bidRequest.getImp().stream()
        .filter(imp -> imp.getExt() != null)
        .toList();
```

**Notes**: When `kind: none`, neither language emits an `ExtImp{Xyz}` POJO/struct. The Go spec has no file under `openrtb_ext/imp_{xyz}.go`; the Java spec has no class under `proto/openrtb/ext/request/{xyz}/`. A porter must NOT generate one.

---

## Mutation rules (4)

Driven by `code.make_requests.mutation.entity_strategies` (cross-language) + `mutation.go_idiom` / `mutation.java_idiom` (per-language).

### Rule 4: Imp.toBuilder rebuild ↔ imp value-mutation

**Pattern**: Imp mutation reuses Lombok builder in Java and value-pointer mutation in Go.
**Spec field driver**: `code.make_requests.mutation.entity_strategies.Imp` + `mutation.{go|java}_idiom`

**Go code**:
```go
// Kobler — mutate imp value via index access.
for i := range sanitizedRequest.Imp {
    imp := &sanitizedRequest.Imp[i]
    if imp.BidFloor > 0 && imp.BidFloorCur != "" && strings.ToUpper(imp.BidFloorCur) != supportedCurrency {
        convertedValue, _ := reqInfo.ConvertCurrency(imp.BidFloor, imp.BidFloorCur, supportedCurrency)
        imp.BidFloor = convertedValue
        imp.BidFloorCur = supportedCurrency
    }
}
```

**Java code**:
```java
// Kobler (Java) — toBuilder rebuild.
private Imp modifyImp(BidRequest bidRequest, Imp imp) {
    final Price resolvedBidFloor = resolveBidFloor(imp, bidRequest);
    return imp.toBuilder()
            .bidfloor(resolvedBidFloor.getValue())
            .bidfloorcur(resolvedBidFloor.getCurrency())
            .build();
}
```

**Notes**: The cross-language strategy is `in-place` (Go) ↔ `immutable-rebuild` (Java). Lombok's `toBuilder()` produces a new instance with selected fields overridden; the Go pointer mutation modifies the existing slice element. A porter must confirm the Go side does NOT also mutate the input request received from the framework — Go specs that mutate `request.Imp[i]` directly without copying first violate Rule 5 (`current` Go-idiom flagged).

### Rule 5: Site/App copy-then-mutate ↔ Site/App toBuilder rebuild

**Pattern**: Site/App scrubbing (e.g., remove user-identifying fields) requires a copy in Go and a builder rebuild in Java.
**Spec field driver**: `code.make_requests.mutation.entity_strategies.Site` (or `.App`)

**Go code**:
```go
// Optidigital — copy-then-mutate.
if request.Site != nil {
    siteCopy := *request.Site
    siteCopy.Publisher = &openrtb2.Publisher{ID: pubID}
    request.Site = &siteCopy
}
```

**Java code**:
```java
// Optidigital (Java) — toBuilder rebuild.
final BidRequest modifiedRequest = bidRequest.toBuilder()
        .site(bidRequest.getSite() != null
                ? bidRequest.getSite().toBuilder()
                        .publisher(Publisher.builder().id(pubID).build())
                        .build()
                : null)
        .build();
```

**Notes**: Strategy is `copy-then-mutate` (Go, `mutation.go_idiom: shallow-copy`) ↔ `immutable-rebuild` (Java, `mutation.java_idiom: lombok-tobuilder`). The Go port should use `ptrutil.Clone` for deep-copy when nested pointers (Publisher) are also mutated; the Java port handles deep-copy implicitly via builders.

### Rule 6: Source schain manipulation

**Pattern**: schain (supply-chain) manipulation in `request.Source` — typically appending a node.
**Spec field driver**: `code.make_requests.mutation.entity_strategies.Source`

**Go code**:
```go
// Adapter appends a schain node.
sourceCopy := ptrutil.Clone(request.Source)
sourceCopy.Ext = appendSchainNode(sourceCopy.Ext, newNode)
request.Source = sourceCopy
```

**Java code**:
```java
final Source modifiedSource = bidRequest.getSource() != null
        ? bidRequest.getSource().toBuilder()
                .ext(appendSchainNode(bidRequest.getSource().getExt(), newNode))
                .build()
        : Source.builder().ext(...).build();

final BidRequest modifiedRequest = bidRequest.toBuilder().source(modifiedSource).build();
```

**Notes**: schain manipulation requires deep-copy because `source.ext.schain.nodes` is a nested pointer. Go MUST use `ptrutil.Clone` (`mutation.go_idiom: ptrutil.Clone`); a `shallow-copy` here leaks mutations back into the framework's request. Java's `toBuilder` chain is deep-copy by default.

### Rule 7: Banner format dimension promotion

**Pattern**: When `imp.banner.w/h` are missing but `imp.banner.format[0]` has dimensions, promote the first format's dimensions to top-level w/h.
**Spec field driver**: `code.make_requests.mutation.entity_strategies.Banner`

**Go code**:
```go
if banner.W == nil && banner.H == nil && len(banner.Format) > 0 {
    bannerCopy := *banner
    w := banner.Format[0].W
    h := banner.Format[0].H
    bannerCopy.W = &w
    bannerCopy.H = &h
    imp.Banner = &bannerCopy
}
```

**Java code**:
```java
final Banner banner = imp.getBanner();
if (banner != null && banner.getW() == null && banner.getH() == null
        && CollectionUtils.isNotEmpty(banner.getFormat())) {
    final Format firstFormat = banner.getFormat().get(0);
    final Banner modifiedBanner = banner.toBuilder()
            .w(firstFormat.getW())
            .h(firstFormat.getH())
            .build();
    imp = imp.toBuilder().banner(modifiedBanner).build();
}
```

**Notes**: Common pattern for adapters that send only top-level w/h (legacy bidder protocols). Both Go and Java specs emit `entity_strategies.Banner: copy-then-mutate` (Go) or `immutable-rebuild` (Java).

---

## HTTP request construction rules (3)

Driven by `code.make_requests.request_body.kind` and `bidder_class.parameterized_request_type` (Java).

### Rule 8: BidderUtil.defaultRequest passthrough ↔ standard RequestData

**Pattern**: A thin wrapper that produces a single OpenRTB-shaped request with default headers.
**Spec field driver**: `code.make_requests.request_body.kind: openrtb2-passthrough` + `code.make_requests.batching.rules: [single-batched]`

**Go code**:
```go
requestJSON, err := jsonutil.Marshal(modifiedRequest)
if err != nil { return nil, []error{err} }

headers := http.Header{}
headers.Add("Content-Type", "application/json;charset=utf-8")

return []*adapters.RequestData{{
    Method:  http.MethodPost,
    Uri:     a.endpoint,
    Body:    requestJSON,
    Headers: headers,
    ImpIDs:  openrtb_ext.GetImpIDs(modifiedRequest.Imp),
}}, nil
```

**Java code**:
```java
final HttpRequest<BidRequest> httpRequest = BidderUtil.defaultRequest(modifiedRequest, endpoint, mapper);
return Result.of(Collections.singletonList(httpRequest), errors);
```

**Notes**: Java has the `BidderUtil.defaultRequest` helper that bundles JSON marshal + headers + URL into one call. Go has no equivalent helper — the boilerplate is repeated per adapter. A porter going Java→Go must expand the helper inline; Go→Java must collapse the boilerplate to the helper call. ImpIDs is mandatory on Go's RequestData; Java's `BidderUtil.defaultRequest` populates impIDs internally.

### Rule 9: Custom-typed body via Bidder<T> generic

**Pattern**: Adapter's request body is NOT an OpenRTB BidRequest — it's a custom shape.
**Spec field driver**: `code.make_requests.request_body.kind: custom` + `bidder_class.parameterized_request_type: <CustomType>` (Java) / `code.make_requests.request_body.custom_body_type: <type>` (Go)

**Go code**:
```go
// Mediasquare — custom request body.
type mediasquareRequest struct {
    Codes []mediasquareCode `json:"codes"`
    Gdpr  *gdprBody         `json:"gdpr,omitempty"`
}

mediasquareReq := mediasquareRequest{...}
requestJSON, err := jsonutil.Marshal(mediasquareReq)
```

**Java code**:
```java
// Mediasquare (Java) — Bidder<MediasquareRequest>.
public class MediasquareBidder implements Bidder<MediasquareRequest> {
    @Override
    public Result<List<HttpRequest<MediasquareRequest>>> makeHttpRequests(BidRequest bidRequest) {
        final MediasquareRequest payload = MediasquareRequest.of(...);
        // Framework will marshal MediasquareRequest, not BidRequest.
    }
}
```

**Notes**: Java parameterizes the `Bidder<T>` interface with the custom type, letting the framework handle marshal. Go has no parameterization — the adapter explicitly marshals the custom struct via `jsonutil.Marshal`. A porter must surface `imp-flatten-aggregate` in `batching.rules[]` when a multi-imp request collapses into a single custom payload (Mediasquare's `codes[]` array carries multiple imp-derived codes in one request).

### Rule 10: Per-imp split with macro substitution

**Pattern**: One HTTP request per imp, with the endpoint URL macro-substituted from imp-level ext data.
**Spec field driver**: `code.make_requests.batching.rules: [{ kind: per-imp }]` + `endpoint_resolution.kind: single-token-substitution`

**Go code**:
```go
for i := range request.Imp {
    impExt, _ := parseImpExt(&request.Imp[i])
    endpoint := strings.Replace(a.endpointTemplate, "{{.AccountID}}", impExt.AccountID, 1)
    // ... build single-imp body, append RequestData
}
```

**Java code**:
```java
final List<HttpRequest<BidRequest>> requests = new ArrayList<>();
for (Imp imp : bidRequest.getImp()) {
    final ExtImpXyz impExt = parseImpExt(imp);
    final String endpoint = endpointUrl.replace("{{.AccountID}}", impExt.getAccountId());
    final BidRequest singleImpRequest = bidRequest.toBuilder().imp(List.of(imp)).build();
    requests.add(BidderUtil.defaultRequest(singleImpRequest, endpoint, mapper));
}
```

**Notes**: Per-imp split is structurally common but each instance must be examined: some bidders split per-imp ALWAYS (adagio); some split only on multi-format imps (adkernel multi-format); some split per-deal not per-imp (rubicon — see Rule 18). The spec's `batching.rules[]` ordered list disambiguates.

---

## Endpoint resolution rules (5)

Driven by `code.make_requests.endpoint_resolution.kind` + `mechanism_*`.

### Rule 11: Single-token substitution

**Pattern**: One macro field substituted at request time.
**Spec field driver**: `endpoint_resolution.kind: single-token-substitution` + `macro_field_set: [<field>]`

**Go code**:
```go
// Adagio — uses text/template parsed at Builder time.
type adapter struct {
    endpointTemplate *template.Template
}

func Builder(...) (adapters.Bidder, error) {
    tmpl, err := template.New("endpoint").Parse(config.Endpoint)
    if err != nil { return nil, err }
    return &adapter{endpointTemplate: tmpl}, nil
}

func (a *adapter) buildEndpoint(accountID string) (string, error) {
    var buf strings.Builder
    err := a.endpointTemplate.Execute(&buf, macros.EndpointTemplateParams{AccountID: accountID})
    return buf.String(), err
}
```

**Java code**:
```java
// Java equivalent — string-replace.
private String buildEndpoint(String accountId) {
    return endpointUrl.replace("{{.AccountID}}", accountId);
}
```

**Notes**: Go parses the template at Builder time (signal: `template_parsed_at_build: true` in spec). Java uses string replace. The macro field set MUST be a subset of `macros.EndpointTemplateParams` (18-field list — see `review/skills/shared/framework-utilities.md`). When porting, a porter must verify the Java `replace()` covers ALL macros the Go template accepts — silent missing macros resolve to empty string at runtime.

### Rule 12: Query parameter augmentation

**Pattern**: Endpoint URL has query params appended at request time.
**Spec field driver**: `endpoint_resolution.kind: query-parameter-augmentation` + `mechanism_go: net/url` / `mechanism_java: URIBuilder`

**Go code**:
```go
// Appnexus — member_id query param.
parsedURL, err := url.Parse(a.endpoint)
if err != nil { return nil, []error{err} }
q := parsedURL.Query()
q.Set("member_id", memberID)
parsedURL.RawQuery = q.Encode()
endpoint := parsedURL.String()
```

**Java code**:
```java
// Appnexus (Java) — URIBuilder.
final String endpoint;
try {
    endpoint = new URIBuilder(endpointUrl)
            .addParameter("member_id", memberId)
            .build()
            .toString();
} catch (URISyntaxException e) {
    throw new PreBidException(e.getMessage());
}
```

**Notes**: Both languages use a structured URI builder rather than string concatenation (which would fail to URL-encode special characters). A porter must NOT translate to `endpoint + "?member_id=" + memberId` — that's a fidelity violation.

### Rule 13: Dev-prod toggle

**Pattern**: Endpoint chosen between two literal URLs based on a request-time flag.
**Spec field driver**: `endpoint_resolution.kind: dev-prod-toggle`

**Go code**:
```go
// Kobler — testMode toggle.
endpoint := a.endpoint
if testMode { endpoint = a.devEndpoint }
```

**Java code**:
```java
// Kobler (Java) — same toggle.
final String endpoint = isTest(imps.getFirst(), errors) ? devEndpoint : endpointUrl;
```

**Notes**: The dev endpoint is a SECOND literal URL stored in adapter state. In Go-Kobler it's a hardcoded `const devBidderEndpoint = "..."` (anti-pattern: surfaces as quirk `hardcoded-config-as-anti-pattern`). In Java-Kobler it's promoted to YAML `dev-endpoint:` config and injected via `KoblerConfigurationProperties.devEndpoint`. Cross-language ports SHOULD promote the dev endpoint to YAML config — Java did this for Kobler, fixing the Go-side anti-pattern. Surfaces as quirk `dev-endpoint-config-promotion`.

### Rule 14: Region from country (runtime-region-selection)

**Pattern**: Endpoint URL chosen at runtime based on a request-context field (typically `device.geo.country` or `regs.geo`).
**Spec field driver**: `endpoint_resolution.kind: runtime-region-selection`

**Go code**:
```go
// Huaweiads — region routing.
func chooseEndpoint(country string) string {
    switch country {
    case "RU": return endpointEU
    case "DE", "FR", "IT": return endpointEU
    default: return endpointGlobal
    }
}
```

**Java code**:
```java
private String chooseEndpoint(BidRequest bidRequest) {
    final String country = Optional.ofNullable(bidRequest.getDevice())
            .map(Device::getGeo).map(Geo::getCountry).orElse(null);
    return switch (country) {
        case "RU", "DE", "FR", "IT" -> endpointEu;
        default -> endpointGlobal;
    };
}
```

**Notes**: Region routing tables MUST be config-driven (YAML `extra_info` field), NOT hardcoded constants. Reviewer convention from PR #4076 (AdUp Tech). Adapters that hardcode the country→region map are flagged with quirk `hardcoded-config-as-anti-pattern`.

### Rule 15: Deploy-time tokens

**Pattern**: Endpoint URL has a non-Go-template placeholder that the operator substitutes pre-deployment.
**Spec field driver**: `endpoint_resolution.kind: deploy-time-token` + `deploy_time_tokens[]`

**Go code**:
```yaml
# static/bidder-info/rubicon.yaml — REGION token left for operator.
endpoint: "https://prebid-server.rubiconproject.com/openrtb2/auction?tk_xint=#{REGION}#"
disabled: true   # MUST be true while a deploy-time token is unresolved.
```

**Java code**:
```yaml
# src/main/resources/bidder-config/rubicon.yaml — same token shape.
adapters:
  rubicon:
    endpoint: "https://prebid-server.rubiconproject.com/openrtb2/auction?tk_xint=#{REGION}#"
    enabled: false
```

**Notes**: `#{REGION}#` is NOT a Go template macro — it's a placeholder the deployment operator substitutes via shell substitution / config templating before PBS starts. Adapters with unresolved deploy-time tokens MUST set `disabled: true` (Go) / `enabled: false` (Java) in YAML and include a comment block enumerating valid REGION values. Reference: PR #4502 appStockSSP `#{REGION}#`. The token surfaces in `deploy_time_tokens[]`, NOT `endpoint_construction.macros_used` (which is for runtime macros).

---

## Multi-imp grouping rules (3)

Driven by `code.make_requests.batching.rules[]`.

### Rule 16: max-imps-per-request split

**Pattern**: Imps split into batches of size N.
**Spec field driver**: `batching.rules: [{ kind: max-imps-per-request, max: <int> }]`

**Go code**:
```go
// Appnexus — max 10 imps per request.
const maxImpsPerRequest = 10

func (a *adapter) splitImps(imps []openrtb2.Imp) [][]openrtb2.Imp {
    var batches [][]openrtb2.Imp
    for i := 0; i < len(imps); i += maxImpsPerRequest {
        end := i + maxImpsPerRequest
        if end > len(imps) { end = len(imps) }
        batches = append(batches, imps[i:end])
    }
    return batches
}
```

**Java code**:
```java
private List<List<Imp>> splitImps(List<Imp> imps) {
    final List<List<Imp>> batches = new ArrayList<>();
    for (int i = 0; i < imps.size(); i += MAX_IMPS_PER_REQUEST) {
        batches.add(imps.subList(i, Math.min(i + MAX_IMPS_PER_REQUEST, imps.size())));
    }
    return batches;
}
```

**Notes**: The `max` value is a per-bidder constant. Both languages emit one HTTP request per batch. When composed with `pod-grouping` (Rule 17), grouping happens FIRST, then size-split inside each group. Spec emits `batching.applied_in_order: true` and `rules: [{ kind: max-imps-per-request, max: 10 }, { kind: pod-grouping, ... }]` — the order matters.

### Rule 17: Pod-grouping by imp.id prefix

**Pattern**: Group imps by `imp.id` prefix-before-underscore (video adpod use case).
**Spec field driver**: `batching.rules: [{ kind: pod-grouping, key: imp.id-prefix-before-underscore }]`

**Go code**:
```go
// Appnexus video adpod.
func groupByPod(imps []openrtb2.Imp) map[string][]openrtb2.Imp {
    groups := map[string][]openrtb2.Imp{}
    for _, imp := range imps {
        prefix := strings.SplitN(imp.ID, "_", 2)[0]
        groups[prefix] = append(groups[prefix], imp)
    }
    return groups
}
```

**Java code**:
```java
private Map<String, List<Imp>> groupByPod(List<Imp> imps) {
    return imps.stream().collect(Collectors.groupingBy(
            imp -> imp.getId().split("_", 2)[0]));
}
```

**Notes**: Each pod becomes one HTTP request. Composes with `max-imps-per-request` (Rule 16) — Appnexus does both. Spec MUST list `pod-grouping` before `max-imps-per-request` to express "group first, then size-split each group" semantics.

### Rule 18: Multi-format split (one request per media type)

**Pattern**: Imps with multiple media types split into one HTTP request per media type.
**Spec field driver**: `batching.rules: [{ kind: format-split, formats: [banner, video, native, audio] }]`

**Go code**:
```go
// Adkernel / Rubicon — one request per media type for multi-format imps.
for _, mediaType := range []openrtb_ext.BidType{BidTypeBanner, BidTypeVideo, BidTypeNative} {
    filteredImps := filterByMediaType(imps, mediaType)
    if len(filteredImps) == 0 { continue }
    // ... build separate request per media type
}
```

**Java code**:
```java
private List<HttpRequest<BidRequest>> splitByMediaType(BidRequest bidRequest) {
    final List<HttpRequest<BidRequest>> requests = new ArrayList<>();
    for (BidType mediaType : List.of(BidType.banner, BidType.video, BidType.xNative)) {
        final List<Imp> filtered = bidRequest.getImp().stream()
                .filter(imp -> hasMediaType(imp, mediaType))
                .toList();
        if (filtered.isEmpty()) continue;
        // ... build separate request per media type
    }
    return requests;
}
```

**Notes**: The `formats[]` order in the spec is significant — it determines the order of HTTP requests emitted. Composes with `deals-split` (Rubicon does both). When porting, the porter MUST preserve format order to keep deterministic test fixture matching.

---

## Header construction rules (3)

Driven by `headers_constructed`.

### Rule 19: Standard headers via HttpUtil.headers / hand-rolled http.Header

**Pattern**: Standard `Content-Type: application/json` + optional `Accept` + optional bidder-specific simple headers.
**Spec field driver**: `headers_constructed.per_request_dynamic: true` + `authentication_kind: none`

**Go code**:
```go
headers := http.Header{}
headers.Add("Content-Type", "application/json;charset=utf-8")
headers.Add("Accept", "application/json")
```

**Java code**:
```java
final MultiMap headers = HttpUtil.headers();
// HttpUtil.headers() pre-populates Content-Type and Accept.
```

**Notes**: `HttpUtil.headers()` (Java) is the canonical helper. Go has no equivalent — the boilerplate is per-adapter. A porter going Java→Go must expand the helper to explicit `Add` calls; Go→Java must replace the boilerplate with the helper call.

### Rule 20: Pre-built basic-auth header in constructor

**Pattern**: Authorization header pre-computed at construction time (basic-auth, no per-request data).
**Spec field driver**: `headers_constructed.pre_built_in_constructor: true` + `authentication_kind: basic-auth` + `authentication_input: [...]`

**Go code**:
```go
type adapter struct {
    endpoint    string
    authHeader  string  // Pre-computed at Builder time.
}

func Builder(name openrtb_ext.BidderName, cfg config.Adapter, server config.Server) (adapters.Bidder, error) {
    auth := base64.StdEncoding.EncodeToString([]byte(cfg.XAPI.Username + ":" + cfg.XAPI.Password))
    return &adapter{endpoint: cfg.Endpoint, authHeader: "Basic " + auth}, nil
}
```

**Java code**:
```java
public class RubiconBidder implements Bidder<BidRequest> {
    private final String authHeader;

    public RubiconBidder(String endpoint, String username, String password, ...) {
        this.authHeader = "Basic " + Base64.getEncoder().encodeToString(
                (username + ":" + password).getBytes(StandardCharsets.UTF_8));
    }
}
```

**Notes**: Pre-building avoids per-request CPU. Both languages compute the header once in the constructor. The `authentication_input` spec field lists the YAML config fields used (e.g., `["XAPI.Username", "XAPI.Password"]` for Rubicon — see `config.Adapter.XAPI` in `review/skills/shared/framework-utilities.md`).

### Rule 21: Per-request HMAC digest

**Pattern**: HMAC-SHA256 digest of the request body, included as a per-request header.
**Spec field driver**: `headers_constructed.per_request_dynamic: true` + `authentication_kind: hmac-digest`

**Go code**:
```go
// Huaweiads — per-request HMAC.
mac := hmac.New(sha256.New, []byte(secret))
mac.Write(requestBody)
digest := hex.EncodeToString(mac.Sum(nil))
headers.Add("Authorization", "Digest "+digest)
```

**Java code**:
```java
final Mac hmac = Mac.getInstance("HmacSHA256");
hmac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
final String digest = Hex.encodeHexString(hmac.doFinal(requestBody));
headers.set("Authorization", "Digest " + digest);
```

**Notes**: Per-request HMAC requires `pre_built_in_constructor: false` (the body changes per request). The secret comes from YAML config; the spec emits `authentication_input: [<secret-field>]`.

---

## Bid type resolution rules (5)

Driven by `code.make_bids.bid_type_resolution.method_chain[]`.

### Rule 22: by-imp-mediatype (default)

**Pattern**: Look up the source `imp` (matched by `bid.impid`); the imp's first non-nil media-type field determines the bid type.
**Spec field driver**: `bid_type_resolution.method_chain: [{ method: by-imp-mediatype, fallback_action: throw }]`

**Go code**:
```go
func getMediaTypeForImp(impID string, imps []openrtb2.Imp) (openrtb_ext.BidType, error) {
    for _, imp := range imps {
        if imp.ID == impID {
            switch {
            case imp.Banner != nil: return openrtb_ext.BidTypeBanner, nil
            case imp.Video != nil:  return openrtb_ext.BidTypeVideo, nil
            case imp.Native != nil: return openrtb_ext.BidTypeNative, nil
            case imp.Audio != nil:  return openrtb_ext.BidTypeAudio, nil
            }
        }
    }
    return "", &errortypes.BadServerResponse{Message: fmt.Sprintf("Unknown imp ID %s", impID)}
}
```

**Java code**:
```java
private BidType resolveBidType(String impId, List<Imp> imps) {
    return imps.stream()
            .filter(imp -> imp.getId().equals(impId))
            .findFirst()
            .map(imp -> {
                if (imp.getBanner() != null) return BidType.banner;
                if (imp.getVideo() != null) return BidType.video;
                if (imp.getXNative() != null) return BidType.xNative;
                if (imp.getAudio() != null) return BidType.audio;
                return null;
            })
            .orElseThrow(() -> new PreBidException("Unknown imp ID " + impId));
}
```

**Notes**: Default first step. The fallback_action `throw` produces `BadServerResponse` (Go) or `BidderError.badServerResponse` (Java). Note Java's `getXNative()` (the Java POJO renames `native` due to keyword collision).

### Rule 23: by-bid-mtype (canonical OpenRTB 2.6)

**Pattern**: Use `bid.mtype` directly — the canonical OpenRTB 2.6 field.
**Spec field driver**: `bid_type_resolution.method_chain: [{ method: by-bid-mtype, fallback_action: ... }]`

**Go code**:
```go
func getMediaTypeFromMType(bid openrtb2.Bid) (openrtb_ext.BidType, error) {
    switch bid.MType {
    case openrtb2.MarkupBanner: return openrtb_ext.BidTypeBanner, nil
    case openrtb2.MarkupVideo:  return openrtb_ext.BidTypeVideo, nil
    case openrtb2.MarkupAudio:  return openrtb_ext.BidTypeAudio, nil
    case openrtb2.MarkupNative: return openrtb_ext.BidTypeNative, nil
    }
    return "", &errortypes.BadServerResponse{...}
}
```

**Java code**:
```java
private BidType resolveBidType(Bid bid) {
    return switch (bid.getMtype()) {
        case 1 -> BidType.banner;
        case 2 -> BidType.video;
        case 3 -> BidType.audio;
        case 4 -> BidType.xNative;
        default -> throw new PreBidException("Unknown bid mtype " + bid.getMtype());
    };
}
```

**Notes**: Modern adapters use `bid.mtype` (canonical since OpenRTB 2.6, ~2022). Older adapters fall back to imp-mediatype lookup. A bidder that supports OpenRTB 2.6 SHOULD declare `ortb-version: "2.6"` in YAML (Java) — which is recorded in `bidder_info.ortb_version`.

### Rule 24: by-bid-ext-typed-field with chain

**Pattern**: Look up a typed field in `bid.ext` (e.g., `bid.ext.prebid.type`, `bid.ext.appnexus.bidAdType`).
**Spec field driver**: `bid_type_resolution.method_chain: [{ method: by-bid-ext-typed-field, fallback_action: next | return-default }, ...]`

**Go code**:
```go
// Kobler — bid.ext.prebid.type with default-banner fallback.
func getMediaTypeForBid(bid openrtb2.Bid) openrtb_ext.BidType {
    if bid.Ext != nil {
        var bidExt openrtb_ext.ExtBid
        err := jsonutil.Unmarshal(bid.Ext, &bidExt)
        if err == nil && bidExt.Prebid != nil {
            mediaType, err := openrtb_ext.ParseBidType(string(bidExt.Prebid.Type))
            if err == nil { return mediaType }
        }
    }
    return openrtb_ext.BidTypeBanner   // fallback_action: return-default
}
```

**Java code**:
```java
// Kobler (Java) — same chain via Optional.
private BidType getBidType(Bid bid) {
    return Optional.ofNullable(bid.getExt())
            .map(ext -> ext.get(EXT_PREBID))
            .filter(JsonNode::isObject)
            .map(ObjectNode.class::cast)
            .map(this::parseExtBidPrebid)
            .map(ExtBidPrebid::getType)
            .orElse(BidType.banner);   // fallback_action: return-default
}
```

**Notes**: The Kobler chain is single-step with `return-default`. Aax has a 3-step chain (`by-bid-ext-typed-field → by-imp-mediatype → throw`). Each step's `fallback_action` is one of `next`, `return-default`, `throw` — a porter must preserve the chain order and fallback semantics.

### Rule 25: by-response-payload-shape

**Pattern**: Inspect the response payload structure to determine bid type (e.g., `bid.video != null` → video).
**Spec field driver**: `bid_type_resolution.method_chain: [{ method: by-response-payload-shape, fallback_action: ... }]`

**Go code**:
```go
// Mediasquare custom response.
func mediaTypeFromMediasquareBid(bid mediasquareBid) openrtb_ext.BidType {
    if bid.Video != nil { return openrtb_ext.BidTypeVideo }
    if bid.Native != nil { return openrtb_ext.BidTypeNative }
    return openrtb_ext.BidTypeBanner
}
```

**Java code**:
```java
private BidType mediaTypeFromMediasquareBid(MediasquareBid bid) {
    if (bid.getVideo() != null) return BidType.video;
    if (bid.getNative() != null) return BidType.xNative;
    return BidType.banner;
}
```

**Notes**: Used only when the response is NOT OpenRTB-shaped (e.g., Mediasquare's custom payload). When the spec has `code.make_bids.response_type: custom`, this resolution method is typical.

### Rule 26: hardcoded fallback

**Pattern**: Always return a fixed media type. Single-mediatype adapters typically use `by-imp-mediatype` instead — `hardcoded` is rare and surfaces as a quirk for fidelity tracking.
**Spec field driver**: `bid_type_resolution.method_chain: [{ method: hardcoded }]` + `default_value: <type>`

**Go code**:
```go
// Forced banner.
return openrtb_ext.BidTypeBanner, nil
```

**Java code**:
```java
return BidType.banner;
```

**Notes**: Even single-mediatype adapters typically lookup by-imp-mediatype for safety. Hardcoded resolution surfaces as quirk `hardcoded-config-as-anti-pattern` because it skips imp validation.

---

## Error emission rules (3)

Driven by `code.make_requests` / `code.make_bids` error-return paths.

### Rule 27: BadInput (publisher-fault errors)

**Pattern**: Emit a `BadInput` error when the publisher's request is malformed.
**Spec field driver**: every error path with `errortypes.BadInput` (Go) / `BidderError.badInput` (Java).

**Go code**:
```go
return nil, []error{&errortypes.BadInput{Message: "Invalid imp.ext for impression " + imp.ID}}
```

**Java code**:
```java
errors.add(BidderError.badInput("Invalid imp.ext for impression " + imp.getId()));
```

**Notes**: Pointer form (`&errortypes.BadInput{...}`) is REQUIRED in Go — value form does not satisfy the error interface and won't compile. Java uses the static factory method `BidderError.badInput(...)`. Error messages should include the imp ID or index when generated inside an imp loop. Reference: `review/skills/shared/framework-utilities.md#error-type-taxonomy`.

### Rule 28: BadServerResponse (bidder-fault errors)

**Pattern**: Emit a `BadServerResponse` error when the upstream bidder returns invalid data.
**Spec field driver**: every error path with `errortypes.BadServerResponse` (Go) / `BidderError.badServerResponse` (Java).

**Go code**:
```go
return nil, []error{&errortypes.BadServerResponse{
    Message: fmt.Sprintf("Unexpected status code: %d. Run with request.debug = 1 for more info.", responseData.StatusCode),
}}
```

**Java code**:
```java
return Result.withError(BidderError.badServerResponse(
        "Unexpected status code: %d. Run with request.debug = 1 for more info.".formatted(statusCode)));
```

**Notes**: Pointer form required in Go. The 4xx/5xx case is typically auto-handled by the framework helpers (`adapters.CheckResponseStatusCodeForErrors` in Go, `HttpUtil.validateResponse` in Java) — but adapters with `http_status_handling.kind: legacy-raw-go` (e.g., kobler) hand-roll this.

### Rule 29: FailedToMarshal / FailedToUnmarshal

**Pattern**: Emit a typed error when adapter-side marshal/unmarshal fails.
**Spec field driver**: every error path with `errortypes.FailedToMarshal` / `FailedToUnmarshal`.

**Go code**:
```go
requestJSON, err := jsonutil.Marshal(modifiedRequest)
if err != nil {
    return nil, []error{&errortypes.FailedToMarshal{Message: err.Error()}}
}
```

**Java code**:
```java
try {
    final byte[] body = mapper.encodeToBytes(modifiedRequest);
} catch (EncodeException e) {
    errors.add(BidderError.badInput("Failed to encode: " + e.getMessage()));
}
```

**Notes**: Marshaling errors MUST NEVER be silently swallowed — production has shown shared-memory corruption causing `Marshal` to fail. If swallowed, the adapter panics with no diagnostic. Reviewer convention from PR #4614 (Go-side). Java's equivalent is `EncodeException` from `JacksonMapper`. The Java side typically wraps it in `BidderError.badInput` rather than a distinct `FailedToMarshal` type — this is a port-translation asymmetry: Go has 4 typed error types (`BadInput`, `BadServerResponse`, `FailedToMarshal`, `FailedToUnmarshal`), Java collapses them into 2 (`badInput`, `badServerResponse`).

---

## Status code handling rules (2)

Driven by `code.make_bids.http_status_handling.kind` + `application_status_handling`.

### Rule 30: Canonical 204+4xx framework helpers

**Pattern**: Use framework helpers to short-circuit on 204 (no content) and 4xx/5xx (server errors).
**Spec field driver**: `http_status_handling.kind: canonical-go-helpers` (Go) / `framework-default` (Java)

**Go code**:
```go
if adapters.IsResponseStatusCodeNoContent(responseData) { return nil, nil }
if err := adapters.CheckResponseStatusCodeForErrors(responseData); err != nil { return nil, []error{err} }
```

**Java code**:
```java
// Java framework auto-handles via HttpUtil.validateResponse — no adapter code needed.
// Optional empty-seatbid short-circuit:
if (CollectionUtils.isEmpty(bidResponse.getSeatbid())) return Collections.emptyList();
```

**Notes**: Go canonical helpers were introduced ~2024; older adapters (kobler) still use `legacy-raw-go` style. A porter Go→Java should NOT include explicit status checks (Java framework handles it); a porter Java→Go SHOULD use the canonical helpers (NOT `legacy-raw-go`).

### Rule 31: Application-layer retcode field

**Pattern**: Adapter checks an application-layer status field IN the response body, distinct from HTTP status.
**Spec field driver**: `application_status_handling.kind: retcode-field` + `field` + `success_codes` + `error_codes`

**Go code**:
```go
// Huaweiads — retcode field in response body.
type huaweiadsResponse struct {
    Retcode int `json:"retcode"`
    // ...
}

if response.Retcode != 200 {
    return nil, []error{&errortypes.BadServerResponse{
        Message: fmt.Sprintf("Application-level error: retcode=%d", response.Retcode),
    }}
}
```

**Java code**:
```java
@Value(staticConstructor = "of")
public class HuaweiAdsResponse {
    Integer retcode;
    // ...
}

if (response.getRetcode() != 200) {
    return Result.withError(BidderError.badServerResponse(
            "Application-level error: retcode=" + response.getRetcode()));
}
```

**Notes**: Application-layer status is rare — Huaweiads is the canonical example. The HTTP status is typically 200 in these cases (the upstream returns success at the transport layer); the application error is in the body. Spec emits BOTH `http_status_handling` (typically `framework-default`) AND `application_status_handling` populated with the field path and success/error code sets.

---

## Currency conversion rules (1)

Driven by `currency_conversion`.

### Rule 32: reqInfo.ConvertCurrency vs CurrencyConversionService.convertCurrency

**Pattern**: Convert a currency value (typically `imp.bidfloor`) from request currency to bidder-supported currency.
**Spec field driver**: `currency_conversion.used: true` + `helper.{go|java}_signature`

**Go code**:
```go
// Kobler.
func convertImpCurrency(imp *openrtb2.Imp, reqInfo *adapters.ExtraRequestInfo) error {
    if imp.BidFloor > 0 && imp.BidFloorCur != "" && strings.ToUpper(imp.BidFloorCur) != supportedCurrency {
        convertedValue, err := reqInfo.ConvertCurrency(imp.BidFloor, imp.BidFloorCur, supportedCurrency)
        if err != nil { return err }
        imp.BidFloor = convertedValue
        imp.BidFloorCur = supportedCurrency
    }
    return nil
}
```

**Java code**:
```java
// Kobler (Java).
private Price convertBidFloor(Price bidFloorPrice, BidRequest bidRequest) {
    final BigDecimal convertedPrice = currencyConversionService.convertCurrency(
            bidFloorPrice.getValue(),
            bidRequest,                          // bidRequest passed for time-context.
            bidFloorPrice.getCurrency(),
            DEFAULT_BID_CURRENCY);
    return Price.of(DEFAULT_BID_CURRENCY, convertedPrice);
}
```

**Notes**: Critical asymmetry — Java passes `bidRequest` for time-context (currency rates can vary by `request.tmax` / time-of-bid); Go does NOT pass any context. The spec emits `bid_request_passed_for_context: true` (Java) / `false` (Go). A port-fidelity violation appears when Go is ported to Java without adding the bidRequest arg, or when Java is ported to Go expecting time-context that Go cannot provide. Surfaces as quirk `currency-conversion-bidrequest-context`. Go's `ConvertCurrency` is available ONLY in `MakeRequests` (which receives `*ExtraRequestInfo`); `MakeBids` does NOT receive currency conversion access — see `review/skills/shared/framework-utilities.md`.

---

## YAML and config rules (3)

Driven by `bidder_info` + `cross_language.port_concerns`.

### Rule 33: Aliases inversion (child→parent vs parent→children)

**Pattern**: Go declares aliases on the child YAML (`aliasOf: parent`); Java declares aliases on the parent YAML (`aliases: { child: ~ }`).
**Spec field driver**: `cross_language.port_concerns.aliases_inverted: true`

**Go YAML** (child file: `static/bidder-info/connektai.yaml`):
```yaml
aliasOf: xeworks
gvlVendorID: 12345
```

**Java YAML** (parent file: `src/main/resources/bidder-config/xeworks.yaml`):
```yaml
adapters:
  xeworks:
    endpoint: "https://..."
    aliases:
      connektai: ~                            # tilde-syntax: inherit everything from xeworks.
```

**Notes**: A porter Go→Java must MOVE the alias declaration from the child file (delete) to the parent file's `aliases:` map. A porter Java→Go must SPLIT the parent's `aliases:` map into separate child YAML files. Both directions touch multiple files — atomic refactor.

### Rule 34: YAML unification (Go split vs Java unified)

**Pattern**: Go splits adapter config across `static/bidder-info/{xyz}.yaml` (info) + main `config.yaml` (endpoint). Java unifies into `src/main/resources/bidder-config/{xyz}.yaml`.
**Spec field driver**: `cross_language.port_concerns.yaml_unification: true`

**Go YAML** (`static/bidder-info/kobler.yaml`):
```yaml
endpoint: "https://bid.essrtb.com/bid/prebid_server_rtb_call"
endpointCompression: gzip
maintainer: { email: bidding-support@kobler.no }
geoscope: [NOR, SWE, DNK]
capabilities:
  site: { mediaTypes: [banner] }
  app:  { mediaTypes: [banner] }
```

**Java YAML** (`src/main/resources/bidder-config/kobler.yaml`):
```yaml
adapters:
  kobler:
    endpoint: "https://bid.essrtb.com/bid/prebid_server_rtb_call"
    dev-endpoint: "https://bid-service.dev.essrtb.com/bid/prebid_server_rtb_call"
    endpoint-compression: gzip
    geoscope: [NOR, SWE, DNK]
    meta-info:
      maintainer-email: bidding-support@kobler.no
      site-media-types: [banner]
      app-media-types: [banner]
      vendor-id: 0
```

**Notes**: Java's `meta-info` block flattens what Go nests under `capabilities.{site|app}.mediaTypes` into separate `site-media-types` / `app-media-types` lists. A porter Go→Java must transform the structure; Java→Go must split apart. Field name conventions also differ: Go uses camelCase (`endpointCompression`), Java uses kebab-case (`endpoint-compression`). The reader skills SHOULD detect mismatched field-name styles and surface as `yaml-field-name-typo` quirks.

### Rule 35: Custom property subclass for extra YAML fields

**Pattern**: Java declares custom YAML fields beyond the default `BidderConfigurationProperties` via a subclass. Go has no equivalent — extra fields go in `static/bidder-info/{xyz}.yaml` `extra_info:` (opaque JSON).
**Spec field driver**: `spring_config.configuration_properties_class.extra_fields[]` (Java) / `bidder_info.yaml_extra_fields` (Go)

**Java code**:
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

**Go YAML**:
```yaml
# static/bidder-info/kobler.yaml — Go has no Spring DI; extra config goes in extra_info.
extra_info: '{"dev_endpoint": "https://bid-service.dev.essrtb.com/bid/prebid_server_rtb_call"}'
```

**Notes**: Java's typed approach is preferred — gives validation (`@NotBlank`), type-safety, and field-level docs. Go's `extra_info` is opaque JSON parsed in the adapter. A porter Go→Java SHOULD promote each `extra_info` field into a typed `BidderConfigurationProperties` subclass field. Kobler's Java port did this for `devEndpoint` — fixing the Go-side `hardcoded-config-as-anti-pattern` quirk. Surfaces as quirk `dev-endpoint-config-promotion` (cross-language win).

---

## Test fixture rules (2)

Driven by `tests`.

### Rule 36: Go httpCalls array vs Java 4-file split

**Pattern**: Go test fixtures embed request/response inside a single JSON file's `httpCalls[]` array; Java splits each test case into 4 separate files.
**Spec field driver**: `tests.fixture_inventory.exemplary[]` (Go) / `tests.fixture_inventory.integration[]` (Java)

**Go fixture** (`adapters/kobler/koblertest/exemplary/site-simple_banner.json`):
```json
{
  "mockBidRequest": { "id": "test", "imp": [...], "site": {...} },
  "httpCalls": [
    {
      "expectedRequest": { "uri": "...", "body": {...} },
      "mockResponse":    { "status": 200, "body": {"seatbid": [...]} }
    }
  ],
  "expectedBidResponses": [...]
}
```

**Java fixture** (4-file split under `src/test/resources/org/prebid/server/it/openrtb2/kobler/`):
- `test-kobler-bid-request.json` — the outbound bid request to Kobler
- `test-kobler-bid-response.json` — the mock response from Kobler
- `test-auction-kobler-request.json` — the inbound auction request to PBS
- `test-auction-kobler-response.json` — the expected outbound auction response

**Notes**: When porting test fixtures, the porter MUST split the Go single-file fixture into 4 Java files (or merge 4 Java files into 1 Go file). The cross-language test harness checks structural parity: same number of cases on both sides, equivalent mock responses. Reference: see `review/skills/adapter-code-pr-review/references/adapter-code-index.md` for the Go fixture format details.

### Rule 37: Per-alias IT class requirement (Java-only)

**Pattern**: Each Java alias REQUIRES its own integration-test class + 4-file fixture set. Go aliases need NO test files (the parent's tests cover them).
**Spec field driver**: `aliases[].test_assets.{it_class, fixture_dir, fixture_file_count}` (Java) / `aliases[]` empty in Go

**Go YAML** (alias only):
```yaml
# static/bidder-info/connektai.yaml — single file, no tests.
aliasOf: xeworks
```

**Java setup** (alias requires 7 files):
```
src/main/resources/bidder-config/xeworks.yaml          # parent declares aliases: { connektai: ~ }
src/test/java/org/prebid/server/it/ConnektaiTest.java   # NEW IT class per alias.
src/test/resources/org/prebid/server/it/openrtb2/connektai/
    test-connektai-bid-request.json
    test-connektai-bid-response.json
    test-auction-connektai-request.json
    test-auction-connektai-response.json
src/test/resources/test-application.properties          # MODIFIED: append 2-4 lines.
```

**Notes**: This is the dominant Java-vs-Go test-fixture-cost asymmetry. Java alias PRs are ~7 files; Go alias PRs are ~1 file. A porter Go-alias→Java-alias must generate the IT class + 4 fixtures. The IT class name uses identifier-rule workarounds for digit-leading bidders (Rule 26 quirk: `152media` → `OneFiveTwoMediaTest`). The `test-application.properties` registry append is a separate concern — central registry edit.

---

## Summary

37 unique port-translation rules total (Rules 1-37, with Rules 5, 8, 9, 19, 29, 32, 33, 34, 35, 36, 37 being the cross-language asymmetry rules that surface as quirks in either direction). Each rule is keyed by an Adapter Specification field; a porter consumes the spec and applies rules in the order the spec emits them.

Cross-skill consumers:

- **`port-go2java`** — reads a Go-source spec, applies rules in Go→Java direction.
- **`port-java2go`** — reads a Java-source spec, applies rules in Java→Go direction.
- **Read skills** — emit specs that satisfy the rules' field drivers; flag quirks for cross-language asymmetries that cannot be auto-translated.
- **Future `diff-spec` skill** — compares two specs for the same bidder across commits or languages, citing rule numbers in the output.

For framework-level reference (helpers, error types, anti-patterns, EndpointTemplateParams 18-field list), see `review/skills/shared/framework-utilities.md`. For canonical schema, see `adapter-spec.md`. For enumerated values used in the spec, see `behavior-taxonomy.md`.

---

## Sources

- Phase 2 reconnaissance findings (in conversation): 17 Go edge cases + 17 Java edge cases identified across `optidigital, kobler, 33across, mediasquare, msft, appnexus, adkernel` (Go) and `kobler, adverxo, ogury, feedad, seedtag, optidigital, mediasquare, elementaltv, 152media` (Java) plus the broader 9-adapter Java behavior taxonomy stress-test (`appnexus, rubicon, generic, aax, adview, kobler, mediasquare, nextmillennium, huaweiads`).
- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27).
- `prebid/prebid-server-java` master at v3.41.0 (commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` as of 2026-04-22).
- `prebid-server-go/references/new-bid-adapter-prs.md` — 89 reference PRs with `Patterns Demonstrated` tags.
- `prebid-server-java/references/new-bid-adapter-prs.md` — 49 reference PRs with `Patterns Demonstrated` tags.
- Sibling shared file: `prebid-server-go/review/skills/shared/framework-utilities.md`.
- Sibling shared file: `prebid-server-go/read/skills/shared/adapter-spec.md`.
- Sibling shared file: `prebid-server-go/read/skills/shared/behavior-taxonomy.md`.
