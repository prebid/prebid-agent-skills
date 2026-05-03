---
name: pr-triage
description: Triages every prebid/prebid-server pull request before reviewer skills run. USE WHEN any PR for prebid/prebid-server is being reviewed; this skill always runs first. Fetches PR data once, checks CI, runs drift checks (including go.mod module-path major-version), categorizes files by skill ownership, detects PR type, surfaces cross-skill concerns, and emits a routing manifest for downstream skills. Do NOT use for prebid-js, prebid-server-java, or non-PR tasks.
version: 1.0.0
---

# PR Triage

Triage any pull request on `prebid/prebid-server`. Fetch PR metadata once, categorize every file, check CI status, detect the PR type, run drift checks, identify cross-skill concerns, and produce a routing manifest that downstream reviewer skills consume.

## Core Principle: Single Source of Truth

**You are the gateway. No downstream skill should re-fetch PR data.** This skill fetches the PR file list, CI status, and drift check data exactly once. The routing manifest you produce becomes the single source of truth that all downstream reviewer skills consume.

- **NEVER** let downstream skills redundantly call the GitHub API for file lists
- **NEVER** skip CI status checking — unstable/blocked PRs need different handling
- **DO** categorize every single file in the PR — no file should be silently ignored
- **DO** detect cross-skill concerns that fall between the cracks of individual skills

## Activation

This skill activates for **any** pull request on `prebid/prebid-server`. It always runs first, before any of the 3 reviewer skills.

There are no file-pattern prerequisites — if a PR number is provided for `prebid/prebid-server`, this skill runs.

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model,
which can paraphrase source code and lose raw JSON structure. `curl` returns
exact, deterministic content. Parse the raw JSON output directly.

### Step 1: Fetch PR Metadata (Single Source of Truth)

Fetch all PR data that downstream skills will need. This step replaces Step 1a in all 3 downstream skills.

**1a. Fetch PR file list.**

- Use `curl` (via Bash tool): `curl -sS "https://api.github.com/repos/{owner}/{repo}/pulls/{N}/files?per_page=100"`
- If the response is paginated (>100 files), follow pagination via `&page=2`, etc., until all files are retrieved
- Store the complete file list: each file's `filename`, `status` (added/modified/removed/renamed), and `patch` (diff hunks)
- **Do NOT use** the `.diff` URL — it redirects to `patch-diff.githubusercontent.com` which is unreliable

**Note on file content availability:**
- For files with status `added`, the `patch` field contains the complete file content (every line prefixed with `+`). Downstream skills do NOT need to fetch these files separately.
- For files with status `modified`, the `patch` contains only changed regions with surrounding context lines. Downstream skills MAY need to fetch the full file from `raw.githubusercontent.com` if their verification requires context beyond the diff.
- For files with status `removed`, the `patch` contains the deleted content (every line prefixed with `-`).

**1b. Fetch PR details and analyze description.**

- Use `curl` (via Bash tool): `curl -sS "https://api.github.com/repos/{owner}/{repo}/pulls/{N}"`
- Extract: `title`, `body` (description), `user.login` (author), `labels`, `draft` status, `mergeable_state`, `head.sha`

- **Parse the PR description (`body`) for:**
  1. **Documentation PR link**: Search for references to `prebid/prebid.github.io` or `prebid.github.io#NNNN`. Record as: `docs_pr: prebid/prebid.github.io#NNNN` or `docs_pr: none`
  2. **Submission template completeness**: For `new-adapter` or `alias-only` PRs, check if the description includes the standard adapter submission template fields (contact email, test parameters, feature explanation). Record as: `template: complete | partial | missing | n/a`
  3. **Feature rationale**: Extract a 1-2 sentence summary of what the PR does and why, for context that downstream skills can reference when assessing design decisions.
  4. **Null/empty body**: If `body` is null or empty, record: `description: null — no PR description provided`
  5. **`agent review` label**: If the PR's `labels` array includes one named `agent review` (or `agent-review` / `agent_review` / `Agent Review`), record `agent_review: yes` in the manifest AND extract any prior agent comments. Detection: PR comments authored by GitHub usernames matching `*[bot]`, `ChrisHuie`, or accounts with names containing "agent" — these are likely the prior agent's findings.
     - Record extracted prior-agent comments in the manifest under `--- PRIOR AGENT FINDINGS ---` block (file:line + finding text + severity if stated).
     - Activation rules unchanged regardless of label — our skills still run their full workflow. But downstream skills MUST cross-reference each of their findings against the `--- PRIOR AGENT FINDINGS ---` list and SUPPRESS exact duplicates (same file, same rule, same severity). Net-new findings are emitted normally; matches are emitted as `Previously flagged by prior agent` (analogous to the existing `Previously flagged by {reviewer}` pattern in Step 1d).
     - Reference: PR #4698 (Apester) reviewer noted "the agent missed this" re: personal-email check — confirms prior agents do miss things; our skills should still run, just dedupe matches.

**1c. Fetch commits and check CI status.**

- Use `curl` (via Bash tool): `curl -sS "https://api.github.com/repos/{owner}/{repo}/pulls/{N}/commits"`
- Extract:
  - `head_sha` (last commit's SHA — used for CI status check below)
  - Commit count
  - Commit messages (for context on PR evolution — e.g., "fixed go fmt", "addressed review feedback")
- Then use `curl`: `curl -sS "https://api.github.com/repos/{owner}/{repo}/commits/{head_sha}/check-runs"`
- Categorize the overall CI status:
  - **clean**: All checks passed, PR is mergeable
  - **unstable**: Some checks failed but PR may still be reviewable
  - **blocked**: Critical checks failed (e.g., `validate` job — go.sum missing, compilation errors, needs rebase)
  - **pending**: Checks still running
- For failed check runs, extract:
  - Check run `name` (e.g., `validate`, `test`, `lint`)
  - Check run `conclusion` (success/failure/neutral/skipped)
  - `output.annotations` if available (exact file + line of failure)
- Produce a CI status summary:

```
CI Status: {clean|unstable|blocked|pending}
Failed checks:
  - {check_name}: {conclusion} - {summary}
    Annotations: {file}:{line} - {message}
```

- **If blocked** (validate failure, needs rebase): Report the CI failures and recommend the PR author fix them before detailed review. Still produce the routing manifest for informational purposes, but flag that downstream reviews should be deferred.
- **If unstable** (some test failures): Proceed with review but include CI failures in the manifest so downstream skills are aware.

**1d. Fetch PR comments.**

Fetch both types of PR comments:
```bash
# Inline review comments (code-level)
curl -sS "https://api.github.com/repos/{owner}/{repo}/pulls/{N}/comments"
# Conversation comments (discussion, CI bot reports)
curl -sS "https://api.github.com/repos/{owner}/{repo}/issues/{N}/comments"
```

- Categorize each comment: `reviewer-feedback`, `ci-bot-report`, `author-response`, `blocking-confirmation-pending`, `other`
- For `blocking-confirmation-pending`: detect reviewer phrases that gate merge on out-of-band confirmation, especially:
  - Phrases include (case-insensitive substring match): "please reply 'received'", "respond to email with 'received'", "I'll merge once you confirm via email", "sent email for verification", "email for verification", "Confirmed" (as a reply to such a comment) — maintainer email verification gate
  - Detect by phrase match in reviewer comment bodies. The "Confirmed" word alone is too broad; only treat it as a confirmation reply if it appears AFTER another comment in the thread containing one of the verification phrases above.
  - Mark these as `blocking-confirmation-pending` so downstream `bidder-info-pr-review` knows the maintainer-email check is in a holding state
- For reviewer feedback: extract the file path, line number, and 1-2 sentence summary
- For CI bot reports: extract the bot name and status (pass/fail/info)
- For author responses: note which reviewer comment they address
- Include categorized summaries in the routing manifest

**1e. Search for duplicate PRs.**

For each bidder name extracted from file paths:
```bash
curl -sS "https://api.github.com/search/issues?q={bidder}+repo:prebid/prebid-server+type:pr+state:open"
```

- Exclude the current PR from results
- Record any open PRs that touch the same bidder: `DUPLICATE: PR #{N2} also touches {bidder} — {title}`
- If no duplicates found, record: `duplicates: none`

All of 1a through 1e should execute in parallel where possible.

### Step 2: Run Drift Checks Centrally

Fetch the 3 upstream reference files that downstream skills use for drift detection. This step replaces Step 1b in all 3 downstream skills.

Fetch all 3 in parallel:

1. **bidder-info drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server/master/config/bidderinfo.go"`
   - Compare against the local field index at `bidder-info-pr-review/references/field-index.md`
   - If the live `BidderInfo` struct has fields not in our index, record: `DRIFT: bidder-info field index — new field(s): {field_names}`

2. **bidder-params drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server/master/openrtb_ext/bidders.go"`
   - Verify `NewBidderParamsValidator` still uses `gojsonschema` with draft-04 schemas
   - If the validation mechanism changed, record: `DRIFT: bidder-params validator mechanism changed`

3. **adapter-code drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server/master/adapters/adapterstest/test_json.go"` (note: the canonical file is now `test_json.go`, not the older `adapterstest.go`)
   - Diff the fetched content against the snapshot conventions described in `adapter-code-pr-review/references/adapter-code-index.md` (Supported test data directories section).
   - If the supported directories list (`exemplary`, `supplemental`, `amp`, `video`, `videosupplemental`) changes, OR if the currency-field assertion logic changes, OR if the multi-request 1:1 matching logic changes, record SPECIFIC drift output (NOT generic "drift detected"):
     - `DRIFT: adapter-code test harness — supported_directories_changed: {old} → {new}`
     - `DRIFT: adapter-code test harness — currency_assertion_changed`
     - `DRIFT: adapter-code test harness — multi_request_matching_changed`
     - `DRIFT: adapter-code test harness — error_comparison_default_changed`
   - Reference: PR #4592 (Microsoft, v3.30.0) introduced the currency assertion + 1:1 matching, cascading test fixture updates to 35+ existing adapters. Concurrent PRs were broken by the cascade — specific drift output lets reviewers attribute failures correctly.

4. **module-path major-version drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server/master/go.mod"`
   - Parse the `module` declaration line — extract the version suffix (e.g., `/v4`).
   - Compare against the canonical major recorded in `shared/framework-utilities.md` (currently `v4`).
   - If the upstream major differs from `v4`, record: `DRIFT: module path major version changed (v4 → vN)`. The skills' references files MUST be updated atomically before proceeding.

Produce a drift summary:

```
Drift Check Results:
  bidder-info:   {OK | DRIFT: ...}
  bidder-params: {OK | DRIFT: ...}
  adapter-code:  {OK | DRIFT: {specific change name}: {one-line description}}
  module-path:   {OK | DRIFT: module path major version changed (v4 → vN)}
```

Drift output schema is pinned: `{skill_name}: OK` or `{skill_name}: DRIFT: {category}: {one-line description}`. Downstream skills consume this and should not parse free-form text.

Any drift warnings are included in the routing manifest for the relevant downstream skill.

### Step 3: Categorize Every File by Skill Ownership

For every file in the PR, determine which skill (if any) owns it. Use the routing rules defined in [references/routing-rules.md](references/routing-rules.md).

**Categorization output** — assign each file to exactly one of these buckets:

| Bucket | Description |
|--------|-------------|
| `bidder-info` | Owned by bidder-info-pr-review |
| `bidder-params` | Owned by bidder-params-pr-review |
| `adapter-code` | Owned by adapter-code-pr-review |
| `shared:bidder-params+adapter-code` | Shared ownership (see shared file rules) |
| `unowned:framework` | Framework/infrastructure file not owned by any skill |
| `unowned:docs` | Documentation file |
| `unowned:ci` | CI/CD configuration file |
| `unowned:config` | Configuration/build file |
| `unowned:other` | Other unowned file |

**Shared file handling:**

The file `openrtb_ext/bidders.go` is referenced by both `bidder-params` (for `NewBidderParamsValidator`) and `adapter-code` (for bidder constant registration). Categorize it as follows:
- If the diff shows changes to `const Bidder{Name}` or `coreBidderNames` entries: assign to `adapter-code`
- If the diff shows changes to `NewBidderParamsValidator` or schema validation logic: assign to `bidder-params`
- If both types of changes are present: assign to `shared:bidder-params+adapter-code` and include in both skills' file lists

The file `exchange/adapter_builders.go` is exclusively owned by `adapter-code`.

**Priority rules for overlapping patterns:**

The pattern `adapters/{bidder}/*.go` in adapter-code overlaps with `adapters/*/params_test.go` in bidder-params. Resolution:
1. `adapters/{bidder}/params_test.go` → **bidder-params** (explicit exclusion in adapter-code, more specific pattern wins)
2. All other `adapters/{bidder}/*.go` → **adapter-code**

**Capabilities extraction:**

For each bidder identified in the PR:
- If `static/bidder-info/{bidder}.yaml` is in the PR with status `added`, extract the `capabilities` object from the patch (all lines are `+` prefixed, so the full content is available)
- If `static/bidder-info/{bidder}.yaml` is in the PR with status `modified`, extract capabilities from the patch if changed, otherwise record: `capabilities: unchanged in this PR`
- If `static/bidder-info/{bidder}.yaml` is NOT in the PR, record: `capabilities: not in PR — downstream must fetch from master`
- Also extract `aliasOf` status: `aliasOf: {parent}` or `aliasOf: none`

**Whitelabel-only flag extraction:**

For each bidder identified in the PR, also extract:
- If `static/bidder-info/{bidder}.yaml` is in the PR with status `added` or `modified`, extract `whiteLabelOnly:` value from the patch (`true`, `false`, or absent).
- If the YAML is NOT in the PR, attempt to fetch the master version: `curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/master/static/bidder-info/{bidder}.yaml"` and extract `whiteLabelOnly:`.
- Record per bidder: `whitelabelOnly: {true | false | absent}`.

This metadata is used by:
- `bidder-info-pr-review` Workflow: White-Label Policy Compliance
- pr-triage cross-skill concern 5g (below)

This metadata is included in the manifest so downstream skills (especially adapter-code) can use capabilities for test data coverage checks without extra API calls.

**For each file, record:**
- `filename`
- `status` (added/modified/removed/renamed)
- `patch` (diff hunks)
- `owner` (bucket assignment)
- `bidder_name` (extracted from path, if applicable)

Produce a categorization summary:

```
File Categorization:
  bidder-info (N files):
    - static/bidder-info/foo.yaml [added]
  bidder-params (N files):
    - static/bidder-params/foo.json [added]
    - openrtb_ext/imp_foo.go [added]
    - adapters/foo/params_test.go [added]
  adapter-code (N files):
    - adapters/foo/foo.go [added]
    - adapters/foo/foo_test.go [added]
    - adapters/foo/footest/exemplary/banner.json [added]
    - exchange/adapter_builders.go [modified]
    - openrtb_ext/bidders.go [modified]
  unowned:framework (N files):
    - macros/macros.go [modified]
  unowned:config (N files):
    - go.sum [modified]
```

### Step 4: Detect PR Type

Based on the categorized files, determine the PR type. A PR may have a primary type and secondary types.

**PR Type Detection Rules** (evaluated in order):

1. **Infrastructure/Bulk Change**
   - Trigger: 5+ distinct bidder directories affected in any single skill's files, OR framework files constitute >50% of total changed files, OR total files >50 with >80% matching a single repeated pattern
   - Label: `infrastructure`
   - Sub-label `framework-debt` (additional, on top of `infrastructure`): if `adapters/adapterstest/test_json.go` or other adapter-test-harness files are modified — this triggers Step 5h cascading-impact assessment
   - Effect: Downstream skills activate in "bulk mode" — verify pattern consistency across affected bidders, not per-bidder detailed review. Focus detailed review only on net-new code that is NOT part of the bulk pattern.
   - **Multi-adapter alias bundle exception**: A PR may contain N alias-only YAMLs for the SAME parent without triggering bulk mode IF: all files target `static/bidder-info/*.yaml` only, all YAML files have identical key set, all `aliasOf:` values match, no file > 5 lines, no diverging fields. In this case PR type is `alias-only` (not `infrastructure`). Canonical example: PR #4651 (5 Limelight aliases). See `references/routing-rules.md#bulk-mode-exception-for-multi-adapter-alias-prs`.

2. **New Adapter**
   - Trigger: An `adapters/{bidder}/{bidder}.go` has status `added`, AND at least one of: `static/bidder-info/{bidder}.yaml` is `added`, or `openrtb_ext/bidders.go` diff contains a new `Bidder{Name}` constant
   - Label: `new-adapter`
   - Effect: All 3 skills should activate. Registration completeness is checked.

3. **Alias-Only**
   - Trigger: Only `static/bidder-info/*.yaml` file(s) changed, AND every changed file's diff contains `aliasOf` on an added (`+`) line
   - Label: `alias-only`
   - Effect: Only bidder-info skill activates. Triage additionally checks cross-skill concerns (Step 5a: invalid endpoint macros).

4. **Adapter Modification**
   - Trigger: Files in an existing `adapters/{bidder}/` directory are modified (not added), or existing bidder-info/bidder-params files are modified
   - Label: `adapter-modification`
   - Effect: Only the relevant skills activate based on which files changed.

5. **Bidder Removal/Disable**
   - Trigger: Adapter files are removed, OR a bidder-info YAML diff shows `disabled: true` being added
   - Label: `bidder-removal`
   - Effect: All skills that have files for this bidder should be notified.

5b. **Whitelabel-Redirect-Mid-Review** (sub-label, applies on top of `alias-only`)
   - Trigger: Final state is `alias-only` AND PR comment history contains:
     - reviewer phrase matching "is this (a )?white.?label" or "looks (very )?similar to" or "this looks like a copy of"
     - + author confirmation containing "white label" or "white-label"
     - + commit count > 1 (indicates code was changed mid-review, suggesting redirection)
   - Sub-label: `whitelabel-redirect-mid-review`
   - Effect: pr-triage records `REDIRECT: PR was originally a full adapter, redirected to alias-only after reviewer flagged white-label policy. Canonical examples: #4329, #4383, #4391, #4376, #4565.`
   - This is INFORMATIONAL and does not change activation; it provides context for downstream skills' findings.

6. **Bidder Rename / Refactor**
   - Trigger: Files are deleted from `adapters/{old_bidder}/` AND added to `adapters/{new_bidder}/` in the same PR; OR `static/bidder-info/{old_bidder}.yaml` deleted with `static/bidder-info/{new_bidder}.yaml` added; OR `openrtb_ext/bidders.go` shows a constant rename
   - Label: `bidder-rename`
   - Effect: All affected files routed to their normal owner skills. pr-triage records `RENAME: {old} → {new}` in the manifest. Reviewer guidance: bidder renames are breaking changes typically deferred to the next major release (per PR #4456 progx → programmaticX, PR #4639 adoppler → elementaltv).

7. **Framework-Only**
   - Trigger: All changed files are in `unowned:*` categories
   - Label: `framework-only`
   - Effect: No downstream reviewer skills activate. Triage produces a summary of framework changes and recommends human review.

8. **Mixed**
   - Trigger: Multiple categories above apply (e.g., new adapter + framework change)
   - Label: `mixed` with sub-labels
   - Effect: Each sub-component is handled according to its type.

Produce a PR type summary:

```
PR Type: {type} [secondary: {type2}, ...]
Bidders affected: {bidder1}, {bidder2}, ...
New bidders: {list or none}
Removed bidders: {list or none}
```

### Step 5: Detect Cross-Skill Concerns

Check for issues that fall between the cracks of individual skills. These are concerns that no single downstream skill would catch because they span skill boundaries.

**5a. Invalid Endpoint Macros in Alias PRs**

If the PR type is `alias-only`:
- For each new alias file, extract the `endpoint` value from the diff
- If the endpoint contains template macros (e.g., `{{.AccountID}}`), cross-reference against the valid macro list from `macros.EndpointTemplateParams` (see [routing-rules.md](references/routing-rules.md) for the full 18-field list)
  - Any `{{.XYZ}}` macro where `XYZ` is not a field in `EndpointTemplateParams` is invalid and will silently resolve to empty string at runtime
- Record as: `CROSS-SKILL: Invalid endpoint macro "{{.XYZ}}" in alias {bidder} — will silently become empty string. Adapter-code skill does not activate for alias-only PRs but this macro validation is critical.`

**5b. Framework File Impact Assessment**

If any files are in an `unowned:framework` bucket:
- Check against the known-impact framework file list in [references/routing-rules.md](references/routing-rules.md)
- For each known-impact file, assess scope:
  - `macros/macros.go` — changes to `EndpointTemplateParams` affect all adapters using template macros
  - `config/bidderinfo.go` — changes to `BidderInfo` struct definition **trigger drift** in bidder-info field index
  - `adapters/bidder.go` — changes to the `Bidder` interface affect ALL adapters
  - `adapters/adapterstest/test_json.go` — changes affect all adapter test runners, **triggers drift** in adapter-code index
  - See routing-rules.md for full list
- For known-impact files, record: `FRAMEWORK IMPACT: {file} changed — affects {scope}. Recommend human review.`
- For unknown framework files, record: `FRAMEWORK: {file} changed — unknown impact scope. Recommend human review.`

**5c. Alias + Parent Consistency**

If a PR modifies both a parent bidder's files AND alias files:
- Verify the changes are consistent (e.g., if parent endpoint changes, do alias endpoints need updating?)
- Record as: `CROSS-SKILL: Parent bidder {parent} and alias {alias} both modified — verify consistency.`

**5d. Registration Without Implementation (and vice versa)**

If `openrtb_ext/bidders.go` or `exchange/adapter_builders.go` is modified but no adapter code files are present:
- Record: `CROSS-SKILL: Registration file modified but no adapter code in PR. Verify this is a split PR or alias registration.`

If adapter code files are present but registration files are not, and PR type is `new-adapter`:
- Record: `CROSS-SKILL: New adapter code present but registration files missing. Incomplete new adapter PR.`

**5e. New Adapter Completeness Check**

If PR type is `new-adapter`, verify the complete expected file set is present for each new bidder. A complete new adapter PR should include:
- `static/bidder-info/{bidder}.yaml` — bidder-info config
- `static/bidder-params/{bidder}.json` — parameter JSON schema
- `openrtb_ext/imp_{bidder}.go` — impression extension Go struct
- `adapters/{bidder}/{bidder}.go` — adapter implementation
- `adapters/{bidder}/{bidder}_test.go` — JSON test runner
- `adapters/{bidder}/params_test.go` — parameter validation tests
- `adapters/{bidder}/{bidder}test/exemplary/*.json` — at least 1 exemplary fixture
- `adapters/{bidder}/{bidder}test/supplemental/*.json` — at least 1 supplemental fixture
- `exchange/adapter_builders.go` — builder registration (modified)
- `openrtb_ext/bidders.go` — bidder constant registration (modified)

For each missing file, record: `COMPLETENESS: New adapter {bidder} missing {file_type}. Incomplete PR.`
This check catches split PRs or forgotten files that no individual downstream skill would detect since each skill only sees its own files.

**5f. Dependency Changes**

If `go.mod` or `go.sum` is modified:
- Record: `DEPENDENCY: go.mod/go.sum modified. Verify new dependencies are necessary and properly vendored.`

**5g. Whitelabel-Only Resemblance Heuristic**

Trigger: ANY of:
- PR is type `new-adapter` AND the new adapter Go code is significantly smaller than typical (e.g., < 100 lines of `{bidder}.go`) AND closely resembles an existing adapter's structure
- PR is type `new-adapter` AND the PR description / commit messages / discussion contains the phrase "white label" / "white-label" / "whitelabel"
- PR is type `new-adapter` AND the new bidder-info YAML's `endpoint:` matches an existing adapter's endpoint domain
- PR is type `alias-only` AND the secondary sub-label `whitelabel-redirect-mid-review` was set per Step 4 rule 5b (i.e., PR was historically a full adapter)

Action:
- Record: `CROSS-SKILL: New adapter {bidder} may be a white-label scenario. Reviewer may redirect to alias-only (aliasOf:) form. The bidder-info-pr-review Workflow: White-Label Policy Compliance evaluates further.`
- Severity: **WARN** (heuristic, not deterministic — final decision is reviewer judgment)
- Reference quotes from PRs #4329, #4383, #4391, #4565 are catalogued in `bidder-info-pr-review/SKILL.md` and `shared/framework-utilities.md#aliasing`.

**5h. Framework Test-Harness Impact**

Trigger: ANY file under `adapters/adapterstest/` is modified.

Action:
- Record: `FRAMEWORK IMPACT: adapter test harness modified ({file}). Expect cascading impact on existing adapter test fixtures across many other adapters in the same PR.`
- Cross-reference the drift output from Step 2.3 — if drift was already detected, the message becomes: `FRAMEWORK IMPACT: adapter test harness modified — {specific drift name from Step 2}`
- Reference: PR #4592 Microsoft cascaded to 35+ adapter test directories. Detailed drift output (not generic "drift detected") helps concurrent-PR reviewers attribute test failures correctly.
- ALSO search open PRs that touch any `adapters/*/{*test,test,test-extrainfo}/**.json` file and were last updated BEFORE this PR's `head_sha` was pushed. Record any matches as: `CONCURRENT-PR RISK: PR #{N} touches {bidder} test fixtures and predates this test_json.go change — likely broken by the cascade. Recommend the PR author rebase.` Reference: PR #4592 → Clydo cascade where bsardo had to manually flag the breakage in an issue comment.

**5i. Approval-to-Merge Stall Detection**

Trigger: Reviewer feedback in `Step 1d` includes approving reviews older than 30 days from current date AND PR is still open.

Action:
- Record: `STALL: PR has approving review(s) older than {N} days but is not merged. Likely waiting on docs PR or queue attention. Reference: PR #4321 (Nativery), PR #4283 (Performist) — both stalled 100+ days post-approval.`
- Severity: **INFO** (process not code)

Produce a cross-skill concerns summary:

```
Cross-Skill Concerns:
  - {concern1}
  - {concern2}
  (or: None detected)
```

### Step 6: Produce Routing Manifest

Assemble all data from Steps 1–5 into a structured routing manifest. This is the complete output of the triage skill and the single source of truth for downstream skills.

**Routing Manifest Format:**

```
=== PR TRIAGE MANIFEST ===
PR: {owner}/{repo}#{number}
Title: {title}
Author: {author}
Draft: {yes/no}

--- PR DESCRIPTION ---
Docs PR: {prebid/prebid.github.io#NNNN | none}
Template: {complete | partial | missing | n/a}
Summary: {1-2 sentence feature rationale}

--- COMMITS ---
Count: {N}
Head SHA: {sha}
Messages:
  - {commit message 1}
  - {commit message 2}

--- PR COMMENTS ---
Reviewer feedback ({N}):
  - {reviewer} on {file}:{line}: {1-2 sentence summary}
CI bot reports ({N}):
  - {bot_name}: {status} — {summary}
Author responses ({N}):
  - Re: {reviewer}'s comment on {file}: {summary}

--- CI STATUS ---
Overall: {clean|unstable|blocked|pending}
Failed checks:
  - {check_name}: {conclusion}
    {annotations if available}
Recommendation: {proceed with review | defer review until CI passes}

--- DRIFT CHECKS ---
bidder-info:   {OK | DRIFT: details}
bidder-params: {OK | DRIFT: details}
adapter-code:  {OK | DRIFT: details}

--- PR TYPE ---
Primary: {type}                          # new-adapter | alias-only | adapter-modification | bidder-removal | bidder-rename | infrastructure | framework-only | mixed
Secondary: {types or none}               # e.g., framework-debt as a sub-label on infrastructure
Bidders affected: {list}
New bidders: {list or none}
Renamed bidders: {old → new list or none}

--- FILE ROUTING ---
bidder-info-pr-review ({N} files):
  {filename} [{status}] (bidder: {name})
  ...

bidder-params-pr-review ({N} files):
  {filename} [{status}] (bidder: {name})
  ...

adapter-code-pr-review ({N} files):
  {filename} [{status}] (bidder: {name})
  ...

Unowned files ({N} files):
  {filename} [{status}] — {subcategory}: {impact note}
  ...

--- CROSS-SKILL CONCERNS ---
{concerns or "None detected"}

--- PRIOR AGENT FINDINGS ---
{Only present when `agent_review: yes` was recorded in Step 1b sub-bullet 5.}
{For each prior-agent comment extracted:}
- {file}:{line | "PR-level"}: {finding text} [{severity if stated}]
{Or: "agent_review: no — section omitted"}

--- BIDDER METADATA ---
{For each bidder in the PR:}
{bidder}:
  aliasOf: {parent | none}
  whitelabelOnly: {true | false | absent}
  capabilities: {extracted object | "unchanged in this PR" | "not in PR — downstream must fetch from master"}

--- PR-LEVEL CHECKS ---
Duplicate PRs:
  - {PR #{N2}: {title} — touches {bidder}} (or "none")
Completeness (new adapters only):
  - {missing file warnings or "all expected files present"}

--- SKILL ACTIVATION ---
Activate bidder-info-pr-review: {yes/no} ({N} files, {reason})
Activate bidder-params-pr-review: {yes/no} ({N} files, {reason})
Activate adapter-code-pr-review: {yes/no} ({N} files, {reason})

{If infrastructure/bulk:}
NOTE: Infrastructure/bulk change detected. Downstream skills should use
bulk review mode (pattern consistency check, not per-bidder detailed review).

{If blocked CI:}
NOTE: CI is blocked. Downstream reviews are deferred. Reporting CI failures only.

=== END MANIFEST ===
```

**Skill activation rules:**
- A skill activates if it has 1 or more files routed to it
- Exception: If PR type is `infrastructure` and the skill's files are all part of the bulk pattern, the skill activates in "bulk mode" (reduced scope)
- Exception: If CI is `blocked`, skills are informed but detailed review is deferred
- If no skill has files (all files unowned), no skills activate — triage reports framework changes and recommends human review

### Step 7: Summary

After producing the routing manifest, output a human-readable summary:

- PR title and author
- CI status (with failure details if applicable)
- PR type classification
- File count by category
- Skills to activate (with file counts)
- Cross-skill concerns (if any)
- Drift warnings (if any)
- Unowned files requiring human attention (if any)
- Overall recommendation: proceed to review | defer until CI passes | recommend human review for framework changes

---

## Optional: Prior-Spec Comparison (read/ integration)

If a prior Adapter Specification exists at `prebid-server-go/read/specs/{bidder}/latest.yaml` (typically because the user has previously read the adapter via `read-adapter-orchestrator --persist`), pr-triage can load it as `prior_spec` and detect behavioral regressions on the PR diff. Reviewer skills receive the loaded spec via the routing manifest's `--- PRIOR SPEC COMPARISON ---` block and flag deviations.

This is OPT-IN: pr-triage continues to work without `prior_spec`. The hook is automatic when the file is present.

**Detection workflow** (runs after Step 4 PR-type detection, before Step 5 cross-skill concerns):

1. For each bidder identified in `Bidders affected:` (Step 4), check whether `prebid-server-go/read/specs/{bidder}/latest.yaml` exists locally. The `read/specs/` directory is `.gitignore`'d by default; users opt into checking specs in for diff-comparison workflows.
2. If present, load the YAML; record `prior_spec.provenance.source.resolved_commit` and `prior_spec.adapter_spec_version`.
3. For each non-removed file in the PR routed to a downstream skill, run targeted regression checks against `prior_spec`. Examples:
   - PR adds `import "text/template"` to `adapters/{xyz}/{xyz}.go` → if `prior_spec.code.imports.has_template_engine: false` AND `prior_spec.code.make_requests.endpoint_resolution.kind: static`, flag: `PRIOR-SPEC: Endpoint kind changing from static to template-macro. Was this intentional? If yes, the spec should be re-read on the post-merge commit.`
   - PR adds custom `func (e *ExtImpXyz) UnmarshalJSON(data []byte) error` method → if `prior_spec.params.ext_struct.custom_unmarshal: false`, flag: `PRIOR-SPEC: Custom UnmarshalJSON added. Verify ext.accepts_shapes captures the new flexibility (see ext_pojo_construction.custom_unmarshal taxonomy).`
   - PR removes a quirk's source line (e.g., the `kobler.go:23` const referenced by `prior_spec.quirks[id=hardcoded-dev-endpoint]`) → flag: `PRIOR-SPEC: Quirk hardcoded-dev-endpoint at kobler.go:23 is no longer load-bearing — orchestrator should remove from spec on next read.`
   - PR adds a new alias YAML at `static/bidder-info/connektai.yaml` → if `prior_spec.meta.parent_aliases` does not contain `connektai`, flag: `PRIOR-SPEC: New alias detected. Java port (if any) needs aliases: { connektai: ~ } entry under the parent's bidder-config YAML (port translation Rule 33).`
   - PR adds `disabled: true` to YAML → if `prior_spec.meta.disabled: false` AND PR also touches the endpoint field with a `#{TOKEN}#`-style placeholder, flag: `PRIOR-SPEC: Bidder being disabled with deploy-time token introduction. Reference: PR #4502 appStockSSP REGION token. Confirm with reviewer.`
   - PR changes adapter struct field from `endpoint string` to `endpointTemplate *template.Template` → if `prior_spec.code.builder.template_parsed_at_build: false`, flag: `PRIOR-SPEC: Builder now parses template at build time. endpoint_resolution.mechanism_go should change to text/template on next read.`
4. Append all `PRIOR-SPEC:` flags to the routing manifest under a new `--- PRIOR SPEC COMPARISON ---` block (between `--- CROSS-SKILL CONCERNS ---` and `--- PRIOR AGENT FINDINGS ---`).
5. If `read/specs/{bidder}/latest.yaml` is missing, omit the block silently. Do NOT recompute the spec — that's the user's opt-in via `read-adapter-orchestrator --persist`. Do NOT block the review on absence.

**Manifest block format**:

```
--- PRIOR SPEC COMPARISON ---
prior_spec: read/specs/{bidder}/latest.yaml
prior_spec.resolved_commit: {sha}
prior_spec.adapter_spec_version: "1.0.0"
Regressions detected ({N}):
  - PRIOR-SPEC: {flag text} (file:{path}:{line if applicable})
  ...
(or: "No regressions detected" if N=0)
(or: "prior_spec not present — section omitted" if no file at read/specs/{bidder}/latest.yaml)
```

The `--- PRIOR SPEC COMPARISON ---` block is consumed by downstream reviewer skills exactly like the existing `--- PRIOR AGENT FINDINGS ---` block: skills cross-reference findings against the prior-spec flags and surface only NET-NEW concerns from the PR diff. Matches dedup as "Previously captured in prior_spec — confirm with reviewer if intentional."

For more on the read/ → review/ composition contract, the spec lifecycle, and worked detection examples, see [`../../../read/skills/shared/cross-skill-integration.md`](../../../read/skills/shared/cross-skill-integration.md) §5 (Read ↔ Review opt-in hook).

### Cross-language ports: `prior_source_spec`

For PRs that PORT an adapter from one language to the other (the canonical case being the Teal flow: read the Java adapter spec → port to Go → review the Go PR → reflect findings back to SKILLs), the SOURCE-language spec is a more useful comparison baseline than the same-language prior spec. pr-triage exposes a second slot, `prior_source_spec`, alongside `prior_spec`:

| Slot | Purpose | Path (when persisted) |
|---|---|---|
| `prior_spec` | Same-language regression detection (Go PR ↔ Go prior-spec) | `prebid-server-go/read/specs/{bidder}/latest.yaml` (gitignored; user-persisted via `read-adapter-orchestrator --persist`) |
| `prior_source_spec` | Cross-language port-fidelity detection (Go PR ↔ Java SOURCE spec, or vice versa) | `prebid-server-java/read/specs/{bidder}/latest.yaml` when the SOURCE language is Java; mirror-image when reviewing a Java PR ported from Go |

When `prior_source_spec` is present, pr-triage emits a complementary `--- PRIOR SOURCE SPEC COMPARISON ---` manifest block. Findings flagged here are port-fidelity divergences, NOT same-language regressions. Severity policy:

- `info` by default — port asymmetries are often legitimate per Rules 5 / 9 / 11 / 35 / 38 / etc. (e.g., Go's `text/template` vs Java's `String.replace` for endpoint construction).
- `warn` when the divergence touches a Rule 38 byte-fidelity assertion, an R5-strict cross-language equivalence, or a known-master-sample pattern.
- `fail` when a dual-spec assertion under `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` declares the divergence as `severity: fail` (the canonical example is aax: Java omits `minLength: 1` on `cid` / `crid`).

### One-shot specs (Teal flow): `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml`

When pr-triage runs as part of a single end-to-end orchestration (the "Teal flow": read Java adapter → port to Go → review Go PR → reflect findings back to SKILL updates), specs are NOT user-persisted to the gitignored `read/specs/{bidder}/latest.yaml` location. Instead, the orchestrator writes them to a transient run-scoped path:

```
.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml
```

Where:

- `{run-id}` is an ISO-like timestamp + short hash (e.g., `2026-05-03T1430Z-a3f9`) generated by the orchestrator at run start.
- `{lang}` is `go` or `java`.
- `{bidder}` is the canonical bidder name (matches `meta.bidder_name`).

pr-triage discovers specs in this resolution order (first match wins):

1. `--prior-spec={path}` / `--prior-source-spec={path}` CLI overrides (explicit).
2. `${PRIOR_SPEC_PATH}` / `${PRIOR_SOURCE_SPEC_PATH}` environment variables.
3. `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` when `${FULL_LOOP_RUN_ID}` is set in the environment (Teal-flow orchestrator hand-off).
4. `prebid-server-{lang}/read/specs/{bidder}/latest.yaml` (the persisted user-opt-in location).

If none resolve, both blocks are silently omitted (the comparison is opt-in; pr-triage continues without). The `.tmp/full-loop/` location is added to `.gitignore` so transient run artifacts never reach origin.

---

## Cross-Skill References (Read-Only)

This skill reads files from downstream skills for drift comparison:

- `bidder-info-pr-review/references/field-index.md` — to compare against live `BidderInfo` struct
- `bidder-params-pr-review/references/params-type-index.md` — for context on schema validation mechanism
- `adapter-code-pr-review/references/adapter-code-index.md` — for context on test harness structure
- `../../../read/skills/shared/cross-skill-integration.md` — read/ → review/ integration contract (opt-in prior-spec comparison hook; spec lifecycle; detection examples). Loaded only when the user has the read/ skill suite installed and `read/specs/{bidder}/latest.yaml` exists locally.

---

## Reference Documentation

See [routing-rules.md](references/routing-rules.md) for:
- Complete file-to-skill routing table
- Priority rules for overlapping patterns
- Shared file resolution logic
- Unowned file patterns and impact assessment
- PR type detection heuristics
- Bidder name extraction rules
- Valid endpoint template macros

---

## Shared Framework Reference

For framework-wide concerns (endpoint template macros canonical list, error type taxonomy, anti-patterns, maintainer email policy, white-label policy, naming conventions, aliasing semantics, test harness contract), the four review skills share [../../shared/framework-utilities.md](../../shared/framework-utilities.md). The pr-triage drift checks (Step 2) reference this file.

---

## One-Alias-Per-PR Rule

Reviewers (per `bsardo` PR #4214 and `pm-isha-bharti` PR #4215) prefer one alias per PR for clean changelog. EXCEPTION: `references/routing-rules.md#bulk-mode-exception-for-multi-adapter-alias-prs` documents when N aliases-of-same-parent in one PR is acceptable.

When the trigger conditions for the exception are NOT met, pr-triage should record:
- `BULK-PR: {N} aliases bundled for {N_parents} different parents — reviewer may request split per pm-isha-bharti's policy.`
- Severity: **WARN** (process recommendation)
