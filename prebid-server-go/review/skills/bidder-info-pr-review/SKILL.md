---
name: bidder-info-pr-review
description: Reviews changes to bidder-info YAML files at static/bidder-info/*.yaml. USE WHEN a PR adds/modifies/removes any of these files. Verifies endpoint reachability, alias parent existence and inheritance, GVL vendor lookups, user-sync URL macros, white-label policy compliance, capability declarations, and SSL certificate validity. Do NOT use for static/bidder-params/*.json, openrtb_ext/imp_*.go, or adapter Go code.
version: 1.0.0
---

# Bidder Info PR Review

Review pull requests that touch `static/bidder-info/*.yaml` files. For every changed field, apply the matching verification workflow to produce actionable review findings.

## Core Principle: Review Only What Changed

**You are a PR reviewer, not a full-file auditor.** The PR diff is your single source of truth. Only create verification tasks for fields that actually changed in the diff. Fields that already exist unchanged in the file were approved in a prior PR and are out of scope.

- **NEVER** review unchanged fields just because they exist in a file
- **NEVER** verify `maintainer`, `capabilities`, `gvlVendorID`, etc. unless the diff shows them as added or modified
- **DO** verify every field line that appears as added (`+`) or modified in the diff
- The number of verification tasks should correspond 1:1 with changed fields, not with total fields in the file

## Activation

This skill activates when a PR adds, modifies, or removes any file matching `static/bidder-info/*.yaml`.

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model,
which can paraphrase source code and lose raw JSON structure. `curl` returns
exact, deterministic content. Parse the raw JSON output directly.

### Step 1: Receive Triage Data

This skill receives pre-fetched PR data from the **pr-triage** skill. Do NOT re-fetch PR files or run drift checks.

**1a. Accept the routing manifest.**

The pr-triage skill provides:
- The complete file list filtered to files owned by this skill (`static/bidder-info/*.yaml`)
- Each file's `filename`, `status`, and `patch` (diff hunks)
- Drift check results for `config/bidderinfo.go` vs local field index
- CI status summary
- PR type classification
- Any cross-skill concerns relevant to bidder-info
- PR description analysis (docs PR link, template completeness, feature rationale)
- Commit history (count, messages, head SHA)
- PR comments (reviewer feedback, CI bot reports, author responses) — categorized and summarized
- Duplicate PR search results
- Bidder metadata (aliasOf status, capabilities if available from the PR)

**1b. Handle drift warnings.**

If the triage manifest reports drift for bidder-info, include the drift warning in the review output. Do not re-fetch `bidderinfo.go`.

**1c. Handle CI status.**

If CI status is `blocked`, acknowledge in the summary and note that review findings are preliminary until CI passes.

**1d. Incorporate reviewer feedback.**

Cross-reference the PR comments from the triage manifest against your review findings:
- If a reviewer has already flagged an issue you also find, note: `Previously flagged by {reviewer}` and reference their comment
- If a CI bot report indicates a failure relevant to your scope (e.g., YAML lint, config validation), use it as additional evidence for your verification steps
- If the author has responded to reviewer feedback with fixes, check whether the current diff reflects those fixes

**1e. Fetch full file content when needed.**

For files with status `modified`, the patch contains only changed regions. When verification requires full file context (e.g., checking all required fields in an existing file, validating alias parent):

```bash
# Fetch full file from PR branch (for modified files needing full context)
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/{head_sha}/{filename}"
# Fetch parent YAML from master (for alias validation)
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/master/static/bidder-info/{parent}.yaml"
```

- For `added` files: full content is already in the patch (all `+` lines) — do NOT re-fetch
- For `modified` files: only fetch if the verification workflow requires context beyond the diff hunks
- Cache fetched content — do not re-fetch the same file multiple times

### Step 2: Extract Field-Level Changes From the Diff

Parse the diff output to identify exactly which fields were added, modified, or removed. Categorize each changed file:

- **Added file** (entire file is new in the diff) — every field in the file is new and needs review
- **Modified file** (file exists, some lines changed) — **ONLY** review the specific fields on changed (`+`/`-`) lines. Unchanged fields are out of scope.
- **Removed file** (entire file deleted) — create a single task to validate the removal is intentional

For **modified files**, extract only the diff hunks. Map each changed line to its corresponding field in the BidderInfo schema (see [field-index.md](references/field-index.md)). Ignore all context lines (lines without `+` or `-` prefix).

**Comment-only changes:** If all changed lines in a file are YAML comments (`#` lines) or whitespace-only changes (e.g., trailing newline fixes) with no actual field values changed, the file has **zero changed fields**. Skip to Step 5 and recommend fast-track approval — note in the summary that the change is comment/formatting only with no functional impact.

### Step 3: Build Verification Task List

For **each changed field only**, look up the matching **Verification Workflow** (see below). Create a task using `TaskCreate` with:

- **subject**: `Verify {bidder}: {field_path}` (e.g., `Verify appnexus: endpoint`)
- **description**: The specific verification steps from the matching workflow, plus any field-specific criteria from the Field Index
- **activeForm**: `Verifying {bidder} {field_path}`

There are two categories of tasks:

**1. PR-level task (at most one):** A single task covering PR-wide checks that don't map to a specific field. Only create this if applicable:
- **Documentation PR check**: Reference the `docs_pr` field from the triage manifest's `PR DESCRIPTION` section. If `none` and this is a new adapter, flag as WARN
- **Duplicate PR check**: Reference the `Duplicate PRs` field from the triage manifest's `PR-LEVEL CHECKS` section. If duplicates exist, assess whether they conflict with this PR

**Bulk-mode handling for multi-adapter alias bundles**: If the triage manifest indicates PR type is `alias-only` AND the multi-adapter alias bundle exception applies (5+ aliases of same parent, identical schema, ≤5 lines each — see pr-triage Step 4 rule 1), do NOT create per-bidder field-level tasks for each alias. Instead, create:
1. One "bulk pattern consistency" task verifying: (a) all aliases reference the same parent that exists in master, (b) all aliases have identical field structure, (c) each alias's endpoint domain plausibly belongs to that alias's organization (not parent's).
2. One shared task for parent existence verification.

Total tasks for a 5-alias bulk PR: 2, not (5 × number-of-fields-per-alias). Reference: PR #4651 (5 Limelight aliases) — this skill should produce ~2 tasks under bulk-mode, not 10.

**2. Field-level tasks (one per changed field):** For each changed field, look up the matching Verification Workflow. Create tasks in this priority order (but only for fields that appear in the diff):
1. `endpoint` — use [Endpoint Changed](#workflow-endpoint-changed) workflow
2. `aliasOf` — use [Alias Adapter Added](#workflow-alias-adapter-added) workflow
3. `capabilities` — use [Capabilities Changed](#workflow-capabilities-changed) workflow
4. `gvlVendorID`, `geoscope` — use respective workflows
5. `openrtb.*`, `endpointCompression`, `modifyingVastXmlAllowed` — use respective workflows
6. `userSync.*` — use [User Sync URL Changed](#workflow-user-sync-url-changed) or related workflows
7. `disabled` — use [Bidder Disabled](#workflow-bidder-disabled) workflow

**Do NOT create separate "new adapter file" tasks.** For new files, the relevant checks (required fields present, white-label detection) are folded into the field-level workflows. For example, white-label detection is part of the Alias Adapter workflow, and required-fields validation is implicit — if `endpoint` or `capabilities` is missing from a new file, it will surface as a missing field, not as a separate task.

**Sanity check**: The number of field-level tasks must equal the number of changed fields across all files. If you have more tasks than changed fields, you are reviewing out-of-scope content — remove the excess tasks. The single PR-level task (if created) does not count toward this check.

### Step 4: Execute Verification Tasks

Work through tasks, parallelizing where possible (e.g., all endpoint reachability checks can run concurrently). For each task:

1. Mark the task `in_progress`
2. Execute every verification step from the matching workflow
3. Record each step's result as PASS, FAIL, or WARN with evidence
4. Check cross-field consistency rules — but only between fields that changed in this PR, or between a changed field and an existing field it directly depends on (e.g., a new `aliasOf` value requires checking the parent exists)
5. Mark the task `completed` with findings

### Step 5: Summary

After all tasks are complete, produce a review summary:

- Files changed (with category: added/modified/removed)
- Fields changed per file
- Verification steps executed
- Issues found (critical / warning / info)
- Recommendation (approve, request changes, or comment)

---

## Verification Workflows

Concrete verification procedures derived from real Prebid Server reviewer practices. Each workflow defines the exact steps to perform when a specific field or file-level change is detected.

### Workflow: New Standalone Adapter File Added

**Triggers when:** A new `static/bidder-info/*.yaml` file is created **without** an `aliasOf` field (i.e., it is a standalone adapter, not an alias).

**Note:** This workflow does NOT generate its own task. Its checks are folded into the field-level tasks and the PR-level task. When a new standalone adapter is detected, incorporate these checks into the relevant field tasks:

1. **Required fields present**: As part of reviewing the file's fields, verify the file contains `endpoint`, `maintainer`, and `capabilities`. If any are missing, flag in the relevant field task or as a standalone finding
2. **White-label check**: As part of the `endpoint` verification, check if the adapter implementation closely resembles an existing adapter (similar endpoint structure, same bidding server). If so, flag that it should use `aliasOf` instead. Prebid policy: "if an adapter is a white label, the aliasing feature should be used instead of copying an adapter"
3. **Documentation PR**: Handled in the PR-level task
4. **Duplicate PR check**: Handled in the PR-level task

### Workflow: Alias Adapter Added

**Triggers when:** A new file contains `aliasOf` field.

1. **Parent exists**: Verify the parent bidder named in `aliasOf` has a corresponding `static/bidder-info/{parent}.yaml` file
2. **No alias chains**: The parent must not itself be an alias (check parent file for `aliasOf`)
3. **Capabilities subset**: If the alias declares capabilities, they must be a subset of the parent's capabilities
4. **White-label compliance**: Confirm the alias approach is appropriate.
   - 4a: If the SAME PR also adds adapter Go code at `adapters/{alias}/`, flag as **FAIL** — alias should not have its own Go code; if it does, it's a full adapter not an alias.
   - 4b: If this is the FINAL state of a PR that historically contained Go code (per pr-triage `whitelabel-redirect-mid-review` sub-label), record as **PASS** with note "alias-only after white-label redirect (canonical pattern)."
   - 4c: If the parent **already has aliases**, aliasing is the established pattern for that parent — **PASS**. Key this carve-out on alias count, NOT on `whiteLabelOnly:`. At master @0ba3523 the parents carrying multiple aliases include `teqblaze` (25), `limelightDigital` (23), and `smarthub` (11); regenerate with `grep -rh "aliasOf" static/bidder-info/ | sort | uniq -c | sort -rn`. Only `teqblaze.yaml` sets `whiteLabelOnly: true` — `smarthub.yaml` does not, so the flag is not a reliable alias-parent marker.
   - 4d: If the alias file itself sets `whiteLabelOnly: true` alongside `aliasOf:` → **FAIL** (BLOCK). `config/bidderinfo.go:461-463` (`validateAliases`) returns `bidder '%s' is an alias and cannot be set as white label only`, which propagates through `processBidderAliases` → `LoadBidderInfoFromDisk` → `logger.Fatalf`. The server will not start. Do not route this to the redundant-inherited-field WARN in step 7 — it is a startup abort, not a style nit.
5. **Endpoint domain**: The alias endpoint domain should belong to the alias organization, not reuse the parent's domain verbatim (unless intentionally shared infrastructure)
6. **Alias completeness — maintainer.email**: Aliases MAY inherit `maintainer.email` from the parent.
   - Flag missing `maintainer.email` as **INFO** (not WARN) when the alias clearly belongs to the parent's organizational family. Heuristics: PR is part of a bulk-mode multi-adapter alias bundle (per pr-triage Step 4), OR alias and parent share a common-stem domain (e.g., both use the same brand-suffix), OR PR description indicates internal-rename rather than third-party alias.
   - Flag as **WARN** when the alias appears to be an independent organization from the parent. Heuristic: distinct endpoint domain that doesn't share a stem with the parent's. Reasoning: without alias-org-specific contact info, support escalation has no path.
   - Reference: PR #4651 (5 Limelight aliases) merged without per-alias `maintainer.email` and without reviewer objection — the parent's `engineering@project-limelight.com` was implicitly accepted as the contact for all 5 aliases. PR #4727 (AppMonstaMedia) DID provide its own `media.support@appmonsta.ai` because it's a distinct organization.
7. **Redundant inherited fields**: If the alias declares a field whose value is identical to the parent's (capabilities, `openrtb`, `userSync`, `gvlVendorID`, `endpointCompression`), the declaration is inherited anyway and may be dropped. Severity: **INFO** (NOTE) — mention once, never block, never open it as a change request.
   - **A parent-identical block is what the repo routinely merges, not a defect.** At master @0ba3523, 43 of 113 alias files carry at least one field whose value is identical to the parent's. The pattern the earlier WARN targeted is the *norm* where it occurs: of the 12 aliases that declare `capabilities` at all, 11 declare a block semantically identical to the parent's; `userSync` is parent-identical on 20 of 55, `gvlVendorID` on 18 of 44. Byte-level comparison understates this — indentation and quoting differ freely — so compare parsed values, not raw text.
     Regenerate: [`field-index.md` → Regeneration commands](field-index.md#regeneration-commands) command 1.
   - **Skip this check entirely when the parent does NOT declare the field.** For example, `whiteLabelOnly: true` parents like teqblaze do not declare `endpoint:` themselves; the alias is supplying a missing required value, not redundantly overriding. Same logic for any field absent on the parent.
   - Two adjacent cases keep a higher severity and are NOT reached by this step: `gvlVendorID: 0` on an alias (step 8 — a zero literal, not a parent-identical value), and an alias `endpoint` that reuses the parent's domain (step 5 — 0 of the 85 aliases declaring `endpoint` upstream copy the parent's value, so that one has no counterexample).
8. **GVL ID on an alias — an alias NEVER inherits the parent's GVL vendor ID**:

   `config/bidderinfo.go:371-373` carries an explicit comment that the alias's `GVLVendorID` is intentionally never set from the parent, "as inheriting from the parent is not safe for legal reasons". The alias-merge block immediately below it copies `AppSecret`/`Capabilities`/`Debug`/`Endpoint`/`EndpointCompression`/`ExtraAdapterInfo`/`Maintainer`/`OpenRTB`/`PlatformID` and deliberately excludes `GVLVendorID`. `ToGVLVendorIDMap` (`config/bidderinfo.go:428-436`) then keeps only bidders with `GVLVendorID != 0`, so an alias that omits the field is dropped from the GDPR vendor map — it receives **no** vendor registration at all.

   | Alias YAML state | Disposition | Note to author |
   |---|---|---|
   | `gvlVendorID: N` (N > 0) | **PASS** (NOTE) | The required form. Verify N against the GVL per Workflow: GVL Vendor ID Changed; do not question the declaration itself or suggest it is redundant. |
   | Omitted, parent declares a GVL | **WARN** (ASK) | "Aliases never inherit the parent's GVL vendor ID; declare your own, or confirm this bidder intentionally has no GVL registration." |
   | Omitted, parent has none either | **PASS** (NOTE) | Nothing to inherit; unregistered by design. |
   | `gvlVendorID: 0` | **WARN** (ASK) | Zero is dropped by `ToGVLVendorIDMap` and reads as a declaration. Ask for removal. Reference: PR #4329 (Tagoras) reviewer convention. |

   Declaring one's own GVL is the norm, not an anomaly: 44 of the 113 upstream alias YAMLs do (regenerate per [../shared/framework-utilities.md#aliasing](../shared/framework-utilities.md#aliasing)). Reference: PR #4727 (AppMonstaMedia / GVL 1283 = Appmonsta Ltd) declared its own even though the parent has none — correct behavior, not an override to second-guess.
9. **1-line alias acceptable**: A YAML containing only `aliasOf: parent` is fully valid (everything inherited). PR #4216 (admaticde) and PR #4357 (ttd) are canonical 1-liner examples. Do not flag as "missing fields".
10. **Bidder rename held for major version**: if the PR description or commit messages indicate a bidder rename (e.g., `adoppler` → `elementaltv` per PR #4639), flag as **INFO** that the rename is a breaking change and is typically deferred to the next major release.
11. **Reviewer-hypothesis vs chosen-parent**: If the PR comments include a reviewer asking "is this similar to the {X} adapter?" or "this looks like a copy of {X}" and the final `aliasOf:` value points to a DIFFERENT bidder name `{Y}`, flag as **INFO** with note: "Reviewer suspected resemblance to {X}; author chose `aliasOf: {Y}`. Verify {Y} is the correct technical parent (e.g., a white-label parent serving multiple aliases including {X})." Reference: PR #4565 Nuba — a reviewer asked about Compass resemblance, author chose `aliasOf: teqblaze`.

12. **Smoke-test evidence (optional informational)**: If the reviewer or author posts a PBS bid-request/response trace in the PR comments (typical pattern: full request body + HTTP status + response body), parse the request URI and response status. A 204 response from the bidder endpoint to a debug-mode PBS request is positive evidence the alias is functional end-to-end. Severity: **INFO** (auxiliary). Reference: PR #4727 AppMonstaMedia included such a trace as final reviewer evidence.

### Workflow: White-Label Policy Compliance

**Triggers when:** any change to `whiteLabelOnly` field, OR a new YAML file is added that resembles an existing adapter (heuristic: same endpoint domain or strikingly similar configuration), OR PR description / comments mention "white label".

1. **`whiteLabelOnly: true` semantics**: Marks the bidder as ineligible for direct auctions — `IsEnabled()` (`config/bidderinfo.go:249-251`) returns false for it. Does NOT preclude Go adapter code on the parent: `teqblaze` has a full Go adapter at `adapters/teqblaze/` AND the flag (PR #4480). **Severity: INFO** if the flag is set on a new file that is NOT an alias.
   - **The flag is rare, and it is not the alias-parent marker.** `static/bidder-info/teqblaze.yaml` is the ONLY upstream file carrying `whiteLabelOnly: true` at master @0ba3523 (`grep -rl whiteLabelOnly static/bidder-info/`). `smarthub.yaml` does NOT set it despite serving 11 aliases. Do not describe a parent as white-label just because it has aliases, and do not expect an alias parent to carry the flag.
   - **`whiteLabelOnly: true` on a file that also declares `aliasOf:` → FAIL** (BLOCK). See Workflow: Alias Adapter Added step 4d — `config/bidderinfo.go:461-463` makes this a startup abort.
2. **Full adapter that looks like a copy**: If a new full Go adapter is being added but the PR description / discussion / file structure resembles an existing adapter (heuristic: identical endpoint domain, comparable parameter schema, copy-paste-style code organization), flag as **WARN** with the suggestion: "this may be a white-label scenario — consider using `aliasOf:` instead of duplicating Go code." Severity stays WARN (not FAIL) because the determination requires reviewer judgment.
3. **Reviewer-redirect quotes**: see canonical examples in [../shared/framework-utilities.md#aliasing](../shared/framework-utilities.md#aliasing) — patterns from PRs #4329 (Tagoras), #4383 (RocketLab), #4391 (MediaYo), #4376 (PinkLion), #4565 (Nuba) where reviewers redirected full → alias-only. Code reduction quoted by reviewer: "1k+ to ~20".

   **Cross-skill de-duplication**: If pr-triage manifest's CROSS-SKILL CONCERNS section already records the 5g whitelabel-resemblance signal OR the `whitelabel-redirect-mid-review` sub-label was set per Step 4 rule 5b, do NOT re-flag the same concern. Note `Previously flagged by triage` in this skill's findings and only emit net-new findings (e.g., parent-choice verification per Workflow: Alias Adapter Added Step 11).
4. **Alias-only directionality**: `aliasOf` is added to NEW files; reviewers do not redirect from alias-only → full. The exception is PR #4614 (TRUSTX) which migrated from alias → full because the bidder organization was establishing independent infrastructure. Treat alias→full as a special case requiring matching deletion of `aliasOf:` line PLUS introduction of full endpoint/capabilities/userSync block.

### Workflow: Endpoint Changed

**Triggers when:** `endpoint` is added or modified.

1. **URL format**: Verify the value is a well-formed URL (scheme + host at minimum)
2. **Reachability check**: Use `curl -sS -o /dev/null -w "HTTP %{http_code} in %{time_total}s" -X POST {url}` to confirm the endpoint responds. Accept 200, 204, or 400 (bad request without proper body) as evidence of a live endpoint. Flag 404, 502, connection refused, or timeout as FAIL
3. **Scheme tolerance**: HTTPS is strongly preferred but HTTP is still permitted (per PR #4211: "While https is strongly preferred, http is still permitted."). Limelight-family adapters routinely use HTTP. Flag HTTP as **INFO** with recommendation to upgrade to HTTPS — never **FAIL**.
   - If the endpoint URL is HTTPS, also validate certificate per Workflow: SSL Certificate Validation (separate workflow below).
4. **HTTP response behavior**: A bare POST to the endpoint should not return 404. Acceptable responses: 200, 204, 400 (invalid body expected). If the endpoint returns 404 for POST requests with bodies, flag for clarification from the bidder
5. **Domain ownership** — **documented judgement call; no mechanical threshold, and name dissimilarity alone is never a finding.** Confirm the endpoint domain plausibly belongs to the bidder organization. A name-similarity threshold was considered and rejected against the corpus: at master @0ba3523, 115 of the 349 bidder-info files with a literal endpoint host (33%) have no 5-character run of the bidder slug anywhere in the host — `pulsepoint` → `bid.contextweb.com`, `conversant` → `api.hb.ad.cpe.dotomi.com`, `thetradedesk` → `direct.adsrvr.org`, `nativo` → `exchange.postrelease.com`, `triplelift_native` → `tlx.3lift.com`. Any similarity gate would flag a third of merged master.
   - Dispose it on **corroboration, not spelling**: the domain is corroborated when the PR description, the `maintainer.email` domain, the bidder's `userSync` domain, the docs PR, or a WHOIS/site check ties it to the same organization. Corroborated → **PASS** (record which evidence corroborated it). Uncorroborated *and* unrelated to every other domain in the file → **WARN** (ASK the author to confirm ownership), never FAIL. Do not open a finding merely because the host string does not contain the bidder name.
   Regenerate: [`field-index.md` → Regeneration commands](field-index.md#regeneration-commands) command 2.
6. **Template macros**: If URL contains `{{...}}` patterns, cross-reference against the canonical allow-list at [../shared/framework-utilities.md#endpoint-template-macros](../shared/framework-utilities.md#endpoint-template-macros). Any `{{.XYZ}}` macro NOT in that list will silently resolve to empty string at runtime — flag as **FAIL**. Non-Go-template placeholders (`#{REGION}#`, `${X}`, `<X>`) are NOT macros and require `disabled: true` plus a comment block listing valid values (PR #4502 appStockSSP convention).
7. **No hardcoded credentials**: Ensure the URL does not contain actual API keys, passwords, or secrets in plain text

### Workflow: SSL Certificate Validation

**Triggers when:** the endpoint URL uses HTTPS (most adapters) and is being added or modified.

1. **Certificate freshness**: Use `echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -subject -dates -issuer` to confirm the certificate is not expired and the subject matches the domain. Flag expired/invalid certs as **FAIL**.
2. **Cert recovery pattern**: Several PRs in the SmartHub family (#4607 Adastra, #4616 RadiantFusion) had reviewers flag "token is exterminated" / "endpoint not reachable" — diagnosis was expired SSL certs that the publisher refreshed mid-review. After cert refresh, re-run reachability check.
3. **Scope**: This workflow applies only to HTTPS endpoints. HTTP scheme tolerance is documented in Workflow: Endpoint Changed step 3 — that workflow handles the HTTP/HTTPS triage; this workflow handles certificate validation when HTTPS is in use.

### Workflow: Endpoint Domain Migration

**Triggers when:** `endpoint` is modified and only the domain portion changed (path stays the same).

1. **All steps from "Endpoint Changed" workflow**
2. **Alias impact**: If this bidder has aliases (other files with `aliasOf` pointing to it), check whether their endpoints also need updating
3. **Merge conflict risk**: Domain migrations in multi-adapter families (e.g., Attekmi aliases) frequently cause merge conflicts. Flag if the PR has conflicts with master

### Workflow: GVL Vendor ID Changed

**Triggers when:** `gvlVendorID` is added or modified.

1. **Value range**: Must be a positive integer (uint16, > 0)
2. **Vendor list lookup**: Fetch the IAB vendor list and verify the ID maps to the correct company. Use `curl -sS "https://vendor-list.consensu.org/v3/vendor-list.json"` and parse with `python3 -c "import json,sys; v=json.load(sys.stdin)['vendors'].get('{id}',{}); print(v.get('name','NOT FOUND'))"` to confirm the vendor name matches the bidder
3. **Company name match**: The vendor name in the GVL should normally match the bidder's organization. Flag mismatches as **WARN** (not FAIL) — corporate restructures are tolerated when there's a credible relationship. Example: PR #4547 (Gravite) declared GVL 377 = "AddApptr GmbH"; reviewer accepted because privacy URL is gravite.net (corporate parent). Example PR #4591 ID 354 = "Apester Ltd" not "PinkLion" was rejected — the determination is reviewer judgment, not a strict equality check.
4. **Alias context**: If this bidder is an alias (`aliasOf` is set), the declared value is the alias's *own* GVL ID — aliases never inherit the parent's (`config/bidderinfo.go:371-373`), so a declaration here is required, not an override. Apply Workflow: Alias Adapter Added step 8
5. **Privacy declarations**: Verify the GVL entry contains appropriate purpose declarations and compliance information

### Workflow: User Sync URL Changed

**Triggers when:** `userSync.iframe.url` or `userSync.redirect.url` is added or modified.

1. **HTTPS required**: URL must use HTTPS scheme
2. **Reachability check**: Use `curl -sS -o /dev/null -w "HTTP %{http_code} in %{time_total}s" {url}` to confirm the sync URL responds (not 404/500)
3. **Privacy macro validation**: Verify required macros are present and correctly formatted:
   - `{{.GDPR}}`, `{{.GDPRConsent}}` for GDPR compliance
   - `{{.USPrivacy}}` for US privacy
   - `{{.GPP}}`, `{{.GPPSID}}` if GPP is supported
   - `{{.RedirectURL}}` for the callback
   - **Exception for shared sync key**: When `userSync.key` does NOT equal the bidder name (intentional cross-bidder syncer sharing — e.g., PR #4592 msft.yaml uses `userSync.key: "adnxs"` to share cookies with AppNexus), missing privacy macros are typically inherited via the shared syncer's parent and are **INFO**, not WARN. Severity escalates only if the shared key is itself missing the macros at the parent.
4. **Both types declared**: If the file declares both `iframe` and `redirect` sync, verify both URLs are functional. It is common for only one type to work — flag if a declared type is unreachable (seen in PR #4597)
5. **Domain ownership** — **documented judgement call; no mechanical threshold.** Same disposition rule as Workflow: Endpoint Changed step 5, and the same corpus reason it has no threshold. A sync domain that differs from both the bidder name and the endpoint domain is routine (sync infrastructure is frequently a separate host or a third-party CDN). Corroborated by the PR description, the `maintainer.email` domain, the endpoint domain, or the docs PR → **PASS**; uncorroborated and unrelated to every other domain in the file → **WARN** (ASK), never FAIL. A cross-bidder sync host is expected, not suspicious, when `userSync.key` differs from the bidder name (deliberate syncer sharing — see step 3's shared-key exception).
6. **userMacro consistency**: If `userMacro` is declared alongside the URL, verify it follows the bidder's expected format (e.g., `$UID`, `[USER_ID]`, `{UID}`)

### Workflow: User Sync Added to Existing Adapter

**Triggers when:** `userSync` object is added to a file that previously had no user sync, or sync endpoints are added to an adapter and its aliases.

1. **All steps from "User Sync URL Changed" workflow** for each URL
2. **Alias consistency**: If sync is being added to a base adapter, check whether its aliases should also get sync configuration (seen in PR #4580 where sync was added to adapter + all aliases simultaneously)
3. **Format override**: If `formatOverride` is set, verify it matches the sync type (`"b"` for iframe, `"i"` for redirect)

### Workflow: GPP Macros Added to User Sync

**Triggers when:** `{{.GPP}}` or `{{.GPPSID}}` macros are added to an existing user sync URL.

1. **Macro placement**: Verify macros are correctly placed as URL parameters (not malformed)
2. **OpenRTB GPP flag**: If adding GPP macros, check whether `openrtb.gpp-supported` should also be set to `true`
3. **Existing macros preserved**: Ensure GDPR and USPrivacy macros are still present after the change

### Workflow: Endpoint Compression Changed

**Triggers when:** `endpointCompression` is added or modified.

1. **Value casing is irrelevant — do NOT flag it at all**: The runtime compares `strings.ToUpper(endpointCompression)` against the `Gzip = "GZIP"` constant (`exchange/bidder.go:849-850`; constant at `:100`), so `"gzip"`, `"GZIP"`, and `"Gzip"` all enable compression. There is no uppercase convention to enforce: at master @0ba3523 lowercase `gzip` outnumbers uppercase `GZIP` 58 to 16 across `static/bidder-info/*.yaml`. Emit **no finding** on value casing in either direction. Regenerate: `grep -rh "endpointCompression" static/bidder-info/*.yaml | sed 's/.*endpointCompression: *//' | tr -d "\"'" | sort | uniq -c`
2. **Field-NAME typo IS the silent-no-op bug (FAIL)**: The real regression is a misspelled YAML *key* — `endpoint-compression` / `endpoint_compression` (kebab/snake) instead of the camelCase `endpointCompression`. A typo'd key does not bind, so compression is silently never applied (canonical regression: Ogury). Flag a non-`endpointCompression` key as **FAIL** (read-side `endpoint-compression-typo` taxon).
3. **Server support verification**: Confirm the bidder's endpoint actually accepts `Content-Encoding: gzip` requests. If possible, test with a gzip-compressed request

### Workflow: Capabilities Changed

**Triggers when:** `capabilities.app.mediaTypes`, `capabilities.site.mediaTypes`, or `capabilities.dooh.mediaTypes` is added or modified.

1. **Valid media types**: Each value must be one of: `banner`, `video`, `native`, `audio`
2. **At least one per platform**: Each declared platform must have at least one media type
3. **Platform addition vs. media type addition**: When adding a new platform (e.g., adding `site` to an adapter that only had `app`), no additional adapter test files are typically required — the existing adapter code handles it
4. **DOOH scrutiny**: DOOH (Digital Out Of Home) is uncommon — if declared, verify the bidder genuinely supports DOOH inventory
5. **Alias impact**: If this bidder has aliases, verify the alias capabilities remain a valid subset
6. **Cross-check vs Go code**: When `static/bidder-info/{bidder}.yaml` capabilities are modified AND `adapters/{bidder}/{bidder}.go` is also in the PR, the adapter-code-pr-review skill will run a YAML-capabilities ↔ Go MType drift check. This skill records the YAML-declared media types in the BIDDER METADATA block of its findings so the adapter-code skill can cross-reference. See [../shared/framework-utilities.md#yaml-capabilities--go-mtype-drift](../shared/framework-utilities.md#yaml-capabilities--go-mtype-drift).
   - **DOOH-specific cross-check**: If `capabilities.dooh` is declared, the adapter MUST include at least one exemplary test fixture exercising `dooh` context (`mockBidRequest.dooh` present). If absent, flag as **WARN** — reviewer may ask the contributor to remove DOOH from capabilities since they have no DOOH supply. Reference: PR #4287 (Optidigital) declared dooh but had no DOOH fixture; the new rule would have caught this.

### Workflow: Bidder Disabled

**Triggers when:** `disabled` is set to `true`.

1. **Intentionality**: Verify the PR description explains why the bidder is being disabled
2. **Simultaneous changes**: If other fields are being modified alongside `disabled: true`, flag as suspicious — why modify configuration for a bidder being disabled?
3. **Code cleanup**: Check whether related adapter code/tests should be removed or retained

### Workflow: Disabled-By-Default Region Endpoint

**Triggers when:** `endpoint` URL contains a non-Go-template placeholder (e.g., `#{REGION}#`, `${X}`, `<X>`) AND/OR `disabled: true` is set.

1. **Placeholder + disabled pairing**: An endpoint with non-Go-template placeholder MUST set `disabled: true`. Otherwise PBS will attempt to resolve the placeholder at runtime and fail silently. Flag missing `disabled: true` as **FAIL**.
2. **Comment block required**: When using non-Go-template placeholders, the YAML should include a comment block listing valid replacement values (e.g., `# REGION values: us-east, eu-west, ap-south`). Flag missing comment as **WARN**.
3. **Reviewer convention**: established by PR #4502 (appStockSSP). When the host configures regional endpoints at deploy time, the canonical pattern is `disabled-by-default + commented placeholder + host-side substitution`.

### Workflow: Typo/Minor Fix

**Triggers when:** A small change is made to an existing field value (e.g., fixing a character in a URL path).

1. **Value correctness**: Verify the new value is correct
2. **No functional regression**: If the change is to an endpoint URL, run the endpoint reachability check
3. **Fast-track**: Minor fixes with obvious correctness can be approved quickly

### Workflow: Bidder Naming Convention

**Triggers when:** a new bidder file is added at `static/bidder-info/{name}.yaml`.

1. **Alphanumeric + underscore allowed**: Server-side accepts alphanumeric AND underscore (per PR #4211 cross-team policy: "I guess we have to allow underscores server-side. The PBJS doc allows it and being in sync is preferred."). Snake_case names like `boldwin_rapid`, `alliance_gravity`, `ads_interactive` are valid. Flag special characters (hyphens, dots) as **FAIL**.
2. **6-character unique prefix**: New bidder names typically must have first 6 characters unique among all registered bidders. Exception: sibling-family aliases (e.g., `admatic` + `admaticde`) are tolerated when the collision is intentional aliasing relationship (PR #4216 ruling).
3. **Naming collision with existing bidder**: If the new name matches an existing one with case-only difference (e.g., `ads_interactive` vs `adsinteractive`), defer the deprecation to the next major release per PR #3929 / issue #3861 convention.

---

## Field Index

Complete mapping of every BidderInfo field to its review criteria. Source: `config/bidderinfo.go`.

### `endpoint` (string, REQUIRED)

- Must be a valid URL
- Must not be fully variable or host-specific
- Can use regional subdomains (e.g., `http://REGION.example.com/openrtb2`)
- Template macros (e.g., `{{.Host}}`) are resolved at startup
- Verify the domain is owned by the bidder organization
- **Workflow**: [Endpoint Changed](#workflow-endpoint-changed)

### `endpointCompression` (string)

- **Value casing is NOT case-sensitive and carries no convention**: runtime compares `strings.ToUpper(endpointCompression)` to the `Gzip = "GZIP"` constant (`exchange/bidder.go:849-850`; constant at `:100`), so `"gzip"`/`"GZIP"`/`"Gzip"` all work. Lowercase `gzip` is in fact the majority form upstream (58 vs 16 at @0ba3523). Emit no finding on casing.
- **Field-NAME typo is the real FAIL**: a misspelled key (`endpoint-compression`/`endpoint_compression` instead of camelCase `endpointCompression`) does not bind → compression silently disabled (Ogury regression) → **FAIL**.
- Omit entirely if bidder does not support compression
- Verify bidder server actually accepts gzip-compressed bid requests
- **Workflow**: [Endpoint Compression Changed](#workflow-endpoint-compression-changed)

### `maintainer.email` (string, REQUIRED)

- Manual reviewer process. A reviewer sends a verification email and blocks merge until the maintainer replies "received". Skills cannot fully automate this gate.
- Flag generic-domain emails (`gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `proton.me`, `icloud.com`) as **INFO** — historically these receive extra scrutiny because they don't establish organizational ownership.
- Flag any `maintainer.email` whose **local-part is not a recognized role/group token** (`tech@`, `support@`, `prebid@`, `info@`, etc.) as **WARN** — a personal name or handle (`firstname.lastname@`, `firstname@`, `flast@`, initials, a nickname) is not a role token **even on the bidder's own corporate domain**. Judge role-vs-person rather than matching a regex: only 7 of 326 upstream maintainer emails use the `firstname.lastname@` shape, so a name-pattern deny-list misses nearly every personal address. Reviewer practice: PR #4321, PR #4441. See [../shared/framework-utilities.md#maintainer-email-policy](../shared/framework-utilities.md#maintainer-email-policy) for the canonical rule.
- For aliases: `maintainer.email` MAY be inherited from the parent (omit the field). If declared on the alias, it should be the alias organization's email — not a copy of the parent's, unless they share infrastructure. Flag the parent-email-on-alias case as **INFO** asking for confirmation it was intentional (per PR #4441 reviewer practice).
- If the PR comments include reviewer phrases like "please reply 'received'" or "I'll merge once you confirm via email", record `email-confirmation-pending` status in the review summary.

### `gvlVendorID` (uint16)

- Must be a valid GDPR Global Vendor List vendor ID
- Omit if bidder is not IAB registered
- Verify the ID matches the bidder at https://vendor-list.consensu.org/
- Value must be > 0 if present — `ToGVLVendorIDMap` (`config/bidderinfo.go:428-436`) drops any bidder with `GVLVendorID == 0`
- **Never inherited by an alias** (`config/bidderinfo.go:371-373`). An alias omitting the field gets no GDPR vendor registration; it does not fall back to the parent's.
- **Workflow**: [GVL Vendor ID Changed](#workflow-gvl-vendor-id-changed)

### `geoscope` ([]string)

- Valid values: 3-letter ISO 3166-1 alpha-3 country codes (e.g., `USA`, `CAN`, `GBR`)
- Special values: `GLOBAL`, `EEA`
- Negation prefix `!` (e.g., `!EEA` = "not in EEA")
- **Casing is not a defect — the runtime is case-insensitive.** `validateGeoscope` (`config/bidderinfo.go:645-675`) applies `strings.ToUpper(strings.TrimSpace(code))` to every entry *before* every comparison, including the `GLOBAL`/`EEA` equality tests and the `char < 'A' || char > 'Z'` character loop. `global`, `Global`, and `GLOBAL` therefore validate identically. Uppercase is conventional for country codes, but lowercase is the dominant form for the special value on master: 27 bidder-info files write lowercase `global` against 1 writing `GLOBAL`. **Never emit FAIL or WARN on geoscope casing** — a merged-code false positive. INFO is appropriate only if one list mixes both forms.
  Regenerate: [`field-index.md` → Regeneration commands](field-index.md#regeneration-commands) command 3.
- Verify geographic claims are accurate for the bidder

### `disabled` (bool)

- `true` unregisters the adapter entirely
- Verify this is intentional — disabling removes the bidder from all auctions
- Check if related code/tests should also be removed or retained
- **Workflow**: [Bidder Disabled](#workflow-bidder-disabled)

### `modifyingVastXmlAllowed` (bool)

- Default: `true`
- Set to `false` to opt-out of video impression tracking
- Only relevant for bidders supporting video media types
- If set to `false`, verify bidder has a reason to opt out

### `openrtb.version` (string)

- Set to `"2.6"` if adapter supports OpenRTB 2.6
- Omit for adapters requiring downgraded values
- Verify the adapter code actually handles the declared version

### `openrtb.gpp-supported` (bool)

- Indicates if bidder supports Global Privacy Platform
- Not yet actively used in production
- Verify bidder actually processes GPP signals if set to `true`

### `openrtb.multiformat-supported` (*bool)

- `true` means bidder can handle multiple media formats in a single imp
- `nil`/omitted means default behavior
- Verify adapter code handles multi-format if enabled

### `capabilities` (object, REQUIRED)

At least one platform (`app`, `site`, `dooh`) must be specified.
- **Workflow**: [Capabilities Changed](#workflow-capabilities-changed)

### `capabilities.app.mediaTypes` ([]string)

- Valid values: `banner`, `video`, `native`, `audio`
- At least one media type required if `app` platform is declared
- Verify adapter code handles each declared media type for app context

### `capabilities.site.mediaTypes` ([]string)

- Valid values: `banner`, `video`, `native`, `audio`
- At least one media type required if `site` platform is declared
- Verify adapter code handles each declared media type for site/web context

### `capabilities.dooh.mediaTypes` ([]string)

- Valid values: `banner`, `video`, `native`, `audio`
- At least one media type required if `dooh` platform is declared
- DOOH (Digital Out Of Home) is less common — verify bidder actually supports it

### `debug.allow` (bool)

- Enables debug output for this bidder
- Verify this is appropriate for the deployment context

### `userSync` (object)

Complex object — review each sub-field individually.
- **Workflow**: [User Sync URL Changed](#workflow-user-sync-url-changed), [User Sync Added to Existing Adapter](#workflow-user-sync-added-to-existing-adapter)

### `userSync.key` (string)

- Case-sensitive identifier, defaults to bidder name
- Use a different key only when multiple bidders share the same bidding server
- Cannot be changed without breaking existing user sync cookies
- Verify uniqueness across all bidder-info files

### `userSync.supports` ([]string)

- Valid values: `iframe`, `redirect` (case-insensitive)
- Declares sync capabilities when host must configure endpoints
- Cannot be overridden by host configuration
- Only specify when bidder provides no default endpoint URLs

### `userSync.iframe.url` (string)

- Must be a valid HTTPS URL with template macros
- Available macros: `{{.GDPR}}`, `{{.GDPRConsent}}`, `{{.USPrivacy}}`, `{{.GPP}}`, `{{.GPPSID}}`, `{{.RedirectURL}}`
- Verify the domain is owned by the bidder
- Verify the endpoint actually functions for iframe-based sync
- **Workflow**: [User Sync URL Changed](#workflow-user-sync-url-changed)

### `userSync.iframe.userMacro` (string)

- Bidder-specific macro replaced with user ID (e.g., `$UID`, `[USER_ID]`)
- Must match what the bidder's server expects

### `userSync.iframe.redirectUrl` (string)

- Template for the redirect destination after sync
- Default template includes `{{.ExternalURL}}`, `{{.BidderName}}`, `{{.SyncType}}`, `{{.UserMacro}}`
- Only override if default is insufficient

### `userSync.iframe.externalUrl` (string)

- Available as macro to redirectUrl template
- Falls back to syncer-level or host-level externalUrl

### `userSync.redirect.url` (string)

- Must be a valid HTTPS URL with template macros
- Same macros as iframe.url
- Verify the domain is owned by the bidder
- Verify the endpoint returns HTTP 302 redirect with user ID substituted
- **Workflow**: [User Sync URL Changed](#workflow-user-sync-url-changed)

### `userSync.redirect.userMacro` (string)

- Same rules as iframe.userMacro

### `userSync.redirect.redirectUrl` (string)

- Same rules as iframe.redirectUrl

### `userSync.redirect.externalUrl` (string)

- Same rules as iframe.externalUrl

### `userSync.externalUrl` (string)

- Syncer-level external URL, available as macro to endpoint redirectUrl templates
- Falls back to host configuration if not specified

### `userSync.formatOverride` (string)

- Valid values: `""` (empty), `"b"` (iframe/blank), `"i"` (redirect/image)
- Overrides the callback response format
- Cannot be overridden by host configuration
- Verify the bidder's sync endpoint matches the declared format

### `userSync.enabled` (*bool)

- `true`/`false` to enable/disable user sync for this bidder
- `nil`/omitted inherits default behavior
- Disabling removes bidder from /cookie_sync responses

### `userSync.skipwhen.gdpr` (bool)

- `true` = skip user sync when GDPR applies
- Verify this aligns with the bidder's privacy policy

### `userSync.skipwhen.gpp_sid` ([]string)

- GPP Section IDs that trigger skipping user sync
- Verify values are valid GPP section identifiers

### `experiment.adsCert.enabled` (bool)

- Enables Ads.cert / Call Sign feature
- Non-production feature — verify bidder is enrolled in the program
- Verify adapter code handles ads.cert signing

### `xapi.username` (string)

- Adapter-specific credential (primarily Rubicon)
- Must not be hardcoded in the YAML — verify it uses config override
- Check for accidental credential exposure

### `xapi.password` (string)

- Adapter-specific credential (primarily Rubicon)
- SECURITY: Must never contain actual passwords in the YAML
- Verify it uses config override mechanism

### `xapi.tracker` (string)

- Adapter-specific tracker URL (primarily Rubicon)

### `platform_id` (string)

- Platform-specific identifier (primarily Facebook/Meta)
- Verify the ID is valid for the target platform

### `app_secret` (string)

- Application secret (primarily Facebook/Meta)
- SECURITY: Must never contain actual secrets in the YAML
- Verify it uses config override mechanism

### `extra_info` (string)

- JSON string with additional adapter-specific data
- Must be valid JSON if present
- Verify the adapter code actually parses and uses this data
- Check for sensitive data leakage

### `aliasOf` (string)

- Names the parent bidder this is an alias of
- Parent bidder must exist and not itself be an alias
- Alias capabilities must be a subset of parent capabilities
- Verify the alias makes sense for the bidder relationship
- **Workflow**: [Alias Adapter Added](#workflow-alias-adapter-added)
- Minimum form: `aliasOf: parent` alone is valid (1-line file). 2-line form (`endpoint:` + `aliasOf:`) is the SmartHub/Limelight family convention. See `bidder-info-pr-review/SKILL.md` Workflow: Alias Adapter Added step 9 for canonical examples (PR #4216 admaticde, PR #4357 ttd).

### `whiteLabelOnly` (bool)

- `true` marks the bidder ineligible for direct auctions — `IsEnabled()` (`config/bidderinfo.go:249-251`) returns false
- **MUST NOT be combined with `aliasOf` on the same file.** `validateAliases` (`config/bidderinfo.go:461-463`) returns `bidder '%s' is an alias and cannot be set as white label only`, aborting startup via `logger.Fatalf`. Flag the combination as **FAIL**.
- Rare: `teqblaze.yaml` is the only upstream file that sets it at @0ba3523, and it is a core bidder with its own Go adapter

---

## Operational Check Commands

Exact commands for operational verification steps referenced in the workflows above. Use these via the Bash tool.

**Endpoint reachability:**
```bash
curl -sS -o /dev/null -w "HTTP %{http_code} in %{time_total}s" -X POST {url}
```
- Accept: 200, 204, 400 (bad request without proper body)
- Fail: 404, 502, connection refused, timeout

**SSL/TLS certificate validation:**
```bash
echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -subject -dates -issuer
```
- Check: certificate not expired, subject matches domain, issuer is a trusted CA

**GVL vendor lookup:**
```bash
curl -sS "https://vendor-list.consensu.org/v3/vendor-list.json" | python3 -c "import json,sys; v=json.load(sys.stdin)['vendors'].get('{id}',{}); print(v.get('name','NOT FOUND'))"
```
- Verify: returned name matches the bidder organization

**User sync URL reachability:**
```bash
curl -sS -o /dev/null -w "HTTP %{http_code} in %{time_total}s" {url}
```
- Accept: 200, 301, 302 (redirects expected for sync URLs)
- Fail: 404, 500, connection refused

---

## Cross-Field Validation Rules

After reviewing individual fields, verify these cross-field constraints:

1. **Alias consistency**: If `aliasOf` is set, capabilities must be a subset of the parent bidder
2. **Video + VAST**: If video media type is declared, `modifyingVastXmlAllowed` setting should be deliberate
3. **GDPR compliance**: If `gvlVendorID` is set, `userSync` should respect GDPR macros
4. **Sync key uniqueness**: `userSync.key` must not conflict with other bidders (unless intentionally shared)
5. **Security fields**: `xapi.password`, `xapi.username`, `app_secret` must not contain real credentials
6. **Disabled + other fields**: If `disabled: true`, question why other fields are being changed simultaneously
7. **Platform + mediaType**: Each declared platform must have at least one media type
8. **Geoscope + capabilities**: Geographic restrictions should align with platform support
9. **GPP consistency**: GPP macros in a user-sync URL and `openrtb.gpp-supported` are **independent settings — their disagreement is not a finding at any severity.** They drive different pipelines: `usersync/syncer.go` `GetSync` resolves the `macros.UserSyncPrivacy` fields (`{{.GPP}}`, `{{.GPPSID}}`, GDPR, USPrivacy) into the sync template unconditionally, with no reference to `OpenRTB.GPPSupported`; `openrtb.gpp-supported` is read only at `exchange/utils.go:424-431` (`shouldSetLegacyPrivacy`), which decides whether PBS down-converts GPP into legacy GDPR/USP fields on the **bid request**. Sync-URL macros keep working with the flag unset. The corpus agrees: at master @0ba3523, 90 bidder-info files carry a GPP macro in a sync URL, 26 set `gpp-supported: true`, and only 16 do both — so 74 files ship exactly the combination this rule flagged. Record it only when the review is *already* about GPP support, and then as **INFO**.
    Regenerate: [`field-index.md` → Regeneration commands](field-index.md#regeneration-commands) command 4.
10. **Alias GVL limitation**: Aliases cannot currently override the base adapter's GVL vendor ID
11. **whiteLabelOnly + aliasOf relationship**: `whiteLabelOnly: true` is typically set on PARENT adapters (e.g., TeqBlaze, SmartHub) to mark them as alias-targets. Aliases inherit semantics. The flag does NOT preclude Go code on the parent. See Workflow: White-Label Policy Compliance.
12. **openrtb 2.6 ↔ X-OpenRTB-Version header**: If the adapter sends an `X-OpenRTB-Version: 2.6` HTTP header but `static/bidder-info/{bidder}.yaml` does not declare `openrtb: version: "2.6"`, the bidder receives a 2.5-downgraded request despite the header. The mechanism is real: `exchange/utils.go:222-228` runs `if !ok || info.OpenRTB == nil || info.OpenRTB.Version != "2.6" { ... openrtb_ext.ConvertDownTo25(reqWrapperCopy) }`. Cross-check is owned by adapter-code-pr-review but documented here. Severity: **INFO** (NOTE) by default — master ships the mismatch for 3 of the 7 adapters that send a 2.6 header (`madsense`, `resetdigital`, `trustx`; the other four — `elementaltv`, `msft`, `synapseHX`, `yahooAds` — declare `2.6`), so it is not a merge-blocking inconsistency and must not be raised as a change request on that basis alone.
    - **Escalate to WARN** only when the adapter's own code depends on a field `ConvertDownTo25` moves or clears — the down-conversion relocates supply chain, GDPR, consent, US-privacy, and EIDs from their 2.6 homes into 2.5 ext locations and clears the 2.6-only fields (`openrtb_ext/convert_down.go`: `moveSupplyChainFrom26To25`, `moveGDPRFrom26To25`, `moveConsentFrom26To25`, `moveUSPrivacyFrom26To25`, `moveEIDFrom26To25`, `Clear26Fields`). An adapter reading `request.Source.SChain`, `request.Regs.GDPR`, `request.User.Consent`, or `request.User.EIDs` while its YAML omits `openrtb.version: "2.6"` has a functional bug, not a documentation mismatch. `bid.MType` on the *response* is unaffected — down-conversion only rewrites the outgoing request.
    Regenerate: [`field-index.md` → Regeneration commands](field-index.md#regeneration-commands) command 5.
13. **modifyingVastXmlAllowed**: Rare YAML field (only #4522 alliance_gravity uses it in 2025–2026). Set deliberately when video adapter wants to opt-in/opt-out of VAST modification tracking. Verify if declared.

## Detailed Documentation

See [field-index.md](references/field-index.md) for the complete Go struct mapping with types, YAML tags, and validation functions, plus common YAML field patterns observed across the 89 reference adapter PRs.

For framework-wide concerns (endpoint template macros canonical list, maintainer email policy, naming conventions, aliasing semantics, anti-patterns, test harness contract), see [../shared/framework-utilities.md](../shared/framework-utilities.md) — this skill references that file rather than duplicating its content.
