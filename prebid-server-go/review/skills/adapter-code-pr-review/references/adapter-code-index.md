# Adapter Code Index

Patterns, conventions, and framework utilities for Prebid Server Go adapter implementations.

---

## Module path and drift

**Current major:** `github.com/prebid/prebid-server/v4` (since release v4.0.0, March 2026).
**Drift detection:** the `pr-triage` skill checks `go.mod` on master per its Step 2; the major version is updated here atomically when an upstream migration occurs.
**Note on PR diffs that show `v3` imports:** the v3 → v4 migration was a mechanical sweep on master, NOT a per-adapter change. PR diffs authored before that sweep can carry `v3` imports and still merge against `v4` master. Do NOT flag `v3` imports inside a PR diff as a stale-author error — only flag them in master.

For shared framework concerns (helper function table, error types, marshaling safety, endpoint template macros, anti-pattern list, test harness contract), see [../../shared/framework-utilities.md](../../shared/framework-utilities.md).

**Upstream sources (canonical):**
- Bidder interface: https://github.com/prebid/prebid-server/blob/master/adapters/bidder.go
- Test harness: https://github.com/prebid/prebid-server/blob/master/adapters/adapterstest/test_json.go
- Builder registry: https://github.com/prebid/prebid-server/blob/master/exchange/adapter_builders.go
- Bidder constants: https://github.com/prebid/prebid-server/blob/master/openrtb_ext/bidders.go
- Error types: https://github.com/prebid/prebid-server/blob/master/errortypes/errortypes.go

**Raw URLs (for fetching):**
- https://raw.githubusercontent.com/prebid/prebid-server/master/adapters/bidder.go
- https://raw.githubusercontent.com/prebid/prebid-server/master/adapters/adapterstest/test_json.go
- https://raw.githubusercontent.com/prebid/prebid-server/master/exchange/adapter_builders.go

> **Sync policy:** This file is a local snapshot. The `pr-triage` skill's Step 2 runs centralized drift checks against the live source on every review run; this skill's Step 1b reads those drift results from the manifest. If signatures or supported test directories change upstream, update this file to match.

---

## Bidder Interface

Every adapter must implement:

```go
type Bidder interface {
    MakeRequests(request *openrtb2.BidRequest, reqInfo *ExtraRequestInfo) ([]*RequestData, []error)
    MakeBids(request *openrtb2.BidRequest, requestData *RequestData, response *ResponseData) (*BidderResponse, []error)
}
```

---

## Builder Function Pattern

```go
func Builder(bidderName openrtb_ext.BidderName, config config.Adapter, server config.Server) (adapters.Bidder, error) {
    bidder := &adapter{
        endpoint: config.Endpoint,
    }
    return bidder, nil
}
```

**With template macro resolution:**
```go
func Builder(bidderName openrtb_ext.BidderName, config config.Adapter, server config.Server) (adapters.Bidder, error) {
    template, err := template.New("endpointTemplate").Parse(config.Endpoint)
    if err != nil {
        return nil, fmt.Errorf("unable to parse endpoint URL template: %v", err)
    }
    urlParams := macros.EndpointTemplateParams{AccountID: "{{.AccountID}}"}
    bidder := &adapter{
        endpointTemplate: template,
    }
    return bidder, nil
}
```

---

## Adapter Struct Pattern

```go
type adapter struct {
    endpoint string
}
```

Key rules:
- **Unexported** (`adapter`, not `Adapter`) — only `Builder` is exported
- Holds only **configuration** (endpoint URL, template)
- Must NOT hold request-scoped state, HTTP clients, or loggers
- The framework provides these via method parameters

---

## MakeRequests Pattern

### Standard (Single Request for All Impressions)

```go
func (a *adapter) MakeRequests(request *openrtb2.BidRequest, requestInfo *adapters.ExtraRequestInfo) ([]*adapters.RequestData, []error) {
    // Marshal the request
    requestJSON, err := jsonutil.Marshal(request)
    if err != nil {
        return nil, []error{err}
    }

    return []*adapters.RequestData{{
        Method:  http.MethodPost,
        Uri:     a.endpoint,
        Body:    requestJSON,
        Headers: makeHeaders(request),
        ImpIDs:  openrtb_ext.GetImpIDs(request.Imp),
    }}, nil
}
```

### Per-Impression (One Request Per Imp)

```go
func (a *adapter) MakeRequests(request *openrtb2.BidRequest, requestInfo *adapters.ExtraRequestInfo) ([]*adapters.RequestData, []error) {
    var requests []*adapters.RequestData
    var errors []error

    for i := range request.Imp {
        // Create a copy with single impression
        reqCopy := *request
        reqCopy.Imp = []openrtb2.Imp{request.Imp[i]}

        requestJSON, err := jsonutil.Marshal(reqCopy)
        if err != nil {
            errors = append(errors, err)
            continue
        }

        requests = append(requests, &adapters.RequestData{
            Method:  http.MethodPost,
            Uri:     a.endpoint,
            Body:    requestJSON,
            ImpIDs:  openrtb_ext.GetImpIDs(reqCopy.Imp),
        })
    }
    return requests, errors
}
```

### Imp Extension Unmarshaling

```go
// Standard two-phase unmarshaling
var bidderExt adapters.ExtImpBidder
if err := jsonutil.Unmarshal(imp.Ext, &bidderExt); err != nil {
    errors = append(errors, &errortypes.BadInput{
        Message: fmt.Sprintf("Invalid imp.ext for impression %s", imp.ID),
    })
    continue
}

var impExt openrtb_ext.ExtImp{Bidder}
if err := jsonutil.Unmarshal(bidderExt.Bidder, &impExt); err != nil {
    errors = append(errors, &errortypes.BadInput{
        Message: fmt.Sprintf("Invalid imp.ext.bidder for impression %s", imp.ID),
    })
    continue
}
```

### Marshal error safety

Marshaling errors must NEVER be silently swallowed — see [../../shared/framework-utilities.md#marshaling-error-safety](../../shared/framework-utilities.md#marshaling-error-safety) for the rule, code examples, and rationale (production shared-memory-corruption surfacing).

### Copy Semantics

**CRITICAL**: Never mutate shared request objects. Always copy before modifying:

```go
// Correct — copy site before modifying
siteCopy := *request.Site
publisherCopy := *siteCopy.Publisher
publisherCopy.ID = accountID
siteCopy.Publisher = &publisherCopy
request.Site = &siteCopy

// Wrong — mutates shared object
request.Site.Publisher.ID = accountID
```

### Required RequestData Fields

| Field | Required | Notes |
|-------|----------|-------|
| `Method` | Yes | Almost always `"POST"` |
| `Uri` | Yes | From adapter struct, not hardcoded |
| `Body` | Yes | Marshaled JSON request body |
| `ImpIDs` | Yes | `openrtb_ext.GetImpIDs(request.Imp)` — required for impression tracking |
| `Headers` | Recommended | At minimum `Content-Type: application/json` |

---

## MakeBids Pattern

```go
func (a *adapter) MakeBids(request *openrtb2.BidRequest, requestData *adapters.RequestData, responseData *adapters.ResponseData) (*adapters.BidderResponse, []error) {
    // 1. Handle no-content
    if adapters.IsResponseStatusCodeNoContent(responseData) {
        return nil, nil
    }

    // 2. Handle errors
    if err := adapters.CheckResponseStatusCodeForErrors(responseData); err != nil {
        return nil, []error{err}
    }

    // 3. Unmarshal response
    var response openrtb2.BidResponse
    if err := jsonutil.Unmarshal(responseData.Body, &response); err != nil {
        return nil, []error{err}
    }

    // 4. Build bid response
    bidResponse := adapters.NewBidderResponseWithBidsCapacity(len(request.Imp))
    bidResponse.Currency = response.Cur

    for _, seatBid := range response.SeatBid {
        for i, bid := range seatBid.Bid {
            bidType, err := getMediaTypeForBid(bid)
            if err != nil {
                return nil, []error{err}
            }
            bidResponse.Bids = append(bidResponse.Bids, &adapters.TypedBid{
                Bid:     &seatBid.Bid[i],  // pointer to slice element, NOT &bid
                BidType: bidType,
            })
        }
    }
    return bidResponse, nil
}
```

### Currency-overwrite hazard

`bidResponse.Currency = response.Cur` is unsafe — if `response.Cur` is empty (some bidders send empty currency on no-bid or error responses), this overwrites the default `"USD"` with an empty string, which downstream rejects. Always guard:

```go
// CORRECT
if response.Cur != "" {
    bidResponse.Currency = response.Cur
}

// WRONG (overwrites default USD with empty string)
bidResponse.Currency = response.Cur
```

Found in PR #4287 (Optidigital) merged unfixed — skill should flag adapters that copy this pattern as **WARN**.

### Bid Type Resolution

**Preferred: From bid.MType (OpenRTB 2.6)**
```go
func getMediaTypeForBid(bid openrtb2.Bid) (openrtb_ext.BidType, error) {
    switch bid.MType {
    case openrtb2.MarkupBanner:
        return openrtb_ext.BidTypeBanner, nil
    case openrtb2.MarkupVideo:
        return openrtb_ext.BidTypeVideo, nil
    case openrtb2.MarkupAudio:
        return openrtb_ext.BidTypeAudio, nil
    case openrtb2.MarkupNative:
        return openrtb_ext.BidTypeNative, nil
    default:
        return "", fmt.Errorf("unsupported media type for bid %s", bid.ImpID)
    }
}
```

**From impression lookup (fallback):**
```go
func getMediaTypeForImpID(impID string, imps []openrtb2.Imp) (openrtb_ext.BidType, error) {
    for _, imp := range imps {
        if imp.ID == impID {
            if imp.Banner != nil { return openrtb_ext.BidTypeBanner, nil }
            if imp.Video != nil { return openrtb_ext.BidTypeVideo, nil }
            if imp.Native != nil { return openrtb_ext.BidTypeNative, nil }
            if imp.Audio != nil { return openrtb_ext.BidTypeAudio, nil }
        }
    }
    return "", fmt.Errorf("no matching imp for bid %s", impID)
}
```

### Bid Pointer Safety

```go
// Correct — pointer to slice element
bidResponse.Bids = append(bidResponse.Bids, &adapters.TypedBid{
    Bid:     &seatBid.Bid[i],
    BidType: bidType,
})

// Wrong — pointer to loop variable (all bids point to last element)
for _, bid := range seatBid.Bid {
    bidResponse.Bids = append(bidResponse.Bids, &adapters.TypedBid{
        Bid:     &bid,  // BUG: all point to same variable
        BidType: bidType,
    })
}
```

---

## Framework Utilities

The framework helper function table (`adapters.IsResponseStatusCodeNoContent`, `adapters.CheckResponseStatusCodeForErrors`, `adapters.NewBidderResponseWithBidsCapacity`, `openrtb_ext.GetImpIDs`, `jsonutil.Marshal/Unmarshal`, `errortypes.*`, `macros.NewStringIndexBasedReplacer`, `ptrutil.Clone`), the `EndpointTemplateParams` 18-field macro list, and the error-type taxonomy live in [../../shared/framework-utilities.md](../../shared/framework-utilities.md). Adapter-code-pr-review workflows reference those tables directly — do not duplicate them here.

---

## Error Types

See [../../shared/framework-utilities.md#error-type-taxonomy](../../shared/framework-utilities.md#error-type-taxonomy) for the canonical mapping of `errortypes.BadInput`, `errortypes.BadServerResponse`, `errortypes.FailedToMarshal`, `errortypes.FailedToUnmarshal`, etc. — including metric implications and impID-in-message guidance.

---

## Test Runner Pattern

```go
package {bidder}

import (
    "testing"

    "github.com/prebid/prebid-server/v4/adapters/adapterstest"
    "github.com/prebid/prebid-server/v4/config"
    "github.com/prebid/prebid-server/v4/openrtb_ext"
)

func TestJsonSamples(t *testing.T) {
    bidder, buildErr := Builder(openrtb_ext.Bidder{Name}, config.Adapter{
        Endpoint: "https://fake.endpoint.test/bid"},
        config.Server{ExternalUrl: "http://hosturl.com", GvlID: 1, DataCenter: "2"})

    if buildErr != nil {
        t.Fatalf("Builder returned unexpected error %v", buildErr)
    }

    adapterstest.RunJSONBidderTest(t, "{bidder}test", bidder)
}
```

Key points:
- Function name: **exactly** `TestJsonSamples`
- Test directory: `{bidder}test` (no separator between name and "test")
- Endpoint should be a fake URL (not real)
- Builder error must be checked with `t.Fatalf`

### Supported test data directories

`adapters/adapterstest/test_json.go` supports five subdirectories under `<bidder>test/`:

| Directory | Purpose |
|-----------|---------|
| `exemplary/` | Happy-path fixtures (treated as documentation source) |
| `supplemental/` | Edge cases, error paths, unsupported scenarios |
| `amp/` | AMP-specific tests |
| `video/` | Video-specific tests (when adapter has substantial video logic) |
| `videosupplemental/` | Video edge cases / error paths |

Canonical test root name is `<bidder>test/`. Legacy alternates (e.g., `adapters/msft/test/`, `adapters/msft/test-extrainfo/`) are tolerated but new adapters should follow the canonical pattern.

Post-PR-#4592 framework changes (v3.30.0, November 2025): `RunJSONBidderTest` now asserts `expectedBidResponses[*].currency` against `BidderResponse.Currency`, and multi-request fixtures must match expected/actual entries 1:1. Older fixtures may need updating when touched.

---

## Test Data JSON Structure

### Exemplary (Happy Path)

```json
{
    "mockBidRequest": {
        "id": "test-request-id",
        "imp": [{ "id": "test-imp-id", "banner": {...}, "ext": {"bidder": {...}} }],
        "site": {"domain": "test.com", "publisher": {"domain": "test.com"}}
    },
    "httpCalls": [{
        "expectedRequest": {
            "uri": "https://fake.endpoint.test/bid",
            "body": { /* expected outgoing request */ },
            "impIDs": ["test-imp-id"]
        },
        "mockResponse": {
            "status": 200,
            "body": { "seatbid": [{ "bid": [{ "mtype": 1, ... }] }], "cur": "USD" }
        }
    }],
    "expectedBidResponses": [{
        "currency": "USD",
        "bids": [{ "bid": {...}, "type": "banner" }]
    }]
}
```

### Supplemental (Error Path)

```json
{
    "mockBidRequest": { /* request that triggers error */ },
    "httpCalls": [{
        "expectedRequest": { "uri": "...", "body": {...}, "impIDs": [...] },
        "mockResponse": { "status": 400, "body": "" }
    }],
    "expectedMakeRequestsErrors": [
        { "value": "Error message text", "comparison": "literal" }
    ],
    "expectedMakeBidsErrors": [
        { "value": "Unexpected status code: 400...", "comparison": "literal" }
    ]
}
```

### Required Test Coverage for New Adapters

**Exemplary tests should cover:**

| Scenario | Test File Naming Convention |
|----------|---------------------------|
| Each declared media type (banner, video, native, audio) | `banner.json`, `video.json`, `native.json`, `audio.json` or `simple-banner.json`, etc. |
| Each declared platform (site, app) | `site-banner.json`, `app-banner.json` or `simple-site-banner.json`, etc. |
| Video-specific (when YAML declares video) | `video.json`, `video-app.json`, `video-web.json`, `dynamic-pod.json` (for video pods) |
| Audio (only if YAML declares audio) | `audio.json` |
| Multiple impressions | `multi-imp.json` or `multiple-impressions.json` |

**Supplemental tests should cover:**

| Error Scenario | Typical Test File Name |
|---------------|----------------------|
| Invalid imp.ext | `bad-imp-ext.json`, `invalid-imp-ext.json` |
| Invalid imp.ext.bidder | `bad-imp-ext-bidder.json`, `invalid-bidder-ext.json` |
| HTTP 204 response | `status-204.json`, `no-content.json` |
| HTTP 400 response | `status-400.json`, `bad-response.json` |
| HTTP 500 response | `status-500.json`, `server-error.json` |
| Invalid response body | `bad-response.json`, `invalid-response.json` |
| Unsupported media type | `bad-media-type.json`, `unsupported-media-type.json` |
| Video error scenarios (when adapter has video logic) | placed in `videosupplemental/` if substantial; otherwise in `supplemental/` (e.g., `bad-video-mime.json`) |

---

## Registration Patterns

### exchange/adapter_builders.go

```go
// Import (alphabetical)
import (
    // ...
    "{bidder}" "github.com/prebid/prebid-server/v4/adapters/{bidder}"
    // ...
)

// Map entry (alphabetical)
func newAdapterBuilders() map[openrtb_ext.BidderName]adapters.Builder {
    return map[openrtb_ext.BidderName]adapters.Builder{
        // ...
        openrtb_ext.Bidder{Name}: {bidder}.Builder,
        // ...
    }
}
```

Import alias needed when:
- Bidder name starts with a number (`ttx "...33across"`)
- Bidder name conflicts with Go keyword
- Bidder name contains special chars (`evolution "...e_volution"`)

### openrtb_ext/bidders.go

```go
// Const (alphabetical)
const (
    // ...
    Bidder{Name} BidderName = "{bidder}"
    // ...
)

// coreBidderNames slice (alphabetical)
var coreBidderNames []BidderName = []BidderName{
    // ...
    Bidder{Name},
    // ...
}
```

---

## Common Adapter Patterns

### Headers Construction

```go
func makeHeaders(request *openrtb2.BidRequest) http.Header {
    headers := http.Header{}
    headers.Add("Content-Type", "application/json;charset=utf-8")
    headers.Add("Accept", "application/json")
    if request.Device != nil {
        if request.Device.UA != "" {
            headers.Add("User-Agent", request.Device.UA)
        }
        if request.Device.IP != "" {
            headers.Add("X-Forwarded-For", request.Device.IP)
        }
    }
    return headers
}
```

### Publisher ID Injection

Many adapters extract an account/publisher ID from bidder params and inject it into the OpenRTB `site.publisher.id` or `app.publisher.id`:

```go
if request.Site != nil {
    siteCopy := *request.Site
    if siteCopy.Publisher != nil {
        pubCopy := *siteCopy.Publisher
        pubCopy.ID = accountID
        siteCopy.Publisher = &pubCopy
    } else {
        siteCopy.Publisher = &openrtb2.Publisher{ID: accountID}
    }
    request.Site = &siteCopy
}
```

### Extension Stripping

Some adapters strip `bidder` and `prebid` from `imp.Ext` before forwarding:

```go
newExt := jsonparser.Delete(imp.Ext, "prebid")
newExt = jsonparser.Delete(newExt, "bidder")
imp.Ext = newExt
```

---

## Config Auto-Discovery

New bidders do NOT need manual config registration. The `config.SetupViper()` function auto-discovers bidders from `bidderInfos` and creates configuration bindings automatically:

```go
for bidderName := range bidderInfos {
    setBidderDefaults(v, strings.ToLower(bidderName))
}
```

This means adding `static/bidder-info/{bidder}.yaml` is sufficient for config — no `config.go` changes needed.

---

## Pattern Catalog

Patterns extracted from periodic review of the 89 reference adapter PRs (`prebid-server-go/references/new-bid-adapter-prs.md`). Stable schema for each entry; cap 8 per skill to keep this file scannable. Phase-2 synthesis populates entries during refresh cycles.

### Schema

```
### Pattern P-{NN}: {short title}
- Symptom in diff: {what the diff looks like}
- Frequency observed: {N of total reference PRs}
- Affected workflow: {Workflow link}
- Severity: FAIL | WARN | INFO
- Action: {what the skill does when it sees this}
```

### Entries

(Populated by current refresh — see SKILL.md for the active rule list.)

---

## Cross-Language Port-Fidelity (consumed in Step 1g)

When the routing manifest carries a `--- PRIOR SOURCE SPEC COMPARISON ---` block, this skill consumes it in [SKILL.md §Step 1g](../SKILL.md). Empirically-grounded adapter-code port-fidelity patterns (canary-cited):

- **F-new-7 EXT-B `imp-id-correlation`** — multi-imp bid-type resolution must walk imps + match by ImpID; cite `docs/runs/d3.8-adkernelAdn-canary-2026-05-05T1636Z-7686.md:209-232`
- **F-new-7 EXT-A `per-key batching`** — multi-pubId inputs emit one HTTP per batch; cite same trace lines 173-205
- **F3 Site↔App synthesis** (`code.make_requests.mutation.entity_strategies = synthesize-replacement`) — vungle canonical; cite `docs/runs/d3.8-vungle-canary-2026-05-05T1529Z-b8a5.md:98-118`
- **F4 bid-post-processing macros** (`${AUCTION_PRICE}` substitution) — thetradedesk master sample; cite `cross-language-pairs/thetradedesk.dual-spec-assertions.yaml:148-212`
- **F-new-45 nil-map panic on JSON `null`** — `urgent` severity, fuzz-discovered runtime bug; cite `docs/runs/d3.8-teal-canary-2026-05-05T-canary8-teal.md:263-270`

Canonical severity / dedup / emission template: [`../../shared/framework-utilities.md` §Cross-Language Port-Fidelity Hook Contract](../../shared/framework-utilities.md#cross-language-port-fidelity-hook-contract). Symmetric Java counterpart: `prebid-server-java/review/skills/bidder-class-pr-review/SKILL.md` §Step 1g.
