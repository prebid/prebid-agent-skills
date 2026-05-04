# Source Modes

How the orchestrator fetches files from `prebid/prebid-server`. Three modes — `local`, `github-raw`, `gh-cli` — plus an `auto` policy that selects between them. This file is the canonical decision tree, ref-resolution table, and auth-handling reference for the read-adapter-orchestrator skill.

The mirrored Java sibling (`prebid-server-java/read/skills/read-bidder-orchestrator/references/source-modes.md`) follows the same structure with `prebid-server-java` substituted for `prebid-server`.

> **Reuse note**: The pr-triage skill's Step 1 (data fetching via `curl` and `gh`) and Step 2 (drift checks via raw fetch) establish the source-mode dispatch pattern this skill mirrors. See [`../../../../review/skills/pr-triage/SKILL.md`](../../../../review/skills/pr-triage/SKILL.md) for the original. The differences: pr-triage targets a single PR's files; this skill targets the full file tree of one bidder at a frozen commit.

---

## Mode summary

| Mode | What it does | Speed | Auth | Best when |
|---|---|---|---|---|
| `local` | Reads from a local `prebid-server` checkout under the user's filesystem. Resolves refs via `git rev-parse`. | Fastest. No network. | None. | The user has a clone AND ref is `master` (or omitted). |
| `github-raw` | Fetches files via `https://raw.githubusercontent.com/prebid/prebid-server/<sha>/<path>` (curl). Lists directories via `https://api.github.com/repos/prebid/prebid-server/git/trees/<sha>?recursive=1` (curl). | Medium. Network round-trips per file. | Anonymous (60 req/hr unauthenticated; 5000 req/hr with `GITHUB_TOKEN`). | No local clone AND `gh` is not installed/authed; or for any non-master ref when local clone is on master. |
| `gh-cli` | Uses `gh api` for tree listing (`gh api repos/prebid/prebid-server/git/trees/<sha>?recursive=1 --paginate`) and content fetch (`gh api repos/prebid/prebid-server/contents/<path>?ref=<sha> --jq .content`). | Medium. Same network roundtrips as `github-raw` but auto-paginated. | gh CLI auth (5000 req/hr authenticated; supports private forks). | `gh auth status` passes; needed for private forks; preferred for any non-master ref when local clone is on master. |
| `auto` | Picks one of the above per the policy below. | Mode-dependent. | Mode-dependent. | Default — let the skill choose. |

---

## Auto policy (decision tree)

The orchestrator runs this decision tree at Step 1 ref resolution to pick the actual source-mode:

```
1. Is `--source-mode` explicitly set?
     yes → use it (skip the rest of the tree)
     no  → continue

2. Is `LOCAL_PREBID_SERVER_PATH` env var set OR is `~/Documents/GitHub/prebid-server` a git repo?
     no  → goto step 5
     yes → continue

3. Is the requested ref `branch=master` or omitted?
     yes → continue
     no  → goto step 5    # local clone may not have the ref checked out

4. Run `git -C <local-path> rev-parse --quiet --verify <ref-or-master>`.
     ok  → use `local` mode (record `provenance.source.fetch_method: local-checkout`)
     err → goto step 5

5. Run `gh auth status` (suppress stderr).
     ok  → use `gh-cli` mode (record `provenance.source.fetch_method: gh-cli`)
     err → goto step 6

6. Use `github-raw` mode (record `provenance.source.fetch_method: github-raw`).
     This is the no-auth fallback. Note rate limit (60 req/hr unauth) — if the bidder
     has a multi-file layout, the orchestrator may hit the limit and fail step 5 dispatch.
     In that case, advise the user to install/auth `gh` or set `GITHUB_TOKEN`.
```

The chosen mode is reported on `provenance.source.fetch_method` in the emitted spec so consumers know which path produced the bytes.

### Why local-only-on-master

A local clone may have arbitrary state (uncommitted changes, detached HEAD, an old `master`). The orchestrator only trusts `local` mode when the requested ref resolves cleanly via `git rev-parse`. For non-`master` refs (a PR head SHA, a tag, an arbitrary commit), the local clone may not have the commit at all, so the orchestrator falls back to `gh-cli`/`github-raw` which always have the full history.

If the user has a local clone with `master` checked out at the commit they want to read, `auto` picks `local` (zero network). If they pass `--ref=pr=4214` and the local clone hasn't fetched that PR, `auto` falls back to `gh-cli` (or `github-raw` if no auth).

---

## Ref resolution per mode

The orchestrator resolves the user-supplied `--ref=<spec>` into a 40-char `resolved_commit` BEFORE any file is fetched. The spec is frozen at this commit.

### Ref types

| Form | Example | Resolution semantics |
|---|---|---|
| `branch=<name>` | `branch=master` (default) | Branch HEAD at read time. May change between reads — the orchestrator resolves it ONCE and pins. |
| `commit=<sha>` | `commit=d7f8515b...` | Verbatim if 40-char hex. The orchestrator validates length+hex; rejects shorter forms (no auto-expansion of 7-char shortshas — too ambiguous; require the full 40 chars). |
| `pr=<N>` | `pr=4214` | PR head.sha (NOT base.sha — captures the proposed state). |
| `tag=<vX.Y.Z>` | `tag=v4.1.0` | Annotated tag → dereferenced to commit; lightweight tag → direct commit. |
| (omitted) | — | Treat as `branch=master`. |

### Per-mode resolution commands

| Ref form | local | gh-cli | github-raw |
|---|---|---|---|
| `branch=master` | `git -C <path> rev-parse master` | `gh api repos/prebid/prebid-server/branches/master --jq .commit.sha` | `curl -sS https://api.github.com/repos/prebid/prebid-server/branches/master \| jq -r .commit.sha` |
| `branch=<other>` | `git -C <path> rev-parse <name>` (must exist locally) | `gh api repos/prebid/prebid-server/branches/<name> --jq .commit.sha` | `curl -sS https://api.github.com/repos/prebid/prebid-server/branches/<name> \| jq -r .commit.sha` |
| `commit=<sha>` | accept verbatim if 40-hex | accept verbatim | accept verbatim |
| `pr=<N>` | NOT supported in local mode (PR not necessarily in local clone) — fall back to `gh-cli` or `github-raw` | `gh pr view <N> --repo prebid/prebid-server --json headRefOid --jq .headRefOid` | `curl -sS https://api.github.com/repos/prebid/prebid-server/pulls/<N> \| jq -r .head.sha` |
| `tag=<vX.Y.Z>` | `git -C <path> rev-parse <tag>^{commit}` | `gh api repos/prebid/prebid-server/git/refs/tags/<tag> --jq '.object.sha'` then dereference if `.object.type == "tag"` | `curl -sS https://api.github.com/repos/prebid/prebid-server/git/refs/tags/<tag> \| jq -r .object.sha` (then a second call to dereference annotated tags) |

### Validation after resolution

After resolution the orchestrator:

1. Verifies the resolved SHA is 40-char lowercase hex.
2. Records both forms on the spec: `provenance.source.ref` (the user-supplied form) AND `provenance.source.resolved_commit` (the 40-char SHA). Both are required.
3. Cross-checks via a one-shot `gh api repos/prebid/prebid-server/commits/<sha>` (or `git cat-file -e <sha>^{commit}` for local) to confirm the commit exists in the repository. Failure here is a hard error.

---

## Auth handling

### `local` mode

No auth required. The orchestrator reads files via the filesystem. Behavior:

- Reads `LOCAL_PREBID_SERVER_PATH` env var. If unset, defaults to `~/Documents/GitHub/prebid-server`.
- If the directory is not a git repo, fall back to `gh-cli`/`github-raw`.
- The orchestrator does NOT modify the local clone (no fetches, no checkouts). It reads raw bytes from `<path>/static/bidder-info/<bidder>.yaml`, `<path>/adapters/<bidder>/*.go`, etc., resolving all paths relative to the resolved commit using `git show <sha>:<path>` so uncommitted local changes are NOT leaked into the spec.

### `gh-cli` mode

Requires `gh` CLI installed and authenticated. Behavior:

- The orchestrator runs `gh auth status` once at startup. Failure → fall back to `github-raw`. Warning emitted: `provenance.warnings[]` of type `auth-fallback` (informational only).
- Authenticated rate limit: 5000 req/hr (vs 60 unauth for `github-raw`).
- Supports private forks — useful when reading a fork's PR before merge.
- Tree listing is auto-paginated via `--paginate`. Content fetches one file at a time via `gh api repos/prebid/prebid-server/contents/<path>?ref=<sha> --jq .content` (base64-decoded by `jq`).

### `github-raw` mode

No auth strictly required, but `GITHUB_TOKEN` env var dramatically helps. Behavior:

- Anonymous: 60 req/hr. Multi-file adapter (msft, mediasquare, appnexus) easily exhausts this on a single read.
- Authenticated (`Authorization: Bearer $GITHUB_TOKEN`): 5000 req/hr. The orchestrator passes the header on every curl when the env var is set.
- Tree listing: `curl -sS "https://api.github.com/repos/prebid/prebid-server/git/trees/<sha>?recursive=1"`. Note: the GitHub Tree API truncates at 100k entries; for prebid-server (current ~5k entries) this is not an issue, but the orchestrator inspects the `truncated` field in the response and falls back to per-directory listing if true.
- Content fetch: `curl -sS "https://raw.githubusercontent.com/prebid/prebid-server/<sha>/<path>"`. This is the canonical raw-content path; bytes are returned verbatim with no API processing.
- The orchestrator NEVER uses `WebFetch` for bytes — `WebFetch` summarizes content through a model and would corrupt the verbatim `bidder_params_json` contract. Same rule as pr-triage.

---

## Failure escalation

The orchestrator handles fetch failures in priority order:

1. **Resolved-commit invalid (404 on commit lookup)**: hard error. Cannot proceed; the spec must reference a valid commit.
2. **Required file missing at resolved commit**: hard R1 error. The orchestrator emits the partial spec UP TO the missing file and aborts.
3. **Optional file missing**: field nulled on the spec, paired `incomplete-classification` quirk emitted, paired `provenance.warnings[]` entry of type `incomplete-classification` recorded. Read continues.
4. **Rate-limit exceeded (github-raw mode)**: emit `provenance.warnings[]` of type `rate-limit-exceeded` with the `X-RateLimit-Reset` timestamp from the response header; abort. Suggest the user set `GITHUB_TOKEN` or `gh auth login`.
5. **gh CLI auth failure mid-read**: emit `provenance.warnings[]` of type `auth-fallback` and switch to `github-raw` mode. The fetch_method on the emitted spec reflects whichever mode succeeded.
6. **Network timeout**: retry with exponential backoff (3 attempts, 2s/4s/8s). After three failures, abort with hard error.
7. **Local-mode `git show` failure**: a corrupt or shallow clone may not have all blobs. Fall back to `gh-cli`/`github-raw` and emit a `local-clone-shallow` warning.

---

## Mode-specific edge cases

### `local` mode + uncommitted changes

The orchestrator uses `git show <sha>:<path>` (NOT direct filesystem reads of working-tree files). This guarantees the bytes captured match the commit, regardless of uncommitted changes in the working tree. If the user wants to spec their working tree (not a commit), they must commit first OR use `--source-mode=github-raw` against a published branch.

### `local` mode + LFS-tracked files

prebid-server does not use Git LFS for adapter files. If an LFS-tracked file appears (unlikely), `git show` returns the LFS pointer text, not the content. The orchestrator detects this via the `version https://git-lfs.github.com/spec/v1` magic string and falls back to `gh-cli`/`github-raw`.

### `gh-cli` mode + repo rename

If `prebid/prebid-server` is renamed (unlikely), `gh api` will 404. The orchestrator does not auto-discover renames; the user must update the canonical repo path in the orchestrator config.

### `github-raw` mode + branch name with slash

Branch names may contain slashes (e.g., `feature/foo`). URLs with slashes work for `https://raw.githubusercontent.com/prebid/prebid-server/<branch>/<path>` (the slash is part of the ref portion, not a path separator) but the orchestrator resolves to a SHA before any content fetch, so this only affects the initial branch resolution call.

### Cross-mode consistency

The orchestrator's R4 round-trip determinism rule requires that re-running on the same `provenance.source.resolved_commit` produces a byte-identical YAML modulo timestamp/operator. This MUST hold across modes — fetching a file via `local`, `gh-cli`, or `github-raw` MUST return identical bytes (they do; all three are reading the same Git object). A mode mismatch producing different bytes is a serious bug — emit a hard error of type `cross-mode-byte-mismatch` to surface it.

---

## Recommended environment

For the best read experience, the user should:

- Install `gh` and run `gh auth login` once. This enables `gh-cli` mode for any non-master ref.
- Have a local clone at `~/Documents/GitHub/prebid-server` (or set `LOCAL_PREBID_SERVER_PATH`). This enables `local` mode for master reads — fastest path.
- Set `GITHUB_TOKEN` env var to a personal access token (no special scopes needed for public repos). This raises the unauthenticated 60 req/hr rate limit to 5000 req/hr for `github-raw` fallback.

The auto policy will pick the best mode given what's available. The user only needs to override with `--source-mode=...` when debugging or forcing a specific path.

---

## Sources

- The plan: (Claude Code planning artifact) — "Source modes" section: auto policy, ref types, the `local`/`github-raw`/`gh-cli` triad.
- Existing source-mode dispatch reused: [`../../../../review/skills/pr-triage/SKILL.md`](../../../../review/skills/pr-triage/SKILL.md) — Step 1c uses `gh api` for `head.sha` resolution; Step 2 uses `curl` for raw content. The "no WebFetch" rule and the choice of `curl` over WebFetch is canonical there.
- File-to-skill routing (used in Step 2 discovery): [`../../../../review/skills/pr-triage/references/routing-rules.md`](../../../../review/skills/pr-triage/references/routing-rules.md) — bidder name extraction rules, file pattern table.
- Framework utilities for module-path major-version drift: [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) — current major `v4` (verified at v4.1.0).
- Spec schema: [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md) — `provenance.source.{repo, ref, resolved_commit, fetch_method}` field definitions.
- prebid-server master: commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (v4.1.0, 2026-04-27).
