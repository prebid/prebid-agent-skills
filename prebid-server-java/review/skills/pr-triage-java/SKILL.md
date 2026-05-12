---
name: pr-triage-java
description: Triages every prebid/prebid-server-java pull request before reviewer skills run. USE WHEN any PR for prebid/prebid-server-java is being reviewed; this skill always runs first. Fetches PR data once, checks CI, runs drift checks, categorizes files by skill ownership, detects PR type, surfaces cross-skill concerns, and emits a routing manifest for downstream skills. Do NOT use for prebid-js, prebid-server (Go), or non-PR tasks.
version: 1.0.0
---

# PR Triage (Java)

Triage any pull request on `prebid/prebid-server-java`. Fetch PR metadata once, categorize every file, check CI status, detect the PR type, run drift checks, identify cross-skill concerns, and produce a routing manifest that downstream reviewer skills consume.

This skill is the Java-tree analog of `prebid-server-go/review/skills/pr-triage`. The orchestrator pattern is identical; the file routing, drift checks, PR-type detection, and cross-skill concerns are specialized for Java's framework (Spring DI, unified bidder-config YAML, inverted aliases, IT test classes, Lombok, mvn-checkstyle).

## Core Principle: Single Source of Truth

**You are the gateway. No downstream skill should re-fetch PR data.** This skill fetches the PR file list, CI status, and drift check data exactly once. The routing manifest you produce becomes the single source of truth that all downstream reviewer skills consume.

- **NEVER** let downstream skills redundantly call the GitHub API for file lists
- **NEVER** skip CI status checking — unstable/blocked PRs need different handling
- **DO** categorize every single file in the PR — no file should be silently ignored
- **DO** detect cross-skill concerns that fall between the cracks of individual skills

## Activation

This skill activates for **any** pull request on `prebid/prebid-server-java`. It always runs first, before any of the 3 reviewer skills (`bidder-class-pr-review`, `bidder-config-pr-review`, `bidder-params-java-pr-review`).

There are no file-pattern prerequisites — if a PR number is provided for `prebid/prebid-server-java`, this skill runs.

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model,
which can paraphrase source code and lose raw JSON structure. `curl` returns
exact, deterministic content. Parse the raw JSON output directly.

### Step 1: Fetch PR Metadata (Single Source of Truth)

Fetch all PR data that downstream skills will need. This step replaces Step 1a in all 3 downstream skills.

**1a. Fetch PR file list.**

- Use `curl` (via Bash tool): `curl -sS "https://api.github.com/repos/prebid/prebid-server-java/pulls/{N}/files?per_page=100"`
- If the response is paginated (>100 files), follow pagination via `&page=2`, etc., until all files are retrieved
- Store the complete file list: each file's `filename`, `status` (added/modified/removed/renamed), and `patch` (diff hunks)
- **Do NOT use** the `.diff` URL — it redirects to `patch-diff.githubusercontent.com` which is unreliable

**Note on file content availability** (same contract as Go side):
- For files with status `added`, the `patch` field contains the complete file content (every line prefixed with `+`). Downstream skills do NOT need to fetch these files separately.
- For files with status `modified`, the `patch` contains only changed regions with surrounding context lines. Downstream skills MAY need to fetch the full file from `raw.githubusercontent.com` if their verification requires context beyond the diff. Note Java's frequent need for full-file context: checkstyle's `OuterTypeFilename` rule and Lombok-annotation review benefit from seeing the entire class declaration.
- For files with status `removed`, the `patch` contains the deleted content (every line prefixed with `-`).

**1b. Fetch PR details and analyze description.**

- Use `curl` (via Bash tool): `curl -sS "https://api.github.com/repos/prebid/prebid-server-java/pulls/{N}"`
- Extract: `title`, `body` (description), `user.login` (author), `labels`, `draft` status, `mergeable_state`, `head.sha`

- **Parse the PR description (`body`) for:**
  1. **Documentation PR link**: Search for references to `prebid/prebid.github.io` or `prebid.github.io#NNNN`. Record as: `docs_pr: prebid/prebid.github.io#NNNN` or `docs_pr: none`. Java-side bidder docs live at the same `prebid.github.io/dev-docs/bidders/` location as Go-side bidders — a docs PR may be needed for new bidders.
  2. **Submission template completeness**: For `new-adapter` or `alias-only` PRs, check if the description includes the standard adapter submission template fields (contact email, test parameters, feature explanation). Record as: `template: complete | partial | missing | n/a`
  3. **Feature rationale**: Extract a 1-2 sentence summary of what the PR does and why, for context that downstream skills can reference when assessing design decisions.
  4. **Null/empty body**: If `body` is null or empty, record: `description: null — no PR description provided`
  5. **`agent review` label**: If the PR's `labels` array includes one named `agent review` (or `agent-review` / `agent_review` / `Agent Review`), record `agent_review: yes` in the manifest AND extract any prior agent comments. Detection: PR comments authored by GitHub usernames matching `*[bot]`, `ChrisHuie`, or accounts with names containing "agent" — these are likely the prior agent's findings. (Username list kept in parity with the Go-side `pr-triage` heuristic.)
     - Record extracted prior-agent comments in the manifest under `--- PRIOR AGENT FINDINGS ---` block (file:line + finding text + severity if stated).
     - Activation rules unchanged regardless of label — our skills still run their full workflow. But downstream skills MUST cross-reference each of their findings against the `--- PRIOR AGENT FINDINGS ---` list and SUPPRESS exact duplicates (same file, same rule, same severity). Net-new findings are emitted normally; matches are emitted as `Previously flagged by prior agent` (analogous to the existing `Previously flagged by {reviewer}` pattern in Step 1d).

**1c. Fetch commits and check CI status.**

- Use `curl` (via Bash tool): `curl -sS "https://api.github.com/repos/prebid/prebid-server-java/pulls/{N}/commits"`
- Extract:
  - `head_sha` (last commit's SHA — used for CI status check below)
  - Commit count
  - Commit messages (for context on PR evolution — e.g., "fix checkstyle", "addressed review feedback", "mvn fmt")
- Then use `curl`: `curl -sS "https://api.github.com/repos/prebid/prebid-server-java/commits/{head_sha}/check-runs"`
- Categorize the overall CI status:
  - **clean**: All checks passed, PR is mergeable
  - **unstable**: Some checks failed but PR may still be reviewable
  - **blocked**: Critical checks failed (e.g., `validate` / `compile` / `checkstyle` jobs)
  - **pending**: Checks still running
- For failed check runs, extract:
  - Check run `name` (Java upstream's CI typically declares: `Build / Test`, `checkstyle`, `JaCoCo Coverage`, others — check the head SHA's actual check names)
  - Check run `conclusion` (success/failure/neutral/skipped)
  - `output.annotations` if available (exact file + line of failure — checkstyle annotations are especially useful)
- Produce a CI status summary:

```
CI Status: {clean|unstable|blocked|pending}
Failed checks:
  - {check_name}: {conclusion} - {summary}
    Annotations: {file}:{line} - {message}
```

- **If blocked** (compile failure, checkstyle violation, needs rebase): Report the CI failures and recommend the PR author fix them before detailed review. Still produce the routing manifest for informational purposes, but flag that downstream reviews should be deferred.
- **If unstable** (some test failures, e.g., flaky Jacoco threshold): Proceed with review but include CI failures in the manifest so downstream skills are aware.

**1d. Fetch PR comments.**

Fetch both types of PR comments:
```bash
# Inline review comments (code-level)
curl -sS "https://api.github.com/repos/prebid/prebid-server-java/pulls/{N}/comments"
# Conversation comments (discussion, CI bot reports)
curl -sS "https://api.github.com/repos/prebid/prebid-server-java/issues/{N}/comments"
```

- Categorize each comment: `reviewer-feedback`, `ci-bot-report`, `author-response`, `blocking-confirmation-pending`, `other`
- For `blocking-confirmation-pending`: detect reviewer phrases that gate merge on out-of-band confirmation, especially:
  - Phrases include (case-insensitive substring match): "please reply 'received'", "respond to email with 'received'", "I'll merge once you confirm via email", "sent email for verification", "email for verification", "Confirmed" (as a reply to such a comment) — maintainer email verification gate
  - The "Confirmed" word alone is too broad; only treat it as a confirmation reply if it appears AFTER another comment in the thread containing one of the verification phrases above.
  - Mark these as `blocking-confirmation-pending` so downstream `bidder-config-pr-review` knows the maintainer-email check is in a holding state
- For reviewer feedback: extract the file path, line number, and 1-2 sentence summary
- For CI bot reports: extract the bot name and status (pass/fail/info)
- For author responses: note which reviewer comment they address
- Include categorized summaries in the routing manifest

**1e. Search for duplicate PRs.**

For each bidder name extracted from file paths:
```bash
curl -sS "https://api.github.com/search/issues?q={bidder}+repo:prebid/prebid-server-java+type:pr+state:open"
```

- Exclude the current PR from results
- Record any open PRs that touch the same bidder: `DUPLICATE: PR #{N2} also touches {bidder} — {title}`
- If no duplicates found, record: `duplicates: none`

All of 1a through 1e should execute in parallel where possible.

### Step 2: Run Drift Checks Centrally

Fetch the upstream reference files that downstream skills use for drift detection. This step replaces per-skill drift checks.

Fetch all in parallel:

1. **bidder-config schema drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/main/java/org/prebid/server/spring/config/bidder/model/BidderConfigurationProperties.java"`
   - Compare against the local field index at [`../bidder-config-pr-review/references/field-index.md`](../bidder-config-pr-review/references/field-index.md) Part A.2 (the base-class field table — 13 YAML-bindable fields).
   - If the live `BidderConfigurationProperties` base class has fields not in our index, record: `DRIFT: bidder-config field index — new field(s): {field_names}`
   - This drives Rule 35 typed-subclass review — if the base class gained fields, subclasses may inherit them silently and the reviewer needs to know.

2. **pom.xml drift (module version + dependency set)**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/pom.xml"` and `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/extra/pom.xml"`
   - Extract `<artifactId>prebid-server</artifactId>` `<version>` — compare against the orchestrator's tested baseline (the `prebid-server-java/read/skills/shared/framework-utilities-java.md` baseline at `3.x`)
   - If major version changed (e.g., `3.x` → `4.x`), record: `DRIFT: prebid-server-java major version changed (3.x → 4.x)`. The skills' references files MUST be updated atomically before proceeding.
   - For dependency drift: if the PR modifies `pom.xml` or `extra/pom.xml` itself, record: `DEPENDENCY: pom.xml modified. Verify new dependencies are necessary and version-pinned.`

3. **checkstyle.xml drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/checkstyle.xml"`
   - Compare against the canonical ruleset pinned in `prebid-server-java/read/skills/shared/framework-utilities-java.md`.
   - The pr-triage MUST detect when the upstream ruleset adds/removes a rule. Record SPECIFIC drift output (not generic "drift detected"):
     - `DRIFT: checkstyle ruleset — new rule added: {rule_name}` (e.g., a new IllegalImport entry)
     - `DRIFT: checkstyle ruleset — rule removed: {rule_name}`
     - `DRIFT: checkstyle ruleset — rule property changed: {rule_name}.{property} ({old} → {new})` (e.g., LineLength max 120 → 140)
     - `DRIFT: checkstyle ruleset — suppression added/removed: {file_pattern}`
   - Reference: F-new-58/59 family (template emits imports out of canonical 3-group order) — checkstyle ImportOrder rule is the most-common cascade trigger; reviewers need pre-PR visibility.

4. **Spring DI framework drift**: parallel fetch:
   - `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/main/java/org/prebid/server/bidder/BidderCatalog.java"`
   - `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/main/java/org/prebid/server/spring/config/bidder/util/BidderDepsAssembler.java"`
   - Compare against the API-surface snapshot embedded in [`../bidder-config-pr-review/references/field-index.md`](../bidder-config-pr-review/references/field-index.md) Part B.2.3 (`BidderDepsAssembler` fluent chain) and [`../shared/framework-utilities-java.md`](../shared/framework-utilities-java.md) §1 (canonical wiring examples)
   - If `BidderCatalog`'s public API (`bidders()`, `bidderInfoByName(...)`, `nameByAlias(...)`) changed, record: `DRIFT: framework-spring-di — BidderCatalog API surface changed`
   - If `BidderDepsAssembler.<T>forBidder(...)` or the builder methods (`withConfig`, `usersyncerCreator`, `bidderCreator`, `assemble`) changed, record: `DRIFT: framework-spring-di — BidderDepsAssembler API changed`
   - This is the Java analog of Go's `openrtb_ext/bidders.go` drift check. Java has no single BidderName enum (per design-doc §8 Q5); the framework drift check is more diffuse.

5. **test-application.properties drift**: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/test/resources/org/prebid/server/it/test-application.properties"`
   - Identify the canonical line patterns: `adapters.{x}.enabled=true`, `adapters.{x}.endpoint=http://localhost:8090/{x}-exchange`, optional `adapters.{x}.aliases.{alias}.enabled=true` + `.endpoint=...`
   - If this PR adds new adapters, verify the registry pattern is followed exactly. (Mismatched ports — i.e., not 8090 — or missing `.enabled=true` lines are common omissions.)
   - Drift here means: if the upstream FILE schema changes (e.g., a new mandatory property per bidder beyond `enabled` + `endpoint`), record: `DRIFT: test-application.properties — new mandatory property: {property}`

Produce a drift summary:

```
Drift Check Results:
  bidder-config:        {OK | DRIFT: ...}
  pom.xml:              {OK | DRIFT: ...}
  checkstyle.xml:       {OK | DRIFT: {category}: {one-line description}}
  framework-spring-di:  {OK | DRIFT: ...}
  test-application:     {OK | DRIFT: ...}
```

Drift output schema is pinned: `{skill_name}: OK` or `{skill_name}: DRIFT: {category}: {one-line description}`. Downstream skills consume this and should not parse free-form text.

Any drift warnings are included in the routing manifest for the relevant downstream skill.

### Step 3: Categorize Every File by Skill Ownership

For every file in the PR, determine which skill (if any) owns it. The full routing table lives at [references/routing-rules.md](references/routing-rules.md); this SKILL embeds the active subset below, byte-aligned with the reference per the routing-rules.md sync policy.

**Categorization output** — assign each file to exactly one of these buckets:

| Bucket | Description |
|---|---|
| `bidder-class` | Owned by bidder-class-pr-review |
| `bidder-config` | Owned by bidder-config-pr-review |
| `bidder-params-java` | Owned by bidder-params-java-pr-review |
| `shared:test-application-properties` | The IT registry; owned by pr-triage-java (multi-bidder) |
| `unowned:framework` | Framework/infrastructure file not owned by any skill |
| `unowned:docs` | Documentation file |
| `unowned:ci` | CI/CD configuration file (Dockerfile, .github/) |
| `unowned:build` | Build/config file (pom.xml, mvnw, .mvn/) |
| `unowned:other` | Other unowned file |

**Routing table (active subset embedded here):**

| Pattern | Owner |
|---|---|
| `src/main/java/org/prebid/server/bidder/{x}/*.java` | `bidder-class` |
| `src/test/java/org/prebid/server/bidder/{x}/*.java` | `bidder-class` |
| `src/test/java/org/prebid/server/it/{X}Test.java` | `bidder-class` |
| `src/main/resources/bidder-config/{x}.yaml` | `bidder-config` |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` | `bidder-config` |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` | `bidder-config` |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` | `bidder-config` |
| `src/main/resources/static/bidder-params/{x}.json` | `bidder-params-java` |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java` | `bidder-params-java` |
| `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` | `bidder-params-java` |
| `src/test/resources/org/prebid/server/it/test-application.properties` | `shared:test-application-properties` |
| `pom.xml`, `extra/pom.xml` | `unowned:build` |
| `checkstyle.xml` | `unowned:framework` (drift-tracked) |
| `Dockerfile*`, `.github/**`, `mvnw*`, `.mvn/**` | `unowned:ci` |
| `*.md`, `docs/**`, `README*`, `LICENSE`, `NOTICE` | `unowned:docs` |
| `src/main/java/org/prebid/server/bidder/BidderCatalog.java`, `…/spring/config/bidder/util/*.java`, `…/spring/config/bidder/model/*.java` | `unowned:framework` (drift-tracked) |
| `src/main/java/org/prebid/server/auction/**`, `…/server/cache/**`, `…/server/currency/**` | `unowned:framework` |
| Any other `src/**` file not matching above | `unowned:framework` (unknown impact) |

**Bidder-name extraction rules:**

| File Pattern | Bidder Name Source |
|---|---|
| `src/main/resources/bidder-config/{x}.yaml` | filename without `.yaml` (lowercase, may have digits like `152media`) |
| `src/main/resources/static/bidder-params/{x}.json` | filename without `.json` |
| `src/main/java/org/prebid/server/bidder/{x}/...` | first path component after `bidder/` (lowercase) |
| `src/test/java/org/prebid/server/bidder/{x}/...` | first path component after `bidder/` (lowercase) |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/...` | first path component after `request/` (lowercase) |
| `src/test/resources/org/prebid/server/it/openrtb2/{x}/...` | first path component after `openrtb2/` (lowercase) |
| `src/test/java/org/prebid/server/it/{X}Test.java` | TitleCase `X` lowercased — applying the read-bidder-orchestrator's identifier-rule + TitleCase-preservation map (e.g., `AaxTest` → `aax`, `OneFiveTwoMediaTest` → `152media`, `BidTheatreTest` → `bidtheatre`). When the lowercased form does not match an existing `bidder-config/*.yaml`, this is likely a per-alias IT class; check `aliases:` in the parent YAMLs. |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` | the leading TitleCase component (e.g., `AaxConfiguration` → `aax`); strip trailing `BidderConfiguration` form when present (e.g., `AdverxoBidderConfiguration` → `adverxo`) |

**Shared file handling:**

The file `src/test/resources/org/prebid/server/it/test-application.properties` is touched by every new-adapter PR and every new-alias PR. It is **owned by pr-triage-java itself**, NOT by any downstream skill. pr-triage performs its own verification:

- For each `adapters.{x}.enabled=true` line ADDED in the PR's diff: confirm a corresponding `src/main/resources/bidder-config/{x}.yaml` is also being added (new-adapter case) OR a corresponding `aliases.{alias}.*` block is added under an existing parent YAML (new-alias case).
- For each `adapters.{x}.endpoint=...` line ADDED: confirm the URL pattern matches `http://localhost:8090/{x}-exchange` (the WireMock localhost convention; deviations are common omissions).
- For each `adapters.{parent}.aliases.{alias}.enabled=true` line ADDED: confirm a corresponding `aliases: { {alias}: ... }` block is being added in `bidder-config/{parent}.yaml`.
- Mismatches are recorded as `IT-REGISTRY: {description}` cross-skill concerns in Step 5.

**For each file, record:**
- `filename`
- `status` (added/modified/removed/renamed)
- `patch` (diff hunks)
- `owner` (bucket assignment)
- `bidder_name` (extracted from path, if applicable)

Produce a categorization summary:

```
File Categorization:
  bidder-class (N files):
    - src/main/java/org/prebid/server/bidder/foo/FooBidder.java [added]
    - src/test/java/org/prebid/server/bidder/foo/FooBidderTest.java [added]
    - src/test/java/org/prebid/server/it/FooTest.java [added]
  bidder-config (N files):
    - src/main/resources/bidder-config/foo.yaml [added]
    - src/main/java/org/prebid/server/spring/config/bidder/FooConfiguration.java [added]
  bidder-params-java (N files):
    - src/main/resources/static/bidder-params/foo.json [added]
    - src/main/java/org/prebid/server/proto/openrtb/ext/request/foo/ExtImpFoo.java [added]
    - src/test/resources/org/prebid/server/it/openrtb2/foo/test-foo-bid-request.json [added]
    (+ 3 more fixture files for the 4-file Rule 36 set)
  shared:test-application-properties (1 file):
    - src/test/resources/org/prebid/server/it/test-application.properties [modified]
  unowned:build (N files):
    - pom.xml [modified]
```

### Step 4: Detect PR Type

Based on the categorized files, determine the PR type. A PR may have a primary type and secondary types.

**PR Type Detection Rules** (evaluated in order):

1. **Infrastructure / Bulk Change**
   - Trigger: 5+ distinct bidder directories affected in any single skill's files, OR framework files constitute >50% of total changed files, OR total files >50 with >80% matching a single repeated pattern
   - Label: `infrastructure`
   - Sub-label `framework-debt` (additional, on top of `infrastructure`): if `checkstyle.xml`, `BidderCatalog.java`, `BidderDepsAssembler.java`, `BidderConfigurationProperties.java` (the base class), or `src/test/java/org/prebid/server/it/IntegrationTest.java` is modified — this triggers cascading-impact assessment because all bidders inherit from these (Step 5h enforces the same 5-file list)
   - Effect: Downstream skills activate in "bulk mode" — verify pattern consistency across affected bidders, not per-bidder detailed review. Focus detailed review only on net-new code that is NOT part of the bulk pattern.
   - **Multi-adapter alias bundle exception**: A PR may contain N aliases for the SAME parent without triggering bulk mode IF: all changes are `aliases:`-block additions inside one `bidder-config/{parent}.yaml`, the IT classes added are all `{Alias}Test.java` for those aliases, the test-application.properties additions are all `adapters.{parent}.aliases.{alias}.*`, and no `{X}Bidder.java` / `ExtImp{X}.java` / `bidder-params/{x}.json` is touched. In this case PR type is `alias-only` (not `infrastructure`). Canonical Java case: Adverxo with `adport`, `bidsmind`, `mobupps` per-alias IT classes shipped in `bidder-config/adverxo.yaml`'s `aliases:` block.

2. **New Adapter**
   - Trigger: ALL FOUR of the following hold for at least one bidder (strict form — byte-aligned with [references/routing-rules.md](references/routing-rules.md) §"New Adapter"):
     - `src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java` has status `added`, AND
     - `src/main/resources/bidder-config/{x}.yaml` has status `added`, AND
     - `src/main/resources/static/bidder-params/{x}.json` has status `added`, AND
     - `src/test/resources/org/prebid/server/it/test-application.properties` diff contains a new top-level `adapters.{x}.enabled=true` line (not under an existing parent's `aliases:`)
   - Label: `new-adapter`
   - Effect: All 3 reviewer skills activate. Registration completeness is checked (Step 5e).
   - Rationale (per design-doc §8 Q3 — Locked in this PR): the strict form eliminates false-positive new-adapter classifications when partial subsets land (e.g., a `{X}Bidder.java` added without the corresponding params/YAML is more likely an adapter-modification refactor than a new-adapter PR).

3. **Alias-Only**
   - Trigger: ALL of:
     - No `{X}Bidder.java` / `{X}BidderTest.java` is added or modified (only `it/{Alias}Test.java` may be added, which is the per-alias IT class)
     - No `ExtImp{X}.java`, `bidder-params/{x}.json` is added or modified
     - Every `bidder-config/*.yaml` diff hunk is restricted to an `aliases:` subtree (no changes outside `aliases:`)
     - `test-application.properties` additions are all `adapters.{parent}.aliases.{alias}.*` (no new top-level `adapters.{x}.` entries)
   - Label: `alias-only`
   - Effect: `bidder-config-pr-review` activates (for the YAML changes); `bidder-class-pr-review` activates IFF a new `it/{Alias}Test.java` was added (per design-doc §8 Q1 the recommendation is YES). `bidder-params-java-pr-review` does NOT activate. Triage additionally checks cross-skill concern 5a (invalid endpoint macros, IT-registry alignment).

4. **Adapter Modification**
   - Trigger: Files in an existing `bidder/{x}/` directory are modified (not added), OR existing `bidder-config/{x}.yaml` / `{X}Configuration.java` / `bidder-params/{x}.json` / `ExtImp{X}.java` are modified
   - Label: `adapter-modification`
   - Effect: Only the relevant skills activate based on which files changed.

5. **Bidder Removal / Disable**
   - Trigger: Adapter files are removed, OR a `bidder-config/{x}.yaml` diff shows `enabled: false` being added at the top-level adapter key (not under aliases)
   - Label: `bidder-removal`
   - Effect: All skills that have files for this bidder are notified.

5b. **Whitelabel-Redirect-Mid-Review** (sub-label, applies on top of `alias-only`)
   - Trigger: Final state is `alias-only` AND PR comment history contains:
     - reviewer phrase matching "is this (a )?white.?label" or "looks (very )?similar to" or "this looks like a copy of"
     - + author confirmation containing "white label" or "white-label"
     - + commit count > 1 (indicates code was changed mid-review, suggesting redirection)
   - Sub-label: `whitelabel-redirect-mid-review`
   - Effect: pr-triage records `REDIRECT: PR was originally a full adapter, redirected to alias-only after reviewer flagged white-label policy.`
   - This is INFORMATIONAL and does not change activation; it provides context for downstream skills' findings.

6. **Bidder Rename / Refactor**
   - Trigger: Files are deleted from `bidder/{old_x}/` AND added to `bidder/{new_x}/` in the same PR; OR `bidder-config/{old_x}.yaml` deleted with `bidder-config/{new_x}.yaml` added; OR a YAML's top-level adapter key is renamed inside an existing file (rare)
   - Label: `bidder-rename`
   - Effect: All affected files routed to their normal owner skills. pr-triage records `RENAME: {old} → {new}` in the manifest. Reviewer guidance: bidder renames are breaking changes typically deferred to the next major release (mirror Go-side guidance from PR #4456 / #4639).

7. **Framework-Only**
   - Trigger: All changed files are in `unowned:*` categories
   - Label: `framework-only`
   - Effect: No downstream reviewer skills activate. Triage produces a summary of framework changes and recommends human review.

8. **Mixed**
   - Trigger: Multiple categories above apply (e.g., new adapter + framework change)
   - Label: `mixed` with sub-labels
   - Effect: Each sub-component is handled according to its type.

9. **Schema Migration** (sub-label, may apply on top of `infrastructure` or `framework-only`)
   - Trigger: `BidderConfigurationProperties.java` or any sibling base class under `spring/config/bidder/model/` is modified; OR the structure of `bidder-config/*.yaml` changes across many bidders (e.g., a new mandatory `meta-info` field)
   - Sub-label: `schema-migration`
   - Effect: All bidders inherit the change; reviewer guidance is to confirm migration coverage across all touched bidders.

Produce a PR type summary:

```
PR Type: {type} [secondary: {type2}, ...]
Bidders affected: {bidder1}, {bidder2}, ...
New bidders: {list or none}
New aliases: {alias → parent list or none}
Removed bidders: {list or none}
```

### Step 5: Detect Cross-Skill Concerns

Check for issues that fall between the cracks of individual skills. These are concerns that no single downstream skill would catch because they span skill boundaries.

**5a. Invalid Endpoint Macros in Alias PRs**

If the PR type is `alias-only`:
- For each new alias entry in the `aliases:` block, extract the `endpoint:` value
- If the endpoint contains template macros (e.g., `{{adUnitId}}`, `{{auth}}`, `{{PREBID_SERVER_ENDPOINT}}`), cross-reference against the parent's `endpoint:` value AND the canonical Java macro list (the parent typically uses a subset; aliases CAN extend the macro set but each macro must be one the framework resolves at runtime)
- Canonical Java macros: `{{PREBID_SERVER_ENDPOINT}}` (resolved from `external-url`), per-bidder template tokens declared in `{X}Configuration.java::resolveEndpoint(...)`. Aliases inherit the parent's `resolveEndpoint`, so an alias declaring a `{{TOKEN}}` not handled by the parent's resolver will silently leave the macro literal in the URL at runtime.
- Record as: `CROSS-SKILL: Invalid endpoint macro "{{XYZ}}" in alias {alias} of parent {parent} — parent's resolveEndpoint does not substitute this token. Will leave macro literal in URL at runtime.`

**5b. Framework File Impact Assessment**

If any files are in the `unowned:framework` bucket:
- `BidderCatalog.java` — changes affect bidder lookup for all adapters
- `BidderDepsAssembler.java` — changes affect the wiring pattern every `{X}Configuration.java` uses
- `BidderConfigurationProperties.java` (the base class) — changes affect every adapter's `@Bean` declaration; subclasses inherit silently. **TRIGGERS DRIFT** in bidder-config field index.
- `JacksonMapper.java` — changes affect JSON serialization in every adapter
- `IntegrationTest.java` (the IT base class) — changes affect every IT test class
- `WireMock` stub configuration files — changes affect every IT test fixture
- For known-impact files, record: `FRAMEWORK IMPACT: {file} changed — affects {scope}. Recommend human review.`
- For unknown framework files, record: `FRAMEWORK: {file} changed — unknown impact scope. Recommend human review.`

**5c. Alias + Parent Consistency**

If a PR modifies both a parent bidder's files AND alias entries inside the same YAML:
- Verify the changes are consistent (e.g., if parent endpoint template-tokens change, do alias endpoints need updating?)
- Verify per-alias IT classes still extend the correct base IT class and reference fixture directories that exist
- Record as: `CROSS-SKILL: Parent bidder {parent} and alias {alias} both modified — verify consistency.`

**5d. Registration Without Implementation (and vice versa)**

If `{X}Configuration.java` is added but no `{X}Bidder.java`:
- Record: `CROSS-SKILL: Spring configuration for {x} added but no adapter implementation. Verify this is a split PR or alias registration.`

If `{X}Bidder.java` is added but no `{X}Configuration.java`:
- Record: `CROSS-SKILL: Adapter implementation for {x} added but no Spring configuration. The bidder will not be wired into the framework. Incomplete new-adapter PR.`

If `test-application.properties` has `adapters.{x}.enabled=true` added but no `bidder-config/{x}.yaml` and no entry under an existing parent's `aliases:`:
- Record: `CROSS-SKILL: IT registry references {x} but neither bidder-config/{x}.yaml nor parent.aliases.{x} exists. The IT test framework will fail to load.`

**5e. New Adapter Completeness Check**

If PR type is `new-adapter`, verify the complete expected file set is present for each new bidder. A complete new-adapter PR includes **12 files** (13 when Rule 35 applies as a SEPARATE-file typed subclass):

1. `src/main/resources/bidder-config/{x}.yaml` — unified config
2. `src/main/resources/static/bidder-params/{x}.json` — parameter JSON schema
3. `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/ExtImp{X}.java` — imp-ext POJO
4. `src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java` — adapter implementation
5. `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` (or `{X}BidderConfiguration.java`) — Spring DI factory
6. `src/test/java/org/prebid/server/bidder/{x}/{X}BidderTest.java` — unit tests
7. `src/test/java/org/prebid/server/it/{X}Test.java` — IT test class
8. `src/test/resources/org/prebid/server/it/openrtb2/{x}/test-auction-{x}-request.json` — IT fixture (inbound publisher auction request; one scenario; full Rule 36 4-file set)
9. `src/test/resources/org/prebid/server/it/openrtb2/{x}/test-auction-{x}-response.json` — IT fixture (expected outbound PBS auction response)
10. `src/test/resources/org/prebid/server/it/openrtb2/{x}/test-{x}-bid-request.json` — IT fixture (outbound bid request sent to bidder)
11. `src/test/resources/org/prebid/server/it/openrtb2/{x}/test-{x}-bid-response.json` — IT fixture (mock bidder response)
12. `src/test/resources/org/prebid/server/it/test-application.properties` — appended `adapters.{x}.enabled=true` + `adapters.{x}.endpoint=...` lines

When Rule 35 applies AND the typed-config subclass is shipped as a separate file (the design-permitted form; in current upstream practice all Rule 35 subclasses are inner `private static class` declarations inside `{X}Configuration.java`), file 13 is required:
- `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java`

For each missing file, record: `COMPLETENESS: New adapter {x} missing {file_type}. Incomplete PR.`

This check catches split PRs or forgotten files that no individual downstream skill would detect since each skill only sees its own files.

**5f. Dependency Changes**

If `pom.xml` or `extra/pom.xml` is modified:
- Record: `DEPENDENCY: pom.xml modified. Verify new dependencies are necessary, version-pinned, and not introducing security or licensing concerns.`
- Note common drift: a new bidder pulling in a non-standard JSON library is an anti-pattern (must use `JacksonMapper`); a new bidder pulling in an HTTP client is an anti-pattern (must use the framework's Vert.x layer).

**5g. Whitelabel-Only Resemblance Heuristic**

Trigger: ANY of:
- PR is type `new-adapter` AND the new `{X}Bidder.java` is significantly smaller than typical (e.g., < 80 lines) AND closely resembles an existing adapter's structure
- PR is type `new-adapter` AND the PR description / commit messages / discussion contains "white label" / "white-label" / "whitelabel"
- PR is type `new-adapter` AND the new `bidder-config/{x}.yaml`'s `endpoint:` matches an existing adapter's endpoint domain
- PR is type `alias-only` AND the secondary sub-label `whitelabel-redirect-mid-review` was set per Step 4 rule 5b

Action:
- Record: `CROSS-SKILL: New adapter {x} may be a white-label scenario. Reviewer may redirect to alias-only (aliases:) form inside an existing parent's YAML. The bidder-config-pr-review white-label policy workflow evaluates further.`
- Severity: **WARN** (heuristic, not deterministic — final decision is reviewer judgment)

**5h. Checkstyle / Framework Test-Harness Impact**

Trigger: ANY change in `checkstyle.xml`, the IT base classes under `src/test/java/org/prebid/server/it/`, or `BidderDepsAssembler.java`.

Action:
- Record: `FRAMEWORK IMPACT: {file} modified. Expect cascading impact on existing bidder files across many other adapters.`
- Cross-reference the drift output from Step 2 — if drift was already detected, the message becomes: `FRAMEWORK IMPACT: {file} modified — {specific drift name from Step 2}`
- ALSO search open PRs that touch files matching `src/main/java/org/prebid/server/bidder/*/...` or `src/test/java/org/prebid/server/bidder/*/...` and were last updated BEFORE this PR's `head_sha` was pushed. Record any matches as: `CONCURRENT-PR RISK: PR #{N} touches {bidder} files and predates this framework change — likely broken by the cascade. Recommend the PR author rebase.`

**5i. IT-Registry Misalignment**

Trigger: Per the shared-file handling in Step 3, `test-application.properties` diff has lines that don't match a corresponding `bidder-config/*.yaml` change.

Action:
- Record: `IT-REGISTRY: {description}` for each mismatch detected. Examples:
  - `IT-REGISTRY: adapters.foo.enabled=true added but bidder-config/foo.yaml not in PR. IT framework will fail to load.`
  - `IT-REGISTRY: adapters.foo.endpoint port is :8091 (expected localhost:8090/foo-exchange). Possible typo.`
  - `IT-REGISTRY: bidder-config/parent.yaml adds aliases.child but test-application.properties has no adapters.parent.aliases.child entry. IT framework will run without alias visibility.`

**5j. Approval-to-Merge Stall Detection**

Trigger: Reviewer feedback in Step 1d includes approving reviews older than 30 days from current date AND PR is still open.

Action:
- Record: `STALL: PR has approving review(s) older than {N} days but is not merged. Likely waiting on docs PR or queue attention.`
- Severity: **INFO** (process not code)

**5k. Lombok / Checkstyle Pre-Flag**

Trigger: Any PR adds a Java file (status=added) under `bidder/{x}/`, `spring/config/bidder/`, or `proto/openrtb/ext/request/{x}/`.

Action: Without simulating checkstyle, pre-flag these common patterns from the diff:
- Import group ordering violation (the F-new-58/59 trap): if added imports are not in the canonical 3-group order (`*` then blank then `java|jakarta`), record: `PRE-CHECKSTYLE: {file} import ordering may violate checkstyle ImportOrder rule. CI will likely fail.`
- Banned Vert.x JSON import: if `io.vertx.core.json.Json` appears in the added imports, record: `PRE-CHECKSTYLE: {file} imports io.vertx.core.json.Json which is banned by checkstyle BanVertxJsonImport. Use JacksonMapper instead.`
- LineLength > 120: any added line exceeding 120 chars (ignoring URLs and package/import lines): record: `PRE-CHECKSTYLE: {file}:{line} exceeds 120 chars. CI will likely fail.`
- OuterTypeFilename mismatch: extract the `public class Xxx` declaration from each added `*.java` file and verify it matches the filename root. Mismatches: `PRE-CHECKSTYLE: {file} declares public class {ClassName} which does not match filename root. checkstyle OuterTypeFilename will fail.`
- Test methods with snake_case names (F-new-60): in added `*Test.java` files, flag `@Test` methods with `_` in the name: `PRE-CHECKSTYLE: {file} has test method {method} with snake_case name. Java convention is camelCase.`

These pre-checks reduce reviewer round-trips by surfacing issues a human would only catch after CI runs.

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
=== PR TRIAGE MANIFEST (Java) ===
PR: prebid/prebid-server-java#{number}
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
bidder-config:        {OK | DRIFT: details}
pom.xml:              {OK | DRIFT: details}
checkstyle.xml:       {OK | DRIFT: details}
framework-spring-di:  {OK | DRIFT: details}
test-application:     {OK | DRIFT: details}

--- PR TYPE ---
Primary: {type}                          # new-adapter | alias-only | adapter-modification | bidder-removal | bidder-rename | infrastructure | framework-only | mixed
Secondary: {types or none}               # e.g., framework-debt, schema-migration, whitelabel-redirect-mid-review
Bidders affected: {list}
New bidders: {list or none}
New aliases: {alias → parent or none}
Renamed bidders: {old → new list or none}

--- FILE ROUTING ---
bidder-class-pr-review ({N} files):
  {filename} [{status}] (bidder: {name})
  ...

bidder-config-pr-review ({N} files):
  {filename} [{status}] (bidder: {name})
  ...

bidder-params-java-pr-review ({N} files):
  {filename} [{status}] (bidder: {name})
  ...

Shared files ({N}, owned by pr-triage-java):
  src/test/resources/org/prebid/server/it/test-application.properties [{status}]
    {per-bidder diff summary}

Unowned files ({N} files):
  {filename} [{status}] — {subcategory}: {impact note}
  ...

--- CROSS-SKILL CONCERNS ---
{concerns or "None detected"}

--- BULK CHANGE ---
{Only present when PR type includes `infrastructure` or `framework-debt`.}
Bulk pattern: {description of the repetitive change}
Outliers ({N}):
  - {filename}: {why it deviates}
Recommended mode for downstream skills: bulk-pattern-consistency-check
{Or: "Not a bulk change — section omitted"}

--- PRIOR AGENT FINDINGS ---
{Only present when `agent_review: yes` was recorded in Step 1b sub-bullet 5.}
{For each prior-agent comment extracted:}
- {file}:{line | "PR-level"}: {finding text} [{severity if stated}]
{Or: "agent_review: no — section omitted"}

--- BIDDER METADATA ---
{For each bidder in the PR:}
{bidder}:
  parent: {parent | none}                          # Java's aliases are inverted; for an alias, this is the parent's name
  aliases: {[alias1, alias2, ...] | none}          # for a parent, the list of aliases declared
  whitelabelOnly: {true | false | absent}          # if the YAML declares this at the adapter top-level
  capabilities:
    app-media-types: [banner, video, native]       # extracted from meta-info if in PR; else "not in PR — downstream must fetch from master"
    site-media-types: [banner, video, native]
  endpoint: {URL with macros, if in PR}
  rule_35_typed_config: {yes | no}                 # whether {X}BidderConfigurationProperties.java exists / is being added

--- PR-LEVEL CHECKS ---
Duplicate PRs:
  - {PR #{N2}: {title} — touches {bidder}} (or "none")
Completeness (new adapters only):
  - {missing file warnings or "all expected files present"}

--- PRIOR SPEC COMPARISON ---
{Only present when prior_spec resolves per the discovery order in §"Prior-Spec Comparison" below.}
prior_spec: {path}
prior_spec.resolved_commit: {sha}
prior_spec.adapter_spec_version: {version}
Regressions detected ({N}):
  - PRIOR-SPEC: {flag text} (file:{path}:{line if applicable})
  ...
{Or: "No regressions detected" if N=0}
{Or: "prior_spec not present — section omitted"}

--- PRIOR SOURCE SPEC COMPARISON ---
{Only present when prior_source_spec resolves per the discovery order in §"Cross-language ports: prior_source_spec" below.}
prior_source_spec: {path}
prior_source_spec.source_language: go
prior_source_spec.resolved_commit: {sha}
prior_source_spec.adapter_spec_version: {version}
Port-fidelity findings ({N}):
  - PRIOR-SOURCE-SPEC: {flag text} (file:{path}:{line if applicable}) [severity: info | warn | fail]
  ...
{Or: "No port-fidelity findings" if N=0}
{Or: "prior_source_spec not present — section omitted"}

--- SKILL ACTIVATION ---
Activate bidder-class-pr-review: {yes/no} ({N} files, {reason})
Activate bidder-config-pr-review: {yes/no} ({N} files, {reason})
Activate bidder-params-java-pr-review: {yes/no} ({N} files, {reason})

{If infrastructure/bulk:}
NOTE: Infrastructure/bulk change detected. Downstream skills should use
bulk review mode (pattern consistency check, not per-bidder detailed review).

{If blocked CI:}
NOTE: CI is blocked. Downstream reviews are deferred. Reporting CI failures only.

=== END MANIFEST ===
```

**Skill activation rules:**
- A skill activates if it has 1 or more files routed to it
- Exception: when PR type is `alias-only` AND only `bidder-config/*.yaml` + `test-application.properties` + a new `it/{Alias}Test.java` are touched, `bidder-class-pr-review` activates ONLY because of the IT class. The activation reason MUST cite the IT class file (per design-doc §8 Q1).
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
- Pre-checkstyle pre-flags (if any)
- Unowned files requiring human attention (if any)
- Overall recommendation: proceed to review | defer until CI passes | recommend human review for framework changes

---

## Optional: Prior-Spec Comparison (read/ integration)

If a prior Adapter Specification exists at `prebid-server-java/read/specs/{bidder}/latest.yaml` (typically because the user has previously read the adapter via `read-bidder-orchestrator --persist`), pr-triage-java can load it as `prior_spec` and detect behavioral regressions on the PR diff. Reviewer skills receive the loaded spec via the routing manifest's `--- PRIOR SPEC COMPARISON ---` block and flag deviations.

This is OPT-IN: pr-triage-java continues to work without `prior_spec`. The hook is automatic when the file is present.

**Detection workflow** (runs after Step 4 PR-type detection, before Step 5 cross-skill concerns):

1. For each bidder identified in `Bidders affected:` (Step 4), check whether `prebid-server-java/read/specs/{bidder}/latest.yaml` exists locally. The `read/specs/` directory is `.gitignore`'d by default; users opt into checking specs in for diff-comparison workflows.
2. If present, load the YAML; record `prior_spec.provenance.source.resolved_commit` and `prior_spec.adapter_spec_version`.
3. For each non-removed file in the PR routed to a downstream skill, run targeted regression checks against `prior_spec`. Java-specific examples:
   - PR adds custom `UnmarshalJSON`-equivalent (Jackson `@JsonDeserialize(using = ...)` annotation) to `ExtImp{X}.java` → if `prior_spec.params.ext_struct.custom_unmarshal: false`, flag: `PRIOR-SPEC: Custom Jackson deserializer added. Verify ext.accepts_shapes captures the new flexibility (see ext_pojo_construction.custom_unmarshal taxonomy).`
   - PR adds `aliases: { newAlias: ~ }` to `bidder-config/{parent}.yaml` → if `prior_spec.meta.parent_aliases` does not contain `newAlias`, flag: `PRIOR-SPEC: New alias detected. Go port (if any) needs static/bidder-info/newAlias.yaml entry with aliasOf: {parent} (port-translation Rule 33 inversion).`
   - PR removes a quirk's source line (e.g., a hardcoded `private static final String DEV_ENDPOINT = ...` referenced by `prior_spec.quirks[id=hardcoded-dev-endpoint]`) → flag: `PRIOR-SPEC: Quirk hardcoded-dev-endpoint at {file}:{line} is no longer load-bearing — orchestrator should remove from spec on next read.`
   - PR changes a bidder's `{X}Bidder.java` constructor to add a `CurrencyConversionService` arg → if `prior_spec.code.builder.currency_used: false`, flag: `PRIOR-SPEC: CurrencyConversionService now injected. currency_conversion.used should change to true on next read.`
   - PR adds Rule 35 typed-config subclass (`{X}BidderConfigurationProperties.java` is new) → if `prior_spec.spring_config.has_typed_subclass: false`, flag: `PRIOR-SPEC: Rule 35 typed-config subclass added. spring_config.has_typed_subclass should change to true on next read.`
4. Append all `PRIOR-SPEC:` flags to the routing manifest under a new `--- PRIOR SPEC COMPARISON ---` block (between `--- BIDDER METADATA ---` and `--- PRIOR SOURCE SPEC COMPARISON ---`).
5. If `read/specs/{bidder}/latest.yaml` is missing, omit the block silently. Do NOT recompute the spec — that's the user's opt-in via `read-bidder-orchestrator --persist`. Do NOT block the review on absence.

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

For more on the read/ → review/ composition contract, the spec lifecycle, and worked detection examples, see [`../../../../prebid-server-go/read/skills/shared/cross-skill-integration.md`](../../../../prebid-server-go/read/skills/shared/cross-skill-integration.md) §5 (Read ↔ Review opt-in hook). The Java-side cross-skill-integration doc is not yet shipped; the Go-side doc covers the cross-language contract symmetrically and applies to both trees.

### Cross-language ports: `prior_source_spec`

For PRs that PORT an adapter from one language to the other (the canonical case being the Teal flow: read the Go adapter spec → port to Java → review the Java PR → reflect findings back to SKILLs), the SOURCE-language spec is a more useful comparison baseline than the same-language prior spec. pr-triage-java exposes a second slot, `prior_source_spec`, alongside `prior_spec`:

| Slot | Purpose | Path (when persisted) |
|---|---|---|
| `prior_spec` | Same-language regression detection (Java PR ↔ Java prior-spec) | `prebid-server-java/read/specs/{bidder}/latest.yaml` (gitignored; user-persisted via `read-bidder-orchestrator --persist`) |
| `prior_source_spec` | Cross-language port-fidelity detection (Java PR ↔ Go SOURCE spec) | `prebid-server-go/read/specs/{bidder}/latest.yaml` (mirror image of the Go-side contract) |

When `prior_source_spec` is present, pr-triage-java emits a complementary `--- PRIOR SOURCE SPEC COMPARISON ---` manifest block. Findings flagged here are port-fidelity divergences, NOT same-language regressions. Severity policy (symmetric with Go-side `pr-triage` per the cross-language hook contract):

- `info` by default — port asymmetries are often legitimate per Rules 5 / 9 / 11 / 35 / 38 / etc. (e.g., Go's `text/template` vs Java's `String.replace` for endpoint construction).
- `warn` when the divergence touches a Rule 38 byte-fidelity assertion (bidder-params JSON formatting), an R5-strict cross-language equivalence (capabilities, gvl_vendor_id, maintainer), or a known-master-sample pattern.
- `fail` when a dual-spec assertion under `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` declares the divergence as `severity: fail` (the canonical example is aax: Java omits `minLength: 1` on `cid` / `crid` — the dual-spec marks this `severity: fail`, so the Java PR review would flag it `fail` even though the canonical Java bidder-params.json is "correct" from Java's standpoint).

**Downstream consumption LANDED in this PR** (audit item 25 resolved): pr-triage-java AUTHORS the `--- PRIOR SOURCE SPEC COMPARISON ---` block AND the three reviewer skills CONSUME it via their own Step 1g (each downstream `SKILL.md` reads the block, deduplicates its own findings against it, and surfaces port-fidelity findings at `info` / `warn` / `fail` severity). The Go-side symmetric downstream consumption is still pending as of audit time (`docs/runs/post-d3.8-remaining-work.md:36`); Java has landed it first.

### One-shot specs (Teal flow): `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml`

When pr-triage-java runs as part of a single end-to-end orchestration (the "Teal flow": read Go adapter → port to Java → review Java PR → reflect findings back to SKILL updates), specs are NOT user-persisted to the gitignored `read/specs/{bidder}/latest.yaml` location. Instead, the orchestrator writes them to a transient run-scoped path:

```
.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml
```

Where:
- `{run-id}` is an ISO-like timestamp + short hash (e.g., `2026-05-03T1430Z-a3f9`) generated by the orchestrator at run start.
- `{lang}` is `go` or `java`.
- `{bidder}` is the canonical bidder name.

pr-triage-java discovers specs in this resolution order (first match wins):

1. `--prior-spec={path}` / `--prior-source-spec={path}` CLI overrides (explicit).
2. `${PRIOR_SPEC_PATH}` / `${PRIOR_SOURCE_SPEC_PATH}` environment variables.
3. `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` when `${FULL_LOOP_RUN_ID}` is set in the environment (Teal-flow orchestrator hand-off; `lang=java` for `prior_spec`, `lang=go` for `prior_source_spec`).
4. `prebid-server-{lang}/read/specs/{bidder}/latest.yaml` (the persisted user-opt-in location).

If none resolve, both blocks are silently omitted (the comparison is opt-in; pr-triage-java continues without). The `.tmp/full-loop/` location is added to `.gitignore` so transient run artifacts never reach origin.

---

## Cross-Skill References (Read-Only)

This skill reads files from downstream skills for drift comparison and context:

- [`../bidder-config-pr-review/references/field-index.md`](../bidder-config-pr-review/references/field-index.md) — Part A.2 (base-class field index) drives the `bidder-config` drift check; Part B.2.3 (`BidderDepsAssembler` chain) drives the `framework-spring-di` drift check.
- [`../bidder-params-java-pr-review/references/params-type-index.md`](../bidder-params-java-pr-review/references/params-type-index.md) — JSON-schema draft-04 surface + `BidderParamValidator` runtime mechanism context.
- [`../bidder-class-pr-review/references/bidder-class-index.md`](../bidder-class-pr-review/references/bidder-class-index.md) — adapter implementation patterns + IT-test conventions.
- [`../shared/framework-utilities-java.md`](../shared/framework-utilities-java.md) — review-side Java framework utilities (Lombok semantics, Spring DI conventions, JacksonMapper rules, checkstyle ruleset, Vert.x ban-list, F-new trap catalog, JUnit5 + AssertJ conventions).
- [`../../../read/skills/shared/framework-utilities-java.md`](../../../read/skills/shared/framework-utilities-java.md) — read-side companion. Endpoint-template-macro lists, error-type taxonomy, anti-patterns.
- [`../../../../prebid-server-go/read/skills/shared/cross-skill-integration.md`](../../../../prebid-server-go/read/skills/shared/cross-skill-integration.md) — Go-tree-side doc covers the cross-language read ↔ review opt-in hook; loaded only when the user has the read/ skill suite installed and `read/specs/{bidder}/latest.yaml` exists locally.

---

## Reference Documentation

The full routing table, framework-impact file list, PR-type detection heuristics, and bidder-name extraction rules live at [references/routing-rules.md](references/routing-rules.md) (LANDED in this PR, step 3, commit `c618fde`). The active subset embedded above (Step 3 routing table) is kept byte-aligned with the reference per the sync policy in routing-rules.md.

---

## Shared Framework Reference

For framework-wide concerns (Lombok annotation conventions, Spring DI patterns, JacksonMapper conventions, checkstyle ruleset, Jacoco coverage gates, Vert.x ban-list, JUnit5 + AssertJ conventions, naming conventions, alias inversion semantics, IT test harness contract), the four review skills share [`../shared/framework-utilities-java.md`](../shared/framework-utilities-java.md) (review-side, LANDED in this PR, step 2, commit `63be93d`), which adds reviewer-specific anti-patterns + verbatim policy quotes on top of the read-side companion at [`../../../read/skills/shared/framework-utilities-java.md`](../../../read/skills/shared/framework-utilities-java.md). Design rationale lives at [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md).

---

## One-Alias-Per-PR Rule

The Go side documents a "one alias per PR for clean changelog" reviewer preference (PR #4214 / #4215). Java's analog is less clearly established because Java's aliases live INSIDE the parent YAML — bundling N aliases for the same parent is a single-file change, low cognitive cost. Reviewers' Java-side preference is more permissive:

- **OK**: N aliases bundled for the SAME parent in one PR (canonical case: Adverxo's `adport` + `bidsmind` + `mobupps` per-alias IT classes shipped together; PR added `aliases: { adport: ..., bidsmind: ..., mobupps: ... }` block plus three IT classes).
- **WARN**: N aliases for DIFFERENT parents in one PR — the cross-cutting blast radius is higher; reviewers may request split per the Go-side `pm-isha-bharti` convention.
- **NOT-OK**: bundling aliases with adapter-modification work for the parent — the diff readability suffers; reviewers will request split.

When the WARN condition is detected, pr-triage-java records:
- `BULK-PR: {N} alias entries bundled across {N_parents} different parents — reviewer may request split for changelog clarity.`
- Severity: **WARN** (process recommendation)
