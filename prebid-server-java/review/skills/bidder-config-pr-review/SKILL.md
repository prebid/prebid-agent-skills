---
name: bidder-config-pr-review
description: Reviews changes to Java bidder Spring config files — bidder-config YAML (src/main/resources/bidder-config/{x}.yaml), Spring `@Configuration` class (src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java OR {X}BidderConfiguration.java), and the Rule 35 typed-config subclass when present (BidderConfigurationProperties.java). USE WHEN a PR touches any of these files. Do NOT use for bidder/{x}/{X}Bidder.java, bidder-params/{x}.json, or ExtImp{X}.java — those are owned by sibling skills.
version: 1.0.0
---

# bidder-config-pr-review (Java)

Review pull requests that touch the three Spring DI files that wire a Java bidder into the framework:

1. `src/main/resources/bidder-config/{x}.yaml` — the **unified** Spring property-source YAML (bidder-info + endpoint + aliases + usersync, under an `adapters.{x}` wrapper). This is the Java analog of Go's `static/bidder-info/{x}.yaml` BUT richer: it carries Spring property keys for the adapter endpoint URL, usersync, and operator-supplied extras.
2. `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` (or the `{X}BidderConfiguration.java` variant) — the Spring `@Configuration` factory that emits the `BidderDeps` bean via `BidderDepsAssembler`. **No Go analog exists**: Go's `exchange/adapter_builders.go` is a single map keyed by BidderName; Java has one factory class per bidder.
3. `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` — the **Rule 35** typed-config subclass when present. In current upstream practice this is almost always an **inner `private static class`** inside the `{X}Configuration.java` file (canonical: Kobler, Rubicon, Appnexus, Adnuntius). Either form (separate file OR inner class) is acceptable; both are reviewed by this skill.

For every changed field/line, apply the matching verification workflow to produce actionable review findings.

## Core Principle: Review Only What Changed

**You are a PR reviewer, not a full-file auditor.** The PR diff is your single source of truth. Only create verification tasks for fields/lines that actually changed in the diff. Lines that already exist unchanged in the file were approved in a prior PR and are out of scope.

- **NEVER** review unchanged fields just because they exist in a file
- **NEVER** verify `maintainer-email`, `endpoint`, `vendor-id`, `aliases`, etc. unless the diff shows them as added or modified
- **NEVER** independently re-validate the @Configuration scaffolding (the `@Bean` quartet, `@PropertySource`, `BidderDepsAssembler.forBidder(...)` line) when those lines are unchanged
- **DO** verify every YAML field line and every Java line that appears as added (`+`) or modified in the diff
- The number of verification tasks should correspond 1:1 with changed fields/lines, not with total content in the file

## Activation

This skill activates when `pr-triage-java`'s routing manifest routes ≥1 file in any of the following patterns to `bidder-config-pr-review`:

| Pattern | Notes |
|---|---|
| `src/main/resources/bidder-config/{x}.yaml` | The unified config (bidder-info + endpoint + aliases + usersync) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` | Spring `@Configuration` factory (default convention; canonical: `AaxConfiguration.java`, `KoblerConfiguration.java`, `RubiconConfiguration.java`) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` | Same role; alternate naming form (canonical: `AdverxoBidderConfiguration.java`, `AdnuntiusBidderConfiguration.java`, `DianomiBidderConfiguration.java`) |
| `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` | Rule 35 typed-config subclass when present as a **separate file** (rare; most subclasses are inner classes) |

It does NOT activate on its own — `pr-triage-java` runs first and routes files here.

### Filename convention guidance

Upstream uses BOTH `{X}Configuration.java` AND `{X}BidderConfiguration.java` naming forms. The choice is historical, not driven by structural meaning. Reviewers should:

- **NOT** reject a PR over the choice of filename form — both are upstream-accepted
- Flag for reviewer attention as **INFO** only when the form differs from sibling adapters of similar age (e.g., new adapter in 2026 using `{X}BidderConfiguration.java` while the surrounding cohort uses `{X}Configuration.java` — likely cargo-culted from an older template)
- **DO** flag as **FAIL** when the internal `public class` name does not match the filename root (checkstyle `OuterTypeFilename` will fail; this is the F-new-79 trap — port-go2java has emitted this wrong in canaries)

Both filename forms map to the same skill; the typed-config subclass (Rule 35) is most often an inner `private static class` inside the Configuration file rather than a separate file. If the PR ships it as a separate file, route + review it here; the Activation table above accepts either form.

## Review Workflow

**Data Fetching: Use `curl` (via Bash tool) for ALL external data retrieval.**
Do NOT use `WebFetch` — it processes content through a summarization model,
which can paraphrase source code and lose raw YAML/Java structure. `curl` returns
exact, deterministic content. Parse the raw output directly.

### Step 1: Receive Triage Data

This skill receives pre-fetched PR data from the **pr-triage-java** skill. Do NOT re-fetch PR files or run drift checks.

**1a. Accept the routing manifest.**

The pr-triage-java skill provides:
- The complete file list filtered to files owned by this skill
- Each file's `filename`, `status` (added/modified/removed/renamed), and `patch` (diff hunks)
- Drift check results for `bidder-config` (BidderConfigurationProperties base class) and `framework-spring-di` (BidderCatalog, BidderDepsAssembler)
- CI status summary (with checkstyle annotations if a checkstyle check failed)
- PR type classification (`new-adapter`, `alias-only`, `adapter-modification`, `bidder-removal`, `bidder-rename`, `infrastructure`, `mixed`)
- Any cross-skill concerns relevant to bidder-config (notably 5a invalid-endpoint-macros-in-alias, 5c alias+parent consistency, 5d registration-without-implementation, 5g whitelabel-resemblance, 5i IT-registry misalignment, 5k pre-checkstyle pre-flags)
- PR description analysis (docs PR link, template completeness, feature rationale)
- Commit history + reviewer feedback + duplicate-PR search results
- Bidder metadata (parent, aliases, whitelabelOnly, capabilities, endpoint, rule_35_typed_config)

**1b. Handle drift warnings.**

If the triage manifest reports drift for `bidder-config` (e.g., `DRIFT: bidder-config field index — new field(s): {field_names}`) or `framework-spring-di` (e.g., `DRIFT: framework-spring-di — BidderDepsAssembler API changed`), include the drift warning in the review output. Do NOT re-fetch the upstream files.

When the BidderConfigurationProperties base class gained fields, every typed-config subclass inherits them silently — flag any Rule 35 subclass in the current PR for fresh review against the new base.

**1c. Handle CI status.**

If CI status is `blocked` (typically: checkstyle failure, compile failure), acknowledge in the summary and note that review findings are preliminary until CI passes. Specifically for this skill:

- A checkstyle `ImportOrder` violation in a `{X}Configuration.java` or `{X}BidderConfigurationProperties.java` is **the F-new-58/59 trap** — the template emits imports out of canonical 3-group order. The CI annotation tells you the exact file:line; flag as **FAIL** with a note that this is template-fixed in current SKILLs.
- A checkstyle `OuterTypeFilename` violation is the F-new-79 trap — class name does not match filename. Flag as **FAIL**.
- A checkstyle `LineLength` violation (> 120 chars) is common in `bidderCreator` lambdas with many constructor args. Flag as **FAIL**; the reviewer's typical fix is to indent the constructor args across multiple lines.

**1d. Incorporate reviewer feedback.**

Cross-reference PR comments from the triage manifest against your findings:
- If a reviewer has already flagged an issue you also find, note: `Previously flagged by {reviewer}` and reference their comment
- If `blocking-confirmation-pending` was recorded (maintainer-email "received" gate), note this in the maintainer-email finding — it does not block this skill's review, but the merge is gated
- If the manifest's `--- PRIOR AGENT FINDINGS ---` block is present (PR has `agent review` label), suppress exact duplicates and emit only net-new findings (mark matches as `Previously flagged by prior agent`)

**1e. Fetch full file content when needed.**

For files with status `modified`, the patch contains only changed regions with surrounding context lines. When verification requires full file context:

```bash
# Fetch full file from PR branch (for modified files needing full context)
curl -sS "https://raw.githubusercontent.com/{owner}/{repo}/{head_sha}/{filename}"

# Fetch parent YAML from master (for alias-against-parent validation when parent is not in PR)
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/main/resources/bidder-config/{parent}.yaml"

# Fetch the bidder's class to verify constructor-arg signature alignment (F-new-57)
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/master/src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java"
```

- For `added` files: full content is already in the patch (all `+` lines) — do NOT re-fetch
- For `modified` files: only fetch if verification requires context beyond the diff hunks (e.g., when verifying that an unchanged `@Bean` quartet still aligns with a changed `bidderCreator` lambda; or when verifying the Configuration file's internal `public class` name matches the filename — checkstyle OuterTypeFilename can fire only when you see the whole file header)
- For Java files specifically, full-file context is frequently needed because `OuterTypeFilename` review and import-order review both require seeing the top of the file
- Cache fetched content — do not re-fetch the same file multiple times

**1f. Consume cross-skill concerns surfaced by pr-triage-java.**

The triage manifest's `--- CROSS-SKILL CONCERNS ---` block may carry items that originate elsewhere but require this skill's analysis to land the verdict. Items that need this skill's attention:

| Concern code | Triage description | This skill's action |
|---|---|---|
| 5a (invalid endpoint macro in alias) | `CROSS-SKILL: Invalid endpoint macro "{{XYZ}}" in alias {alias} of parent {parent}` | Run §"Aliases:" workflow + verify against parent's `resolveEndpoint` |
| 5c (parent + alias both modified) | `CROSS-SKILL: Parent bidder {parent} and alias {alias} both modified` | Run §"Aliases:" workflow with consistency-check sub-step |
| 5d (registration without implementation) | `CROSS-SKILL: Spring configuration for {x} added but no adapter implementation` | Note in summary; do NOT re-verify (Spring config can be split-PR) |
| 5g (whitelabel resemblance heuristic) | `CROSS-SKILL: New adapter {x} may be a white-label scenario` | Run §"White-label policy" workflow |
| 5i (IT-registry misalignment) | `IT-REGISTRY: ...` | Do NOT re-verify — the registry file is owned by pr-triage-java; this skill records the cross-link only when the YAML side is incomplete (e.g., adapter name in test-application.properties but not in this PR's YAML) |
| 5k (pre-checkstyle pre-flag) | `PRE-CHECKSTYLE: {file} ...` | If the flagged file is owned by this skill, cite the pre-flag in the relevant finding; do not duplicate the analysis |

**1g. Cross-language port-fidelity check (consume `--- PRIOR SOURCE SPEC COMPARISON ---`).**

When the triage manifest carries a `--- PRIOR SOURCE SPEC COMPARISON ---` block (the PR is porting a bidder from Go to Java; the SOURCE-language spec lives at `prebid-server-go/read/specs/{bidder}/latest.yaml` or under the Teal-flow `.tmp/full-loop/{run-id}/go/{bidder}.yaml`), cross-reference each port-fidelity finding against this skill's bidder-config-specific surface:

- **Source spec carries `bidder_info.{capabilities, gvl_vendor_id, geoscope, maintainer, modifying_vast_xml_allowed, endpoint_compression}` (the R5-strict shared set)** → verify the Java YAML emits the same values after kebab-case↔camelCase normalization. The mapping table:
  - Go `capabilities.{app,site,dooh}.mediaTypes: [...]` ↔ Java `meta-info.{app,site,dooh}-media-types: [...]` (flattened; per Port Translation Rule 34)
  - Go `gvlVendorID: N` ↔ Java `meta-info.vendor-id: N`
  - Go `geoscope: [...]` ↔ Java `geoscope: [...]` (same shape; values identical)
  - Go `maintainer.email: ...` ↔ Java `meta-info.maintainer-email: ...`
  - Go `modifyingVastXmlAllowed: bool` ↔ Java `modifying-vast-xml-allowed: bool` (camelCase ↔ kebab-case)
  - Go `endpointCompression: GZIP` ↔ Java `endpoint-compression: gzip` (Java lowercase; resolves to `CompressionType.GZIP` enum via Spring relaxed-binding)
  - Divergence on any of these is **fail** severity per the cross-language R5-strict rule
- **Source spec carries openrtb version / multiformat / gpp signals (per F-new-44 family)** → verify Java YAML mirrors **with the correct keys**:
  - Go `openrtb.version: "2.6"` ↔ Java `adapters.{x}.ortb-version: "2.6"` (top-level field on base `BidderConfigurationProperties`, NOT under an `ortb:` block; the key is `ortb-version`, not `ortb.version`). Both accept the string `"2.6"` per Java edge case #29 quoting rule.
  - Go `openrtb.multiformat-supported: true` ↔ Java `adapters.{x}.ortb.multiformat-supported: true` (this IS under the `ortb:` block — it's the only field on the Java `Ortb` POJO).
  - Go `openrtb.gpp-supported: true` ↔ Java HAS NO `gpp-supported` boolean. GPP capability is signaled implicitly via the presence of `{{gpp}}` / `{{gpp_sid}}` macros in `usersync.iframe.url` / `usersync.redirect.url`. When source-spec declares `gpp-supported: true`, verify the Java YAML's usersync URLs include the GPP macros.
- **Source spec carries `code.make_bids.http_status_handling.kind=canonical-go-helpers`** → cross-reference: Java framework defaults handle 204/non-200 status codes BEFORE `makeBids` is invoked (Rule 30 framework-default no-op). The Java `{X}Configuration.java` should NOT include explicit status-check wiring. If the Configuration file includes a custom HTTP status handler bean or registers a non-default response filter, flag as **warn** — divergence from the canonical Go semantics is suspicious for a port.
- **F-new-67/69/72 (empty `geoscope:` bare-line)** — pre-flagged by pr-triage-java Step 5k. If the YAML contains a bare `geoscope:` line with no list value, this resolves to YAML null which Spring then maps to an empty list — but the line is unused (the canonical pattern is to omit the field entirely). Flag as **info** with note: "Empty `geoscope:` bare-line — omit the field entirely or supply a list."
- **F-new-44 (ortb fields missing on Java port)** — when source spec declares `openrtb.version: "2.6"` but Java YAML omits the `ortb` block, the adapter will send `X-OpenRTB-Version: 2.5` headers despite the Go side declaring 2.6. Flag as **fail**.
- **Source spec carries `cross_language.port_concerns.aliases_inverted: true`** → the Java port MUST collapse Go's per-child alias YAMLs into the parent's `aliases:` map. Verify each Go alias appears under Java's `aliases.{alias}: ~` (tilde-inherit) or `aliases.{alias}: { ... }` (full-block) — missing aliases are **fail**; the port is incomplete.
- **Source spec carries `quirks[edge_case_taxon=hardcoded-config-as-anti-pattern]` (e.g., Go-side hardcoded `DEV_ENDPOINT` constant)** → the Java port is expected to promote the constant to Spring config via Rule 35 typed-subclass (the canonical Kobler case). Verify the Java YAML has the new field (e.g., `dev-endpoint: ...`) AND the Configuration file has a typed-subclass extending `BidderConfigurationProperties` with the matching `private String devEndpoint` field. Missing either is **fail**.

Severity policy (symmetric with Go side):
- `info` by default — most port asymmetries are legitimate per Rules 5/9/11/35/38
- `warn` when divergence touches a Rule 38 byte-fidelity assertion or R5-strict cross-language equivalence
- `fail` when the divergence is a documented `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` `severity: fail` entry

**Note**: this skill's port-fidelity check is the Java-side first downstream consumer of `prior_source_spec` (audit item 25 LANDED in this F4 PR). pr-triage-java emits the block; this skill, `bidder-class-pr-review`, and `bidder-params-java-pr-review` each consume it via their Step 1g. The Go-side symmetric consumer is still pending as of audit time (per `docs/runs/post-d3.8-remaining-work.md:36`).

### Step 2: Extract Changes From the Diff

Parse the diff output to identify exactly which YAML fields and Java lines were added, modified, or removed. Categorize each file:

- **Added file** (entire file is new) — every line is new; review each in context
- **Modified file** (file exists, some lines changed) — **ONLY** review the specific lines on `+`/`-` lines. Unchanged surrounding context is out of scope.
- **Removed file** (entire file deleted) — create a single task to validate the removal is intentional (typically `bidder-removal` PR type)
- **Renamed file** (rare; `{old}.yaml` → `{new}.yaml`) — verify rename is consistent across YAML + Configuration + bidder-class + ExtImp (cross-skill); for this skill the only check is that the wrapper key inside the YAML matches the new filename

For **modified files**, extract only the diff hunks. Within each hunk:

- For YAML files: map each changed line to its corresponding field path (e.g., `meta-info.maintainer-email`, `aliases.adport.endpoint`, `usersync.iframe.url`). Java's unified YAML is nested deeper than Go's; track path correctly.
- For Java files: classify each changed line as one of: import (the F-new-58/59 trap zone), class declaration (F-new-79 zone), `@Bean` declaration, `@Configuration` annotation, `@PropertySource` value, `BidderDepsAssembler.forBidder(...)` constant, `.withConfig(...)`, `.usersyncerCreator(...)`, `.bidderCreator(...)` lambda, `resolveEndpoint(...)` helper, inner `BidderConfigurationProperties` subclass body. Each category maps to a specific verification workflow below.
- Ignore all context lines (lines without `+` or `-` prefix).

**Comment-only / whitespace-only changes:** If all changed lines in a file are YAML comments (`#` lines), Java comments (`//` or `/* */`), or whitespace-only (trailing newline, indentation), the file has **zero changed fields**. Skip to Step 5 and recommend fast-track approval — note in the summary that the change is comment/formatting only with no functional impact.

### Step 3: Build Verification Task List

For **each changed line/field only**, look up the matching **Verification Workflow** (see below). Create tasks with:

- **subject**: `Verify {bidder}: {field_path}` (e.g., `Verify adverxo: aliases.adport.endpoint`) for YAML; `Verify {bidder}: {Configuration.java}: {section}` (e.g., `Verify kobler: KoblerConfiguration.java: bidderCreator lambda`) for Java
- **description**: The specific verification steps from the matching workflow, plus any field-specific criteria
- **activeForm**: `Verifying {bidder} {field_path}`

There are two categories of tasks:

**1. PR-level task (at most one):** A single task covering PR-wide checks that don't map to a specific field. Only create this if applicable:
- **Documentation PR check**: Reference `docs_pr` from the triage manifest. If `none` and PR type is `new-adapter`, flag as WARN. Java bidder docs live alongside the Go-side bidder docs at `prebid.github.io/dev-docs/bidders/{bidder}.md`.
- **Duplicate PR check**: Reference `Duplicate PRs` from triage. If duplicates exist and they touch the same `bidder-config/{x}.yaml`, assess conflict potential.
- **Completeness check**: For PR type `new-adapter`, verify the bidder-config-pr-review's required files are present: `bidder-config/{x}.yaml` + `{X}Configuration.java` (the BidderConfigurationProperties subclass is conditional — only required when source-spec quirks demand it). Missing files from this skill's owned set is **fail** (PR is incomplete); pr-triage-java may also flag this under 5e.

**Bulk-mode handling for multi-adapter alias bundles**: If the triage manifest indicates PR type `alias-only` AND the bundle exception applies (N aliases of same parent, identical schema), do NOT create per-alias field-level tasks. Instead create:
1. One "bulk pattern consistency" task verifying: (a) all aliases reference the same parent's `aliases:` block, (b) all aliases have identical structural shape (tilde-inherit OR full-block; not mixed), (c) each alias's endpoint domain plausibly belongs to that alias's organization, (d) each alias's usersync URL plausibly belongs to the alias org.
2. One shared task for parent-endpoint and parent-resolveEndpoint verification.

Total tasks for a 5-alias bulk PR: 2, not (5 × number-of-fields-per-alias). The canonical Java case is Adverxo's `adport`+`bidsmind`+`mobupps` per-alias bundle shipped together — this skill should produce ~2 tasks under bulk-mode, not 30.

**2. Field-level tasks (one per changed field/section):** For each changed line, look up the matching Verification Workflow. Create tasks in this priority order (but only for fields that appear in the diff):

YAML side (within `adapters.{x}`):
1. `endpoint:` — use [Endpoint Changed](#workflow-endpoint-changed) workflow
2. `aliases:` block — use [Aliases Block Changed](#workflow-aliases-block-changed) workflow
3. `usersync.iframe.url` / `usersync.redirect.url` — use [User Sync URL Changed](#workflow-user-sync-url-changed)
4. `meta-info.maintainer-email` — use [Maintainer Email Changed](#workflow-maintainer-email-changed)
5. `meta-info.{app,site,dooh}-media-types` — use [Capabilities Changed](#workflow-capabilities-changed)
6. `meta-info.vendor-id` — use [GVL Vendor ID Changed](#workflow-gvl-vendor-id-changed)
7. `geoscope` — use [Geoscope Changed](#workflow-geoscope-changed)
8. `endpoint-compression` — use [Endpoint Compression Changed](#workflow-endpoint-compression-changed)
9. `modifying-vast-xml-allowed` — use [Modifying VAST XML Changed](#workflow-modifying-vast-xml-changed)
10. `ortb-version` (top-level, on base class) or `ortb.multiformat-supported` (under the `ortb:` block — the only field in Java's `Ortb` POJO) — use [ORTB Block Changed](#workflow-ortb-block-changed). Note: Java has NO `ortb.version` (top-level `ortb-version` instead) and NO `ortb.gpp-supported` key — GPP capability is implicit via usersync macros.
11. `enabled: false` at adapter top-level — use [Bidder Disabled](#workflow-bidder-disabled)

Java side (within `{X}Configuration.java`):
1. `@PropertySource` value — use [PropertySource Wiring](#workflow-propertysource-wiring)
2. `@Bean("{x}ConfigurationProperties") @ConfigurationProperties("adapters.{x}")` quartet — use [Bean Quartet](#workflow-bean-quartet)
3. `BidderDepsAssembler.<T>forBidder(BIDDER_NAME)` — use [BidderDepsAssembler Generic](#workflow-bidderdepsassembler-generic)
4. `.withConfig(...)` — use [withConfig Binding](#workflow-withconfig-binding)
5. `.usersyncerCreator(UsersyncerCreator.create(externalUrl))` — use [UsersyncerCreator URL](#workflow-usersyncercreator-url)
6. `.bidderCreator(cfg -> new {X}Bidder(...))` lambda — use [bidderCreator Lambda](#workflow-biddercreator-lambda) (HIGH PRIORITY — F-new-57 trap)
7. `resolveEndpoint(...)` helper method — use [resolveEndpoint Helper](#workflow-resolveendpoint-helper)
8. Inner `BidderConfigurationProperties` subclass — use [Typed-Config Subclass](#workflow-typed-config-subclass)
9. Import block — use [Import Order Pre-Check](#workflow-import-order-pre-check) (F-new-58/59 trap)
10. `public class {Name}` declaration — use [Class-Filename Match](#workflow-class-filename-match) (F-new-79 trap)

**Do NOT create separate "new adapter file" tasks.** For new files, required-field validation is implicit — if `endpoint:` or `meta-info.maintainer-email:` is missing from a new YAML, it will surface as a missing-field finding within the field-level task that covers that field's expected location. Same for Java: missing `@Bean BidderDeps {x}BidderDeps(...)` will surface within Bean Quartet workflow.

**Sanity check**: The number of field-level tasks must equal the number of distinct changed sections across all files. If you have more tasks than changed sections, you are reviewing out-of-scope content — remove the excess. The single PR-level task (if created) does not count toward this check.

### Step 4: Execute Verification Tasks

Work through tasks, parallelizing where possible (endpoint reachability checks, GVL lookup, SSL cert validation can run concurrently). For each task:

1. Mark task `in_progress`
2. Execute every verification step from the matching workflow
3. Record each step's result as PASS, FAIL, or WARN with evidence
4. Check cross-field consistency rules — only between fields that changed in this PR, or between a changed field and an existing field it directly depends on (e.g., a new alias requires checking the parent's `endpoint:` template macros)
5. Mark task `completed` with findings

### Step 5: Summary

After all tasks complete, produce a review summary:

- Files changed (with category: added/modified/removed/renamed)
- Fields/sections changed per file
- Verification steps executed (count by PASS/WARN/FAIL)
- Issues found (critical / warning / info), with file:line references
- Cross-skill concerns this skill resolved or referenced
- Port-fidelity findings (when `prior_source_spec` was present)
- Recommendation (approve, request changes, or comment)

---

## Verification Workflows — YAML side

The YAML side mirrors the Go-side `bidder-info-pr-review` workflows but adapts field names to Java's unified-YAML kebab-case schema.

### Workflow: Endpoint Changed

**Triggers when:** `endpoint:` (under `adapters.{x}`) is added or modified.

1. **URL format**: Verify the value is a well-formed URL (scheme + host at minimum).
2. **Reachability check** (HTTPS):
   ```bash
   curl -sS -o /dev/null -w "HTTP %{http_code} in %{time_total}s" -X POST {url}
   ```
   Accept 200, 204, 400 (bad-request expected without proper body) as evidence of a live endpoint. Flag 404, 502, connection refused, or timeout as **FAIL**.
3. **Scheme tolerance**: HTTPS is strongly preferred; HTTP is permitted but flag as **INFO** with recommendation to upgrade. Never **FAIL** on HTTP scheme alone.
4. **SSL cert** (HTTPS endpoints only):
   ```bash
   echo | openssl s_client -connect {host}:443 -servername {host} 2>/dev/null | openssl x509 -noout -subject -dates -issuer
   ```
   Flag expired/invalid as **FAIL**.
5. **Template macros**: Two macro syntaxes are valid in Java:
   - `{{PREBID_SERVER_ENDPOINT}}` — resolved at construction time via the `resolveEndpoint(...)` helper in `{X}Configuration.java` (canonical: aax — see AaxConfiguration.java line 24). This single macro is the canonical framework-provided one.
   - Per-bidder template tokens — e.g., `{{adUnitId}}`, `{{auth}}` (canonical: Adverxo `endpoint: https://pbsadverxo.com/auction?adUnitId={{adUnitId}}&auth={{auth}}`). These are passed through to the adapter and resolved by `{X}Bidder.java`'s `makeHttpRequests(...)` via `String.replace(...)`.
   - Any macro NOT handled by the Configuration's `resolveEndpoint` AND NOT consumed by `{X}Bidder.java`'s request builder will leave the literal `{{TOKEN}}` in the URL at runtime. Cross-reference both files (the read-side companion's macro list at [../../../read/skills/shared/framework-utilities-java.md](../../../read/skills/shared/framework-utilities-java.md) catalogs known framework-level macros). Unknown macros: **FAIL**.
6. **Non-template tokens** (`#{REGION}#`, `${X}`, `<X>`): MUST be paired with `enabled: false` at the adapter top-level + a YAML comment block listing valid replacement values. Otherwise Spring will not substitute and runtime calls will fail. Missing `enabled: false` pairing: **FAIL** (mirror of Go-side `disabled-by-default region endpoint` rule).
7. **Domain ownership**: Verify the domain plausibly belongs to the bidder organization (domain name relates to bidder name). Flag mismatch as **INFO**.
8. **No hardcoded credentials**: Ensure the URL does not contain actual API keys, passwords, or secrets in plain text. **FAIL** if present.
9. **White-label policy**: If the endpoint domain matches an existing adapter's endpoint, run the [White-Label Policy](#workflow-white-label-policy) workflow.

### Workflow: Aliases Block Changed

**Triggers when:** `aliases:` (under `adapters.{x}`) gains, loses, or modifies entries.

Java aliases are NESTED under the parent — port-translation Rule 33 inversion. Each alias is one of two forms:

- **Tilde-inherit** (`adport: ~`) — inherits ALL parent fields. The YAML value is YAML null.
- **Full-block** (`adport: { endpoint: ..., usersync: { ... } }`) — overrides one or more parent fields. The YAML value is a non-null map.

For each added or modified alias entry:

1. **Parent existence**: The wrapping bidder MUST be a parent (not itself an alias of another bidder). Java does not support alias-of-alias chains. Check the parent YAML's adapter key is NOT itself inside another bidder's `aliases:` block. **FAIL** on chain detection.
2. **Alias name uniqueness**: The alias name MUST NOT collide with any existing bidder name (top-level adapter key in any other `bidder-config/*.yaml`). pr-triage-java's bidder-name extraction surfaces collisions in the manifest's `New aliases:` section; cross-check.
3. **Endpoint resolveability** (full-block only): Extract the alias's `endpoint:` value. For each `{{TOKEN}}` macro found:
   - Cross-reference against parent's `resolveEndpoint(...)` method in `{X}Configuration.java` (if present).
   - Cross-reference against parent's `{X}Bidder.java` `makeHttpRequests(...)` (read-only; this skill READS bidder-class for this check — owned by bidder-class-pr-review).
   - Any macro NOT handled in either location: **FAIL** — silently leaves literal in URL (this is the 5a cross-skill concern surfaced by pr-triage-java).
4. **Endpoint domain ownership**: The alias endpoint domain SHOULD belong to the alias organization, not reuse the parent's verbatim (unless shared infrastructure is intentional — canonical: Adverxo aliases share `pbsadverxo.com` but each has its own subdomain like `adport.pbsadverxo.com`, `bidsmind.pbsadverxo.com`). Flag domain match with no subdomain differentiation as **WARN**.
5. **Per-alias usersync** (full-block only):
   - When the alias declares a full `usersync:` block, verify each URL passes the [User Sync URL Changed](#workflow-user-sync-url-changed) workflow.
   - The alias usersync `cookie-family-name` MUST equal the alias name (canonical Adverxo pattern). Mismatch: **FAIL**.
   - When tilde-inherit, the alias inherits the parent's usersync — no additional checks needed.
6. **Per-alias `enabled: false`**: New aliases typically ship with `enabled: false` (canonical Adverxo pattern). When the alias is `enabled: true` from the start, flag as **INFO** with note: "alias enabled by default — confirm intentional".
7. **Parent + alias consistency** (when pr-triage-java surfaced concern 5c): If both parent and alias were modified in the same PR, verify:
   - Parent endpoint template-token changes are reflected in alias endpoints (where applicable)
   - Parent capability changes (media-types) are inherited by aliases unless explicitly overridden (Java does NOT have an alias-side `meta-info` override; aliases inherit capabilities from parent verbatim)
8. **Tilde + alias-back-after-rename detection**: If the alias is tilde-inherit AND the alias name matches a previously-deleted top-level adapter key (i.e., the bidder was renamed; canonical: Adoppler → ElementalTV via PR #4326), flag as **INFO** with note: "tilde alias-back for bidder rename (`{old}` → `{new}`) — confirm rename was intentional and major-version-bounded." This pattern is the Java edge case #33 bidder-rename three-step refactor.
9. **One-line alias OK**: `aliases: { adport: ~ }` (tilde-inherit) is fully valid. Do not flag as "missing fields".
10. **Cross-skill consistency with test-application.properties**: For each added alias, pr-triage-java's `IT-REGISTRY` check verifies `adapters.{parent}.aliases.{alias}.enabled=true` + `.endpoint=...` lines exist. This skill records the YAML-side completeness; if a YAML alias is added but pr-triage reports no IT-registry entry, this is **FAIL** — IT framework will run without alias visibility.

### Workflow: User Sync URL Changed

**Triggers when:** `usersync.iframe.url` or `usersync.redirect.url` (at adapter top-level OR under an alias) is added or modified.

1. **HTTPS required**: URL must use HTTPS scheme. HTTP usersync URLs are **FAIL**.
2. **Reachability check**:
   ```bash
   curl -sS -o /dev/null -w "HTTP %{http_code} in %{time_total}s" {url}
   ```
   Accept 200, 301, 302 (redirects expected for sync URLs). Flag 404, 500, connection refused as **FAIL**.
3. **Privacy macro validation**: Verify required macros are present:
   - `{{gdpr}}`, `{{gdpr_consent}}` for GDPR compliance (note: Java uses lowercase + underscore; Go uses `{{.GDPR}}` / `{{.GDPRConsent}}` — Port Translation Rule 12)
   - `{{us_privacy}}` for US privacy
   - `{{redirect_url}}` for the callback
   - `{{gpp}}` / `{{gpp_sid}}` if GPP is supported (note: Java has NO `ortb.gpp-supported` boolean; the presence of these macros in usersync URLs IS the GPP-support signal — see Workflow: ORTB Block Changed)
4. **userMacro consistency**: If `uid-macro` is declared, verify it follows the bidder's expected format (e.g., `$UID`, `<vsid>`, `[USER_ID]`).
5. **Domain ownership**: Sync URL domain SHOULD belong to the bidder organization. Flag mismatch as **WARN**.
6. **Both types declared**: If the bidder declares both iframe AND redirect, verify both URLs are functional. Flag unreachable declared type as **FAIL**.

### Workflow: Maintainer Email Changed

**Triggers when:** `meta-info.maintainer-email` is added or modified.

1. **Manual reviewer process**: The maintainer-email "received" verification gate is a manual reviewer process (typical: bsardo sends an email; merge is gated on the maintainer replying "received"). Skills cannot automate this gate. When the triage manifest reports `blocking-confirmation-pending`, note this in the finding.
2. **Generic-domain emails** (`gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `proton.me`, `icloud.com`): flag as **INFO** — these don't establish organizational ownership and historically receive extra scrutiny.
3. **Personal-name patterns** (`firstname.lastname@`, `firstname@`): flag as **WARN** — reviewer convention is to require a group/role mailbox (`tech@`, `support@`, `prebid@`, etc.).
4. **Aliases inherit**: When the change is to a parent's `maintainer-email` and aliases are tilde-inherit, the new email applies to all aliases. Note this in the finding.
5. If the PR comments include phrases like "please reply 'received'", record `email-confirmation-pending` status.

### Workflow: Capabilities Changed

**Triggers when:** `meta-info.app-media-types`, `meta-info.site-media-types`, or `meta-info.dooh-media-types` is added or modified.

1. **Valid media types**: Each value must be one of: `banner`, `video`, `native`, `audio`.
2. **At least one per platform**: Each declared platform must have at least one media type.
3. **DOOH scrutiny**: DOOH is uncommon — if declared, verify the bidder genuinely supports DOOH inventory. Cross-skill concern: at least one IT fixture under `it/openrtb2/{x}/` must exercise DOOH context (`mockBidRequest.dooh` present); this is owned by bidder-params-java-pr-review. Cross-reference but do not duplicate.
4. **Adapter code alignment**: Cross-skill READ — `{X}Bidder.java`'s `makeHttpRequests(...)` should handle each declared media type. If a media type is added here but the adapter code only handles banner, flag as **WARN** and reference the bidder-class skill's responsibility for the deeper code-side check.
5. **Schema alignment**: Cross-skill READ — `static/bidder-params/{x}.json` should not gate out a media type that the YAML declares. (Owned by bidder-params-java-pr-review.)
6. **R5-strict cross-language equivalence**: When `prior_source_spec` is present and source-spec carries `capabilities`, the Java values MUST match exactly after the structural unflattening. Divergence is **fail**.

### Workflow: GVL Vendor ID Changed

**Triggers when:** `meta-info.vendor-id` is added or modified.

1. **Value range**: Must be a non-negative integer. Value `0` means "not IAB registered" and is the default.
2. **Vendor list lookup** (when value > 0):
   ```bash
   curl -sS "https://vendor-list.consensu.org/v3/vendor-list.json" | python3 -c "import json,sys; v=json.load(sys.stdin)['vendors'].get('{id}',{}); print(v.get('name','NOT FOUND'))"
   ```
   Verify the returned name corresponds to the bidder organization. Flag mismatches as **WARN** (corporate restructures tolerated when there's a credible relationship).
3. **GVL ID `0` redundancy**: When the YAML declares `vendor-id: 0` explicitly, this is the default. Flag as **INFO** asking for removal (cleaner YAML) — but do not **FAIL**; explicit declaration is tolerated upstream (see Adverxo's explicit `vendor-id: 0`).
4. **Java kebab-case typo trap (Java edge case #34 family)**: If the diff adds `gvlVendorID` at the root (Go camelCase form bleeding into Java), this is **FAIL** — silently defaults to 0. Canonical Java key is `meta-info.vendor-id`.
5. **R5-strict cross-language equivalence**: When `prior_source_spec` is present and source-spec carries `gvl_vendor_id`, the Java value MUST match exactly. Divergence is **fail**.

### Workflow: Geoscope Changed

**Triggers when:** `geoscope` (at adapter top-level OR under an alias) is added or modified.

**Operator-warning context (verified at SHA `a1fe64e123d6`)**: the `geoscope` key is **currently UNBOUND in upstream Java** — `BidderConfigurationProperties` has no `geoscope` field and `BidderInfoCreator` has no `getGeoscope()` reference. Spring relaxed-binding silently discards the value. Reviewer guidance: still apply the value-validity checks below (so YAML stays correct when upstream binds the field), but mark the finding INFO with note: "geoscope is currently silently dropped by Spring relaxed-binding — operator should treat as documentation until upstream wires it." Operators upgrading or hand-mirroring the Go-side geoscope should not expect runtime enforcement on the Java side today.

1. **Valid values**: 3-letter ISO 3166-1 alpha-3 country codes (e.g., `USA`, `CAN`, `GBR`, `NOR`, `SWE`, `DNK`). Special values: `GLOBAL`, `EEA`. Negation prefix `!` (e.g., `!EEA`).
2. **Uppercase required**: All values MUST be uppercase. Lowercase is **FAIL** (when upstream binds the field; today only style).
3. **Bare-line empty (F-new-67/69/72 trap)**: If the diff adds a bare `geoscope:` line with no list value, this resolves to YAML null which Spring would map to an empty list — but the field is currently unbound regardless. Flag as **INFO** with recommendation to omit the field entirely. pr-triage-java's Step 5k may also pre-flag this.
4. **Geographic claims plausibility**: Verify the country list aligns with the bidder's organizational geography (Kobler declares `NOR/SWE/DNK` — Scandinavian; matches `bidding-support@kobler.no`). Flag implausible claims as **WARN** (documentation hygiene).
5. **Alias inheritance**: When parent declares geoscope and an alias does NOT, the alias would inherit (when bound). When an alias explicitly declares geoscope, the alias value would override. Flag redundant alias geoscope matching parent as **WARN** (cleaner YAML).

### Workflow: Endpoint Compression Changed

**Triggers when:** `endpoint-compression` is added or modified.

1. **Valid value**: `gzip` (lowercase per Java's `CompressionType` enum + Spring relaxed-binding). Some upstream YAMLs use `GZIP` (uppercase) — both bind to `CompressionType.GZIP` via Spring. Reviewer-preferred form is `gzip` (lowercase) per canonical examples (kobler.yaml, adverxo.yaml). Flag uppercase as **INFO** (functional but non-canonical).
2. **CamelCase typo (Java edge case #34, `endpoint-compression-typo` family)**: If the diff uses `endpointCompression` (camelCase) at the YAML key level, this is **FAIL** — Java's relaxed-binding does NOT handle the camelCase form for this key; it is silently ignored and compression is NOT applied. Canonical regression: Ogury PR #3788. Read-side companion's edge-case taxonomy taxonomizes this as `endpoint-compression-typo`. (Distinct from F-new-86, which is the ADR-007 F3 Site→App synthesis trap owned by `bidder-class-pr-review`.)
3. **Server support verification**: Confirm the bidder's endpoint actually accepts `Content-Encoding: gzip`. (Cannot test directly without a real bid request; flag as **INFO** asking the contributor to confirm.)

### Workflow: Modifying VAST XML Changed

**Triggers when:** `modifying-vast-xml-allowed` is added or modified.

1. **Valid value**: Boolean (`true` or `false`).
2. **Default behavior**: Default is `true` framework-wide. Setting `false` opts out of video impression tracking.
3. **Video media-type prerequisite**: Setting `modifying-vast-xml-allowed: false` only makes sense if the bidder declares video in `meta-info.{app,site}-media-types`. If `false` is set but no video capability, flag as **WARN**.
4. **CamelCase typo (Java edge case #31)**: If the diff uses `modifyingVastXmlAllowed` (camelCase) at the YAML key level, this is **FAIL** — silently defaults to true. Canonical Java key is `modifying-vast-xml-allowed`. (Distinct from F-new-86, which is the ADR-007 F3 Site→App synthesis trap owned by `bidder-class-pr-review`.)
5. **R5-strict cross-language equivalence**: When `prior_source_spec` declares `modifying_vast_xml_allowed`, the Java value MUST match.

### Workflow: ORTB Block Changed

**Triggers when:** `ortb-version` (top-level, on base class) or `ortb.multiformat-supported` (under the `ortb:` block) is added or modified.

**Important — what does NOT exist in Java's POJO surface:**
- `ortb.version` (nested) is NOT a Java key. The version field is `ortb-version` at adapter top-level, binding to `BidderConfigurationProperties.ortbVersion`.
- `ortb.gpp-supported` is NOT a Java key. GPP capability is signaled implicitly via `{{gpp}}` / `{{gpp_sid}}` macros in `usersync.*.url`. The Java `Ortb` POJO contains ONLY `multiFormatSupported` (kebab-case `multiformat-supported`).

1. **`ortb-version: "2.6"` quoting (Java edge case #29)**: Must be a QUOTED string. `ortb-version: 2.6` (unquoted) parses as YAML float `2.6` — Spring's binding to `OrtbVersion` enum then fails silently (or maps to wrong enum). Flag unquoted as **FAIL**. Canonical examples: kobler.yaml does NOT declare the field at all (defaults apply); declared examples must quote.
2. **`ortb.multiformat-supported: bool`**: Boolean. Controls whether adapter handles multi-format imps in a single request. Verify adapter code's `makeHttpRequests(...)` actually splits or merges multi-format correctly.
3. **Pseudo-`gpp-supported`**: When source-spec carries `gpp-supported: true` (Go side), verify Java's usersync URLs include `{{gpp}}` / `{{gpp_sid}}` macros — flag mismatch as **WARN**. There is no `ortb.gpp-supported` boolean to set on the Java side.
4. **F-new-44 family**: When `prior_source_spec` declares `openrtb.version: "2.6"` but Java YAML omits the top-level `ortb-version` field, the adapter sends 2.5 requests. Flag as **fail** — port is incomplete.

### Workflow: Bidder Disabled

**Triggers when:** `enabled: false` is added at the adapter top-level (not under `aliases:`).

1. **Intentionality**: Verify the PR description explains why the bidder is being disabled.
2. **Simultaneous changes**: If other fields are being modified alongside `enabled: false`, flag as suspicious — why modify configuration for a bidder being disabled?
3. **Code cleanup**: Check whether related adapter code/tests should be removed or retained — cross-skill READ.
4. **Disabled-by-default region pairing**: If `enabled: false` is being added BECAUSE the endpoint contains non-Go-template placeholders (`#{REGION}#`), this is the canonical disabled-by-default pattern — **INFO** with note: "appStockSSP-style host-configured region endpoint; ensure comment block listing valid replacement values is present."

### Workflow: White-Label Policy

**Triggers when:** ANY of:
- pr-triage-java surfaced cross-skill concern 5g (`CROSS-SKILL: New adapter {x} may be a white-label scenario`)
- PR description / comments include "white label", "white-label", "whitelabel"
- A new YAML's `endpoint:` matches an existing adapter's endpoint domain

1. **Prebid policy quote (verbatim)**: "If an adapter is a white label, the aliasing feature should be used instead of copying an adapter."
2. **`white-label-only: true` semantics (Java kebab-case key; Go side uses camelCase `whiteLabelOnly`)**: Marks parent as available only as white-label target (aliases reference it). Does NOT preclude `{X}Bidder.java` Java code on the parent — canonical white-label parents (TeqBlaze, SmartHub) have full Java code AND `white-label-only: true`. **INFO** if the flag is set on a new file.
3. **Full adapter that looks like a copy**: If a new full Java adapter is being added but the diff structure resembles an existing adapter (heuristic: identical endpoint domain, comparable parameter schema, copy-paste-style Configuration class), flag as **WARN** with the suggestion: "this may be a white-label scenario — consider adding the new bidder as an alias under an existing parent's `aliases:` block instead of duplicating Java code."
4. **Alias-only directionality**: `aliases:` entries are typically added (not deleted from full). Reverse migration (alias → full) is rare and requires reviewer judgment.
5. **Cross-skill de-duplication**: If pr-triage-java's CROSS-SKILL CONCERNS already records the 5g resemblance signal OR the `whitelabel-redirect-mid-review` sub-label was set, do NOT re-flag — note `Previously flagged by triage` and surface only net-new findings (e.g., parent-choice verification: when the redirect-resolution chose a different parent than the reviewer originally suspected).

---

## Verification Workflows — Spring `@Configuration` class side

These workflows have NO Go analog — Java's per-bidder Spring DI factory is unique to the Java tree.

### Workflow: PropertySource Wiring

**Triggers when:** the `@PropertySource(value = "classpath:/bidder-config/{x}.yaml", factory = YamlPropertySourceFactory.class)` annotation is added or modified.

1. **Path matches filename**: The `value=` MUST equal `classpath:/bidder-config/{x}.yaml` where `{x}` is the lowercase bidder name (matching the YAML filename). Mismatch is **FAIL** — Spring will load the wrong file.
2. **Factory class hardcoded**: `factory = YamlPropertySourceFactory.class`. NEVER another class. Hardcoded across all bidders.
3. **No additional `@PropertySource` entries**: Each Configuration class has exactly ONE `@PropertySource`. Multiple is **FAIL** (unintended; cargo-cult mistake).

### Workflow: Bean Quartet

**Triggers when:** the `@Bean("{x}ConfigurationProperties") @ConfigurationProperties("adapters.{x}") ... configurationProperties()` method is added or modified.

1. **Bean name = `{x}ConfigurationProperties`** (camelCase, bidder-prefix). Must match what the `@Bean BidderDeps {x}BidderDeps(...)` method's parameter declaration consumes (Spring autowires by name when types are ambiguous).
2. **`@ConfigurationProperties` prefix = `adapters.{x}`**. Must match the YAML's wrapper key. Mismatch is **FAIL** — Spring binds zero fields.
3. **Return type**: `BidderConfigurationProperties` (the base class) OR the typed-subclass (Rule 35; e.g., `KoblerConfigurationProperties`). When Rule 35 applies, the return type MUST be the subclass — if it returns the base class, the typed fields will not bind. **FAIL**.
4. **Method body**: `return new {ReturnType}();`. Single-statement constructor invocation. Anything more complex (custom initialization) is **WARN** and warrants closer review — Spring's lifecycle handles initialization via `@PostConstruct`.

### Workflow: BidderDepsAssembler Generic

**Triggers when:** the line `BidderDepsAssembler.<T>forBidder(BIDDER_NAME)` (or the non-generic `BidderDepsAssembler.forBidder(BIDDER_NAME)`) is added or modified.

1. **`BIDDER_NAME` constant**: Must equal the lowercase bidder name (matching the YAML's `adapters.{x}` key AND the `@PropertySource` filename). Declared as `private static final String BIDDER_NAME = "{x}";` — hardcoded check.
2. **Generic type parameter (when present)**: `BidderDepsAssembler.<{X}ConfigurationProperties>forBidder(...)`. Required when Rule 35 typed-subclass is used; the generic enables type-safe `.withConfig(config)` parameter binding. Missing generic when subclass is in use: **WARN** (compiles but loses type safety).
3. **Non-generic form (default)**: `BidderDepsAssembler.forBidder(BIDDER_NAME)` — when no Rule 35 subclass. Canonical form for the majority of bidders.

### Workflow: withConfig Binding

**Triggers when:** the `.withConfig(...)` line of the `BidderDepsAssembler` chain is added or modified.

1. **Argument matches the `@Bean` parameter name**: `.withConfig({x}ConfigurationProperties)` where `{x}ConfigurationProperties` is the method parameter declared on `{x}BidderDeps(...)` — and that parameter is autowired by name from the `@Bean("{x}ConfigurationProperties")` method above.
2. **Type alignment**: When Rule 35 subclass is used, the parameter type MUST be the subclass (`{X}ConfigurationProperties`), not the base class. Mismatched types is **FAIL** (compile error; CI will catch but pre-flag).
3. **Single config binding**: Exactly one `.withConfig(...)` call per chain. Multiple is **FAIL** (overwrites).

### Workflow: UsersyncerCreator URL

**Triggers when:** the `.usersyncerCreator(UsersyncerCreator.create(externalUrl))` line is added or modified.

1. **Hardcoded factory call**: Always `UsersyncerCreator.create(externalUrl)` — never an alternate factory or a `null`. Adapter has NO usersync? Then the YAML simply omits `usersync:` block; the framework handles the absence. Do NOT skip this line in the chain (the chain requires it).
2. **`externalUrl` parameter**: Must come from `@NotBlank @Value("${external-url}") String externalUrl` in the method signature. Other sources (constructor field, static constant) are **FAIL** — Spring will not inject correctly.

### Workflow: bidderCreator Lambda (HIGH PRIORITY — F-new-57 trap)

**Triggers when:** the `.bidderCreator(cfg -> new {X}Bidder(...))` lambda is added or modified.

This is the **highest-priority** workflow in the Spring DI side because it bridges the Configuration file with the bidder-class file, and the F-new-57 trap (canonical regression) happens here: the template emits a constructor signature mismatch (e.g., `new {X}Bidder(cfg.getEndpoint(), mapper)` when the actual class requires `(endpoint, mapper, currencyConversionService)`).

1. **Cross-skill READ — fetch the bidder class**:
   ```bash
   curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/{head_sha}/src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java"
   ```
   Locate the public constructor of `{X}Bidder`. Constructors come in two forms:
   - Lombok `@RequiredArgsConstructor` — the constructor is synthesized from the `final` fields declared in order. The actual constructor signature is `(field1, field2, ...)` in declaration order.
   - Explicit `public {X}Bidder(...)` — the constructor signature is whatever appears in the source.
2. **Argument count match**: The lambda body's `new {X}Bidder(a, b, c)` argument count MUST equal the constructor's parameter count. Mismatch is **FAIL** (compile error; CI catches but pre-flag).
3. **Argument type alignment**: For each argument in the lambda, verify:
   - `cfg.getEndpoint()` returns `String` (always; from base `BidderConfigurationProperties.endpoint`).
   - `cfg.get{ExtraField}()` (Rule 35 typed-subclass) returns `String` or whatever the subclass field declares.
   - `mapper` parameter on the outer method is `JacksonMapper` and the constructor accepts `JacksonMapper`.
   - `currencyConversionService` parameter on the outer method is `CurrencyConversionService` and the constructor accepts the same.
   - `externalUrl` parameter is `String`.
   - Any helper service (`PriceFloorResolver`, `PrebidVersionProvider`, `UUIDIdGenerator`, etc.) requires the matching constructor parameter type. Cross-reference [../../../read/skills/shared/framework-utilities-java.md](../../../read/skills/shared/framework-utilities-java.md) for the canonical service list.
4. **Argument order match**: The lambda's arguments MUST appear in the same ORDER as the constructor expects. Mismatch is **FAIL** (compile error OR — worse — silent runtime misbinding when types coincidentally line up).
5. **`resolveEndpoint(...)` indirection (when present)**: When the Configuration class declares a `private String resolveEndpoint(String, String)` helper (canonical: AaxConfiguration line 44), the lambda should pass `resolveEndpoint(config.getEndpoint(), externalUrl)` rather than `config.getEndpoint()` directly. This indirection substitutes the `{{PREBID_SERVER_ENDPOINT}}` macro at startup. If the helper is declared but the lambda calls `config.getEndpoint()` directly, the macro will leak into runtime URLs — **FAIL**.
6. **No `.bidderInfo(...)` call on `BidderDepsAssembler` (F-new-57b — HIGH BLOCKING FAIL)**: `BidderDepsAssembler` exposes only `forBidder`, `withConfig`, `usersyncerCreator`, `bidderCreator`, `assemble` as its public builder methods. There is NO public `.bidderInfo(...)` method. A `.bidderInfo(BidderInfoCreator.create(mapper)::create)` line is a COMPILE ERROR — verified against `BidderDepsAssembler.java` at SHA `a1fe64e123d6`. The framework auto-creates `BidderInfo` internally inside `BidderDepsAssembler.coreDeps()` from the `@ConfigurationProperties`'d YAML; per-bidder Configuration files MUST NOT call `BidderInfoCreator.create(...)` directly nor chain `.bidderInfo(...)` on the assembler. Flag any such call as **FAIL** (port-go2java emit trap; will not compile).
7. **No `BidderUtil.*` non-existent method calls (F-new-90)**: The Rule 30 framework-default mapping for HTTP status handling, error wrapping, and bidresponse parsing means the Configuration class should NOT include `BidderUtil.handleStatusCode(...)` / `BidderUtil.wrapError(...)` / similar method calls — these do not exist in the framework. Calls to `BidderUtil.*` non-existent methods are **FAIL** (compile error; CI catches but pre-flag).

### Workflow: resolveEndpoint Helper

**Triggers when:** the `private String resolveEndpoint(String, String)` method is added or modified.

1. **Method signature canonical**: `private String resolveEndpoint(String configEndpoint, String externalUrl)`. Parameter names may vary but types and order are fixed.
2. **Body uses `HttpUtil.encodeUrl(externalUrl)`**: The canonical form (canonical: AaxConfiguration line 45) — `configEndpoint.replace(EXTERNAL_URL_MACRO, HttpUtil.encodeUrl(externalUrl))`. Direct `String.replace(macro, externalUrl)` without `HttpUtil.encodeUrl` is **WARN** — URL-encoding ensures special characters in the external URL don't break the bid URL.
3. **`EXTERNAL_URL_MACRO` constant**: Declared as `private static final String EXTERNAL_URL_MACRO = "{{PREBID_SERVER_ENDPOINT}}";`. Hardcoded check.
4. **Called from `bidderCreator` lambda**: The lambda MUST invoke `resolveEndpoint(...)` — otherwise the helper is dead code. Cross-reference [bidderCreator Lambda](#workflow-biddercreator-lambda) Step 5.

### Workflow: Typed-Config Subclass

**Triggers when:** an inner `private static class {X}ConfigurationProperties extends BidderConfigurationProperties` (or a separate `{X}BidderConfigurationProperties.java` file) is added or modified.

This is Rule 35: typed-config subclass for bidders that need extra config fields beyond the framework default. **Canonical case: Kobler's `dev-endpoint`** (the Java port promoted Go's hardcoded `DEV_ENDPOINT` constant into Spring config). When this skill detects Rule 35 surface, also surface the cross-language port concern: this subclass is the Java-side resolution of the source spec's `hardcoded-config-as-anti-pattern` quirk.

1. **Existence emission rule**: This file/inner-class is emitted ONLY when the source spec carries `cross_language.go_specific_concerns[]: hardcoded-config-as-anti-pattern` (Kobler-style typed-config promotion). For new-adapter PRs without a prior source spec, the subclass is created when the bidder needs config beyond the framework defaults (operator-supplied fields like `dev-endpoint`, `platform-id`, `iab-categories`, `extra-info`).
2. **Extends `BidderConfigurationProperties` (the base)**: Subclass MUST extend the base class from `org.prebid.server.spring.config.bidder.model.BidderConfigurationProperties`. Other parent classes are **FAIL** — Spring will not bind correctly.
3. **Lombok `@Data` + `@NoArgsConstructor` + `@EqualsAndHashCode(callSuper = true)` presence**:
   - `@Data` is REQUIRED — Spring's bean form needs setters. `@Value` (immutable) is **FAIL**.
   - `@NoArgsConstructor` is REQUIRED — Spring needs the default constructor.
   - `@EqualsAndHashCode(callSuper = true)` is REQUIRED — without `callSuper = true`, the equals/hashCode would ignore base-class fields. Missing or `callSuper = false` is **WARN** (correctness issue; rarely test-observable).
   - `@Validated` (Spring) is REQUIRED on the subclass when any field declares jakarta validation annotations. Optional otherwise (canonical: present on KoblerConfigurationProperties and RubiconConfigurationProperties).
4. **Field-level annotations**:
   - `@NotBlank` on required `String` fields. Canonical: Kobler's `private String devEndpoint` has `@NotBlank` — the dev URL is REQUIRED when this subclass is used.
   - `@NotNull` on required object fields. Canonical: Rubicon's `private XAPI xapi = new XAPI()` has `@NotNull` plus `@Valid` to cascade validation into the nested type.
   - `@Min` / `@Max` on numeric fields with declared ranges. Use when the YAML semantics demand a range.
   - All annotations come from `jakarta.validation.constraints.*` (NOT `javax.validation.*` — javax is the pre-Java-9 namespace and will not compile in current upstream).
5. **F-new-59 import group order**: The Lombok `@Data` import block follows the canonical 3-group order: external libraries (lombok.*, org.springframework.*, org.prebid.server.*) → blank line → `java|jakarta` imports. Already template-fixed in current SKILLs; flag as **FAIL** if hand-authored PR has them out of order (checkstyle ImportOrder will catch it).
6. **Cross-skill consistency**:
   - When this subclass declares `@NotBlank private String devEndpoint`, the YAML's `adapters.{x}` MUST declare `dev-endpoint:` with a non-empty value. Missing YAML key when subclass requires the field: **FAIL** — Spring's `@NotBlank` validation fails at startup.
   - When this subclass declares fields beyond `BidderConfigurationProperties` base, those field names (camelCase) MUST have matching kebab-case keys in the YAML. Spring's relaxed-binding handles the case conversion. Mismatch: **FAIL** (silent default).
7. **R5 / Rule 35 cross-language emission rule**: When `prior_source_spec` declares `cross_language.go_specific_concerns: [hardcoded-config-as-anti-pattern]` AND the Java PR introduces this subclass, this is the EXPECTED port resolution — flag as **info** with note: "Rule 35 typed-config promotion (Go-side hardcoded constant → Java Spring config)". When the source spec does NOT declare the concern but the Java PR introduces a typed subclass, the subclass is operator-driven (not a port resolution) — review on its own merits.

### Workflow: Import Order Pre-Check

**Triggers when:** any added Java line in `{X}Configuration.java` or `{X}BidderConfigurationProperties.java` is an `import ...;` statement.

The checkstyle `ImportOrder` rule enforces a 3-group structure: external libraries → blank line → `java|jakarta` imports. This is the F-new-58/59 trap zone: the port-go2java template historically emitted imports in incorrect order.

1. **3-group structure**: Verify added imports do not interleave groups. The canonical order:
   ```java
   import lombok.Data;                                           // group 1: external
   import org.prebid.server.bidder.BidderDeps;
   import org.prebid.server.bidder.{x}.{X}Bidder;
   import org.springframework.context.annotation.Bean;
                                                                  // blank line
   import jakarta.validation.constraints.NotBlank;               // group 2: java|jakarta
   import java.util.List;
   ```
2. **No `*` star imports** (checkstyle `AvoidStarImport`). Always import specific classes. Star is **FAIL**.
3. **No banned imports**:
   - `io.vertx.core.json.Json` BANNED via `BanVertxJsonImport` — must use `JacksonMapper`. **FAIL**.
   - `org.junit.Test` BANNED — must use `org.junit.jupiter.api.Test`. **FAIL** (more applicable to test files; flagged here when the Configuration file accidentally imports it).
   - `org.apache.commons.lang` BANNED — use `lang3` instead. **FAIL**.
4. **Unused imports** (checkstyle `UnusedImports processJavadoc=true`). If the diff adds an import but no use in the same diff, fetch the full file to verify. **FAIL** when unused.
5. **F-new-58 (BidderDeps import group order)**: Already template-fixed in current SKILLs. If a hand-authored PR has the BidderDeps import in the wrong group, flag as **FAIL**.

### Workflow: Class-Filename Match

**Triggers when:** the `public class {Name}` line is added or modified in any Configuration / BidderConfigurationProperties file.

This is the **F-new-79 trap** zone: checkstyle's `OuterTypeFilename` requires the public class declared at file root to match the filename root.

1. **Match check**: For file `{X}Configuration.java`, the declaration MUST be `public class {X}Configuration { ... }`. For file `{X}BidderConfiguration.java`, the declaration MUST be `public class {X}BidderConfiguration { ... }`. For file `{X}BidderConfigurationProperties.java` (separate file form), the declaration MUST be `public class {X}BidderConfigurationProperties { ... }`. Mismatch is **FAIL** — checkstyle will fail at CI.
2. **Inner class names**: Inner `private static class` declarations (the Rule 35 subclass typically) are NOT bound by OuterTypeFilename. Free-form. Canonical: `KoblerConfigurationProperties` lives as an inner class inside `KoblerConfiguration.java` at file scope.
3. **Multiple public top-level classes**: A `.java` file can contain only one public top-level class. Multiple public top-level classes are **FAIL** (Java compile error).
4. **Generic class names (Java edge case #26 / #27)**: Java identifier rules require the class name start with a letter and contain only letters/digits/underscore. TitleCase acronym preservation: canonical `AaxConfiguration` (not `AAXConfiguration`), `OneFiveTwoMediaConfiguration` (not `152MediaConfiguration` — illegal Java identifier). Misnaming surfaces here.

---

## Cross-Field Validation Rules

After reviewing individual fields, verify these cross-field constraints. Apply ONLY when the cross-referenced fields are touched in the same PR or one of them is being added/changed and depends on an existing unchanged field:

1. **YAML `adapters.{x}` key ↔ `{X}Configuration.java` BIDDER_NAME constant**: MUST match (lowercase). Drives every Spring binding.
2. **YAML `endpoint:` macros ↔ `resolveEndpoint(...)` substitutions**: Every `{{TOKEN}}` in the YAML endpoint that uses framework-level macros (like `{{PREBID_SERVER_ENDPOINT}}`) MUST have a matching substitution in the Configuration class's `resolveEndpoint` method. Per-bidder template tokens (like `{{adUnitId}}`) are NOT resolved by the Configuration class — they pass through to the adapter and are resolved by `{X}Bidder.java` (cross-skill READ).
3. **`@Bean("{x}ConfigurationProperties")` name ↔ `bidderDeps(...)` parameter name**: MUST match. Spring autowires by name.
4. **`@ConfigurationProperties("adapters.{x}")` prefix ↔ YAML wrapper key**: MUST match. Spring binds zero fields on mismatch.
5. **`resolveEndpoint` declared ↔ `bidderCreator` lambda uses it**: If the helper is declared, the lambda MUST call it. Otherwise dead code (and macro leaks).
6. **Rule 35 subclass declared ↔ `@Bean` return type ↔ `.withConfig` parameter type**: All three MUST reference the same subclass.
7. **Rule 35 subclass field `@NotBlank` ↔ YAML field present + non-empty**: Spring validation will fail at startup if the YAML field is missing.
8. **YAML capabilities ↔ `{X}Bidder.java`'s handled media types**: Cross-skill READ; this skill records the YAML side, bidder-class-pr-review owns the code-side check.
9. **YAML aliases ↔ `test-application.properties` registry entries**: Cross-skill READ; pr-triage-java owns the registry check, this skill records the YAML side.
10. **YAML usersync GPP macros (implicit GPP-support signal)**: When `{{gpp}}` / `{{gpp_sid}}` appear in usersync URLs, the bidder is implicitly claiming GPP support — verify against source-spec's `gpp-supported` claim (Go side). There is NO Java `ortb.gpp-supported` boolean to flip. Macros-without-source-spec-claim: **INFO**; source-spec-claim-without-macros: **WARN**.
11. **Alias endpoint macros ↔ parent's `resolveEndpoint` capability**: Every `{{TOKEN}}` in an alias's overridden endpoint MUST be a token the parent's `resolveEndpoint` resolves OR a per-bidder template token the parent's `{X}Bidder` consumes. Otherwise the literal leaks. (Cross-skill concern 5a from pr-triage-java.)
12. **`white-label-only: true` + alias presence**: When parent declares `white-label-only: true` (Java kebab-case key), an `aliases:` block MUST be present (it's the whole point). Empty `aliases:` block on a whitelabel parent: **WARN**.

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

**Fetch full file from PR branch (for modified Java files requiring full-file context):**
```bash
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/{head_sha}/{filename}"
```

**Fetch bidder-class for cross-skill F-new-57 constructor-arg verification:**
```bash
curl -sS "https://raw.githubusercontent.com/prebid/prebid-server-java/{head_sha}/src/main/java/org/prebid/server/bidder/{x}/{X}Bidder.java"
```

---

## Cross-Skill References (Read-Only)

This skill reads files from sibling skills for context. It does NOT create review tasks for them.

- **`bidder/{x}/{X}Bidder.java`** — to verify the `bidderCreator` lambda's constructor arg list matches `{X}Bidder`'s actual constructor signature (the F-new-57 trap). Owned by `bidder-class-pr-review`.
- **`static/bidder-params/{x}.json`** — to verify `meta-info.{app,site}-media-types` alignment with what the schema allows. Owned by `bidder-params-java-pr-review`.
- **`test-application.properties`** — to verify aliases declared in YAML have matching IT-registry entries. Owned by `pr-triage-java`.
- **`{X}BidderTest.java`** — to verify unit tests cover any changed config fields (cross-skill READ for completeness; bidder-class-pr-review owns the test review).

The reciprocal direction (other skills reading THIS skill's files) is documented in those skills' SKILL.md.

---

## Sibling Skills + Design Doc + Read Companion

- [`pr-triage-java/SKILL.md`](../pr-triage-java/SKILL.md) — orchestrator emitting the routing manifest this skill consumes
- [`bidder-class-pr-review/SKILL.md`](../bidder-class-pr-review/SKILL.md) — adapter class + IT class + unit-test review
- [`bidder-params-java-pr-review/SKILL.md`](../bidder-params-java-pr-review/SKILL.md) — JSON Schema + ExtImp{X} POJO + IT-fixture review
- [`../shared/framework-utilities-java.md`](../shared/framework-utilities-java.md) — review-side framework utilities (LANDED in this PR, step 2, commit `63be93d`); read-side companion at [`../../../read/skills/shared/framework-utilities-java.md`](../../../read/skills/shared/framework-utilities-java.md)
- [`../../../read/skills/read-bidder-config/SKILL.md`](../../../read/skills/read-bidder-config/SKILL.md) — read-side companion that EXTRACTS the same YAML surface this skill REVIEWS (round-trip: read populates `bidder_info` block; review verifies PR diff against that block when persisted)
- [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) — design contract (§5 Java framework conventions, §8 open questions; this skill locks down Q2 typed-subclass ownership as "owned by bidder-config-pr-review per inner-class-or-separate-file convention" and Q4 alias-only detection heuristic as "alias hunk inside parent YAML's `aliases:` block")
