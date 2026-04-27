# Framework Utilities (Shared Reference)

Canonical framework-level reference shared by all four prebid-server-go review skills (`pr-triage`, `adapter-code-pr-review`, `bidder-info-pr-review`, `bidder-params-pr-review`). Skills' `references/` files link here instead of duplicating content.

**Module path (current major):** `github.com/prebid/prebid-server/v4` (since release v4.0.0, March 2026).
**Drift policy:** `pr-triage` Step 2 fetches `https://raw.githubusercontent.com/prebid/prebid-server/master/go.mod` and parses the `module` declaration. If the upstream major differs from `v4`, report `DRIFT: module path major version changed (v4 → vN)` and update this file in the same migration.

> **Note on PR diffs that show `v3` imports.** The v3 → v4 migration was a single mechanical sweep on master — NOT a per-adapter author change. PRs authored before that sweep can show `v3` imports in their diff and still merge against `v4` master. Skills MUST NOT flag `v3` imports inside a PR diff as a stale-author error. Only flag `v3` imports in *master* (which would mean the sweep regressed).

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

Stable across v3 and v4. Verified current as of v4.1.0.

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
| `errortypes.BadInput{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Client request invalid (publisher's fault) |
| `errortypes.BadServerResponse{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Upstream bidder returned invalid data |
| `errortypes.FailedToMarshal{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Adapter-side marshaling failed |
| `errortypes.FailedToUnmarshal{Message: ...}` | `github.com/prebid/prebid-server/v4/errortypes` | Adapter-side unmarshaling failed |
| `errortypes.Timeout` / `errortypes.TmaxTimeout` | `github.com/prebid/prebid-server/v4/errortypes` | Network/budget timeouts |
| `errortypes.BidderTemporarilyDisabled` / `errortypes.BidderThrottled` | `github.com/prebid/prebid-server/v4/errortypes` | Operational state |
| `macros.NewStringIndexBasedReplacer()` | `github.com/prebid/prebid-server/v4/macros` | Resolve endpoint URL template macros |
| `ptrutil.Clone[T](*T)` | `github.com/prebid/prebid-server/v4/util/ptrutil` | Deep-copy pointer fields (suggested for `Site`, `Publisher`, `App` mutations) — INFO-level recommendation only |
| `iterutil.SlicePointerValues(s)` | `github.com/prebid/prebid-server/v4/util/iterutil` | Range over slice without value-copy (perf) — INFO-level only |
| `adapterstest.RunJSONBidderTest(t, dir, bidder)` | `github.com/prebid/prebid-server/v4/adapters/adapterstest` | The JSON test harness |

`encoding/json` direct usage is discouraged for `Marshal`/`Unmarshal` calls but acceptable for `json.RawMessage` type alone.

---

## Endpoint Template Macros

`macros.EndpointTemplateParams` supports these 18 fields. Any `{{.XYZ}}` macro NOT in this list silently resolves to empty string at runtime — which usually breaks the endpoint URL.

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

Source: `macros/macros.go` `EndpointTemplateParams` struct on `prebid/prebid-server` master.

> **Note**: `{{.ExternalURL}}` is NOT an endpoint template macro — it belongs to user-sync URL templates (separate macro set used by `userSync.iframe.url` / `userSync.redirect.url`). User-sync URL templates support privacy macros (`{{.GDPR}}`, `{{.GDPRConsent}}`, `{{.USPrivacy}}`, `{{.GPP}}`, `{{.GPPSID}}`) and substitution macros (`{{.RedirectURL}}`, `{{.ExternalURL}}`, `{{.BidderName}}`, `{{.SyncType}}`, `{{.UserMacro}}`). Older skill files conflated these — they are distinct.

**Non-Go-template placeholders** (e.g., `#{REGION}#`, `${X}`, `<X>`) are NOT runtime macros — they are deployment-time substitution placeholders. An endpoint that contains an unresolved non-template placeholder requires `disabled: true` in YAML plus a comment block enumerating valid values. Reviewers reject endpoints with unresolved non-template placeholders unless paired with `disabled: true` (canonical: PR #4502 appStockSSP `#{REGION}#`).

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

---

## Anti-pattern: PBS core already does this

Adapters MUST NOT re-implement validation that PBS core enforces upstream. Frequently rejected defensive checks:

| Anti-pattern in adapter Go code | What PBS core handles |
|---------------------------------|------------------------|
| `if len(request.Imp) == 0 { return error }` | PBS core rejects empty-imp requests before calling adapters |
| `if config.Endpoint == "" { return error }` in `Builder` | YAML loader validates endpoint at startup |
| `if banner == nil && video == nil && audio == nil && native == nil { skip }` | PBS core filters by `static/bidder-info/{bidder}.yaml` capabilities |
| `if site == nil && app == nil { error }` | Same — capabilities-based filtering |
| Re-validating bidder-params with `minLength`/regex in Go | `static/bidder-params/{bidder}.json` schema validation runs upstream |
| Re-checking required imp.ext fields | Same — schema does it |
| `hasSiteOrAppID` style functions | Capability filtering already guarantees this |

Reviewers consistently say "delete this — PBS core does it upstream." Flag re-implementations as **WARN**.

---

## YAML capabilities ↔ Go MType drift

A frequent (7+ PRs in 2025–2026) review finding: `static/bidder-info/{bidder}.yaml` declares `capabilities.{site,app,dooh}.mediaTypes` including (e.g.) `audio`, but the adapter's `MakeBids` switch only handles banner/video/native — or vice versa. PBS core uses YAML capabilities for filtering; the Go switch must cover every declared media type or return a typed error for unsupported ones.

The cross-check: extract every media type from YAML capabilities; verify the adapter's bid-type resolution (`MType` switch or fallback) covers each. **Severity: FAIL** when YAML declares a media type the Go code cannot return; **WARN** when Go handles a media type not declared in YAML (dead branch).

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
- A reviewer (typically `bsardo`) sends a verification email and blocks merge until the maintainer replies "received". This is a manual blocking gate — skills cannot fully automate it but should:
  - Flag `maintainer.email` matching personal-name patterns (e.g., `firstname.lastname@`, `firstname@`) as **WARN** with note "may require change to group mailbox per reviewer policy"
  - Note in summary: "email confirmation pending" until evidence of reply is in PR comments
- Personal-domain emails (gmail, yahoo, hotmail, outlook, proton.me, icloud) are tolerated for small bidders but flagged as **INFO** — reviewer historically requests change.

For aliases, `maintainer.email` MAY be inherited from the parent (omit the field). If declared on the alias, it should be the alias organization's email — not a copy of the parent's, unless they share infrastructure.

---

## Bidder-name conventions

- All-lowercase or snake_case directory name under `adapters/` (e.g., `adkernel`, `alliance_gravity`, `boldwin_rapid`). Underscore is permitted server-side per cross-team policy (PR #4211 escalation to `bretg`).
- The 6-character unique-prefix rule (`bsardo` PR #4216) is waived for sibling-family aliases — `admatic`/`admaticde` co-existed.
- New bidders must NOT collide with existing names; if they do (e.g., `ads_interactive` vs `adsinteractive`), defer the deprecation to the next major release.

---

## Aliasing

When a YAML file declares `aliasOf: parent`, the bidder inherits all of the parent's configuration — `endpoint`, `maintainer`, `capabilities`, `userSync`, `gvlVendorID`, etc. The alias YAML should declare only the fields it overrides:

- `aliasOf: parent` — required
- `gvlVendorID: N` — override, if alias has its own GVL ID
- `whiteLabelOnly: true` — typically only on the parent (e.g., TeqBlaze, SmartHub) to mark it as alias-only. Aliases inherit semantics.
- Other fields — only if they differ from parent

A 1-line alias (`aliasOf: parent` only) is acceptable when the alias inherits everything.

**GVL inheritance quirk**: Aliases cannot effectively override the parent's GVL vendor ID — `config/bidderinfo.go` deliberately inherits whether the alias sets `gvlVendorID: 0` or omits the field. Setting `gvlVendorID: 0` adds confusion; reviewers ask to remove it.

**Disabled-by-default + region placeholder pattern** (PR #4502 appStockSSP): adapters with host-configurable region endpoints that contain non-Go-template placeholders (`#{REGION}#`) MUST set `disabled: true` and include a comment block listing valid REGION values.

**HTTPS preferred but HTTP permitted**: HTTPS is strongly preferred but HTTP is still permitted (per `bsardo` PR #4211). Limelight family adapters routinely use HTTP.

---

## Test fixture conventions

- **Filename matches content**: `multi-imp.json` should have multiple impressions; `status-204.json` should have `mockResponse.status: 204`. Avoid internal codes (`200-212.json`) — PR #4053 reviewer convention.
- **Use canonical fake endpoints** in JSON fixtures: `https://fake.endpoint.test/bid` or `http://localhost:8080`. Real endpoints break maintenance when domains move.
- **Required supplemental coverage** for new adapters: `status-204.json`, `status-400.json`, `status-500.json`, malformed-response (e.g., `bad-response.json`), unsupported-media-type (`bad-media-type.json`), and at least one `bad-imp-ext.json` exercising malformed `imp.ext`.
- **JSON framework first**: Coverage via `RunJSONBidderTest` is preferred over Go unit tests. Go unit tests are tolerated only when the JSON harness genuinely cannot exercise the case (e.g., the loader rejects malformed JSON before the adapter sees it). Reviewer convention since PR #4533 (`przemkaczmarek`): "test coverage must be achieved via the JSON test framework wherever possible. The JSON test framework has shared memory checks built in which are very important."

---

## Sources

- `prebid/prebid-server` master branch (verified at v4.1.0 release)
- `adapters/bidder.go`, `adapters/adapterstest/test_json.go`
- `util/jsonutil/jsonutil.go`, `util/ptrutil/ptrutil.go`, `util/iterutil/iterutil.go`
- `errortypes/errortypes.go`
- `macros/macros.go` (`EndpointTemplateParams`)
- `config/bidderinfo.go` (`BidderInfo` struct)
- `openrtb_ext/bidders.go` (`NewBidderParamsValidator`, bidder constants)
- Reviewer practice synthesized from 89 reference PRs at `prebid-server-go/references/new-bid-adapter-prs.md`
