# Source Modes (Java)

Three modes for reading `prebid-server-java` files at a specific commit. Auto-detect default, with explicit override via `--source-mode`. The orchestrator records the chosen mode in `provenance.source.fetch_method`.

## Modes

### `local`

Read from a local checkout of `prebid/prebid-server-java`. Fastest; no rate limits.

- Discovery rule: orchestrator probes for a checkout at `${PREBID_JAVA_REPO:-$HOME/Documents/GitHub/prebid-server-java}` (or per user config).
- Resolves `--ref=branch=master` via `git -C <repo> rev-parse master`.
- For non-master refs, `git fetch origin <ref>` first if not already present locally; warn and fall back to `gh-cli` if fetch fails.
- File reads use direct filesystem access; `git -C <repo> show <sha>:<path>` for non-current commits.
- All reads MUST be at the resolved commit SHA — even if the working tree has uncommitted changes, the orchestrator reads via `git show`, never the working tree.

### `github-raw`

Curl `raw.githubusercontent.com/prebid/prebid-server-java/{sha}/{path}`. Works for any ref; rate-limited unauthenticated (60/hr/IP).

- Resolves `--ref` via `https://api.github.com/repos/prebid/prebid-server-java/commits/{ref}` first to get the 40-char SHA.
- Each file read is a separate HTTPS GET. Cache responses keyed by `(sha, path)` to avoid redundant fetches across the orchestrator's 3 readers.
- Tree listing (for discovering all files in a directory like `proto/openrtb/ext/request/{xyz}/`) requires `https://api.github.com/repos/prebid/prebid-server-java/git/trees/{sha}?recursive=1`. Tree responses are large; orchestrator filters by prefix.
- Falls back to `gh-cli` if rate-limited (HTTP 403 + `X-RateLimit-Remaining: 0`).

### `gh-cli`

Use `gh api` for both tree listing and content fetch. Authenticated rate limit (5000/hr); supports private repos and forks. Required for forks of prebid-server-java.

- Resolves `--ref`: `gh api repos/prebid/prebid-server-java/commits/{ref} --jq .sha`.
- Tree listing: `gh api 'repos/prebid/prebid-server-java/git/trees/{sha}?recursive=1' --jq '.tree[] | select(.path | startswith("src/main/java/org/prebid/server/bidder/{xyz}/")) | .path'`.
- Content fetch: `gh api 'repos/prebid/prebid-server-java/contents/{path}?ref={sha}' --jq '.content' | base64 -d`.
- Larger blobs (>1MB) hit the contents API limit; fall back to `gh api repos/.../git/blobs/{sha}`.

### `auto`

Default mode. Selects by probing in this order:

1. If `--ref` is `branch=master` or omitted AND a local checkout exists at the configured path AND the local `master` SHA matches GitHub's current `master` (via `gh api repos/prebid/prebid-server-java --jq .default_branch` + a `git fetch --dry-run`), use `local`.
2. Else if `gh` is on `PATH` and `gh auth status` reports authenticated, use `gh-cli`.
3. Else use `github-raw`.

The auto policy can be overridden per invocation. CI environments typically force `gh-cli` for predictable rate limits.

## Ref types

`--ref=` accepts one of four forms; default is `branch=master`.

| Form | Example | Resolution |
|---|---|---|
| `branch=<name>` | `branch=master` | `git rev-parse <name>` (local) or commits API (`branch:<name>` ref). |
| `commit=<sha>` | `commit=69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` | Used directly; no resolution. SHA can be 40-char or 7+ char prefix; orchestrator expands prefix via `git rev-parse` (local) or commits API (network). |
| `pr=<N>` | `pr=3684` | Resolves to `pulls/{N}.head.sha` (NOT `merge_commit_sha`). The spec captures the PR's contributor branch state, not the post-merge state. |
| `tag=<vX.Y.Z>` | `tag=3.41.0` | `git rev-parse refs/tags/<tag>^{commit}` (local) or commits API with `tag:<name>` ref. |

## Resolution edge cases

- **Force-pushed PR**: a PR's `head.sha` can change between two reads if the contributor force-pushed. Orchestrator records the resolved SHA in `provenance.source.resolved_commit`; round-trip determinism (R4) is per-SHA, not per-ref.
- **Merged PR**: after merge, `pulls/{N}.head.sha` may be detached. Resolution still works via the commits API.
- **Closed unmerged PR**: `head.sha` may be force-deleted. Resolution fails with HTTP 404; orchestrator emits `ref-resolution-failure` and aborts.
- **Tag annotated vs lightweight**: annotated tags resolve to a tag object, not a commit; the orchestrator dereferences via `^{commit}` (local) or accepts whatever the commits API returns (which de-references implicitly).
- **`master` rename**: prebid-server-java uses `master` (NOT `main`). If upstream renames to `main`, the orchestrator's default `branch=master` will fail; users must pass `--ref=branch=main` explicitly. This is documented as a known regression hazard.

## Recording in `provenance`

The orchestrator emits:

```yaml
provenance:
  source:
    repo: prebid/prebid-server-java
    ref:
      branch: master                            # OR commit, pr, tag — exactly one.
    resolved_commit: 69b1993c39ed3212ca63012a8c0924fdfa0b5d4a
    fetch_method: gh-cli                        # The mode actually used (auto resolves to a concrete value).
```

The `ref` block carries the user-provided ref form, NOT the resolved SHA. `resolved_commit` is always populated; downstream consumers compare against it for determinism.

## Sources

- Canonical schema: `../../../../../prebid-server-go/read/skills/shared/adapter-spec.md` (provenance section).
- Sibling Go skill: `../../../../../prebid-server-go/read/skills/read-adapter-orchestrator/references/source-modes.md` (when authored — same content shape).
