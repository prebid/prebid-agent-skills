# Discovery Rules

How the orchestrator finds the files it needs at the resolved commit. The skill mirrors the file-to-domain mapping pattern of pr-triage (see [`../../../../review/skills/pr-triage/references/routing-rules.md`](../../../../review/skills/pr-triage/references/routing-rules.md)) but with two structural differences:

1. **read does not route — it discovers + dispatches.** pr-triage routes a known PR's diff files to one of three skills. read takes a bidder name + commit and discovers the canonical files for THAT bidder, dispatching them to per-domain readers.
2. **read needs ALL the files for that bidder, not just the diffed subset.** Multi-file adapters (msft, mediasquare, appnexus) have N Go files; read enumerates ALL of them. PR routing only sees what changed.

This file canonicalizes the per-domain glob patterns, alias short-circuit detection, drift detection, multi-file adapter inventory, and legacy-naming detection.

---

## Per-domain file globs

For a bidder name `<xyz>`, at the resolved commit:

### `bidder_info` domain (read-bidder-info skill)

| Path | Required | Notes |
|---|---|---|
| `static/bidder-info/<xyz>.yaml` | yes (required for ALL bidders, including aliases) | The single source of truth for endpoint, capabilities, geoscope, gvl_vendor_id, user_sync, maintainer. Filename is lowercase + extension `.yaml` (NOT `.yml`). |

If this file is missing, the bidder does not exist at the resolved commit — hard R1 error.

### `bidder_params` domain (read-bidder-params skill)

| Path | Required | Notes |
|---|---|---|
| `static/bidder-params/<xyz>.json` | yes for non-alias | The bidder-params JSON schema (draft-04). VERBATIM bytes are the cross-language contract. Absent for pure aliases (the parent's params apply). |
| `openrtb_ext/imp_<xyz>.go` | optional | The `ExtImp<Xyz>` struct. May be absent for adapters with no bidder-specific params. Note the `imp_` prefix style (not `ext_imp_`). |
| `adapters/<xyz>/params_test.go` | optional | The unit-test file for params validation. The orchestrator extracts `valid_cases_count`, `invalid_cases_count`, and `bidder_constant_referenced`. The latter drives R7 mismatch detection. |

> **Priority override**: `adapters/<xyz>/params_test.go` is owned by the `bidder_params` domain, NOT the `code` domain. This mirrors the pr-triage routing rule "more specific pattern wins" — see [`../../../../review/skills/pr-triage/references/routing-rules.md`](../../../../review/skills/pr-triage/references/routing-rules.md) "Priority Rules for Overlapping Patterns".

### `code` domain (read-adapter-code skill)

| Path | Required | Notes |
|---|---|---|
| `adapters/<xyz>/<xyz>.go` | yes for non-alias | The primary implementation file. Contains `Builder`, `MakeRequests`, `MakeBids`. |
| `adapters/<xyz>/*.go` (excluding `params_test.go`) | catchall | Any additional Go files in the adapter directory. Multi-file adapters live here. |
| `adapters/<xyz>/<xyz>_test.go` | optional | The JSON test runner (typically a thin `RunJSONBidderTest` wrapper). Presence drives `tests.uses_canonical_harness`. |
| `adapters/<xyz>/<xyz>test/exemplary/*.json` | optional | Happy-path test fixtures. |
| `adapters/<xyz>/<xyz>test/supplemental/*.json` | optional | Edge cases, error paths. |
| `adapters/<xyz>/<xyz>test/amp/*.json` | optional | AMP-specific tests. |
| `adapters/<xyz>/<xyz>test/video/*.json` | optional | Video-specific tests. |
| `adapters/<xyz>/<xyz>test/videosupplemental/*.json` | optional | Video error-path fixtures. |

Each fixture file is recorded with `{ filename, sha256, bytes }` (`fixture-mode=count`, default), or with extracted media types (`summary`), or inlined (`verbatim`). See [`output-format.md`](output-format.md) for the per-mode payload.

### Registration files (read-only — orchestrator inspects, doesn't dispatch)

| Path | Used for |
|---|---|
| `exchange/adapter_builders.go` | Verify the bidder constant exists in the `coreBidderBuilders` map. Mismatch surfaces as `bidder-not-registered` warning. |
| `openrtb_ext/bidders.go` | Verify `BidderXyz BidderName = "<xyz>"` is declared. The capitalization here drives R7's expected `params_test.go:bidder_constant_referenced` value. |
| `go.mod` | Module-path major-version drift detection (Step 3). |

These files are NOT parsed in full — the orchestrator extracts only the relevant lines.

---

## Alias short-circuit detection

For each bidder, BEFORE dispatching to all readers, the orchestrator checks for alias status by parsing `static/bidder-info/<xyz>.yaml`:

1. **Pure alias** (Step 4 short-circuit): YAML has top-level `aliasOf: <parent>` field. The bidder has no Go implementation and typically no bidder-params JSON.
   - Action: emit minimal alias spec with `meta.is_alias: true`, `meta.alias_of: <parent>`, the YAML extra fields, and skip dispatch to `read-adapter-code` and `read-bidder-params`. Only `read-bidder-info` runs.
   - The `code:` and `params:` sections of the spec are emitted as `null` (NOT omitted — schema completeness).

2. **Alias with co-existing params** (edge case): `aliasOf:` is set AND `static/bidder-params/<xyz>.json` exists.
   - Action: emit `provenance.warnings[]` of type `alias-resolution-circular` with summary "alias declares aliasOf:<parent> but has its own bidder-params JSON; parent's params would normally apply but the dedicated file overrides at runtime". Continue to dispatch `read-bidder-params` best-effort.

3. **Parent with aliases** (informational only): Parent's YAML has `parent_aliases: [child1, child2]` field (this list is computed by scanning all other YAMLs for `aliasOf: <xyz>` references).
   - Action: populate `meta.parent_aliases: [...]` on the parent's spec. The parent is NOT an alias; full dispatch proceeds.
   - Note: in Go, the alias inversion is `child→parent` (child YAML declares `aliasOf:`). In Java, it is `parent→children` (parent's YAML lists children under `aliases:`). This divergence is captured in `cross_language.port_concerns.aliases_inverted: true`.

4. **Whitelabel-only parent**: YAML has `whiteLabelOnly: true`. The parent is NOT an alias but is policy-restricted to alias-only consumption.
   - Action: populate `meta.whitelabel_only: true`. Full dispatch proceeds (whitelabel parents typically have full Go code that serves the aliases — TeqBlaze, SmartHub).

5. **Disabled bidder**: YAML has `disabled: true`.
   - Action: populate `meta.disabled: true`, emit `provenance.warnings[]` of type `disabled-bidder-read` ("bidder is currently disabled in master; spec captures last known shape"). Full dispatch proceeds — the spec is still valid for archaeology.

---

## Drift detection

At Step 3, the orchestrator reads `go.mod` at the resolved commit and parses the `module` declaration to detect major-version drift. The current major is canonicalized at [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) — currently `v4`.

### Parsing logic

```
1. Fetch go.mod at the resolved commit.
2. Extract the module declaration line: `module github.com/prebid/prebid-server/<vN>` or
   (legacy v0/v1) `module github.com/prebid/prebid-server`.
3. Parse the trailing path segment:
   - matches `/v(\d+)$` → major version is N
   - no version suffix → major version is 1 (Go module convention: v0 and v1 omit the suffix)
4. Compare against the canonical major (currently 4).
5. If different, emit provenance.warnings[] entry:
     type: module-major-mismatch
     file: go.mod
     line: <line of module declaration>
     summary: "module path major version changed (canonical=v4 → upstream=v<N>); reader heuristics may be stale and downstream framework-utilities.md must be updated"
```

The warning is informational. The orchestrator continues dispatch; downstream readers reading code that imports `prebid-server/v4/...` while master is `v5` will produce a spec with stale field interpretations, but the spec is still emitted. The user should re-read with updated heuristics after the framework-utilities.md migration.

> **Note**: pr-triage flags `v3` imports inside a PR diff as NOT a stale-author error (see [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) note about the v3 → v4 sweep). The same rule applies here: a single adapter file inside a PR may import `v3` even when master is `v4`. The drift check ONLY fires on `go.mod`'s top-level `module` declaration.

### What is NOT drift

The following are NOT drift signals — they are normal file content:

- Adapter code imports of `github.com/prebid/prebid-server/v4/...` — expected; this is what `v4` means.
- Test fixture files (`*.json`) referencing v3 in deprecated examples — these are documentation, not module imports.
- Vendored or legacy `go.mod` files in subdirectories — only the top-level `go.mod` is the canonical declaration.

---

## Multi-file adapter inventory

Most adapters are single-file (`adapters/<xyz>/<xyz>.go`). Some have multi-file layouts where the implementation is split. The orchestrator inventories ALL `*.go` files in `adapters/<xyz>/` and assigns each a role.

### Known multi-file adapters

| Bidder | Files | Role pattern |
|---|---|---|
| `msft` (Microsoft) | `msft.go`, `models.go`, `iab_categories.go`, `usersync.go` | implementation + models + data-table + utils |
| `mediasquare` | `mediasquare.go`, `parsers.go`, `structs.go` | implementation + parsers + types |
| `appnexus` | `appnexus.go`, `models.go`, `appnexus_keywords.go`, `parser.go` | implementation + models + parsers + utils |
| `adkernel` | `adkernel.go` (single-file) | implementation only — listed for clarity (NOT multi-file) |

### Role classification heuristics

For each `*.go` file, the orchestrator (via dispatch to `read-adapter-code`) classifies its role:

| Role | Heuristic |
|---|---|
| `implementation` | Contains `Builder`, `MakeRequests`, OR `MakeBids` function. Typically the `<xyz>.go` file. |
| `types` | Contains `type X struct` declarations only; no functions. Often `structs.go` or `models.go`. |
| `parsers` | Contains string parsing or JSON parsing functions; no `Builder`/`MakeRequests`/`MakeBids`. Often `parsers.go`. |
| `utils` | Helper functions referenced from implementation; no struct definitions. |
| `models` | Domain models (request/response payloads). May overlap with `types`; orchestrator picks the more specific role when in doubt. |
| `data-table` | A package-level `var X = map[...]...{...}` literal that takes >50% of the file's LOC. Canonical: `iab_categories.go` for msft. |

The role classification is RECORDED on `code.file_layout.files[]` but the heuristic is NOT load-bearing for spec correctness — the orchestrator does not behave differently based on role; downstream consumers (write/, port-go2java/) use it for code generation.

### File ordering on the spec

The orchestrator sorts `code.file_layout.files[]` by:
1. `<xyz>.go` first (the canonical entry-point file).
2. Other files alphabetically.

This ensures byte-identical specs across re-reads (R4 round-trip determinism).

---

## Legacy test-directory naming

The canonical test root is `adapters/<xyz>/<xyz>test/` (no separator, no underscore). Some legacy adapters use different names:

| Bidder | Test root | Naming kind |
|---|---|---|
| `optidigital` | `optidigitaltest/` | `canonical` |
| `kobler` | `koblertest/` | `canonical` |
| `33across` | `ttxtest/` | `canonical` (note: directory `33across` but package `ttx`, so test root uses `ttx` prefix matching the package) |
| `msft` | `test/` AND `test-extrainfo/` | `custom` (dual-directory + non-`<xyz>test/` naming — REQUIRES paired quirk) |
| (theoretical) | `<xyz>/test/` (without `<xyz>` prefix) | `legacy-test` |

The reader extracts the test root and assigns one of three values to `tests.go_directory_naming`:

- `canonical` — `<xyz>test/` exactly. Default.
- `legacy-test` — `<xyz>/test/`. Older convention, tolerated.
- `custom` — anything else. Includes msft's dual `test/` + `test-extrainfo/` layout. REQUIRES a paired `quirks[]` entry referencing `tests.go_directory_naming`.

For the `custom` case, the orchestrator emits a `quirks[]` entry of taxon `multi-file-layout-justified` (or `incomplete-classification` if the reader cannot identify the actual root).

---

## Discovery output format (internal)

After Step 2, the orchestrator holds an internal manifest:

```yaml
discovery:
  resolved_commit: <40-char SHA>
  bidder_info:
    yaml: static/bidder-info/<xyz>.yaml
  bidder_params:
    json: static/bidder-params/<xyz>.json     # null if alias
    ext_struct: openrtb_ext/imp_<xyz>.go      # null if absent
    params_test: adapters/<xyz>/params_test.go # null if absent
  code:
    primary: adapters/<xyz>/<xyz>.go
    additional_files:                          # multi-file adapters
      - adapters/<xyz>/models.go
      - adapters/<xyz>/iab_categories.go
    test_runner: adapters/<xyz>/<xyz>_test.go  # null if absent
    test_root: adapters/<xyz>/<xyz>test/        # or legacy form
    test_root_naming: canonical | legacy-test | custom
    fixtures:
      exemplary: [<file paths>]
      supplemental: [<file paths>]
      amp: [<file paths>]
      video: [<file paths>]
      videosupplemental: [<file paths>]
  registration:
    adapter_builders: exchange/adapter_builders.go
    bidders_const: openrtb_ext/bidders.go
  module:
    go_mod: go.mod
    declared_major: v4
  alias_status:
    is_alias: false
    alias_of: null
    parent_aliases: [<other bidder names>]    # if THIS is a parent
```

This manifest is the input to Step 5 dispatch. Each per-domain reader receives only the slice of the manifest relevant to its domain. The manifest itself is NOT serialized into the final spec — it is internal accounting; the spec records only `provenance.source.discovered_files[]` (a flat path list) for R1 validation.

---

## Sources

- The plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` — Phase B Go orchestrator workflow Step 2 ("discover files at the resolved commit"), edge case 4 (multi-file Go layout — mediasquare, msft, appnexus), edge case 3 (test directory naming exceptions — msft uses `test/`/`test-extrainfo/`), edge case 1 (package vs directory mismatch — 33across→ttx).
- Existing file→domain mapping mirrored: [`../../../../review/skills/pr-triage/references/routing-rules.md`](../../../../review/skills/pr-triage/references/routing-rules.md) — file-to-skill routing table, priority rule for `params_test.go`, shared file resolution for `openrtb_ext/bidders.go`, valid endpoint template macros, test data directories table.
- Framework utilities (Go): [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) — module path major-version reference (currently `v4`), `EndpointTemplateParams` 18-field list (used in R8 placeholder validation), framework helper functions (drives `code.imports.has_jsonutil` etc.), v3-import-in-PR-diff is NOT drift rule.
- Spec schema: [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md) — `meta.{is_alias, alias_of, parent_aliases, whitelabel_only, disabled, module_path_major}` field semantics, `code.file_layout.{kind, files[].role}` enumeration, `tests.{test_root_directory, go_directory_naming, fixture_inventory.*}` structure.
- Behavior taxonomy: [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md) — `tests.go_directory_naming` enum values (`canonical | legacy-test | custom`).
- prebid-server master: commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (v4.1.0, 2026-04-27).
