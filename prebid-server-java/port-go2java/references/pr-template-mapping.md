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

## 4. PR body — checkbox population

The upstream template carries a checklist the port skill auto-populates against the source spec. Each line below is reproduced from the upstream template; the algorithm column shows how the port skill decides `[x]` vs `[ ]`.

| Checklist line | Algorithm |
|---|---|
| `[x] I followed the porting guide` | Always `[x]` when port-report exists. |
| `[x] My PR title follows the convention 'Port {Bidder}: ...'` | Always `[x]` when `recommended_pr_title` matches the Section 2 form. |
| `[x] I added the bidder to test-application.properties` | Always `[x]` (port skill emits this append per `java-artifact-shapes.md` §10). |
| `[x] My adapter has integration tests` | `[x]` iff the port skill emitted at least one IT-test fixture pair under `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/`. |
| `[x] My adapter implements proper error handling` | `[x]` iff the source spec's `code.make_bids.http_status_handling.kind == "canonical-go-helpers"` (Rule 30 satisfied) AND the source has at least one error-path fixture in `tests.fixture_inventory.supplemental[]`. |
| `[x] My adapter passes coverage threshold` | `[x]` IFF the port skill's emit-side Jacoco run (per [`java-artifact-shapes.md`](java-artifact-shapes.md) §13) reports ≥ 90%. The port skill MUST run this gate before populating the checkbox. |
| `[ ] If currency_conversion: Required currency feature` | `[x]` iff source spec's `currency_conversion.used == true`. |
| `[ ] If gvl_vendor_id: Documented` | `[x]` iff source spec's `bidder_info.gvl_vendor_id != null`. |
| `[ ] If user_sync: Documented in bidder docs` | `[x]` iff source spec's `bidder_info.user_sync != null`. |
| `[x] I added the bidder to the bidders.yaml` | Maps to `src/main/resources/bidder-config/{bidder}.yaml` create — always `[x]` for new-bidder ports. |
| `[x] I created the documentation page` | `[x]` IFF `port-report.json::companion_docs_pr_draft` is non-null (i.e., the port skill emitted the docs PR draft). |

The `[x]` marks must be FACTUALLY accurate — operators reading the PR see the boxes pre-checked and skip detailed verification of those items. Templates that lie about the state of the port lose maintainer trust.

## 5. PR body — narrative sections

The upstream template has three free-text sections. The port skill auto-populates each from spec data:

### Description

```markdown
## Description

Ports the {Bidder} adapter from prebid-server (Go) to prebid-server-java
(this repo). Source upstream PR: {source_pr_url}; merged at
{source_pr_merged_commit_sha}. Port-translation-rules version
{port_translation_rules_version} applied; {N} rules emitted "applied"
verdict (see port-report.json `rules_consumed[]` for the full list).

R5-strict cross-language equivalence at port time: state={r5_check.state}.
{r5_check.summary or "All R5 strict-key fields match between source spec and emitted Java spec."}
```

### Test Plan

```markdown
## Test Plan

- mvn -B compile --file extra/pom.xml: passes
- mvn -B checkstyle:check: passes
- mvn -B test -Dtest={Bidder}BidderTest: passes
- Jacoco line-coverage on {Bidder}Bidder.java: {N}% (≥ 90% required)
- {Bidder}Test integration test scenarios: {list of fixture pair names}
```

### Notes for reviewers

```markdown
## Notes for reviewers

{For each port-report.json::human_todos[] entry:}
- {category}: {summary}
{For each port-report.json::source_discussion_anchors[] entry:}
- Source-side context: {url} ({load_bearing_for})
```

## 6. Companion docs PR (`prebid/prebid.github.io`)

Maintainer-mandatory per BeOp #4660 review pattern. The port skill emits `port-report.json::companion_docs_pr_draft` populated against the source spec:

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

If conflicts surface (e.g., upstream PR #4126 URL validation lands between port-emit and PR-open), abort with operator notification and let the operator resolve before submit. See [`../../../docs/methodology/repo-rules.md`](../../../docs/methodology/repo-rules.md) "In-flight upstream changes" for current PRs in flight.

## See also

- [`java-artifact-shapes.md`](java-artifact-shapes.md) — what the emitted Java files must look like (precondition for the checkbox population to be honest).
- [`registration-rules.md`](registration-rules.md) — what files the port skill writes; drives the "added to test-application.properties" checkbox.
- [`../../../prebid-server-go/read/skills/shared/port-report.schema.json`](../../../prebid-server-go/read/skills/shared/port-report.schema.json) — the contract for `recommended_pr_title`, `target_pr_label_recommendations[]`, `companion_docs_pr_draft`, `pre_submit_rebase`.
