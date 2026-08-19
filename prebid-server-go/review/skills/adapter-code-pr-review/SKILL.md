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
- **Cross-file JSON tag consistency — same-direction only**: When the PR includes both `openrtb_ext/imp_{bidder}.go` AND adapter Go files in `adapters/{bidder}/`, cross-verify JSON tag spellings **within each direction**, never across them. The two directions are independent wire contracts:
  - **Inbound** (publisher → PBS): `openrtb_ext.ExtImp{Bidder}` tags must match the property names in `static/bidder-params/{bidder}.json`. A mismatch here rejects valid publisher params. Severity: **FAIL**.
  - **Outbound** (PBS → bidder server): the adapter's own payload struct tags must match what the upstream server expects. A mismatch here is only detectable against the bidder's own API, so use the exemplary fixtures' `expectedRequest.body` as the assertion of record. Severity: **FAIL** when the fixture and the struct disagree.
  - **Inbound tag ≠ outbound tag is NOT a defect.** Deliberate renames across the boundary are normal and merged. Canonical counterexample (merged `msft`): `openrtb_ext/imp_msft.go:14` declares `json:"pubclick"` matching `static/bidder-params/msft.json`, while `adapters/msft/models.go:30` emits `json:"pub_click,omitempty"` outbound, and `adapters/msft/test/exemplary/all-params.json` asserts **both** spellings (`pubclick` in the request, `pub_click` in the expected outgoing body). Severity: **INFO** at most — note the rename so a reader knows it is intentional, and only escalate if no fixture pins the outbound spelling. The matching rule in [../bidder-params-pr-review/references/params-type-index.md](../bidder-params-pr-review/references/params-type-index.md) states the same thing; keep the two aligned.
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
5. **Template macros**: If the endpoint URL uses template macros (e.g., `{{.AccountID}}`), verify the builder resolves them using `macros.NewStringIndexBasedReplacer()` or similar. Check the macro name against the canonical `EndpointTemplateParams` allow-list at [../shared/framework-utilities.md#endpoint-template-macros](../shared/framework-utilities.md#endpoint-template-macros) — **read it there, do not keep a copy here**; a second list is what goes stale and produces false FAILs. **`ExternalURL` is NOT an endpoint macro** — it belongs only to user-sync URL templates. Flag an unsupported macro name as **FAIL**: `config/bidderinfo.go:492-507` resolves the template at startup and `text/template` errors on an unknown struct field, so `config.New` refuses to boot.

### Workflow: MakeRequests Changed

**Triggers when:** The `MakeRequests` method is added or modified.

1. **Correct signature**: Must be `func (a *adapter) MakeRequests(request *openrtb2.BidRequest, requestInfo *adapters.ExtraRequestInfo) ([]*adapters.RequestData, []error)`
2. **Imp extension unmarshaling**: Must extract bidder params from `imp.Ext` correctly:
   - First unmarshal to `adapters.ExtImpBidder` (or use `jsonutil.Unmarshal`)
   - Then unmarshal `bidderExt.Bidder` to the bidder-specific imp ext struct from `openrtb_ext`
   - Use `jsonutil.Unmarshal` (not `json.Unmarshal`) for consistent error handling
   - **Distinct message per failure mode**: the two unmarshal sites (`imp.ext` → `ExtImpBidder`, then `bidderExt.Bidder` → the imp-ext struct) MUST return distinguishable error messages, and should wrap the cause with `%w`. Flag reusing one shared message constant across both — so production logs cannot separate a malformed `imp.ext` from a wrong `imp.ext.bidder` structure — as **WARN** (**INFO** if the two sites live in different functions where the call stack already disambiguates). Canonical: the Teal #4765 `parseImpExt`, where both sites returned `"Error parsing imp.ext for impression %s"`; the port template `bidder.go.j2` already emits distinct messages, so a single shared constant is a regression from it.
   - The target struct MUST be the shared `openrtb_ext.ExtImp{Bidder}` (canonical convention) or `openrtb_ext.ImpExt{Bidder}` (legacy / tolerated for older adapters) from `openrtb_ext/imp_{bidder}.go`, NOT a struct defined inline in the adapter code. Flag inline imp ext struct definitions as WARN — they should be in `openrtb_ext/`. For new adapters, recommend `ExtImp{Bidder}` if the file uses `ImpExt{Bidder}` (INFO).
3. **RequestData fields**: Each returned `adapters.RequestData` must include:
   - `Method`: Typically POST. **The `http.MethodPost` constant and the `"POST"` string literal are equally acceptable — not a finding in either direction.** `http.MethodPost` is defined as `"POST"`, so the choice is purely lexical, and the literal is the upstream majority — 201 literal sites versus 69 constant sites at master @0ba3523. Do not emit a finding, at any severity, on this choice.
     ```bash
     grep -rEn --include='*.go' 'Method: +"POST"' adapters/ | grep -vc _test.go            # 201
     grep -rEn --include='*.go' 'Method: +http\.MethodPost' adapters/ | grep -vc _test.go  # 69
     ```
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
11. **Request-level key derived from imps — divergence handling**: If the adapter derives a *request-level* value from impressions (e.g., account ID → `publisher.id`, an endpoint token, a host shard) by reading it from the first valid imp, verify it handles imps that disagree. Silently letting "first valid wins" while ignoring divergent values across imps is a latent bug (the Teal #4765 mixed-account class). Expected: validate and return `errortypes.BadInput` on divergence, OR document why first-wins is safe for this bidder. Severity: **WARN** (escalate to **FAIL** if divergence would route a publisher's request to the wrong account/endpoint). See the **Review disposition system** in [../shared/framework-utilities.md](../shared/framework-utilities.md).
12. **Destructive write to caller-provided ext/JSON — document the intentional clobber**: If the adapter unconditionally sets a nested key in caller- or upstream-provided JSON (e.g., stamping `ext.bids`, or a key under `request.ext` / `imp.ext`) without merging or guarding any pre-existing value, verify the intent is stated. Silently overwriting a value a publisher or upstream middleware may have set is a latent-bug surface even when the new value is correct. Expected: a brief code comment stating the overwrite is intentional and why (e.g., a required billing/reporting marker), OR a merge/guard that preserves an existing value; for a port, the intent may instead be vouched in `port-report.json` `quirks[]`. Severity: **INFO** (a missing comment on an otherwise-correct clobber), escalating to **WARN** only if the clobbered key has plausible legitimate upstream callers. See the **Review disposition system** in [../shared/framework-utilities.md](../shared/framework-utilities.md).

    **Canonical PASS exemplar — `mergeBidsPBSFlag` (Teal #4765).** The merged upstream function (`adapters/teal/teal.go:258-272` at master @0ba3523, single commit `643268ca`) does set the `bids` key of the decoded `request.ext` map to the raw JSON `{"pbs":1}` unconditionally, and it carries exactly the statement this step asks for — a doc comment naming the marker as "a Teal-side reporting/billing signal", plus an inline comment at the assignment: *"Overwrite any caller-provided ext.bids: the {"pbs":1} marker must be authoritative for Teal's reporting/billing pipeline, so a value set by the publisher or upstream middleware is intentionally replaced, not merged."* Running this step against that function must yield **no finding** — it is the model of what passes, not a defect to reproduce. Use it to check the rule is wired correctly: a run over `adapters/teal/teal.go` that emits a step-12 finding is a false positive in the checker, not a real one in the adapter.

    **The finding shape is the same stamp with the intent unstated** — the assignment present, both comments absent, and no `quirks[]` vouch. That single difference is the whole of what this step detects, at the INFO/WARN severities above.

### Workflow: MakeBids Changed

**Triggers when:** The `MakeBids` method is added or modified.

1. **Correct signature**: Must be `func (a *adapter) MakeBids(request *openrtb2.BidRequest, requestData *adapters.RequestData, responseData *adapters.ResponseData) (*adapters.BidderResponse, []error)`
2. **HTTP status handling**: Must handle standard response codes:
   - 204 (No Content): Return `nil, nil` — use `adapters.IsResponseStatusCodeNoContent(responseData)`. **`MakeBids` IS invoked for 204** — PBS does NOT skip 204 responses (verified at `exchange/bidder.go:304`); adapters that don't handle it will attempt to unmarshal an empty body and may produce confusing errors.
   - Non-2xx errors (4xx/5xx): `MakeBids` is NOT called for these (PBS surfaces `BadServerResponse` automatically). Defensive checks for non-2xx in `MakeBids` are redundant unless the adapter specifically handles a 3xx redirect path.
   - Both checks must come BEFORE attempting to unmarshal the response body.
3. **Response unmarshaling**: Use `jsonutil.Unmarshal` (not `json.Unmarshal`) to unmarshal `responseData.Body` into `openrtb2.BidResponse`
4. **Bid type resolution**: Must determine bid type for each bid. Resolution order (use the first the bidder actually populates):
   - From `bid.MType` (OpenRTB 2.6 markup type): `openrtb2.MarkupBanner` (1), `openrtb2.MarkupVideo` (2), `openrtb2.MarkupAudio` (3), `openrtb2.MarkupNative` (4)
   - From response ext (e.g., `bid.Ext.prebid.type`)
   - From impression lookup (match `bid.ImpID` to the original imp and check which media type is set)
   - **Multiformat is the DEFAULT — assume it, and require `bid.MType` first unless an exemption is affirmatively proven.** `adapters/infoawarebidder.go:295-300` (`IsMultiFormatSupported`) returns `true` when `OpenRTB` is nil OR `OpenRTB.MultiformatSupported` is nil; the YAML key is a *negative opt-out* that only 3 of 385 bidder-info files mention. **Do not open the YAML, find no `multiformat-supported` key, and exempt the adapter — that inversion is the exact Teal #4765 miss.** Exempt ONLY when one of these is affirmatively true:
     1. the YAML explicitly sets `openrtb.multiformat-supported: false`, or
     2. exactly one media type is declared across all of `capabilities.app`, `capabilities.site`, and `capabilities.dooh` combined.

     Otherwise the adapter is multiformat: a single imp can carry co-present formats, so imp-mediatype introspection with fixed priority (banner>video>native) mis-types every non-first-priority bid. If bid-type resolution is *primarily* imp-lookup, flag **FAIL** and require switching on `bid.MType` first with imp lookup as the omitted-mtype fallback — see [../shared/framework-utilities.md#multiformat-imps-require-per-bid-disambiguation-bidmtype](../shared/framework-utilities.md#multiformat-imps-require-per-bid-disambiguation-bidmtype). This is the Teal #4765 `postindustria-code` finding — orthogonal to the constant-fallback calibration below.
   - **Unresolved type should ERROR, not silently default.** The robust pattern returns a typed error and skips the bid (canonical model: `teqblaze::getMediaTypeForBid` returning `(openrtb_ext.BidType, error)`, collected/skipped in `MakeBids`) rather than silently assigning a constant such as `BidTypeBanner`. Severity calibration (per the **Review disposition system** tie-breaker in [../shared/framework-utilities.md](../shared/framework-utilities.md) — a source-fidelity argument like "the Java original defaults to banner" does NOT lower it):
     - **FAIL** when a constant fallback can MIS-TYPE a YAML-declared media type — the bidder declares video/native/audio but unresolved bids silently become `banner`, mislabeling a real non-banner bid (the Teal #4765 latent bug).
     - **WARN** when the constant is a likely-unreachable safety net on a bidder whose primary chain (`bid.MType` / response ext) already covers every declared type — recommend erroring on the unreachable branch.
     - **Acceptable** when the constant matches the only media type declared across *all* platforms in the bidder's YAML and the choice is operator-vouched — either an inline comment or, for a port, `port-report.json` `quirks[]`. Verified exemplar at master @0ba3523: `adrino` declares exactly `capabilities.site.mediaTypes: [native]` and `adapters/adrino/adrino.go:71` returns the bare `openrtb_ext.BidTypeNative` with the inline vouch `// our adserver supports only native ads`. **Counter-exemplar — do not cite `adkernelAdn` here**: its YAML declares `app: [banner]` plus `site: [banner, video]`, and `getMediaTypeForImpID` (`adapters/adkernelAdn/adkernelAdn.go:255-262`) falls back to `BidTypeVideo`, so it trips the FAIL one bullet above rather than illustrating the carve-out.
     - A bare-constant bid type is used legitimately by a substantial minority of upstream adapters, so do NOT blanket-flag it, and do NOT require an `impsByID` map — only a small minority build one (an optional perf choice, see step 10). Regenerate before quoting any proportion: `grep -rlE 'func .*\(.*openrtb_ext\.BidType, error\)' adapters/*/ | wc -l` against `ls -d adapters/*/ | wc -l`.
   - Bid-type resolution errors **should** include the `bid.ImpID` for log diagnosability — e.g. `fmt.Errorf("unsupported bid mtype %d for impID %s", bid.MType, bid.ImpID)`; use `%w` when wrapping a downstream error. Severity: **INFO** (NOTE) when it is omitted. It is the majority form but not a convention the repo enforces: 101 bid-type/media-type error messages across 92 adapter files carry an imp id at master @0ba3523, while 47 across 43 files omit it (`metax` "Unsupported MType %d", `loyal` "invalid BidType: %s", `thetradedesk` "unsupported mtype: %d"). Do not raise it as a change request on its own; do mention it when the error is the sole diagnostic for a bid the adapter then drops.
5. **BidderResponse construction**: `adapters.NewBidderResponseWithBidsCapacity(len(request.Imp))` is the most common constructor but is **not required — the capacity argument is not a finding at any severity.** The argument only sizes a `make([]*TypedBid, 0, n)` (`adapters/bidder.go:73-78`); length is always 0, so every value is functionally identical and no argument can be wrong. Upstream at master @0ba3523 the argument is whatever the author chose: 94 sites pass `len(request.Imp)`, 40 pass `1`, 22 pass `5`, 22 pass `len(bidResp.SeatBid[0].Bid)`, 12 pass `len(internalRequest.Imp)`, and 26 further sites skip the capacity constructor entirely for the bare `adapters.NewBidderResponse()`. Flag only what the constructor cannot fix: indexing `SeatBid[0]` without a length check panics on an empty `SeatBid` — that is a **FAIL**, and it is a nil-index bug, not a capacity finding.
   ```bash
   grep -rhoE --include='*.go' 'NewBidderResponseWithBidsCapacity\([^)]*\)' adapters/ | sort | uniq -c | sort -rn | head
   grep -rEn --include='*.go' 'adapters\.NewBidderResponse\(\)' adapters/ | grep -vc _test.go   # 26
   ```
6. **Currency**: `bidResponse.Currency = response.Cur` is correct with or without a non-empty guard — **not a finding either way**. PBS core re-defaults an empty currency: `exchange/bidder.go:316-318` runs `if bidResponse.Currency == "" { bidResponse.Currency = defaultCurrency }` with `defaultCurrency := "USD"` (`:269`), so an empty `response.Cur` copied over the `"USD"` that `NewBidderResponseWithBidsCapacity` sets (`adapters/bidder.go:73-78`) is restored before the value is used. The unguarded form is also the upstream majority — 86 of 140 assignment sites at master @0ba3523. Do not raise the guard as a change request; mention it at most once as an INFO if the surrounding review is already discussing `MakeBids` currency handling.
   ```bash
   # in a prebid-server checkout
   grep -rEn --include='*.go' '\.Currency = [A-Za-z]+\.Cur\b' adapters/ | grep -v '_test.go' | wc -l   # 140 sites
   grep -rE  --include='*.go' -B3 '\.Currency = [A-Za-z]+\.Cur\b' adapters/ | grep -cE 'if .*\.Cur'    # 54 guarded -> 86 unguarded
   ```
   The genuine currency finding is a *wrong* value, not an empty one: an adapter that hardcodes a currency the bidder does not actually bid in, or that drops `response.Cur` entirely when the bidder bids in a non-USD currency. `exchange/bidder_validate_bids.go:79` (`validateCurrency`) reconciles the declared currency against `request.Cur`.
7. **Bid pointer safety**: When appending bids, use `&seatBid.Bid[i]` (pointer to slice element), not `&bid` (pointer to loop variable)
8. **BidMeta / BidVideo population**: If the adapter extracts metadata from `bid.Ext` (e.g., advertiser ID, network ID, brand ID for BidMeta; duration, primary category for BidVideo), verify: proper error handling for malformed `bid.Ext`, zero-value checking before populating numeric fields, and JSON framework test coverage for the extraction wherever possible (unit tests only as last resort when the framework can't compare enriched objects)
9. **Coverage of declared media types (code ↔ config)**: Cross-reference the bid type resolution against `static/bidder-info/{bidder}.yaml` capabilities. Every media type declared in capabilities must have a Go-side handling path (return value or typed error). If YAML declares `audio` but `MakeBids` only covers banner/video/native, flag as **FAIL** — PBS core routes audio impressions here based on YAML and the adapter cannot handle them. Conversely, if Go handles a media type NOT in YAML (dead branch — `infoawarebidder.go::pruneImps` strips it before `MakeRequests`), do not just leave it: **investigate** whether the bidder genuinely supports that type (the source adapter's meta-info + docs.prebid.org), then either **remove the Go branch** (if unsupported — the Teal #4765 audio case) or **add it to YAML capabilities** (if genuinely supported). Severity: **WARN** pending that determination. Coverage is necessary but not sufficient: if the adapter is `multiformat-supported`, also apply the per-bid disambiguation check in step 4 — every declared type having *a* return path does not mean co-present formats on one imp are typed correctly.
10. **Imp-lookup loop efficiency (perf — nested loops only)**: If bid-type resolution scans `request.Imp` *inside* the per-bid loop (O(bids × imps)), suggest building an `impsByID map[string]openrtb2.Imp` once before the loop. Severity: **INFO** (WARN only when both collections are plausibly large). A single non-nested O(n) pass is fine — do NOT flag it, and building the map is never *required* (only a small minority of upstream adapters do; see step 4). This is the only perf pattern this skill flags; ordinary linear scans are idiomatic.

### Workflow: Helper Function Changed

**Triggers when:** A non-interface helper function is added or modified in the adapter file.

1. **Necessity**: Helper should serve a clear purpose (bid type mapping, header construction, extension extraction, etc.). Flag unnecessary wrappers that just marshal/unmarshal without transformation
2. **No dead or commented-out code**: Flag blocks of commented-out code as **WARN** — code should be removed, not commented out. This applies to test files too. Also flag debug-print statements (`fmt.Println`, `log.Debugf` referencing local variables) left in production paths.
3. **No JSON injection via RawMessage**: NEVER insert `json.RawMessage` directly into a JSON structure by string concatenation or format string (e.g., `fmt.Sprintf("{\"key\":%s}", rawMsg)`). This exposes a JSON injection attack. Always use `json.Marshal` / `jsonutil.Marshal` to re-serialize. Flag as **FAIL** (security)
4. **Error handling**: Helpers that can fail should return errors, not panic
5. **No side effects**: Helpers should not modify global state
6. **Unexported**: Helper functions in the adapter package should be unexported (lowercase) unless needed externally
7. **No function-parameter shadowing**: Closures or inner blocks in helpers must not shadow the enclosing function's parameters (declaring an inner variable with the same name as a parameter). Severity: **INFO** with recommendation to rename. Reviewer-flagged in PR #4592 (Microsoft) on `displayManagerVerBuilder` and `getMediaTypeForBid` helpers.
8. **Stdlib duplication (target-idiom)**: Flag a hand-rolled helper that reproduces a one-line Go stdlib idiom — e.g., a `unicode.IsSpace` rune-loop `isBlank` that `strings.TrimSpace(s) == ""` replaces (and which lets the now-unused `unicode` import drop); a manual membership loop that `slices.Contains` covers; a hand-built trim/split a `strings` call covers. Severity: **WARN**. A source-fidelity defense — "the Java source loops like this", "it mirrors `StringUtils.isBlank`" — does NOT lower it: re-rate against the Go norm per the tie-breaker in [../shared/framework-utilities.md](../shared/framework-utilities.md). Canonical: the Teal #4765 `isBlank`, hand-rolled rune-for-rune from Apache-Commons `StringUtils.isBlank` when `strings.TrimSpace(s) == ""` is identical — `TrimSpace` uses `unicode.IsSpace`, so even the NBSP divergence the port documented as a "fidelity surface" is preserved by the idiom (the hand-rolling bought nothing).

### Workflow: Adapter Type Changed

**Triggers when:** A struct or type declaration in the adapter file is added or modified.

1. **Adapter struct**: The main adapter struct should be unexported (`type adapter struct`), hold only configuration (typically just `endpoint string`), and not store request-scoped state
2. **No exported types**: Adapter-internal types should be unexported. Only the `Builder` function should be exported
3. **No exported struct fields**: Adapter struct fields should be unexported (lowercase). For example, `endpoint string` not `Endpoint string`, `endpointTemplate *template.Template` not `EndpointTemplate *template.Template`. Exported fields expose adapter internals unnecessarily. Flag as WARN
4. **No unnecessary fields**: The adapter struct should not hold HTTP clients, loggers, or other infrastructure — these are provided by the framework

### Workflow: Additional Go File Changed

**Triggers when:** A Go file in `adapters/{bidder}/` is added or modified that does NOT match `{bidder}.go`, `{bidder}_test.go`, or `params_test.go`. Examples: `{bidder}_utils.go`, `models.go`, `{bidder}_relay_test.go`, `doc.go`, `{bidder}_fuzz_test.go`, `{bidder}_bench_test.go`.

1. **Non-canonical artifact (lean-conformance)**: The following are NOT part of the canonical adapter corpus the target repo merges — they are dev-time aids, not PR deliverables. Flag for removal (ADR-009 + the "more artifacts ≠ quality" corollary in the [Review disposition system](../shared/framework-utilities.md)):
   - `doc.go` (package-doc file) — **FAIL**; remove (no upstream adapter ships one).
   - `*_fuzz_test.go` — **FAIL**; fuzzing is a dev-time tool. If a fuzz run found a real bug, pin it with a normal supplemental JSON fixture (or a minimal unit test) and remove the harness.
   - `*_bench_test.go` — **FAIL**; benchmarks are dev-time. Remove before the PR.
   - A large stand-alone Go unit-test file (>~100 lines) that duplicates coverage achievable via JSON fixtures — **WARN**; convert to `exemplary/`/`supplemental/` fixtures (reviewer convention PR #4533: coverage via the JSON framework wherever possible). Pin only genuinely Go-only cases (e.g., malformed JSON the loader rejects before the adapter sees it) in a minimal unit test.
2. **Necessity (legit multi-file split)**: A non-test helper file (`models.go`, `utils.go`, `parsers.go`, `structs.go`, etc.) IS allowed when justified by non-trivial non-OpenRTB serialization or sizeable helper logic — single-file is the default, the Mediasquare split is the canonical exception. Flag as **WARN** only if it duplicates logic already in `{bidder}.go` or exists with no clear purpose — not merely for existing.
3. **Package name**: Must match `package {bidder}`
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
   - `uri` — must match the endpoint the test runner configures. Whether that endpoint is a fake host or the bidder's real domain is **not a finding** (see [../shared/framework-utilities.md#test-fixture-conventions](../shared/framework-utilities.md#test-fixture-conventions)); the match itself is enforced mechanically at `adapters/adapterstest/test_json.go:341-342`, so a mismatch fails CI rather than needing a review finding.
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
3. **Error path coverage**: For new adapters, the coverage a reviewer looks for, with the severity each carries:
   - HTTP 204 (no content response) — **WARN** if absent. This is the one near-universal item: 34 of the 37 adapters added in the last 18 months ship it, and an adapter that never exercises 204 has an untested `IsResponseStatusCodeNoContent` path that PBS *will* hit (204 is inside the `[200,400)` window where `MakeBids` is invoked).
   - Invalid/malformed `imp.ext` (bad JSON) — **INFO**
   - Invalid `imp.ext.bidder` (bad bidder params) — **INFO**
   - HTTP 400+ (server error response) — **INFO**
   - Invalid/malformed response body — **INFO**
   - Unsupported or unknown bid media type — **INFO**

   **Do not treat the list as a checklist gate — no upstream adapter satisfies it.** At master @0ba3523, 0 of the 37 adapters added in the last 18 months cover all six; the best cover 5 (`eskimi`, `ezoic`, `flatads`, `proxistore`, `rtbstack`, `sparteo`, `stackadapt`, `trustx`) and the median is 3–4. Per-item rates across those 37: 204 92%, HTTP 400 65%, malformed body 65%, 5xx 43%, bad media type 41%, bad `imp.ext` 38%. Report any absences other than 204 as a single INFO naming what is missing; never as six findings, and never as a FAIL.
4. **Error-path fixture that forgets its assertion**: Flag as **WARN** only when a supplemental fixture *exercises* an error path yet asserts no error. The diagnostic shape is a `mockResponse.status` of 400 or above (or a deliberately corrupt `mockResponse.body`) with no `expectedMakeRequestsErrors` / `expectedMakeBidsErrors` entry — such a fixture passes whether or not the adapter surfaces the error, so it proves nothing.
   - **Do NOT flag a fixture asserting graceful degradation.** A supplemental fixture whose entire purpose is proving that a bad, empty, or absent input degrades *without* an error legitimately has no expected errors. This covers HTTP 204 / no-content, an empty or zero-bid response body, a suppressed request (no `httpCalls` at all), and tolerated-malformed input the adapter skips rather than rejects (`invalid-imp-ext`, `invalid-bid-ext` style). "No expected error" is the assertion, not an omission.
   - **Do NOT flag "this looks like it belongs in `exemplary/`".** Directory placement is author judgement, not a defect.
   - Calibration at master @0ba3523: 623 of 1986 supplemental fixtures (31%) declare no expected errors — an unscoped "no expected errors ⇒ WARN" rule flags roughly a third of the merged corpus (228 of them 204/no-content, 65 empty/zero-bid, 27 with no HTTP call, 303 asserting bids). Re-scoped to error paths it flags 4: the only ≥400-status supplemental fixtures upstream with no error assertion (`e_volution`, `infytv`, `kidoz`, `krushmedia` — all `status-503`), out of 401 fixtures that mock a ≥400 status.
     Regenerate: [`adapter-code-index.md` → Regeneration commands](adapter-code-index.md#regeneration-commands) command 1.

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
