---
name: adapter-code-pr-review
description: Reviews changes to adapter Go code, adapter tests, JSON test fixtures (exemplary/supplemental/amp/video/videosupplemental), and bidder registration entries. USE WHEN a PR touches adapters/{bidder}/*.go (excluding params_test.go), any {bidder}test/**/*.json, exchange/adapter_builders.go, or openrtb_ext/bidders.go. Do NOT use for static/bidder-info/*.yaml, static/bidder-params/*.json, openrtb_ext/imp_*.go, or params_test.go — those are owned by sibling skills.
version: 1.0.0
---

# Adapter Code PR Review

Review pull requests that touch adapter implementation code, adapter tests, JSON test data, and bidder registration files. For every changed function, test, or registration entry, apply the matching verification workflow to produce actionable review findings.

## Core Principle: Review Only What Changed

**You are a PR reviewer, not a full-file auditor.** The PR diff is your single source of truth. Only create verification tasks for code, tests, or registrations that actually changed in the diff. Code that already exists unchanged in the file was approved in a prior PR and is out of scope.

- **NEVER** review unchanged functions, test cases, or registration entries just because they exist in a file
- **NEVER** audit the entire adapter implementation when only one function changed
- **DO** verify every line that appears as added (`+`) or modified in the diff
- The number of verification tasks should correspond to changed items, not total items in the file

## Activation

This skill activates when a PR adds, modifies, or removes any file matching:
- `adapters/{bidder}/{bidder}.go` — adapter implementation
- `adapters/{bidder}/{bidder}_test.go` — adapter JSON test runner
- `adapters/{bidder}/*.go` — any additional Go files in the adapter directory (e.g., `{bidder}_relay_test.go`, helper files)
- `adapters/{bidder}/{bidder}test/exemplary/*.json` — exemplary test fixtures
- `adapters/{bidder}/{bidder}test/supplemental/*.json` — supplemental/error test fixtures
- `adapters/{bidder}/{bidder}test/amp/*.json` — AMP (Accelerated Mobile Pages) test fixtures
- `adapters/{bidder}/{bidder}test/video/*.json` — video-specific test fixtures
- `adapters/{bidder}/{bidder}test/videosupplemental/*.json` — video error-path fixtures
- `exchange/adapter_builders.go` — builder registration (only lines adding/removing bidder entries)
- `openrtb_ext/bidders.go` — bidder constant registration (only lines adding/removing bidder entries)

**Exclusion:** `adapters/*/params_test.go` is owned by `bidder-params-pr-review` and must be excluded even though it matches the `adapters/{bidder}/*.go` pattern.

This skill does **NOT** activate for files owned by other skills:
- `static/bidder-info/*.yaml` — owned by `bidder-info-pr-review`
- `static/bidder-params/*.json` — owned by `bidder-params-pr-review`
- `openrtb_ext/imp_*.go` — owned by `bidder-params-pr-review`
- `adapters/*/params_test.go` — owned by `bidder-params-pr-review`

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model,
which can paraphrase source code and lose raw JSON structure. `curl` returns
exact, deterministic content. Parse the raw JSON output directly.

### Step 1: Receive Triage Data

This skill receives pre-fetched PR data from the **pr-triage** skill. Do NOT re-fetch PR files or run drift checks.

**1a. Accept the routing manifest.**

The pr-triage skill provides:
- The complete file list filtered to files owned by this skill (adapter Go files, test fixtures, registration files)
- Each file's `filename`, `status`, and `patch` (diff hunks)
- Drift check results for `adapters/adapterstest/test_json.go` test harness
- CI status summary
- PR type classification
- Bulk change flag (if applicable)
- PR description analysis (docs PR link, template completeness, feature rationale)
- Commit history (count, messages, head SHA)
- PR comments (reviewer feedback, CI bot reports, author responses) — categorized and summarized
- Duplicate PR search results
- Bidder metadata per bidder: `aliasOf` status and `capabilities` (extracted from PR or "not in PR — downstream must fetch from master")

**1b. Handle drift warnings.**

If the triage manifest reports drift for adapter-code, include the drift warning in the review output. Do not re-fetch `test_json.go`.

**1c. Handle CI status.**

If CI status is `blocked`, acknowledge in the summary and note that review findings are preliminary until CI passes.

**1d. Incorporate reviewer feedback.**

Cross-reference the PR comments from the triage manifest against your review findings:
- If a reviewer has already flagged an issue you also find, note: `Previously flagged by {reviewer}` and reference their comment
- If a CI bot report indicates a failure relevant to your scope (e.g., test failures, build errors), use it as additional evidence for your verification steps
- If the author has responded to reviewer feedback with fixes, check whether the current diff reflects those fixes

**1e. Fetch full file content and capabilities.**

For files with status `modified`, the patch contains only changed regions. When verification requires full file context (e.g., understanding the complete adapter flow, checking all error paths):

```bash
# Full file for modified adapter code
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/{head_sha}/{filename}"
# Capabilities from master when not in PR (for test data coverage checks)
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/master/static/bidder-info/{bidder}.yaml"
```

- For `added` files: full content is already in the patch (all `+` lines) — do NOT re-fetch
- For `modified` files: only fetch if the verification workflow requires context beyond the diff hunks
- **Capabilities strategy**: Check the triage manifest's `BIDDER METADATA` section first. If capabilities are `"not in PR — downstream must fetch from master"`, use the curl command above to fetch from master. Use capabilities for: test data media type coverage, Site/App parity checks, bid type resolution validation
- Cache fetched content — do not re-fetch the same file multiple times

**1f. Handle bulk change mode.**

If the triage manifest indicates PR type is `infrastructure` and this skill's files are part of the bulk pattern:
- Do NOT create per-bidder item-level tasks
- Instead, create a single "bulk pattern consistency" task:
  - Verify the same change was applied consistently across all affected bidders
  - Flag any bidders that deviate from the pattern (outliers)
  - Focus detailed review only on net-new adapter code that is NOT part of the bulk pattern

### Step 2: Extract Changes From the Diff

Group changed files by bidder name (extracted from filename patterns). For each bidder, identify which file types changed:

- `adapters/{bidder}/{bidder}.go` — adapter code changes
- `adapters/{bidder}/{bidder}_test.go` — test runner changes
- `adapters/{bidder}/{bidder}test/exemplary/*.json` — exemplary test data changes
- `adapters/{bidder}/{bidder}test/supplemental/*.json` — supplemental test data changes
- `adapters/{bidder}/{bidder}test/amp/*.json` — AMP test data changes
- `exchange/adapter_builders.go` — registration changes
- `openrtb_ext/bidders.go` — registration changes

For each changed file, parse the diff to identify exactly what changed:

- **Added file** (entire file is new) — every function/test/entry is new and needs review
- **Modified file** (some lines changed) — **ONLY** review the specific functions/entries that changed. Unchanged code is out of scope.
- **Removed file** (entire file deleted) — create a single task to validate the removal is intentional

**Comment-only changes:** If all changed lines are Go comments (`//` lines) or whitespace with no functional code changes, the file has **zero changed items**. Skip to Step 5 and recommend fast-track approval.

### Step 3: Build Verification Task List

There are two categories of tasks:

**1. PR-level task (at most one):** A single task covering PR-wide checks that don't map to a specific code change:
- **Registration completeness**: For new adapters, verify all registration points are present (see [Registration Completeness](#workflow-registration-completeness) workflow)
- **Test data coverage**: Verify test fixtures cover the media types declared in capabilities (cross-read `static/bidder-info/{bidder}.yaml`)
- **Dependency check**: If `go.mod` or `go.sum` is modified, verify new dependencies are reasonable and necessary
- **Naming consistency**: Bidder name matches across all files (directory name, package name, test directory name, builder registration, bidder constant)
- **Cross-file JSON tag consistency**: When the PR includes both `openrtb_ext/imp_{bidder}.go` AND adapter Go files in `adapters/{bidder}/`, cross-verify that JSON tag spellings are consistent across files (publisher-facing struct tags vs adapter outgoing-payload struct tags). Mismatch examples: `pubclick` in one file but `pub_click` in another. Severity: **FAIL** on detected mismatch. (Triggered post-merge in PR #4592 Microsoft.)
- **YAML capabilities ↔ Go MType drift**: Cross-read `static/bidder-info/{bidder}.yaml` capabilities and the adapter's `MakeBids` bid-type resolution. Every YAML-declared media type must have a Go return path; every Go-handled media type should be in YAML. See the canonical rule at [../shared/framework-utilities.md#yaml-capabilities--go-mtype-drift](../shared/framework-utilities.md#yaml-capabilities--go-mtype-drift). Severity: **FAIL** when YAML declares a type Go cannot return; **WARN** for the dead-branch direction.

**2. Item-level tasks (one per changed item):** For each changed function, entry, or test fixture, look up the matching Verification Workflow:

For **adapter code changes** (`adapters/{bidder}/{bidder}.go`):
1. Changed Builder function — use [Builder Function Changed](#workflow-builder-function-changed)
2. Changed MakeRequests — use [MakeRequests Changed](#workflow-makerequests-changed)
3. Changed MakeBids — use [MakeBids Changed](#workflow-makebids-changed)
4. Changed helper functions — use [Helper Function Changed](#workflow-helper-function-changed)
5. Changed struct/type declarations — use [Adapter Type Changed](#workflow-adapter-type-changed)

For **additional Go files** (`adapters/{bidder}/*.go` not matching `{bidder}.go`, `{bidder}_test.go`, or `params_test.go`):
6. Additional Go files — use [Additional Go File Changed](#workflow-additional-go-file-changed)

For **registration changes**:
7. Changed `exchange/adapter_builders.go` — use [Builder Registration Changed](#workflow-builder-registration-changed)
8. Changed `openrtb_ext/bidders.go` — use [Bidder Constant Changed](#workflow-bidder-constant-changed)

For **test runner changes** (`adapters/{bidder}/{bidder}_test.go`):
9. Changed test runner — use [Test Runner Changed](#workflow-test-runner-changed)

For **test data changes** (`adapters/{bidder}/{bidder}test/**/*.json`):
10. Changed/added exemplary fixtures — use [Exemplary Test Data Changed](#workflow-exemplary-test-data-changed)
11. Changed/added supplemental fixtures — use [Supplemental Test Data Changed](#workflow-supplemental-test-data-changed)
12. Changed/added AMP fixtures — use [AMP Test Data Changed](#workflow-amp-test-data-changed)

**Test data grouping:** Group test data files by directory for task creation. Create **one task** for all exemplary fixtures, **one task** for all supplemental fixtures, and **one task** for all AMP fixtures per bidder — not one task per JSON file. The workflows define set-level coverage checks. For modified existing test files, create one task per changed file.

**Do NOT create separate "new adapter" tasks.** For new adapters, the relevant checks are folded into the item-level workflows plus the PR-level registration completeness check.

**Bulk change handling:** If the triage manifest indicates this is an infrastructure/bulk change (5+ bidder directories with the same pattern), use the reduced-scope review described in Step 1d instead of per-bidder task creation. Create a single "bulk pattern consistency" task for the repeated pattern, and only create per-bidder item-level tasks for net-new adapter code that deviates from the bulk pattern.

**Sanity check**: The number of item-level tasks should correspond to the number of distinct changed items across all files (with test data grouped per directory). If you have significantly more tasks than changed items, you may be reviewing out-of-scope content. The PR-level task does not count toward this check.

### Step 4: Execute Verification Tasks

Work through tasks, parallelizing where possible. For each task:

1. Mark the task `in_progress`
2. Execute every verification step from the matching workflow
3. Record each step's result as PASS, FAIL, or WARN with evidence
4. Mark the task `completed` with findings

### Step 5: Summary

After all tasks are complete, produce a review summary:

- Files changed (with category: added/modified/removed)
- Items changed per file
- Verification steps executed
- Issues found (critical / warning / info)
- Recommendation (approve, request changes, or comment)

---

## Verification Workflows

### Workflow: Builder Function Changed

**Triggers when:** The `Builder` function in `adapters/{bidder}/{bidder}.go` is added or modified.

1. **Correct signature**: Must be `func Builder(bidderName openrtb_ext.BidderName, config config.Adapter, server config.Server) (adapters.Bidder, error)`
2. **Endpoint from config**: The adapter struct should store `config.Endpoint`, not a hardcoded URL
3. **No hardcoded credentials**: Builder must not embed API keys, passwords, or secrets. Configuration should come from `config.Adapter` or `server` parameters
4. **Error handling**: If the builder performs validation (e.g., URL template parsing), errors should be returned, not panicked
5. **Template macros**: If the endpoint URL uses template macros (e.g., `{{.AccountID}}`), verify the builder resolves them using `macros.NewStringIndexBasedReplacer()` or similar. Supported `EndpointTemplateParams` fields (18 total — see [../shared/framework-utilities.md#endpoint-template-macros](../shared/framework-utilities.md#endpoint-template-macros) for canonical list): `Host`, `PublisherID`, `ZoneID`, `SourceId`, `AccountID`, `AdUnit`, `MediaType`, `GvlID`, `PageID`, `SupplyId`, `ImpID`, `SspId`, `SspID`, `SeatID`, `TokenID`, `PartnerId`, `Region`, `PlacementID`. **`ExternalURL` is NOT an endpoint macro** — it belongs only to user-sync URL templates. Flag any unsupported macro names as FAIL

### Workflow: MakeRequests Changed

**Triggers when:** The `MakeRequests` method is added or modified.

1. **Correct signature**: Must be `func (a *adapter) MakeRequests(request *openrtb2.BidRequest, requestInfo *adapters.ExtraRequestInfo) ([]*adapters.RequestData, []error)`
2. **Imp extension unmarshaling**: Must extract bidder params from `imp.Ext` correctly:
   - First unmarshal to `adapters.ExtImpBidder` (or use `jsonutil.Unmarshal`)
   - Then unmarshal `bidderExt.Bidder` to the bidder-specific imp ext struct from `openrtb_ext`
   - Use `jsonutil.Unmarshal` (not `json.Unmarshal`) for consistent error handling
   - The target struct MUST be the shared `openrtb_ext.ExtImp{Bidder}` (canonical convention) or `openrtb_ext.ImpExt{Bidder}` (legacy / tolerated for older adapters) from `openrtb_ext/imp_{bidder}.go`, NOT a struct defined inline in the adapter code. Flag inline imp ext struct definitions as WARN — they should be in `openrtb_ext/`. For new adapters, recommend `ExtImp{Bidder}` if the file uses `ImpExt{Bidder}` (INFO).
3. **RequestData fields**: Each returned `adapters.RequestData` must include:
   - `Method`: Typically `http.MethodPost` (use the `net/http` constant, not the string literal `"POST"`)
   - `Uri`: The endpoint URL (from adapter struct, not hardcoded)
   - `Body`: Marshaled request JSON
   - `ImpIDs`: Must call `openrtb_ext.GetImpIDs(request.Imp)` — this is required for impression tracking
   - `Headers`: Should include `Content-Type: application/json` at minimum. Adapters that omit `Headers` entirely from `RequestData` should be flagged as **WARN** — some upstream servers reject the request body without an explicit Content-Type header. Severity escalates to FAIL only if the upstream is known to require it.
4. **Copy semantics**: Must NOT mutate the shared `*openrtb2.BidRequest` or its nested objects directly. Create copies before modification:
   - Copy `request.Site`, `request.App` before modifying publisher
   - Copy `imp.Banner`, `imp.Video` before modifying fields
   - Copy `request` itself if modifying top-level fields
   - **Range-loop variable trap**: when iterating `for i, imp := range request.Imp`, the loop variable `imp` is a copy. Use `&request.Imp[i]` (index access) when you need a pointer to the actual slice element. Flag `&imp` (pointer to range variable) as **FAIL** — Go 1.21 fixed loop-variable scoping but only when explicitly opted in.
   - **Pointer write-back hazard**: `request.Site` and `request.App` are `*` pointers shared across adapters. Mutating `request.Site.Publisher.ID = X` writes to shared state. Always: `siteCopy := *request.Site; pubCopy := *siteCopy.Publisher; pubCopy.ID = X; siteCopy.Publisher = &pubCopy; request.Site = &siteCopy`. The `ptrutil.Clone` helper (`util/ptrutil`) is acceptable shorthand — INFO-level recommendation only.
   - **Site/App parity**: If the adapter adds handling for `request.Site` (e.g., setting publisher), cross-read `static/bidder-info/{bidder}.yaml` — if both `site` and `app` are in capabilities, verify `request.App` is also handled (and vice versa). Flag missing context handling as WARN
5. **Error types**: Use `errortypes.BadInput` for invalid request data (client's fault), not generic errors. Errors generated within an impression loop should include the impression ID or index for log context
6. **Marshal vs unmarshal error safety**: **Marshaling errors must NEVER be silently swallowed** — they can indicate shared memory corruption in production and will cause adapter panics if not surfaced. Unmarshaling errors for optional extension data MAY be swallowed if the data is truly optional and the request is valid without it. Flag any `json.Marshal` / `jsonutil.Marshal` call whose error is ignored or discarded as **FAIL**
7. **Use framework JSON utilities**: Adapters should use `jsonutil.Marshal`/`jsonutil.Unmarshal` from `github.com/prebid/prebid-server/v4/util/jsonutil`, not `encoding/json.Marshal`/`json.Unmarshal`. The framework versions provide consistent error handling and format. Flag use of `encoding/json` for marshal/unmarshal operations as **WARN**
8. **Currency conversion**: If converting bid floors, use `requestInfo.ConvertCurrency()` with proper error handling. **Available ONLY in `MakeRequests`** — the `MakeBids` signature does not include `reqInfo`. If you need to convert currencies based on the bid response, set `bidResponse.Currency` to the bidder's currency and let PBS `exchange/bidder_validate_bids.go:79` (`validateCurrency`) handle the mismatch reconciliation.
9. **Multi-impression handling**: If the adapter sends one request per impression, verify each request has the correct single-impression slice. If batching all impressions, verify the full slice is included
10. **No redundant PBS core checks**: PBS core handles validation that adapters frequently re-implement defensively. Flag re-implementations as **WARN**:
    - `if len(request.Imp) == 0 { return error }` — PBS core rejects empty-imp requests
    - `if config.Endpoint == "" { return error }` in `Builder` — YAML loader validates endpoint at startup
    - `if banner == nil && video == nil && audio == nil && native == nil { skip }` — PBS core filters by `static/bidder-info/{bidder}.yaml` capabilities
    - `if site == nil && app == nil { error }` — same capability filtering
    - Re-validating bidder-params with `minLength`/regex/required — schema validation runs upstream
    - `hasSiteOrAppID` style helpers — capability filtering already guarantees this
    - **Specific-field defensive checks ARE valid**: PBS only enforces `Site.ID || Site.Page` (not `Site.ID` alone), does NOT enforce `App.ID`, does NOT enforce `Publisher.ID`. If your endpoint specifically needs one of these fields, KEEP the defensive check — see [../shared/framework-utilities.md#site--app-id--nuanced-enforcement](../shared/framework-utilities.md#site--app-id--nuanced-enforcement) for the full table.
    
    See [../shared/framework-utilities.md#anti-pattern-pbs-core-already-does-this](../shared/framework-utilities.md#anti-pattern-pbs-core-already-does-this) for the canonical list.

### Workflow: MakeBids Changed

**Triggers when:** The `MakeBids` method is added or modified.

1. **Correct signature**: Must be `func (a *adapter) MakeBids(request *openrtb2.BidRequest, requestData *adapters.RequestData, responseData *adapters.ResponseData) (*adapters.BidderResponse, []error)`
2. **HTTP status handling**: Must handle standard response codes:
   - 204 (No Content): Return `nil, nil` — use `adapters.IsResponseStatusCodeNoContent(responseData)`. **`MakeBids` IS invoked for 204** — PBS does NOT skip 204 responses (verified at `exchange/bidder.go:304`); adapters that don't handle it will attempt to unmarshal an empty body and may produce confusing errors.
   - Non-2xx errors (4xx/5xx): `MakeBids` is NOT called for these (PBS surfaces `BadServerResponse` automatically). Defensive checks for non-2xx in `MakeBids` are redundant unless the adapter specifically handles a 3xx redirect path.
   - Both checks must come BEFORE attempting to unmarshal the response body.
3. **Response unmarshaling**: Use `jsonutil.Unmarshal` (not `json.Unmarshal`) to unmarshal `responseData.Body` into `openrtb2.BidResponse`
4. **Bid type resolution**: Must determine bid type for each bid. Preferred approach (in order):
   - From `bid.MType` (OpenRTB 2.6 markup type): `openrtb2.MarkupBanner` (1), `openrtb2.MarkupVideo` (2), `openrtb2.MarkupAudio` (3), `openrtb2.MarkupNative` (4)
   - From response ext (e.g., `bid.Ext.prebid.type`)
   - From impression lookup (match `bid.ImpID` to original imp and check which media type exists)
   - Flag if bid type resolution has no fallback for unknown types
   - Error messages from MakeBids that fail to resolve bid type MUST include the `bid.ImpID` for log diagnosability. Example: `fmt.Errorf("unsupported bid mtype %d for impID %s", bid.MType, bid.ImpID)`. Use `%w` (wrapping) when wrapping a downstream error.
5. **BidderResponse construction**: Must use `adapters.NewBidderResponseWithBidsCapacity(len(request.Imp))` for proper allocation
6. **Currency**: Set `bidResponse.Currency` from the response **only if non-empty** — do not overwrite the default `"USD"` with an empty string. Guard with `if response.Cur != "" { bidResponse.Currency = response.Cur }`
7. **Bid pointer safety**: When appending bids, use `&seatBid.Bid[i]` (pointer to slice element), not `&bid` (pointer to loop variable)
8. **BidMeta / BidVideo population**: If the adapter extracts metadata from `bid.Ext` (e.g., advertiser ID, network ID, brand ID for BidMeta; duration, primary category for BidVideo), verify: proper error handling for malformed `bid.Ext`, zero-value checking before populating numeric fields, and JSON framework test coverage for the extraction wherever possible (unit tests only as last resort when the framework can't compare enriched objects)
9. **Coverage of declared media types**: Cross-reference the bid type resolution against `static/bidder-info/{bidder}.yaml` capabilities. Every media type declared in capabilities must have a Go-side handling path (return value or typed error). If YAML declares `audio` but `MakeBids` switch only covers banner/video/native, flag as **FAIL** — PBS core will route audio impressions here based on YAML and the adapter cannot handle them. Conversely, if Go handles a media type not in YAML, flag as **WARN** (dead branch).

### Workflow: Helper Function Changed

**Triggers when:** A non-interface helper function is added or modified in the adapter file.

1. **Necessity**: Helper should serve a clear purpose (bid type mapping, header construction, extension extraction, etc.). Flag unnecessary wrappers that just marshal/unmarshal without transformation
2. **No dead or commented-out code**: Flag blocks of commented-out code as **WARN** — code should be removed, not commented out. This applies to test files too. Also flag debug-print statements (`fmt.Println`, `log.Debugf` referencing local variables) left in production paths.
3. **No JSON injection via RawMessage**: NEVER insert `json.RawMessage` directly into a JSON structure by string concatenation or format string (e.g., `fmt.Sprintf("{\"key\":%s}", rawMsg)`). This exposes a JSON injection attack. Always use `json.Marshal` / `jsonutil.Marshal` to re-serialize. Flag as **FAIL** (security)
4. **Error handling**: Helpers that can fail should return errors, not panic
5. **No side effects**: Helpers should not modify global state
6. **Unexported**: Helper functions in the adapter package should be unexported (lowercase) unless needed externally
7. **No function-parameter shadowing**: Closures or inner blocks in helpers must not shadow the enclosing function's parameters (declaring an inner variable with the same name as a parameter). Severity: **INFO** with recommendation to rename. Reviewer-flagged in PR #4592 (Microsoft) on `displayManagerVerBuilder` and `getMediaTypeForBid` helpers.

### Workflow: Adapter Type Changed

**Triggers when:** A struct or type declaration in the adapter file is added or modified.

1. **Adapter struct**: The main adapter struct should be unexported (`type adapter struct`), hold only configuration (typically just `endpoint string`), and not store request-scoped state
2. **No exported types**: Adapter-internal types should be unexported. Only the `Builder` function should be exported
3. **No exported struct fields**: Adapter struct fields should be unexported (lowercase). For example, `endpoint string` not `Endpoint string`, `endpointTemplate *template.Template` not `EndpointTemplate *template.Template`. Exported fields expose adapter internals unnecessarily. Flag as WARN
4. **No unnecessary fields**: The adapter struct should not hold HTTP clients, loggers, or other infrastructure — these are provided by the framework

### Workflow: Additional Go File Changed

**Triggers when:** A Go file in `adapters/{bidder}/` is added or modified that does NOT match `{bidder}.go`, `{bidder}_test.go`, or `params_test.go`. Examples: `{bidder}_relay_test.go`, `{bidder}_utils.go`, `{bidder}_types.go`.

1. **Necessity**: The additional file should serve a clear purpose (separate test suite, helper utilities, type definitions). Flag if it duplicates logic already in the main adapter file
2. **Package name**: Must match `package {bidder}`
3. **Test files**: If the file is a `_test.go` file, verify it follows Go testing conventions and tests meaningful adapter behavior. Large test files (>500 lines) may indicate the adapter has custom test infrastructure beyond the standard JSON test runner — review for correctness but note this is non-standard
4. **No exported symbols**: Additional Go files in adapter packages should generally not export types or functions (same rules as the main adapter file — only `Builder` should be exported)

### Workflow: Builder Registration Changed

**Triggers when:** `exchange/adapter_builders.go` is modified.

1. **Import present**: A new import line for `"github.com/prebid/prebid-server/v4/adapters/{bidder}"` must be added. If the bidder name conflicts with a Go keyword or existing package, an import alias is used (e.g., `ttx "...33across"`)
2. **Map entry present**: An entry `openrtb_ext.Bidder{Name}: {package}.Builder,` must be in the `newAdapterBuilders()` map
3. **Alphabetical order**: Both the import and map entry should be in alphabetical order relative to neighbors
4. **Correct bidder constant**: The `openrtb_ext.Bidder{Name}` must match the constant defined in `openrtb_ext/bidders.go`
5. **No extra changes**: Registration should only add the import + map entry. Flag any other modifications to this file

### Workflow: Bidder Constant Changed

**Triggers when:** `openrtb_ext/bidders.go` is modified.

1. **Const declaration**: `Bidder{Name} BidderName = "{bidder}"` — the string value (right-hand side) must be all-lowercase and match the directory name under `adapters/`. The constant identifier (left-hand side) usually matches the slug (e.g., `BidderMsft = "msft"`) but a marketing-name identifier is acceptable when the bidder organization markets under a name distinct from its slug (e.g., `BidderMicrosoft = "msft"` per PR #4592). Both forms are tolerated.
2. **CoreBidderNames entry**: The constant must be added to the `coreBidderNames` slice
3. **Alphabetical order**: Both the const and slice entry should be in alphabetical order
4. **No extra changes**: Registration should only add the const + slice entry. Flag any other modifications to this file (unless adding alias constants, which is acceptable)

### Workflow: Test Runner Changed

**Triggers when:** `adapters/{bidder}/{bidder}_test.go` is added or modified.

1. **Package name**: Must be `package {bidder}`
2. **Test function**: Must be `func TestJsonSamples(t *testing.T)` (exact name required by convention)
3. **Builder invocation**: Must call `Builder` with:
   - Correct bidder constant: `openrtb_ext.Bidder{Name}`
   - A config with a fake endpoint: `config.Adapter{Endpoint: "https://..."}`
   - A server config: `config.Server{ExternalUrl: "http://hosturl.com", GvlID: 1, DataCenter: "2"}`
4. **Test directory reference**: Calls `adapterstest.RunJSONBidderTest(t, "{dir}", bidder)`.
   - Canonical: `{dir}` = `{bidder}test` (no separator). Required for new adapters.
   - Legacy alternates tolerated: `adapters/msft/test/`, `adapters/msft/test-extrainfo/`. Severity: **INFO** (not FAIL) when reviewing such an adapter — the canonical naming was not in convention when these were added.
   - Multiple `RunJSONBidderTest` calls in a single test runner (one per directory) are tolerated when an adapter genuinely needs distinct test scenarios (e.g., different ExtraAdapterInfo configurations, as in msft).
5. **Build error check**: Should check and `t.Fatalf` if `Builder` returns an error
6. **Minimal test runner**: The test runner should be a thin wrapper (~20 lines) that delegates to `adapterstest.RunJSONBidderTest`. Extensive custom unit test logic (>100 lines) in the test runner is non-standard — reviewers expect custom test scenarios to be covered via JSON test fixtures, not Go unit tests. Flag as WARN if the test runner contains substantial test logic beyond the standard pattern

### Workflow: Exemplary Test Data Changed

**Triggers when:** A file in `adapters/{bidder}/{bidder}test/exemplary/` is added or modified.

1. **Valid JSON structure**: Must have the standard test fixture structure:
   - `mockBidRequest` — the incoming OpenRTB bid request
   - `httpCalls` — array of `{ expectedRequest, mockResponse }` pairs
   - `expectedBidResponses` — array of expected adapter output
2. **expectedRequest fields**:
   - `uri` — must match the fake endpoint from the test runner
   - `body` — the expected outgoing request body after adapter processing
   - `impIDs` — must be present listing the impression IDs (required by the test harness)
3. **mockResponse fields**:
   - `status` — HTTP status code (200 for exemplary)
   - `body` — the mock OpenRTB bid response
4. **Bid type present**: Each bid in `expectedBidResponses` should have a `type` field (`banner`, `video`, `native`, `audio`)
5. **Media type coverage**: For new adapters, the set of exemplary tests should collectively cover each media type declared in `capabilities` (cross-read `static/bidder-info/{bidder}.yaml`). Flag missing media types as WARN
6. **Context coverage**: For new adapters, exemplary tests should include at least one fixture per declared `capabilities` platform (one with `mockBidRequest.app` for app, one with `mockBidRequest.site` for site, one with `mockBidRequest.dooh` for DOOH). Flag missing platform coverage as **WARN**. Sample-PR evidence: PR #4287 (Optidigital) declared all three platforms but only had a single fixture without site/app/dooh in the request — this rule would have caught it.
7. **Realistic data**: Test fixtures should use realistic bid request data (not obviously placeholder values). Check for `test-request-id` style IDs (acceptable in tests) vs obviously invalid data

### Workflow: Supplemental Test Data Changed

**Triggers when:** A file in `adapters/{bidder}/{bidder}test/supplemental/` is added or modified.

1. **Valid JSON structure**: Same base structure as exemplary, but may include:
   - `expectedMakeRequestsErrors` — errors expected from MakeRequests
   - `expectedMakeBidsErrors` — errors expected from MakeBids
2. **Error format**: Each expected error should have:
   - `value` — the error message string
   - `comparison` — typically `"literal"` or `"regex"`
3. **Error path coverage**: For new adapters, supplemental tests should cover at minimum:
   - Invalid/malformed `imp.ext` (bad JSON)
   - Invalid `imp.ext.bidder` (bad bidder params)
   - HTTP 204 (no content response)
   - HTTP 400+ (server error response)
   - Invalid/malformed response body
   - Unsupported or unknown bid media type
4. **No exemplary patterns**: Supplemental tests should test error paths. Flag as WARN if a supplemental test has no expected errors (it may belong in exemplary/)

### Workflow: AMP Test Data Changed

**Triggers when:** A file in `adapters/{bidder}/{bidder}test/amp/` is added or modified.

1. **Valid JSON structure**: Same structure as exemplary test fixtures (`mockBidRequest`, `httpCalls`, `expectedBidResponses`)
2. **AMP context**: The `mockBidRequest` should represent an AMP scenario — typically includes `site` context (not `app`) and may include AMP-specific extensions or signals
3. **Media type coverage**: AMP tests should cover the media types the adapter supports in the site/web context (banner, video, native as applicable)
4. **Not a duplicate**: AMP tests should exercise AMP-specific adapter behavior (e.g., AMP detection, format restrictions). If the adapter has no AMP-specific logic, AMP tests may duplicate exemplary tests — flag as INFO

### Workflow: Video Test Data Changed

**Triggers when:** A file in `adapters/{bidder}/{bidder}test/video/*.json` is added or modified.

1. **Valid JSON structure**: Same shape as exemplary fixtures (`mockBidRequest`, `httpCalls`, `expectedBidResponses`).
2. **Video-specific request shape**: `mockBidRequest.imp[*].video` populated with realistic fields (`mimes`, `w`, `h`, `protocols`, `linearity`, etc.). The expected outgoing request body in `httpCalls[*].expectedRequest.body` should preserve the video object.
3. **Video bid type**: `expectedBidResponses[*].bids[*].type` should be `"video"` for these fixtures.
4. **Pod video specifics**: If the adapter supports video pods (multi-imp video), include a `dynamic-pod.json` or similar fixture exercising the pod adapter behavior.
5. **Coverage**: Use `video/` only when the adapter has substantial video-specific logic (e.g., per-format markup, pod batching) that benefits from a dedicated suite. Otherwise video coverage in `exemplary/` is sufficient.

### Workflow: VideoSupplemental Test Data Changed

**Triggers when:** A file in `adapters/{bidder}/{bidder}test/videosupplemental/*.json` is added or modified.

1. **Error-path structure**: Same shape as supplemental — may include `expectedMakeRequestsErrors` / `expectedMakeBidsErrors`.
2. **Video error scenarios**: typical cases include malformed `imp.video`, video MIME type rejection, unsupported `protocols`, missing required video fields, video format mismatch with declared capabilities.
3. **Distinct from supplemental**: Place a fixture in `videosupplemental/` only if the error path is video-specific. Generic error paths (HTTP 204/400/500, malformed `imp.ext`) belong in `supplemental/`.

### Workflow: Test Data Accuracy

**Applies as a cross-check to all test data workflows (exemplary, supplemental, AMP).**

1. **Filename matches content**: The test fixture filename should accurately describe what it tests. Flag mismatches as WARN:
   - A file named `multi-imp.json` should have multiple impressions in `mockBidRequest.imp`
   - A file named `banner.json` should test banner media type
   - A file named `status-204.json` should have `mockResponse.status: 204`
2. **Consistent identifiers**: Bidder name in test data (e.g., seat name in `seatBid`) should match the actual bidder name. Flag misspellings as INFO

### Workflow: Open-URL Endpoint Detection

**Triggers when:** Adapter Go code reads an endpoint URL from `imp.ext.bidder.endpoint` (or any publisher-controlled field) instead of from `config.Endpoint`.

1. **Reject open-URL pattern**: Endpoints MUST come from `static/bidder-info/{bidder}.yaml` `endpoint:` field. Acceptable: hardcoded URL, predefined enum, subdomain template via `{{.Host}}`. Unacceptable: full URL from publisher input. Severity: **FAIL**.
2. **Reviewer policy citation**: see [../shared/framework-utilities.md#open-url-endpoint-policy](../shared/framework-utilities.md#open-url-endpoint-policy) for the canonical rule and the PR #4233 quote.

---

## Workflow: Registration Completeness

**Triggers as a PR-level check when a new adapter directory is added.**

For a complete new adapter, the PR should contain ALL of the following. Check each:

**This skill owns:**
- [ ] `adapters/{bidder}/{bidder}.go` — adapter implementation
- [ ] `adapters/{bidder}/{bidder}_test.go` — JSON test runner
- [ ] `adapters/{bidder}/{bidder}test/exemplary/` — at least one exemplary test
- [ ] `adapters/{bidder}/{bidder}test/supplemental/` — at least one supplemental test
- [ ] `exchange/adapter_builders.go` — import + map entry
- [ ] `openrtb_ext/bidders.go` — const + coreBidderNames entry

**Other skills own (verify presence, not content):**
- [ ] `static/bidder-info/{bidder}.yaml` — bidder info (bidder-info-pr-review)
- [ ] `static/bidder-params/{bidder}.json` — params schema (bidder-params-pr-review)
- [ ] `openrtb_ext/imp_{bidder}.go` — imp ext struct (bidder-params-pr-review)
- [ ] `adapters/{bidder}/params_test.go` — params test (bidder-params-pr-review)

**Split PR handling:** Some adapters are added across multiple PRs (e.g., registration + config in one PR, adapter code in a follow-up). If owned files are missing from this PR:
- If registration files (`adapter_builders.go`, `bidders.go`) are missing but the adapter code is present: flag as **WARN** — "Registration not in this PR. Verify it was completed in a prior PR or will follow."
- If adapter code is missing but registration files are present: flag as **INFO** — "Adapter code may be in a follow-up PR."
- If both code and registration are present but other-skill files are missing: flag as **WARN** — the other skills will handle their own files.
- Only flag as **FAIL** if a clearly required file is missing with no evidence of a split PR (e.g., adapter code references a struct that doesn't exist anywhere).

**Naming consistency check:**
- Directory: `adapters/{bidder}/`
- Package: `package {bidder}`
- Test directory: `{bidder}test`
- Builder import: `"github.com/prebid/prebid-server/v4/adapters/{bidder}"`
- Bidder constant string: `"{bidder}"`
- All must use the exact same bidder name slug (lowercase, no hyphens unless the bidder name itself contains them)

---

## Cross-Skill References (Read-Only)

This skill may read files owned by other skills for context, but does NOT create tasks for them:

- `static/bidder-info/{bidder}.yaml` — read to check declared capabilities (which media types and platforms to expect in test data)
- `static/bidder-params/{bidder}.json` — read to verify adapter code correctly references all declared params
- `openrtb_ext/imp_{bidder}.go` — read to verify adapter code uses the correct imp ext struct type and field names
- `adapters/{bidder}/params_test.go` — read to verify naming consistency

For framework-wide concerns (helper function names, error types, marshaling safety, endpoint template macros, anti-pattern lists, test harness contract), this skill references the shared file at [../shared/framework-utilities.md](../shared/framework-utilities.md) — do not duplicate that content here.

---

## Reference Documentation

See [adapter-code-index.md](references/adapter-code-index.md) for:
- Builder function and adapter struct patterns
- MakeRequests/MakeBids implementation patterns
- Standard helper functions and framework utilities
- Test runner and test data structure
- Registration file patterns
- Common adapter implementation patterns across existing adapters
