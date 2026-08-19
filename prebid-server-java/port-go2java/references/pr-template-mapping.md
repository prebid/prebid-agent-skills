# PR-template auto-population (Java target)

Phase D1.3 deliverable — captures the upstream `prebid/prebid-server-java` PR template and the algorithm port-go2java uses to populate it from the source spec's behavioral fields. The output lands in `port-report.json::recommended_pr_title` + `target_pr_label_recommendations[]` plus a draft body used when the operator opens the PR.

## 1. Source-of-truth pinning

Upstream PR template: [`prebid/prebid-server-java/.github/pull_request_template.md`](https://github.com/prebid/prebid-server-java/blob/master/.github/pull_request_template.md). Last verified 2026-05-04 (per [`../../../docs/methodology/repo-rules.md`](../../../docs/methodology/repo-rules.md)).

Upstream porting guide that mandates this template: [`prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md`](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md) (PR #3768). The port skill version-pins to the porting guide's SHA — when upstream amends the template, the templates regenerate AND the SHA pin in `repo-rules.md` bumps in the same PR.

## 2. PR title shape

For new-bidder ports: `Port {Bidder}: New Adapter`

Where `{Bidder}` is PascalCase (matching the Java class root, e.g., `Kobler`, `AdkernelAdn`, `ThirtyThreeAcross`). The port skill computes the form from the source spec's `meta.bidder_name` (Go-side) routed through the Rule 46 mapping + the Java edge-case-#26 digit-leading rule.

For alias-only ports: `Port {AliasName}: New alias for {ParentName}`

The port skill emits the title to `port-report.json::recommended_pr_title`. The operator copies it verbatim when opening the PR.

## 3. PR labels

`target_pr_label_recommendations: ["do not port"]`

The `do not port` label is **mandatory** per upstream porting guide — it signals the prebid-server-java maintainers that this PR is the Java target of an upstream Go port (not a candidate for further porting downstream). Without the label, the maintainer-cohort treats the PR as a regular new-adapter contribution and may apply different review rigor.

For alias ports without a Java code change (new alias entry only on existing parent's YAML), `do not port` still applies — the convention is direction-agnostic.

## 4. PR body — checkbox population (faithful to live upstream template)

Live upstream `prebid/prebid-server-java/.github/pull_request_template.md` (verified 2026-05-04 against `master` HEAD) carries three checkbox sections plus three free-text sections. The port skill renders the template verbatim, populates the checkboxes per the algorithm tables below, and fills the free-text sections per §5.

The `[x]` marks must be FACTUALLY accurate — reviewers reading the PR see the boxes pre-checked and skip detailed verification of those items. Templates that lie about the state of the port lose maintainer trust.

### 4.1 `### 🔧 Type of changes`

11 boxes. New-adapter ports check exactly one:

| Upstream checkbox | Algorithm |
|---|---|
| `new bid adapter` | `[x]` for new-adapter ports (`port_run.target_branch` is null OR alias-only false). |
| `bid adapter update` | `[x]` for delta-ports only (out of MVP scope per execution-plan-phase-d.md "Out of scope"; deferred). |
| `new feature` | `[ ]` for ports. |
| `new analytics adapter` | `[ ]` (analytics modules are out of MVP scope). |
| `new module` | `[ ]` (general modules are out of MVP scope). |
| `module update` | `[ ]`. |
| `bugfix` | `[ ]`. |
| `documentation` | `[ ]`. |
| `configuration` | `[ ]`. |
| `dependency update` | `[ ]`. |
| `tech debt (test coverage, refactorings, etc.)` | `[ ]`. |

### 4.2 `### 🔎 New Bid Adapter Checklist`

6 boxes. The port skill populates each from spec evidence:

| Upstream checkbox | Algorithm |
|---|---|
| `verify email contact works` | `[x]` iff source spec's `bidder_info.maintainer.email` is non-null AND syntactically a valid email. The port skill emits the email verbatim into the Java `bidder-config/{bidder}.yaml`; the box claims maintainer-email-presence, not deliverability (which is a manual reviewer step). |
| `NO fully dynamic hostnames` | `[x]` iff source spec's `bidder_info.endpoint_construction.kind` is one of `static`, `single-token-substitution`, `dev-prod-toggle`, `query-parameter-augmentation`. Box stays `[ ]` if `kind: fully-dynamic-hostname` (the port skill rejects emit in that case anyway — Rule 11 prohibits). |
| `geographic host parameters are NOT required` | `[x]` iff source spec's `bidder_info.geoscope` does NOT include geographic-host substitution macros AND `bidder_info.endpoint_construction.macros_used[]` does not reference `${region}` / `{{Region}}`. Box stays `[ ]` if a geo-host macro is detected (per Rule 12 prose). |
| `direct use of HTTP is prohibited - implement an existing Bidder interface that will do all the job` | Always `[x]` for ports. The port skill emits a `Bidder<BidRequest>` implementation; direct `HttpClient` use does not appear in templated output. |
| `if the ORTB is just forwarded to the endpoint, use the generic adapter - define the new adapter as the alias of the generic adapter` | `[x]` iff the source spec is a pure-forwarding adapter (`code.make_requests.batching.rules == [{kind: single-batched}]` AND `code.make_requests.endpoint_resolution.kind: static` AND no imp-mutation). For most ports the source already had its own bidder code, so the box is `[ ]` — the port emits a real adapter. The template line is informational. |
| `cover an adapter configuration with an integration test` | `[x]` iff the port skill emitted at least one IT-test fixture pair under `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/` AND `src/test/java/org/prebid/server/it/{Bidder}Test.java` exists. |

### 4.3 `### 🏎 Quality check`

4 boxes:

| Upstream checkbox | Algorithm |
|---|---|
| `Are your changes following our code style guidelines?` | `[x]` iff `mvn -B checkstyle:check` exits 0 against the emitted tree. Templates emit checkstyle-compliant by construction (see [`java-artifact-shapes.md`](java-artifact-shapes.md)); D4.3 adds a pre-submit dry-run gate. |
| `Are there any breaking changes in your code?` | `[x]` (interpreted as "I have CHECKED for breaking changes"). New-adapter ports add code; they do not modify existing public APIs. The port skill verifies no edits land outside `src/main/java/org/prebid/server/bidder/{bidder}/`, the corresponding test paths, the `bidder-config/{bidder}.yaml`, the `bidder-params/{bidder}.json`, and the two-line `test-application.properties` append. |
| `Does your test coverage exceed 90%?` | `[x]` iff the port skill's emit-side Jacoco run on `{Bidder}Bidder.java` reports ≥ 90% line-coverage (per [`java-artifact-shapes.md`](java-artifact-shapes.md) §13). |
| `Are there any erroneous console logs, debuggers or leftover code in your changes?` | `[x]` (interpreted as "checked and there are NO leftovers"). The port skill emits via Jinja templates — operator-edited debug code does not appear in templated output. |

## 5. PR body — narrative sections (`✨`, `🧠`, `🧪`)

The upstream template has three free-text sections; the port skill auto-populates each from spec data.

### `### ✨ What's the context?`

```markdown
This PR ports the {Bidder} adapter from prebid-server (Go) to
prebid-server-java (this repo). Source upstream PR: {source_pr_url}
(merged at {source_pr_merged_commit_sha}). The Go-side {Bidder} adapter
has been live since that PR; this port brings the same bidder to the
Java codebase using port-translation-rules version
{port_translation_rules_version}, with {N} rules emitting "applied"
verdict (see `port-report.json::rules_consumed[]` for the full list).
```

### `### 🧠 Rationale behind the change`

```markdown
{Bidder} is requested by {bidder_info.maintainer.email}'s organization;
operating across {bidder_info.geoscope}. R5-strict cross-language
equivalence at port time: state={r5_check.state}.
{r5_check.summary or "All R5 strict-key fields match between source spec and emitted Java spec."}

Trade-offs documented in `port-report.json::human_todos[]` and
`upstream_bugs_to_file[]` (none for clean ports; one+ for
fail-source-omits-target-constraint or warn-target-strengthens-source
states).
```

### `### 🧪 Test plan`

```markdown
- `mvn -B compile --file extra/pom.xml`: passes
- `mvn -B checkstyle:check`: passes
- `mvn -B test -Dtest={Bidder}BidderTest`: passes
- Jacoco line-coverage on `{Bidder}Bidder.java`: {N}% (≥ 90% required by upstream Quality check)
- `{Bidder}Test` integration test scenarios: {list of fixture pair names}
- Pre-submit rebase against `master` at `{pre_submit_rebase.base_sha_at_submit}`: clean (no conflicts)

For source-side context: see `port-report.json::source_discussion_anchors[]`
({list of anchor URLs and load-bearing fields}).
```

## 5a. Additional rigor checks (beyond the template)

The upstream template's checks above are necessary but not sufficient — the porting guide at [`prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md`](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md) imposes additional narrative requirements not exposed as checkboxes. The port skill applies these as part of Step 5 emission AND surfaces evidence in the PR body's "Notes for reviewers" sub-section the operator pastes below the template:

```markdown
**Beyond the template — porting guide compliance**:

- Feature parity with Go source confirmed: source spec `code.*` blocks and
  emitted Java code structurally match (every `make_requests.batching.rules`
  entry, `endpoint_resolution.kind`, `make_bids.http_status_handling.kind`
  has its Java analog per port-translation-rules.yaml Rules 5, 11–12, 16–17,
  19–20, 30).
- Java adapter code uses framework utilities (BidderUtil, JacksonMapper,
  HttpUtil) per [`framework-utilities-java.md`](../../read/skills/shared/framework-utilities-java.md);
  no direct Vert.x JSON usage; no direct HttpClient usage.
- Specific rules and tips per the porting guide: bidder-params byte-fidelity
  (Rule 38 verified via `port_engine.byte_copy` SHA-256 check); naming
  normalization (Rule 46 + ADR-005); alias-empire flavor coherence (Rule 44
  if applicable); IAB-cat translation (Rule 42 if applicable).
- Companion docs PR drafted at `prebid/prebid.github.io::dev-docs/bidders/{bidder}.md`
  (recommended; see §6 for the evidence base); see `companion_docs_pr_draft`
  in port-report.json.
```

This sub-section is NOT part of the upstream template. The operator pastes it below the template's last checkbox. Reviewers benefit from the explicit linkage to the port-translation rules; if a maintainer asks for a different format, the port skill template at `../templates/pr-body.md.j2` can be amended in a future PR.

## 6. Companion docs PR (`prebid/prebid.github.io`)

Recommended companion artifact. Evidence base: the request is a **Go-repo**
review pattern (`prebid/prebid-server#4660`, BeOp, merged 2026-03-03 — a reviewer
asked for a documentation PR linked from the description). `prebid/prebid-server-java#4660`
does not exist, and no equivalent request appears on recent merged Java new-adapter PRs
(#4476 BeOp, #4502, #4428, #4310), so this is NOT a verified Java maintainer requirement.
Emit the draft as a courtesy and let the operator decide; do not assert it as mandatory in
the PR body. The port skill emits `port-report.json::companion_docs_pr_draft` populated against the source spec:

```yaml
companion_docs_pr_draft:
  target_repo: prebid/prebid.github.io
  file_path: dev-docs/bidders/{bidder}.md
  body_markdown: |
    ---
    layout: bidder
    title: {Bidder}
    description: Prebid {Bidder} Bidder Adapter
    biddercode: {bidder}
    ...
    ---

    ### Bid Params

    {Generated table from source spec's params.schema_interpretation.required_fields[] + properties}

    ### Configuration

    Endpoint: {bidder_info.endpoint}
    GVL ID: {bidder_info.gvl_vendor_id or "(none)"}
    Geoscope: {bidder_info.geoscope}
    Capabilities: {bidder_info.capabilities}
```

The operator submits the docs PR alongside the main PR (see [the porting guide](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md) for the exact submission protocol). Failure to ship the docs PR is a frequent reviewer-flagged issue; the port-report drafts the body so operator just-needs-to-submit.

## 7. Pre-submit rebase

The port skill MUST rebase the target branch onto upstream `prebid/prebid-server-java` `master` HEAD immediately before opening the PR. The outcome is captured in `port-report.json::pre_submit_rebase`:

```yaml
pre_submit_rebase:
  upstream_repo: prebid/prebid-server-java
  base_sha_at_emit: {sha}
  base_sha_at_submit: {sha}
  conflicts_detected: false
  conflicts_summary: null
```

If conflicts surface (an upstream PR touching bidder-config shape landing between port-emit and PR-open), abort with operator notification and let the operator resolve before submit. See [`../../../docs/methodology/repo-rules.md`](../../../docs/methodology/repo-rules.md) "In-flight upstream changes" for current PRs in flight.

## See also

- [`java-artifact-shapes.md`](java-artifact-shapes.md) — what the emitted Java files must look like (precondition for the checkbox population to be honest).
- [`registration-rules.md`](registration-rules.md) — what files the port skill writes; drives the "added to test-application.properties" checkbox.
- [`../../../prebid-server-go/read/skills/shared/port-report.schema.json`](../../../prebid-server-go/read/skills/shared/port-report.schema.json) — the contract for `recommended_pr_title`, `target_pr_label_recommendations[]`, `companion_docs_pr_draft`, `pre_submit_rebase`.
