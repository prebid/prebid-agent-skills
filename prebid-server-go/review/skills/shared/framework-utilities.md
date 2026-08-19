# Framework Utilities (Shared Reference)

Canonical framework-level reference shared by all four prebid-server-go review skills (`pr-triage`, `adapter-code-pr-review`, `bidder-info-pr-review`, `bidder-params-pr-review`). Skills' `references/` files link here instead of duplicating content.

**Module path (current major):** `github.com/prebid/prebid-server/v4` (since release v4.0.0, March 2026).
**Drift policy:** `pr-triage` Step 2 fetches `https://raw.githubusercontent.com/prebid/prebid-server/master/go.mod` and parses the `module` declaration. If the upstream major differs from `v4`, report `DRIFT: module path major version changed (v4 → vN)` and update this file in the same migration.

> **Note on PR diffs that show `v3` imports.** The v3 → v4 migration was a single mechanical sweep on master — NOT a per-adapter author change. PRs authored before that sweep can show `v3` imports in their diff and still merge against `v4` master. Skills MUST NOT flag `v3` imports inside a PR diff as a stale-author error. Only flag `v3` imports in *master* (which would mean the sweep regressed).

---

## Review disposition system (severity · action · fidelity↔conformance tie-breaker)

> **Governs how every finding across the four Go review skills is rated and acted on.** This is the canonical disposition reference; per-skill checks cite it instead of re-deriving severity. Established by [ADR-009 — lean-conformance doctrine](../../../../docs/decisions/009-lean-conformance-doctrine.md).

### Severity → disposition ladder

Every finding carries a **severity** (what kind of defect) and a **disposition** (what the reviewer does about it):

| Severity | Disposition | Meaning |
|---|---|---|
| **FAIL** | **BLOCK** merge | Won't compile / build / pass CI, a correctness bug, or a violation of a hard target-repo merge norm. Cannot merge until resolved. |
| **WARN** | **ASK** the author | Likely a problem but context-dependent. Raise as a change request; the author fixes it or vouches with a reason the reviewer accepts. |
| **INFO** | **NOTE** (non-blocking) | Style/perf nicety or heads-up. Mention once; never blocks. |

A finding's severity is set by the **target repo's merge bar** (prebid-server Go), not by how the source adapter behaves. The two ways a reviewer historically *under*-rates a finding — "the source does it this way" and "extra coverage/artifacts can't hurt" — are both miscalibrations, corrected by the tie-breaker and the more-artifacts corollary below.

### Tie-breaker: target-conformance beats source-fidelity

When a finding is defended by source-fidelity — *"the Java source adapter does exactly this, so the Go port should too"* — do NOT dismiss it on that basis. Re-rate against the **target (Go)** norm:

- If upstream Go would reject the pattern, **the finding stands at its target-norm severity**, regardless of faithful reproduction. Fidelity is the porting *means*; a merge-ready target PR is the *end* (ADR-009).
- Record the divergence so it is deliberate, not silent: note it in the port's `port-report.json` `quirks[]`, and for a genuine source-side defect recommend an upstream issue against the source repo so both sides re-align.
- Canonical example (Teal #4765): the Java source's `getBidType` returned `banner` *silently* for an undeterminable type. Faithfully porting that ships a latent bug; the Go bar (error-or-skip on unresolved type) wins. The fidelity defense does NOT lower the severity.

This is the core calibration fix from the Teal review: our reviews *saw* the issues and resolved them toward fidelity — they must resolve toward target-conformance.

### Guard: the tie-breaker does NOT auto-promote WARN-by-design findings

The tie-breaker resolves *fidelity-vs-conformance* conflicts. It is NOT license to escalate every divergence-from-a-strict-reading to FAIL. The following are **WARN/INFO by design** and stay there unless an independent target-norm violation applies:

- **Specific-ID defensive checks the framework does NOT enforce** — `Site.ID`, `App.ID`, `Publisher.ID` non-empty guards are legitimately KEEP/WARN (see "Site / App ID — nuanced enforcement" below). Only the *outer* `Site == nil && App == nil` check is genuinely redundant.
- **Forward-compat branches** handling fields/values not yet in the current schema.
- **Operator-vouched constant fallbacks** that match the source's *real* default (e.g., a `getBidType` returning a constant the bidder genuinely always serves, vouched in `quirks[]`). Flag only *silent / unvouched / mis-typing* fallbacks — not every constant fallback. A substantial minority of upstream adapters legitimately return a bare constant bid type rather than `(BidType, error)`; a bare constant is therefore not by itself a defect. Regenerate the split before quoting any proportion:

  ```bash
  # bare-constant vs (BidType, error) shapes, run at the repo root
  grep -rlE 'func .*\(.*openrtb_ext\.BidType, error\)' adapters/*/  | wc -l
  ```

When uncertain between WARN and FAIL on a defensive check, default to WARN (ASK) and let the author vouch — over-blocking erodes reviewer trust as much as under-blocking.

### Corollary: more artifacts ≠ higher quality

A PR that ships *more than the canonical corpus* is off-spec, not premium. Non-canonical artifacts — `doc.go`, `*_fuzz_test.go`, `*_bench_test.go`, and large stand-alone Go unit-test files that duplicate JSON-fixture coverage — are **findings to flag, not merits to praise** (ADR-009). They are dev-time aids: run them during development, pin any bug they surface with a normal test or supplemental fixture, and strip them before the PR. Per-skill checks set the exact severity; the default disposition is to flag, never to commend.

---

## Builder inputs and call signatures

The framework passes these struct values into adapter implementations. Adapters can rely on every field listed here being present in v4 master. Verified at master @2fae16f31693452b62dd2a0924b78e71bbec43ec (2026-05-03).

### `config.Adapter` (passed into `Builder`)

```go
type Adapter struct {
    Endpoint            string  // From static/bidder-info/{bidder}.yaml `endpoint:`
    ExtraAdapterInfo    string  // From static/bidder-info/{bidder}.yaml `extra_info:` — opaque JSON / config string for runtime-tunable adapter config (avoid hardcoding)
    XAPI                AdapterXAPI  // Rubicon-specific (Username/Password/Tracker)
    PlatformID          string  // AppNexus / Facebook
    AppSecret           string  // Facebook
}
```

**Adapters SHOULD use `ExtraAdapterInfo` for runtime-tunable config** (e.g., currency conversion endpoint, region routing tables) instead of hardcoding values inline. PR #4076 (AdUp Tech) reviewer convention.

### `config.Server` (passed into `Builder`)

```go
type Server struct {
    ExternalUrl  string  // PBS deployment's external URL — used for {{.ExternalURL}} macro substitution in user-sync URLs
    GvlID        int     // PBS deployment's GVL ID (host-level, not bidder)
    DataCenter   string  // Region/datacenter identifier
}
```

Used in test runners as `config.Server{ExternalUrl: "http://hosturl.com", GvlID: 1, DataCenter: "2"}`.

### `adapters.ExtraRequestInfo` (passed into `MakeRequests`)

```go
type ExtraRequestInfo struct {
    PbsEntryPoint              metrics.RequestType   // Auction / AMP / video / etc.
    GlobalPrivacyControlHeader string                // GPC header value (privacy)
    CurrencyConversions        currency.Conversions  // Currency rates source
    PreferredMediaType         openrtb_ext.BidType   // Reverses on the auction request — adapters MAY use this to filter media types when ambiguous
}
```

Method: `func (r ExtraRequestInfo) ConvertCurrency(value float64, from, to string) (float64, error)`. Use this when converting bid floors between currencies — do NOT call `currency.Conversions` directly.

> **Important**: `ConvertCurrency` is available ONLY in `MakeRequests` (which receives `*ExtraRequestInfo`). The `MakeBids` signature does NOT include `reqInfo` — there is no PBS-provided way to convert currencies inside `MakeBids`. If you need request-currency-to-bidder-currency conversion of bid floors, do it in `MakeRequests`. If a bid response has a different currency than expected, set `bidResponse.Currency` to the actual currency and let `exchange/bidder_validate_bids.go:79` (`validateCurrency`) handle the mismatch.

### `adapters.RequestData` (returned from `MakeRequests`)

```go
type RequestData struct {
    Method   string       // http.MethodPost (constant) — not literal "POST"
    Uri      string       // Endpoint URL — from adapter struct, not hardcoded
    Body     []byte       // Marshaled request JSON
    Headers  http.Header  // At minimum Content-Type: application/json
    ImpIDs   []string     // openrtb_ext.GetImpIDs(request.Imp) — REQUIRED for impression tracking
}
```

### `adapters.ResponseData` (passed into `MakeBids`)

```go
type ResponseData struct {
    StatusCode int          // HTTP status from upstream
    Body       []byte       // Response body
    Headers    http.Header  // Response headers
}
```

Use the framework helpers to inspect status (`adapters.IsResponseStatusCodeNoContent`, `adapters.CheckResponseStatusCodeForErrors`) before unmarshaling `Body`.

### `adapters.ExtImpBidder` (used inside `MakeRequests`)

```go
type ExtImpBidder struct {
    Prebid             *openrtb_ext.ExtImpPrebid           `json:"prebid"`
    Bidder             json.RawMessage                     `json:"bidder"`
    AuctionEnvironment openrtb_ext.AuctionEnvironmentType  `json:"ae,omitempty"`  // PAAPI / Protected Audience API
}
```

Standard two-phase imp.ext unmarshaling: first unmarshal `imp.Ext` to `adapters.ExtImpBidder`, then unmarshal `bidderExt.Bidder` to the bidder-specific `openrtb_ext.ExtImp{Bidder}` struct.

---

## Bidder Interface

Every adapter implements:

```go
type Bidder interface {
    MakeRequests(request *openrtb2.BidRequest, reqInfo *ExtraRequestInfo) ([]*RequestData, []error)
    MakeBids(internalRequest *openrtb2.BidRequest, externalRequest *RequestData, response *ResponseData) (*BidderResponse, []error)
}
```

Source: `adapters/bidder.go` on `prebid/prebid-server` master.

## Builder Function Signature

```go
func Builder(bidderName openrtb_ext.BidderName, config config.Adapter, server config.Server) (adapters.Bidder, error)
```

Stable across v3 and v4. Verified current at master @2fae16f31693452b62dd2a0924b78e71bbec43ec (2026-05-03).

## Adapter Struct Convention

```go
type adapter struct {
    endpoint string
}
```

- Type name **unexported** (lowercase). Only `Builder` is exported from the adapter package.
- Holds only configuration. Must NOT hold request-scoped state, HTTP clients, or loggers — the framework provides those via method parameters.
- Multi-file layout (e.g., `parsers.go`, `structs.go`, `utils.go`, `models.go`) is tolerated when justified by non-trivial non-OpenRTB serialization (e.g., the Mediasquare exception). Single-file is the default.

## RequestData Fields

```go
type RequestData struct {
    Method  string      // Use http.MethodPost (constant), not literal "POST"
    Uri     string      // Endpoint URL — from adapter struct, not hardcoded
    Body    []byte      // Marshaled request JSON
    Headers http.Header // At minimum Content-Type: application/json
    ImpIDs  []string    // openrtb_ext.GetImpIDs(request.Imp) — required for impression tracking
}
```

`ImpIDs` is required. Use `openrtb_ext.GetImpIDs(imps)` to populate — do not hand-roll.

---

## Framework Helper Functions

| Function | Package | Purpose |
|----------|---------|---------|
| `adapters.IsResponseStatusCodeNoContent(resp)` | `github.com/prebid/prebid-server/v4/adapters` | Return-true on HTTP 204 — check before unmarshaling |
| `adapters.CheckResponseStatusCodeForErrors(resp)` | `github.com/prebid/prebid-server/v4/adapters` | Return error on non-2xx — check before unmarshaling |
| `adapters.NewBidderResponseWithBidsCapacity(n)` | `github.com/prebid/prebid-server/v4/adapters` | Pre-allocate `BidderResponse` with bid capacity |
| `openrtb_ext.GetImpIDs(imps)` | `github.com/prebid/prebid-server/v4/openrtb_ext` | Extract impression IDs (required for `RequestData.ImpIDs`) |
| `openrtb_ext.ParseBidType(s)` | `github.com/prebid/prebid-server/v4/openrtb_ext` | Parse bid type from string |
| `jsonutil.Marshal(v)` | `github.com/prebid/prebid-server/v4/util/jsonutil` | JSON marshal — recommended over `encoding/json.Marshal` |
| `jsonutil.Unmarshal(data, v)` | `github.com/prebid/prebid-server/v4/util/jsonutil` | JSON unmarshal — recommended over `encoding/json.Unmarshal` |
| `jsonutil.StringInt` | `github.com/prebid/prebid-server/v4/util/jsonutil` | Type for schema fields that accept `["integer", "string"]` |
| `&errortypes.BadInput{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Client request invalid (publisher's fault). MUST use pointer form (`&`) — receivers are pointer receivers; value form does not satisfy `error` interface and won't compile. |
| `&errortypes.BadServerResponse{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Upstream bidder returned invalid data. Pointer form required. |
| `&errortypes.FailedToMarshal{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Adapter-side marshaling failed. Pointer form required. |
| `&errortypes.FailedToUnmarshal{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Adapter-side unmarshaling failed. Pointer form required. |
| `errortypes.Timeout` / `errortypes.TmaxTimeout` | `github.com/prebid/prebid-server/v4/errortypes` | Network/budget timeouts |
| `errortypes.BidderTemporarilyDisabled` / `errortypes.BidderThrottled` | `github.com/prebid/prebid-server/v4/errortypes` | Operational state |
| `macros.NewStringIndexBasedReplacer()` | `github.com/prebid/prebid-server/v4/macros` | Resolve endpoint URL template macros |
| `ptrutil.Clone[T](*T)` | `github.com/prebid/prebid-server/v4/util/ptrutil` | Deep-copy pointer fields (suggested for `Site`, `Publisher`, `App` mutations) — INFO-level recommendation only |
| `iterutil.SlicePointerValues(s)` | `github.com/prebid/prebid-server/v4/util/iterutil` | Range over slice without value-copy (perf) — INFO-level only |
| `adapterstest.RunJSONBidderTest(t, dir, bidder)` | `github.com/prebid/prebid-server/v4/adapters/adapterstest` | The JSON test harness |

`encoding/json` direct usage is discouraged for `Marshal`/`Unmarshal` calls but acceptable for `json.RawMessage` type alone.

### `util/jsonutil` extras beyond Marshal/Unmarshal

The package provides additional helpers for JSON manipulation:

| Function/Type | Purpose |
|---|---|
| `jsonutil.UnmarshalValid(data, v)` | Unmarshal that ALSO validates JSON structure — stricter than `Unmarshal` |
| `jsonutil.MergeClone(v, data)` | Merge a `json.RawMessage` into an existing struct value, cloning slices/maps/pointers (avoids shared-state mutation) — useful for layering optional ext on top of base config |
| `jsonutil.FindElement(extension, names...)` | Locate a JSON element by path without full unmarshal — returns offset/length |
| `jsonutil.DropElement(extension, names...)` | Remove a JSON element by path; returns modified bytes — useful for stripping `prebid` / `bidder` keys from `imp.Ext` before forwarding |
| `jsonutil.ParseIntoString(b, **string)` | Coerce a JSON value (string/int/etc.) into `*string` — for fields that arrive as multiple types |
| `jsonutil.StringInt` (type) | Type for fields declared `["integer", "string"]` in schema — accepts both forms |
| `jsonutil.IntString` (type) | Type for fields declared as integer but the upstream sends as a string — useful for legacy bidder responses |

`StringInt` and `IntString` are NOT interchangeable: `StringInt` accepts `42` or `"42"` and stores as int; `IntString` is for the inverse (forces a JSON int into a string for serialization). Match the type to the schema.

**Use `MergeClone` over `Unmarshal` into pre-populated struct** when applying optional bidder ext on top of a base structure — direct unmarshal can mutate shared slice/map references.

**Use `FindElement` / `DropElement`** instead of full unmarshal-modify-marshal cycles when only inspecting or stripping a small subset of a larger ext object — significantly faster on large extensions.

---

## Endpoint Template Macros

`macros.EndpointTemplateParams` supports these 22 fields (`macros/macros.go:9-32`, master @0ba3523).

**What an unrecognized macro actually does — it does NOT silently resolve to empty string.** `config/bidderinfo.go:492-507` (`validateAdapterEndpoint`) parses the endpoint with `text/template` and runs `macros.ResolveMacros(endpointTemplate, testEndpointTemplateParams)` at startup. `text/template` Execute returns an error for a field that does not exist on the struct, so the endpoint fails validation, `config.New` refuses to boot, and `TestBidderInfoFiles` fails in CI. The defect is a hard startup abort, not a silent empty substitution. **Severity stays FAIL** — the consequence is louder than previously documented, not milder.

| Macro | Field | Typical use |
|-------|-------|-------------|
| `{{.Host}}` | `Host` | Regional endpoint selection (e.g., `us`, `eu`) |
| `{{.PublisherID}}` | `PublisherID` | Publisher identification |
| `{{.ZoneID}}` | `ZoneID` | Zone/placement routing |
| `{{.SourceId}}` | `SourceId` | Source/network ID |
| `{{.AccountID}}` | `AccountID` | Publisher/host account identification |
| `{{.AdUnit}}` | `AdUnit` | Ad unit identifier |
| `{{.MediaType}}` | `MediaType` | Media type routing |
| `{{.GvlID}}` | `GvlID` | GVL vendor ID |
| `{{.PageID}}` | `PageID` | Page identifier |
| `{{.SupplyId}}` | `SupplyId` | Supply source ID |
| `{{.ImpID}}` | `ImpID` | Impression ID |
| `{{.SspId}}` | `SspId` | SSP ID (lowercase d) |
| `{{.SspID}}` | `SspID` | SSP ID (uppercase D) |
| `{{.SeatID}}` | `SeatID` | Seat identifier |
| `{{.TokenID}}` | `TokenID` | Authentication token ID |
| `{{.PartnerId}}` | `PartnerId` | Partner identifier |
| `{{.Region}}` | `Region` | Regional deployment routing |
| `{{.PlacementID}}` | `PlacementID` | Placement identifier |
| `{{.NetworkId}}` | `NetworkId` | Network identifier |
| `{{.SiteDomain}}` | `SiteDomain` | Site domain |
| `{{.AppDomain}}` | `AppDomain` | App domain |
| `{{.Bundle}}` | `Bundle` | App bundle identifier |

Source: `macros/macros.go:9-32` `EndpointTemplateParams` struct, master @0ba3523. This table is the **single source of truth** for the allow-list; per-skill checks link here rather than re-listing the fields, so the list drifts in one place only.

> `ImpID`, `NetworkId`, `SiteDomain`, `AppDomain`, and `Bundle` currently have zero uses across `static/bidder-info/`. They are valid macros that no shipped YAML exercises — a stale allow-list omitting them is a latent false-FAIL, not a live one. Regenerate usage with:
> ```bash
> grep -rhoE '\{\{\s*\.[A-Za-z]+\s*\}\}' static/bidder-info/ | sort | uniq -c | sort -rn
> ```

> **Note**: `{{.ExternalURL}}` is NOT an endpoint template macro — it belongs to user-sync URL templates (separate macro set used by `userSync.iframe.url` / `userSync.redirect.url`). See "## User-sync URL macros" below for the verified canonical list. Older skill files conflated endpoint and user-sync macros — they are distinct.

**Non-Go-template placeholders** (e.g., `#{REGION}#`, `${X}`, `<X>`) are NOT runtime macros — they are deployment-time substitution placeholders. An endpoint that contains an unresolved non-template placeholder requires `disabled: true` in YAML plus a comment block enumerating valid values. Reviewers reject endpoints with unresolved non-template placeholders unless paired with `disabled: true` (canonical: PR #4502 appStockSSP `#{REGION}#`).

---

## User-sync URL macros

User-sync URLs in `static/bidder-info/{bidder}.yaml` (`userSync.iframe.url`, `userSync.redirect.url`) use TWO distinct macro mechanisms — Go template substitution AND regex-based string replacement.

### Privacy macros (Go template, fields of `macros.UserSyncPrivacy`)

| Macro | Field | Source |
|---|---|---|
| `{{.GDPR}}` | `GDPR` | "1" if GDPR applies, "0" otherwise |
| `{{.GDPRConsent}}` | `GDPRConsent` | TCF v2 consent string |
| `{{.USPrivacy}}` | `USPrivacy` | CCPA / IAB US Privacy String |
| `{{.GPP}}` | `GPP` | Global Privacy Platform consent string |
| `{{.GPPSID}}` | `GPPSID` | GPP Section ID list |

Source: `macros/macros.go` `UserSyncPrivacy` struct.

### Substitution macros (regex-based, in `usersync/syncer.go`)

These are NOT Go template fields — they're substituted via `regexp.MustCompile(...).ReplaceAllLiteralString(...)` calls in `buildTemplate`:

| Macro | Substituted with |
|---|---|
| `{{.SyncerKey}}` | The bidder's syncer key (defaults to bidder name; can be shared cross-bidder per `userSync.key`) |
| `{{.BidderName}}` | The actual bidder name (alias resolution applied) |
| `{{.SyncType}}` | `"iframe"` or `"redirect"` (or `formatOverride` value) |
| `{{.UserMacro}}` | The bidder's `userMacro` value (e.g., `$UID`, `[USER_ID]`, `{UID}`) |
| `{{.ExternalURL}}` | The PBS host's external URL (chosen from `userSync.endpoint.externalUrl` → `userSync.externalUrl` → host-level config) |
| `{{.RedirectURL}}` | The fully-resolved redirect-back URL after sync (built from the redirect template) |

Source: `usersync/syncer.go` (regex patterns: `macroRegexSyncerKey`, `macroRegexBidderName`, `macroRegexSyncType`, `macroRegexUserMacro`, `macroRegexExternalHost`, `macroRegexRedirect`).

> **Note on naming**: the Go regex variable in `usersync/syncer.go:105` is named `macroRegexExternalHost`, but the regex pattern it compiles is `{{\s*\.ExternalURL\s*}}` — so the canonical macro form to write in YAML is `{{.ExternalURL}}`, NOT `{{.ExternalHost}}`. Older docs sometimes invert this based on the Go variable name.

### Macro applicability per URL field

| YAML field | Privacy macros | Substitution macros |
|---|---|---|
| `userSync.iframe.url` | All 5 | All 6 |
| `userSync.redirect.url` | All 5 | All 6 |
| `userSync.iframe.redirectUrl` | None | `{{.ExternalURL}}`, `{{.BidderName}}`, `{{.SyncType}}`, `{{.UserMacro}}` |
| `userSync.redirect.redirectUrl` | None | `{{.ExternalURL}}`, `{{.BidderName}}`, `{{.SyncType}}`, `{{.UserMacro}}` |

Endpoint URL templates (`endpoint:` field) use the SEPARATE `EndpointTemplateParams` set documented above. Do NOT mix the two sets.

---

## Error-Type Taxonomy

| Type | When to Use |
|------|------------|
| `errortypes.BadInput` | Invalid impression data, malformed `imp.ext`, missing required fields — the publisher's request is wrong. Maps to client-error metric. |
| `errortypes.BadServerResponse` | Upstream bidder returned invalid data — the bidder's response is wrong. Maps to server-error metric. |
| `errortypes.FailedToMarshal` | Adapter-side `Marshal` failure — surfaces shared-memory corruption. Maps to a distinct metric counter. |
| `errortypes.FailedToUnmarshal` | Adapter-side `Unmarshal` failure (validation errors). Maps to "unknown error type" metric. |
| `errortypes.Timeout` / `errortypes.TmaxTimeout` | Network or auction-budget timeouts |
| `errortypes.BidderTemporarilyDisabled` / `errortypes.BidderThrottled` | Operational state |
| Generic `error` | Internal errors that don't fit a typed category |

Do NOT use `errortypes.BadInput` for upstream server errors. Do NOT use `errortypes.BadServerResponse` for client input errors. The metric pipeline counts each typed error separately — using the wrong type pollutes metrics.

Error message context: include the impression ID or index when the error is generated inside an impression loop, e.g., `fmt.Sprintf("Invalid imp.ext for impression %s", imp.ID)`. Use `%w` for error wrapping, not `%v`.

---

## Marshaling Error Safety

**CRITICAL**: Marshaling errors must NEVER be silently swallowed. Production has shown shared-memory-corruption causing `jsonutil.Marshal` / `json.Marshal` to fail. If swallowed, the adapter panics with no diagnostic.

```go
// CORRECT — always check and return marshal errors
requestJSON, err := jsonutil.Marshal(request)
if err != nil {
    return nil, []error{err}
}

// WRONG — silently ignoring marshal error
requestJSON, _ := jsonutil.Marshal(request)
```

**Unmarshaling** errors for genuinely-optional extension data MAY be swallowed if the adapter remains valid without it. Marshaling errors — never. The reviewer convention (PR #4614 verbatim): *"please do not swallow marshaling errors. We've seen instances in production where shared memory corruption results in a marshalling error causing an adapter panic that tips us off that there is a real problem."*

---

## Test Harness Contract

`adapters/adapterstest/test_json.go` exposes `RunJSONBidderTest(t, rootDir, bidder)` and supports five test data subdirectories:

| Directory | Purpose |
|-----------|---------|
| `exemplary/` | Happy-path fixtures, treated as documentation source-of-truth |
| `supplemental/` | Edge cases, error paths, unsupported scenarios |
| `amp/` | AMP (Accelerated Mobile Pages) specific tests |
| `video/` | Video-specific tests (use when adapter has substantial video logic) |
| `videosupplemental/` | Video edge cases / error paths |

The canonical test root directory name is `<bidder>test/` (no separator between bidder and "test"). A small number of legacy adapters use alternate names (e.g., `adapters/msft/test/`, `adapters/msft/test-extrainfo/`); tolerated for compatibility but new adapters should use `<bidder>test/`.

### `currency` field assertion

As of PR #4592 (v3.30.0, November 2025), `RunJSONBidderTest` asserts `expectedBidResponses[*].currency` against `BidderResponse.Currency`. Before #4592, this field was silently ignored. New fixtures should include `"currency": "USD"` (or the expected currency) explicitly when the adapter is expected to return a specific currency.

### Multi-request 1:1 matching

As of PR #4592, multi-request fixtures must have each `httpCalls` entry match a distinct expected entry. Previously a duplicate-match was silently accepted (e.g., `expected[1]` matching the same `actual[0]` as `expected[0]`).

### Error-comparison field

`expectedMakeRequestsErrors[*].comparison` accepts `"literal"` (default), `"regex"`, or `"startswith"`. An empty `comparison` field falls through to `"literal"`.

### `adapter_test_util.go` (auxiliary helpers)

The directory `adapters/adapterstest/` also contains a non-canonical helpers file `adapter_test_util.go` exposing:

- `OrtbMockService` — scaffolded `httptest.Server` + last request capture
- `BidOnTags(tags string) map[string]bool` — comma-separated tag list to set
- `SampleBid(width, height *int64, impId string, index int) openrtb2.Bid` — minimal bid factory
- `VerifyStringValue(value, expected string, t *testing.T)` — assertion helper

These are NOT used by `RunJSONBidderTest` (the canonical JSON harness). Some legacy adapters (e.g., older `cadent_aperture_mx`) used these helpers in custom Go unit tests. New adapters should NOT use these — write JSON fixtures instead. If a new adapter's `_test.go` imports `adapterstest.OrtbMockService` etc., flag as **WARN** and recommend converting to the JSON harness.

### MakeBids invocation gating

`MakeBids` is invoked ONLY when the upstream HTTP call succeeded with a status in `[200, 400)`. Verified at `exchange/bidder.go:304-306` (`if httpInfo.err == nil { ... bidder.Bidder.MakeBids(...) }`) and `exchange/bidder.go:651-658` (any 4xx/5xx triggers `BadServerResponse` and `MakeBids` is skipped).

- **204 is NOT skipped**: HTTP 204 is in `[200, 400)`, so `MakeBids` IS called with `responseData.StatusCode == 204` and an empty body. Adapters MUST explicitly handle 204 (canonical idiom: `if adapters.IsResponseStatusCodeNoContent(responseData) { return nil, nil }`).
- **4xx / 5xx**: `MakeBids` is NOT called for these. PBS surfaces `BadServerResponse` automatically.
- **Network/timeout errors**: `MakeBids` is NOT called.
- **`responseData.StatusCode`** is the actual HTTP status from the upstream — direct copy of `httpResp.StatusCode`, never normalized or mapped.

---

## Anti-pattern: PBS core already does this

Adapters MUST NOT re-implement validation that PBS core enforces upstream. Frequently rejected defensive checks:

| Anti-pattern in adapter Go code | What PBS core handles |
|---------------------------------|------------------------|
| `if len(request.Imp) == 0 { return error }` | PBS core rejects empty-imp requests before calling adapters |
| `if config.Endpoint == "" { return error }` in `Builder` | YAML loader validates endpoint at startup |
| `if banner == nil && video == nil && audio == nil && native == nil { skip }` | PBS strips media-type fields your YAML doesn't declare and drops imps with no remaining media types BEFORE `MakeRequests` is invoked, via `adapters/infoawarebidder.go:78-105` (`pruneImps`). Filtering is **per-imp + per-media-type**, NOT per-bidder — by the time you see an imp, at least one media type is set. Single-format adapters that cannot handle multi-format must set `openrtb.multiformat-supported: false` in YAML for the additional narrowing. |
| `if site == nil && app == nil && dooh == nil { error }` | PBS enforces `validateExactlyOneInventoryType` (`endpoints/openrtb2/auction.go:1430`) — exactly one of `Site`/`App`/`DOOH` is non-nil. **However**: PBS does NOT enforce that `Site.ID` is non-empty (only requires `Site.ID || Site.Page`), does NOT enforce `App.ID`, does NOT enforce `Publisher.ID`. **KEEP defensive checks** for those specific fields if your endpoint requires them. Severity: WARN if reviewer flags `if site == nil && app == nil` as redundant (the OUTER check IS redundant); DO NOT flag specific-ID checks. |
| Re-validating bidder-params with `minLength`/regex in Go | `static/bidder-params/{bidder}.json` schema validation runs upstream |
| Re-checking required imp.ext fields | Same — schema does it |
| `hasSiteOrAppID` style functions | Capability filtering already guarantees this |

Reviewers consistently say "delete this — PBS core does it upstream." Flag re-implementations as **WARN**.

### Additional PBS-enforced validation (verified at master @2fae16f31693452b62dd2a0924b78e71bbec43ec, 2026-05-03)

These are checks PBS performs that adapter authors sometimes redundantly re-implement. Flag re-implementations as **WARN**.

| Anti-pattern in adapter Go code | What PBS core handles |
|---|---|
| `if bid.ID == "" \|\| bid.ImpID == "" \|\| bid.Price < 0 \|\| bid.CrID == "" { skip }` | `exchange/bidder_validate_bids.go:115` (`validateBid`) drops bids missing these fields after `MakeBids` returns. Adapters can return malformed bids; PBS will drop them and surface the error. |
| `if bid.Price <= 0 { skip }` | Same — `validateBid` drops `Price < 0` always, and `Price == 0 && DealID == ""` always. |
| Currency-mismatch filtering in adapter | `exchange/bidder_validate_bids.go:79` (`validateCurrency`) rejects bids whose currency doesn't match `request.Cur`. Just set `bidResponse.Currency` correctly. |
| Imp.ID uniqueness / non-empty checks | `endpoints/openrtb2/auction.go:925` enforces uniqueness; `ortb/request_validator.go:36` enforces non-empty. |
| Request.ID, TMax >= 0 checks | `endpoints/openrtb2/auction.go:776, 780` |
| Banner/Video/Audio/Native structural validation (e.g., banner w/h consistency, video mimes non-empty, native asset uniqueness) | `ortb/request_validator_banner.go`, `request_validator_video.go`, `request_validator_audio.go`, `request_validator_native.go` |
| GPP/CCPA/GDPR consent-string parsing | `endpoints/openrtb2/auction.go:866-921` parses + scrubs invalid strings before adapter sees them. |
| App blocklist enforcement | `endpoints/openrtb2/auction.go:1224` rejects requests for any `App.ID` in `BlockedAppsLookup` config. |
| Unknown-bidder rejection | `ortb/request_validator.go:147` returns "unknown bidder" error for misspelled `imp.ext.prebid.bidder.{name}`. |

### Site / App ID — nuanced enforcement

Adapter authors sometimes write defensive checks like `if request.Site.ID == "" { error }`. The truth depends on the field:

| Field | Enforced by PBS? | Adapter defensive check? |
|---|---|---|
| `request.Site != nil \|\| request.App != nil \|\| request.DOOH != nil` (exactly one) | Yes (`validateExactlyOneInventoryType`) | Delete — redundant |
| `request.Site.ID != "" \|\| request.Site.Page != ""` (at least one) | Yes (`validateSite`) | Delete — redundant |
| `request.Site.ID != ""` (specifically the ID) | **No** — only `ID || Page` enforced | **Keep** if your endpoint specifically needs `Site.ID` |
| `request.App.ID != ""` | **No** | **Keep** if your endpoint specifically needs `App.ID` |
| `request.DOOH.ID != "" \|\| len(request.DOOH.VenueType) != 0` | Yes (`validateDOOH`) | Delete — redundant |
| `request.Site.Publisher.ID != ""` (or `App.Publisher`/`DOOH.Publisher`) | **No** | **Keep** if your endpoint specifically needs Publisher.ID |

---

## YAML capabilities ↔ Go MType drift

A frequent (7+ PRs in 2025–2026) review finding: `static/bidder-info/{bidder}.yaml` declares `capabilities.{site,app,dooh}.mediaTypes` including (e.g.) `audio`, but the adapter's `MakeBids` switch only handles banner/video/native — or vice versa. PBS core uses YAML capabilities for filtering; the Go switch must cover every declared media type or return a typed error for unsupported ones.

The cross-check: extract every media type from YAML capabilities; verify the adapter's bid-type resolution (`MType` switch or fallback) covers each. **Severity: FAIL** when YAML declares a media type the Go code cannot return; **WARN** when Go handles a media type not declared in YAML (dead branch).

### Multiformat imps require per-bid disambiguation (`bid.MType`)

**Multiformat is the DEFAULT. Do NOT open the YAML looking for an opt-in.** `adapters/infoawarebidder.go:295-300` (`IsMultiFormatSupported`) returns `true` whenever `OpenRTB` is nil OR `OpenRTB.MultiformatSupported` is nil — the field is a *negative* opt-out, and only 3 of 385 `static/bidder-info/*.yaml` files mention it at all. A reviewer who opens the YAML, finds no `multiformat-supported` key, and exempts the adapter has inverted the default — the exact Teal #4765 miss.

```go
func IsMultiFormatSupported(bidderInfo config.BidderInfo) bool {
	if bidderInfo.OpenRTB != nil && bidderInfo.OpenRTB.MultiformatSupported != nil {
		return *bidderInfo.OpenRTB.MultiformatSupported
	}
	return true
}
```

**Exempt an adapter only when one of these two is affirmatively true:**

1. The YAML explicitly sets `openrtb.multiformat-supported: false`, or
2. Exactly one media type is declared across **all** platforms (`capabilities.app`, `capabilities.site`, `capabilities.dooh` combined) — imp introspection is unambiguous there.

Everything else is multiformat and is in scope for the per-bid check below.

Coverage is necessary but NOT sufficient. On a multiformat adapter a **single imp can carry more than one format at once** (e.g. `banner` + `video` on one imp). Bid-type resolution that keys **only** off the imp — introspecting `imp.Banner/Video/Native` in a fixed priority order — cannot tell which format a given returned bid is for, so the first-priority branch wins for *every* bid and non-banner bids get silently mis-typed. This passes the coverage check above (each type has *a* return path) yet is still wrong.

For a multiformat adapter the authoritative per-bid signal is the response's own `bid.mtype` (OpenRTB 2.6). The correct shape switches on `bid.MType` **first**, keeping imp introspection only as a fallback for responses that omit mtype, then errors:

```go
switch bid.MType {
case openrtb2.MarkupBanner: return openrtb_ext.BidTypeBanner, nil
case openrtb2.MarkupVideo:  return openrtb_ext.BidTypeVideo, nil
case openrtb2.MarkupNative:  return openrtb_ext.BidTypeNative, nil
}
// fallback: imp introspection by ImpID, then error
```

**Severity: FAIL** when a multiformat adapter — i.e. any adapter not carrying one of the two exemptions above — resolves bid type *primarily* by imp-mediatype introspection (fixed banner>video>native priority) instead of `bid.MType`; it mis-types co-present formats. This holds even when the imp lookup is the source adapter's faithful shape (apply the source-fidelity tie-breaker above). Canonical example: Teal #4765 (`postindustria-code` review) — imp-priority resolution on a banner+video+native imp typed every bid `banner`; fixed by switching on `bid.MType` first + a multi-format-imp fixture with mtype-tagged bids.

---

## Open-URL endpoint policy

Endpoints must come from `static/bidder-info/{bidder}.yaml` `endpoint:` field, NOT from a publisher-provided URL in `imp.ext.bidder.endpoint` or similar. Reviewer policy quote (PR #4233): *"Our policy is that we take hardcoded URL as the bid adapter endpoint, or a predefined list of possible endpoints, or perhaps unlimited subdomains of a domain, but not a full open URL like this. We can't have an adapter with the ability of sending requests to any URL a request comes with."*

Acceptable patterns:
- Hardcoded full URL in YAML
- Predefined enum/list in YAML (selected by bidder-param value)
- Subdomain template via YAML + `{{.Host}}` macro

Unacceptable: full URL from `imp.ext` or other publisher-controlled input. **Severity: FAIL.**

---

## Maintainer email policy

`static/bidder-info/{bidder}.yaml` `maintainer.email`:
- Must be a **group/role mailbox** (e.g., `tech@bidder.com`, `prebid@bidder.com`, `support@bidder.com`), NOT a personal address (e.g., `firstname.lastname@bidder.com`).
- A reviewer sends a verification email and blocks merge until the maintainer replies "received". This is a manual blocking gate — skills cannot fully automate it but should:
  - Flag any `maintainer.email` whose **local-part is not a recognized role/group token** as **WARN** with note "may require change to group mailbox per reviewer policy". A role token is a function/team word (`tech`, `prebid`, `support`, `info`, `engineering`, `adops`, `partnerships`, `dev`, `contact`, or a clear product/team handle — but NOT `noreply`/`donotreply`, which defeat the reply-based verification gate); a personal name or handle — `firstname.lastname@`, `firstname@`, `flast@`, initials, a nickname — is NOT a role token **even on the bidder's own corporate domain**. Judge the local-part's role-vs-person character rather than matching a `firstname.lastname@` regex: across the 326 upstream `maintainer.email` values only 7 carry that shape, so a name-pattern deny-list would pass nearly every personal address that does not happen to use it. Reviewer practice on the personal-address case: PR #4321 (address changed at reviewer request) and PR #4441 ("Is this email correct? It appears to be the email of the original bidder from which this alias was created.").
  - Note in summary: "email confirmation pending" until evidence of reply is in PR comments
- Personal-domain emails (gmail, yahoo, hotmail, outlook, proton.me, icloud) are tolerated for small bidders but flagged as **INFO** — reviewer historically requests change.

For aliases, `maintainer.email` MAY be inherited from the parent (omit the field). If declared on the alias, it should be the alias organization's email — not a copy of the parent's, unless they share infrastructure.

**Aliases — clarification:**
- Aliases MAY inherit `maintainer.email` from the parent (omit the field) when the alias is part of the parent's organizational family. Heuristics: bulk-mode multi-adapter alias bundle (e.g., PR #4651 5 Limelight aliases — none declared their own email, all merged), OR alias and parent share a common-stem domain.
- Aliases SHOULD declare their own `maintainer.email` when the alias is an independent organization. Heuristic: distinct endpoint domain that doesn't share a stem with parent's. Reference: PR #4727 (AppMonstaMedia) declared its own `media.support@appmonsta.ai` because Appmonsta Ltd is distinct from teqblaze.
- The skill SHOULD downgrade missing `maintainer.email` to **INFO** in the bulk-mode case and **WARN** in the independent-organization case — see `bidder-info-pr-review/SKILL.md` Workflow: Alias Adapter Added step 6.

---

## Bidder-name conventions

- All-lowercase or snake_case directory name under `adapters/` (e.g., `adkernel`, `alliance_gravity`, `boldwin_rapid`). Underscore is permitted server-side per cross-team policy (PR #4211).
- The 6-character unique-prefix rule (PR #4216) is waived for sibling-family aliases — `admatic`/`admaticde` co-existed.
- New bidders must NOT collide with existing names; if they do (e.g., `ads_interactive` vs `adsinteractive`), defer the deprecation to the next major release.

---

## Aliasing

When a YAML file declares `aliasOf: parent`, `processBidderAliases` (`config/bidderinfo.go:360-422`) fills unset alias fields from the parent. The merge copies `AppSecret`, `Capabilities`, `Debug`, `Endpoint`, `EndpointCompression`, `ExtraAdapterInfo`, `Maintainer`, `OpenRTB`, `PlatformID`, `Disabled`, `Experiment`, `ModifyingVastXmlAllowed`, `XAPI`, and a syncer **key** (not the parent's sync URLs). The alias YAML should declare only the fields it overrides:

- `aliasOf: parent` — required
- `gvlVendorID: N` — **not inherited; declare it or accept no GDPR vendor registration** (see below)
- Other fields — only if they differ from parent

A 1-line alias (`aliasOf: parent` only) is acceptable when the alias inherits everything *except* GVL, which it never inherits.

**GVL vendor ID is never inherited — assert this forward, not backward.** `config/bidderinfo.go:371-373` carries an explicit comment on the alias-merge block:

> the alias's `GVLVendorID` is intentionally never set to the parent's; each alias must declare its own, "as inheriting from the parent is not safe for legal reasons"

`GVLVendorID` is the one field the merge block deliberately omits. `ToGVLVendorIDMap` (`config/bidderinfo.go:428-436`) then keeps only bidders with `GVLVendorID != 0`, so an alias that omits the field is dropped from the GDPR vendor map entirely — it gets **no** vendor registration, it does not borrow the parent's. Consequences for review:

| Alias YAML state | Disposition | Why |
|---|---|---|
| `gvlVendorID: N` (N > 0) | **PASS** (NOTE) | The required form. Verify N against the GVL as usual; do not question the declaration itself. |
| Field omitted, parent declares a GVL | **WARN** (ASK) | "Aliases never inherit GVL vendor ID; declare your own, or confirm this bidder intentionally has none." |
| Field omitted, parent has none either | **PASS** (NOTE) | Nothing to inherit; the alias is unregistered by design. |
| `gvlVendorID: 0` | **WARN** (ASK) | Zero is dropped by `ToGVLVendorIDMap` and reads as a declaration; ask for removal. |

44 of the 113 upstream alias YAMLs declare their own `gvlVendorID`. Regenerate:

```bash
grep -rl "aliasOf" static/bidder-info/ > /tmp/aliases.txt
xargs grep -l "gvlVendorID" < /tmp/aliases.txt | wc -l   # 44 at @0ba3523
wc -l < /tmp/aliases.txt                                  # 113 at @0ba3523
```

**`whiteLabelOnly: true` on a file that also has `aliasOf:` is a hard startup abort — FAIL.** `config/bidderinfo.go:461-463` (`validateAliases`) returns `bidder '%s' is an alias and cannot be set as white label only`; that error propagates `validateAliases` → `processBidderAliases` → `LoadBidderInfoFromDisk` → `logger.Fatalf`. The server does not start. This is **FAIL** (BLOCK), never a redundant-field WARN.

The flag itself is rare: `teqblaze.yaml` is the **only** upstream file carrying `whiteLabelOnly: true`, and it is a core bidder with its own Go adapter, not an alias. Do not treat the flag as the marker of an alias parent — key alias-parent reasoning on whether the bidder actually *has* aliases:

```bash
grep -rh "aliasOf" static/bidder-info/ | sort | uniq -c | sort -rn   # parents by alias count
```

At @0ba3523 the largest parents are `limelightDigital` (23), `teqblaze` (25 across quoting styles), `smarthub` (11) — and only `teqblaze` sets the flag.

**Disabled-by-default + region placeholder pattern** (PR #4502 appStockSSP): adapters with host-configurable region endpoints that contain non-Go-template placeholders (`#{REGION}#`) MUST set `disabled: true` and include a comment block listing valid REGION values.

**HTTPS preferred but HTTP permitted**: HTTPS is strongly preferred but HTTP is still permitted (PR #4211). Limelight family adapters routinely use HTTP.

---

## Test fixture conventions

- **Filename matches content**: `multi-imp.json` should have multiple impressions; `status-204.json` should have `mockResponse.status: 204`. Avoid internal codes (`200-212.json`) — PR #4053 reviewer convention.
- **Use canonical fake endpoints** in JSON fixtures: `https://fake.endpoint.test/bid` or `http://localhost:8080`. Real endpoints break maintenance when domains move.
- **Required supplemental coverage** for new adapters: `status-204.json`, `status-400.json`, `status-500.json`, malformed-response (e.g., `bad-response.json`), unsupported-media-type (`bad-media-type.json`), and at least one `bad-imp-ext.json` exercising malformed `imp.ext`.
- **JSON framework first**: Coverage via `RunJSONBidderTest` is preferred over Go unit tests. Go unit tests are tolerated only when the JSON harness genuinely cannot exercise the case (e.g., the loader rejects malformed JSON before the adapter sees it). Reviewer convention since PR #4533: "test coverage must be achieved via the JSON test framework wherever possible. The JSON test framework has shared memory checks built in which are very important."

---

## Sources

- `prebid/prebid-server` master at @2fae16f31693452b62dd2a0924b78e71bbec43ec (2026-05-03)
- Alias/GVL, whiteLabelOnly, macro allow-list, multiformat-default, and endpoint-compression claims re-verified at master @0ba3523 ("Reklamup: Add GVL vendor ID", #4861)
- `adapters/bidder.go`, `adapters/adapterstest/test_json.go`
- `util/jsonutil/jsonutil.go`, `util/ptrutil/ptrutil.go`, `util/iterutil/slices.go` (`SlicePointerValues`)
- `errortypes/errortypes.go`
- `macros/macros.go` (`EndpointTemplateParams`)
- `config/bidderinfo.go` (`BidderInfo` struct, `processBidderAliases`, `validateAliases`, `validateAdapterEndpoint`)
- `adapters/infoawarebidder.go` (`IsMultiFormatSupported`, `pruneImps`)
- `openrtb_ext/bidders.go` (`NewBidderParamsValidator`, bidder constants)
- Reviewer practice synthesized from 89 reference PRs at `prebid-server-go/references/new-bid-adapter-prs.md`
