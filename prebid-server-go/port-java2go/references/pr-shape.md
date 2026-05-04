# PR shape (Go target)

Phase D1.3 deliverable — captures the convention for opening a Go-side new-adapter PR. Unlike the Java side (where upstream `prebid/prebid-server-java` ships `.github/pull_request_template.md`), the Go upstream `prebid/prebid-server` has **no PR template** — verified 404 on the conventional path.

## 1. Why no template? (research finding)

Real-PR audit across 50+ merged new-adapter PRs in `prebid/prebid-server` (years 2023-2026) shows zero PRs reference a template. Maintainers review against the contributor docs at [`prebid/prebid-server/docs/developers/`](https://github.com/prebid/prebid-server/tree/master/docs/developers) directly. Title and body conventions are observed empirically below.

Implication for the port skill: there is NO checkbox auto-population (no template → no checkboxes). The `port-report.json::target_pr_label_recommendations` defaults to `[]` (Go has no mandatory labels). The skill emits a free-text PR body driven by spec data.

## 2. PR title shape

For new-bidder ports: `New Adapter: {Bidder}`

The capitalization is consistent across observed merged PRs:
- `Adapter` is capitalized.
- `{Bidder}` matches the Go YAML name's natural case (lowercase for `kobler`, camelCase for `adkernelAdn`, mixed for `33across`).
- The colon is followed by exactly one space.

For alias-only ports: `New Alias: {AliasName} (parent: {ParentName})`

Less standardized; the port skill emits this shape and operators may adjust.

## 3. PR body convention

Distilled from real merged PRs (notably `kobler` PR #3904, `adverxo` PR #3921, recent zero-config adapters in 2026). The port skill emits:

```markdown
## Summary

This PR adds a Go bid adapter for {Bidder} ({biddercode}), ported from
prebid-server-java. Source upstream PR: {source_pr_url}; merged at
{source_pr_merged_commit_sha}.

Port-translation-rules version {port_translation_rules_version} applied;
{N} rules emitted "applied" verdict. R5-strict cross-language equivalence
at port time: state={r5_check.state}.

## Test Plan

- `go build ./adapters/{bidder}/...`: passes
- `gofmt -s -l ./adapters/{bidder}/...`: no diff
- `go vet ./adapters/{bidder}/...`: passes
- `go test ./adapters/{bidder}/...`: passes
- `TestBidderUniquenessGatekeeping`: passes (first-6-letter prefix unique)
- Adapter-coverage report (`./scripts/check_coverage.sh`): {N}% (≥ 80% real-world median; well above 30% CI minimum)

## Cross-language provenance

- Source spec (Java): {.tmp/full-loop/{run-id}/java/{bidder}.yaml}
- R5-strict comparison: see port-report.json::r5_check
- Lossy-direction items (per port-translation-rules.yaml Round-Trip Safety):
  {list of quirks emitted with category=hardcoded-config-as-anti-pattern,
   helper-collapse-to-explicit-expansion, etc.}

## Notes for reviewers

{For each port-report.json::human_todos[] entry:}
- {category}: {summary}
{For each port-report.json::source_discussion_anchors[] entry:}
- Source-side context: {url} ({load_bearing_for})
```

## 4. Companion docs PR (`prebid/prebid.github.io`)

Less maintainer-pressure than on the Java side, but expected for parity. Real-PR audit shows ~60% of new Go adapters ship a companion docs PR within 7 days of the code PR. The port skill emits `port-report.json::companion_docs_pr_draft` with the same shape as the Java target (see [`../../../prebid-server-java/port-go2java/references/pr-template-mapping.md`](../../../prebid-server-java/port-go2java/references/pr-template-mapping.md) §6).

## 5. Pre-submit rebase

Same protocol as Java target: rebase the target branch onto upstream `prebid/prebid-server` `master` HEAD immediately before opening the PR. Outcome captured in `port-report.json::pre_submit_rebase`:

```yaml
pre_submit_rebase:
  upstream_repo: prebid/prebid-server
  base_sha_at_emit: {sha}
  base_sha_at_submit: {sha}
  conflicts_detected: false
  conflicts_summary: null
```

If conflicts surface (e.g., upstream amends `adapters.IsResponseStatusCodeNoContent` signature between port-emit and PR-open), abort with operator notification.

## 6. Anti-patterns observed in declined PRs

Real-PR audit identified recurring reasons new-adapter PRs were declined or asked for revision. The port skill avoids these by construction:

- **Hardcoded URLs in code instead of YAML config**: `const endpoint = "https://..."` declared in `{bidder}.go` instead of read from `static/bidder-info/{bidder}.yaml`. (Rule 13 spec field; the port skill emits the YAML-driven form.)
- **Empty `params_test.go`**: file present but no actual test cases. The port skill emits at least one positive-path test from the source spec's `params.schema_interpretation.required_fields[]`.
- **Missing `MakeBids` error path coverage**: when the bidder returns 4xx/5xx, no test fixture exercises the response. The port skill carries over Java's IT-test error-path fixtures into `{bidder}test/supplemental/` (when reachable in Go; per Rule 36 inverse).
- **Forgetting to update `bidders.go` AND `adapter_builders.go`**: `port_engine.alphabetical_insert` writes both as part of Step 5.
- **Skipping `gofmt -s -w`**: `port_engine.gofmt_post_process` runs before any commit.
- **Brand-acronym Go constant naming inconsistency**: `BidderAJA` vs `BidderAja` — the port skill consults [`../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml`](../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml) for the canonical form.

## See also

- [`go-artifact-shapes.md`](go-artifact-shapes.md) — file naming, package conventions, Builder/MakeRequests/MakeBids skeleton (precondition for accurate Test Plan reporting).
- [`registration-rules.md`](registration-rules.md) — what files the port skill writes (drives "the bidder is registered" claim).
- [`porting-guide.md`](porting-guide.md) — the inverse porting guide; covers lossy-direction asymmetries that must be flagged in the PR's "Notes for reviewers" section.
- [`../../../prebid-server-go/read/skills/shared/port-report.schema.json`](../../../prebid-server-go/read/skills/shared/port-report.schema.json) — the contract for `recommended_pr_title`, `companion_docs_pr_draft`, `pre_submit_rebase`.
