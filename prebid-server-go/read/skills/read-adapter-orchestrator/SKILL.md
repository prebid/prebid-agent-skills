---
name: read-adapter-orchestrator
description: Extracts a structured Adapter Specification from any prebid/prebid-server (Go) bid adapter. USE WHEN a user asks to "read", "spec out", "extract", "snapshot", "summarize", or "describe" a Go bid adapter, alias, or its YAML/params/code by name, branch, PR, tag, or commit; or to produce the input artifact for the future write/port-go2java skills. The skill resolves a ref to a commit, discovers files, dispatches to per-domain readers, assembles the canonical YAML spec, and emits YAML+Markdown. Do NOT use for prebid-server-java (use read-bidder-orchestrator instead), prebid-js, PR review (use review/ skills), or generating a new adapter from a spec (future write/ skill).
version: 1.0.0
---

# read-adapter-orchestrator

The skill extracts a canonical Adapter Specification (YAML) from any Go bid adapter in `prebid/prebid-server`. It is the entry point of the Go read-skill suite: discovery, fetch, dispatch, assembly, validation, and emission. The four per-domain readers (`read-adapter-code`, `read-bidder-info`, `read-bidder-params`) own one slice of the spec each; this skill stitches their fragments into the schema defined at [`../shared/adapter-spec.md`](../shared/adapter-spec.md) and validates against rules R1–R10.

## Overview / what it produces

For a single bidder pinned to a single commit, the skill produces:

1. **YAML Adapter Specification** — a language-neutral document conforming to [`../shared/adapter-spec.md`](../shared/adapter-spec.md) version 1. Sections include `provenance`, `meta`, `bidder_info`, `bidder_params_json` (verbatim) + `bidder_params_sha256`, `params`, `code`, `tests`, `quirks[]`, and `cross_language` (with Go-side dense + Java-side path-hint stubs).
2. **Markdown summary** — a human-friendly `.spec.md` companion that surfaces the load-bearing fields (endpoint, capabilities, batching rules, bid-type method chain, quirks, cross-language port concerns).

The YAML is the contract; the Markdown is the dashboard. Both are emitted at the same `provenance.source.resolved_commit`. Re-running the skill on the same commit MUST produce a byte-identical YAML modulo `provenance.read.timestamp_utc` and `provenance.read.operator` (R4 round-trip determinism).

The output is the input contract for the future `write/` skill (regenerate adapter from spec) and the future `port-go2java/` skill (translate Go-source spec into Java artifacts; will consume [`../shared/port-translation-rules.md`](../shared/port-translation-rules.md)). Both are Phase D/E milestones — see [`../../../ROADMAP.md`](../../../ROADMAP.md).

## Inputs

The skill accepts one bidder per invocation. Flags:

| Flag | Required | Default | Notes |
|---|---|---|---|
| `--bidder=<name>` | yes | — | Lowercase or snake_case bidder identifier (e.g., `kobler`, `33across`, `optidigital`). Must match the directory name under `adapters/`. |
| `--ref=<spec>` | no | `branch=master` | One of `branch=<name>`, `commit=<sha>`, `pr=<N>`, `tag=<vX.Y.Z>`. PR refs resolve to `head.sha`. |
| `--source-mode=<mode>` | no | auto | `local`, `github-raw`, `gh-cli`, or `auto`. See [`references/source-modes.md`](references/source-modes.md). |
| `--out=<path>` | no | stdout | Write to PATH instead of stdout. With `--persist`, this is ignored. |
| `--persist` | no | off | Write to `prebid-server-go/read/specs/{bidder}/{shortsha}.{yaml,md}` and refresh `latest.yaml` symlink. The `read/specs/` directory is gitignored by default. |
| `--format=<fmt>` | no | `yaml,md` | `yaml`, `md`, or `yaml,md`. |
| `--fixture-mode=<mode>` | no | `count` | `count` (filename + sha + bytes), `summary` (adds extracted media types per fixture), or `verbatim` (full JSON inlined). |

See [Output](#output) below for destination precedence and YAML encoding contract.

## Workflow

The orchestrator runs seven steps. Each step is testable in isolation against a corpus adapter (see Verification).

### Step 1 — Resolve `ref` to a commit

The spec is frozen at a SHA. Translate the ref into a 40-char `resolved_commit` before any file is read. The seven supported ref types:

- `branch=master` (default) — resolve to the branch HEAD via `gh api repos/prebid/prebid-server/branches/master --jq .commit.sha` (gh-cli mode) or `git rev-parse master` (local mode) or fetch `https://api.github.com/repos/prebid/prebid-server/branches/master` (github-raw mode).
- `branch=<other>` — same, with the named branch.
- `commit=<sha>` — accept verbatim if it is a 40-char hex; reject otherwise.
- `pr=<N>` — resolve to `head.sha` via `gh pr view N --repo prebid/prebid-server --json headRefOid` (gh-cli) or `https://api.github.com/repos/prebid/prebid-server/pulls/N` (github-raw). Use `head.sha` (NOT `base.sha`) so the spec captures the proposed state.
- `tag=<vX.Y.Z>` — resolve via `gh api repos/prebid/prebid-server/git/refs/tags/vX.Y.Z` (gh-cli) or `https://api.github.com/repos/prebid/prebid-server/git/refs/tags/vX.Y.Z` (github-raw). Annotated tags require dereferencing `object.sha` to the underlying commit.
- omitted — treat as `branch=master`.

The orchestrator emits `provenance.source.ref` reflecting the user's input form AND `provenance.source.resolved_commit` (always 40 chars). Both are required.

### Step 2 — Discover files at the resolved commit

For each domain, locate the canonical paths AND any aliases. Discovery uses the source-mode selected in Step 1's mode resolution. Full discovery glob table at [`references/discovery-rules.md`](references/discovery-rules.md). At a glance:

- **YAML metadata**: `static/bidder-info/{bidder}.yaml` (required — its absence is a hard error unless the bidder is alias-only via a parent's child entry).
- **Bidder params JSON**: `static/bidder-params/{bidder}.json` (required for non-alias bidders; absent for pure aliases).
- **Imp ext struct**: `openrtb_ext/imp_{bidder}.go` (Go) — note the `imp_` prefix style. May not exist for adapters with no bidder-specific params.
- **Adapter code**: `adapters/{bidder}/*.go` (excluding `params_test.go` per the routing-rules priority — that file is owned by the params reader). At minimum `adapters/{bidder}/{bidder}.go`. Multi-file adapters (msft, mediasquare, appnexus) include additional `*.go` siblings.
- **Test fixtures**: `adapters/{bidder}/{bidder}test/` (canonical), or `adapters/{bidder}/test/` + `adapters/{bidder}/test-extrainfo/` (legacy — msft). Subdirectories: `exemplary/`, `supplemental/`, `amp/`, `video/`, `videosupplemental/`.
- **Params test**: `adapters/{bidder}/params_test.go` (owned by the params reader, NOT the code reader; per routing-rules priority).
- **Adapter test runner**: `adapters/{bidder}/{bidder}_test.go` (typically a thin `RunJSONBidderTest` wrapper).
- **Registration files**: `exchange/adapter_builders.go` and `openrtb_ext/bidders.go` (read-only — used to verify the bidder constant exists; not parsed in full).

Discovery records every found path in an internal manifest used by Step 5 dispatch. Missing required files trigger hard errors per R1. The manifest is NOT serialized into the final spec; R1 verification re-walks the YAML against `provenance.source.resolved_commit` rather than against a captured file list.

### Step 3 — Drift check the module path major

Read `go.mod` at the resolved commit and parse the `module` declaration. Expected form: `module github.com/prebid/prebid-server/v4`. The current major is canonicalized at [`../../../review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md) — currently `v4`.

If the major differs (e.g., `v5`), emit a `provenance.warnings[]` entry of type `module-major-drift` with `summary: module path major version changed (v4 → vN); reader heuristics may be stale`. The orchestrator continues but this signals downstream readers may misinterpret framework helpers. See [`references/provenance-warnings.md`](references/provenance-warnings.md) for the warning schema.

### Step 4 — Detect alias short-circuit

Read `static/bidder-info/{bidder}.yaml` (the only file required for this check). If the YAML has a top-level `aliasOf: <parent>` field, the bidder is a pure alias — it has no Go implementation and no `static/bidder-params/{bidder}.json`. The orchestrator short-circuits:

- Emit a minimal alias spec: `meta.is_alias: true`, `meta.alias_of: <parent>`, the verbatim YAML extra fields, `cross_language.go_artifacts.bidder_dir: null`, no `code:` section, no `params:` section, no `bidder_params_json`.
- Skip dispatch to `read-adapter-code` and `read-bidder-params`. Only `read-bidder-info` runs.
- If `static/bidder-params/{bidder}.json` ALSO exists despite `aliasOf:`, emit a `provenance.warnings[]` entry of type `alias-resolution-circular` and continue to dispatch the params reader (best-effort; the parent's params usually apply).

### Step 5 — Dispatch in parallel

For non-alias bidders, run the three per-domain readers concurrently, each receiving the resolved commit + discovered file list for its domain:

- **`read-adapter-code`** owns the `code:` and `tests:` sections. Inputs: `adapters/{bidder}/*.go` (excluding `params_test.go`), `adapters/{bidder}/{bidder}_test.go`, fixture directories. Output: a YAML fragment with `code.*` and `tests.*` populated.
- **`read-bidder-info`** owns the `bidder_info:` section. Input: `static/bidder-info/{bidder}.yaml`. Output: `bidder_info.*` populated, including `endpoint_construction.kind`, `capabilities`, `geoscope`, `gvl_vendor_id`, `user_sync`, `yaml_extra_fields` (verbatim passthrough), and `yaml_field_name_quirks[]` (e.g., `endpoint-compression` typo regression).
- **`read-bidder-params`** owns `bidder_params_json`, `bidder_params_sha256`, and `params:`. Inputs: `static/bidder-params/{bidder}.json`, `openrtb_ext/imp_{bidder}.go`, `adapters/{bidder}/params_test.go`. Output: verbatim JSON bytes + sha256 + interpreted schema + ext struct + params_test counts.

The orchestrator collects all three fragments. A reader that fails (file unparseable, file missing where required) returns its fragment with affected fields nulled and a `quirks[]` entry of taxon `incomplete-classification` plus a `provenance.warnings[]` entry — never an exception that aborts the whole read.

### Step 6 — Assemble + validate

The orchestrator merges fragments into the canonical schema and computes derived fields:

1. **SHA recomputation**: Independently compute `sha256(bidder_params_json)` and assert it matches the `bidder_params_sha256` reported by `read-bidder-params`. Mismatch = R2 hard error of type `bidder-params-sha-conflict`.
2. **Cross-language path stubs**: For every Go-source spec, populate `cross_language.java_artifacts` with PATH HINTS:
   - `bidder_dir: src/main/java/org/prebid/server/bidder/{bidder}/`
   - `bidder_class: <PascalCase(bidder)>Bidder`
   - `config_class: <PascalCase(bidder)>Configuration`
   - `yaml_path: src/main/resources/bidder-config/{bidder}.yaml`
   - `proto_dir: src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/`
3. **Cross-bidder warnings**:
   - R6: Verify `meta.bidder_name == cross_language.go_artifacts.package_name`. Mismatch = `package-directory-mismatch` warning (33across-style — captured here AND in `code.package_directory_mismatch`).
   - R7: Verify `params.params_test.bidder_constant_referenced == openrtb_ext.Bidder<PascalCase(bidder)>`. Mismatch = `bidder-constant-mismatch` warning. Two real bugs at kobler_test.go:12 (BidderKargo) and params_test.go:47 (BidderKrushmedia) demonstrate this — see [`references/provenance-warnings.md`](references/provenance-warnings.md).
   - R8: Endpoint placeholder validation against `macros.EndpointTemplateParams` (the canonical 18-field list at [`../../../review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md) Endpoint Template Macros section). Unrecognized `{{.XYZ}}` = `endpoint-placeholder-unresolved` warning.
   - R9: If `code.imports.has_jsonutil == false` AND any `Marshal`/`Unmarshal` import from `encoding/json` is used in adapter code, emit `legacy-encoding-json-direct-usage` warning.
   - R10: If `tests.uses_canonical_harness == false` (no `RunJSONBidderTest`), emit `legacy-test-helpers-imported` warning.
4. **Schema validation R1–R3**: Reject hard if any spec field references a path that does NOT exist at `provenance.source.resolved_commit`. Reject hard if any enumerated field has value `custom` without a paired `quirks[]` entry referencing the same field.
5. **Disabled bidder check**: If `bidder_info.disabled: true`, set `meta.disabled: true`, emit a `provenance.warnings[]` of type `disabled-bidder-read` ("bidder is currently disabled in master; spec captures last known shape"), and continue. The spec is still valid; downstream consumers decide what to do.

The complete validation rule list R1–R10 is canonical at [`../shared/adapter-spec.md`](../shared/adapter-spec.md) (Validation rules section). Warning types and schema are canonical at [`references/provenance-warnings.md`](references/provenance-warnings.md).

### Step 7 — Emit YAML + Markdown

Emit per the [Output](#output) contract below.

## Output

Destination precedence (one per invocation):

1. `--persist` set → `prebid-server-go/read/specs/{bidder}/{shortsha}.{yaml,md}` plus a relative `latest.yaml` symlink. The `read/specs/` directory is `.gitignore`d by default; users opt into committing specs.
2. `--out=<path>` set (and `--persist` not) → write to PATH. If PATH is a directory, write `{bidder}-{shortsha}.spec.{yaml,md}` inside; if PATH has a `.yaml` or `.md` extension, write to that exact file; otherwise treat as a directory and create it.
3. (default) → stdout, with literal delimiters `--- yaml ---` and `--- markdown ---` separating the two halves.

`--format=yaml` suppresses the Markdown half; `--format=md` suppresses the YAML half; `--format=yaml,md` (default) emits both. `--fixture-mode={count,summary,verbatim}` controls per-fixture payload in `tests.fixture_inventory.*`: `count` (filename + sha + bytes), `summary` (adds extracted media types), `verbatim` (inlines the JSON; 10–100× larger).

YAML encoding contract (R4 byte-stable): LF line endings, 2-space indent, exactly one trailing `\n`, fixture lists sorted alphabetically by `filename`. Header order matches `../shared/adapter-spec.schema.json` property order; Java-only blocks (`spring_config`, `bidder_class`) emit as `null` on Go specs to keep the schema shape complete. Goldens at `read/test-fixtures/*.golden.spec.yaml` demonstrate the canonical format.

The Markdown summary is a derived dashboard surfacing `meta`, `bidder_info`, `code` highlights, `quirks` count, and `provenance.warnings[]`. It is NOT a replacement for the YAML — consumers wanting structured data read the YAML.

## Provenance & warnings

The `provenance.warnings[]` block carries non-blocking read-time anomalies. See [`references/provenance-warnings.md`](references/provenance-warnings.md) for:

- Full warning type registry (`bidder-constant-mismatch`, `module-major-drift`, `disabled-bidder-read`, `alias-resolution-circular`, `bidder-params-sha-conflict`, `yaml-field-name-typo`, `package-directory-mismatch`, `endpoint-placeholder-unresolved`, `legacy-encoding-json-direct-usage`, `legacy-test-helpers-imported`, `cross-language-byte-divergence`)
- Per-warning schema (`{ type, file, line, summary }`)
- The two real Kobler bugs that drove the warning schema design

## Discovery rules

See [`references/discovery-rules.md`](references/discovery-rules.md) for:

- Per-domain glob patterns (with the `params_test.go` priority override)
- Alias short-circuit detection (Step 4 logic)
- Drift detection (`go.mod` major-version parsing)
- Multi-file adapter inventory (msft, mediasquare, appnexus)
- Legacy test-directory naming (msft `test/` and `test-extrainfo/`)

## Source modes

See [`references/source-modes.md`](references/source-modes.md) for:

- `local` / `github-raw` / `gh-cli` decision tree
- Auth handling (gh CLI auth check, GitHub anonymous rate limit)
- Ref resolution per source-mode (branch HEAD, PR head.sha, tag SHA, explicit commit)
- Auto policy: prefer `local` if the master clone exists and ref is master; else `gh-cli` if `gh auth status` passes; else `github-raw`
- Failure escalation (private fork detection, rate-limit graceful fallback)

## Cross-skill integration

The orchestrator's output feeds three downstream surfaces:

1. **`write/` (Go) — future**: Generates a new Go adapter from a spec. Consumes the verbatim `bidder_params_json` byte-for-byte, the `params.ext_struct.fields[]` to scaffold `openrtb_ext/imp_{bidder}.go`, and the behavioral fields (`make_requests.batching.rules[]`, `make_bids.bid_type_resolution.method_chain[]`) to drive code-generation templates. `quirks[]` entries surface as TODO comments where they cannot be auto-applied.
2. **`port-go2java/` — Phase D, future**: Translates a Go-source spec into Java artifacts. Will consume `cross_language.java_artifacts` path hints + `port_concerns` flags + the verbatim `bidder_params_json` (which copies byte-identical to `src/main/resources/static/bidder-params/{bidder}.json`). The 46 cross-language translation rules at [`../shared/port-translation-rules.md`](../shared/port-translation-rules.md) will be the contract.
3. **`review/` skills — opt-in composition**: `pr-triage` (at [`../../../review/skills/pr-triage/SKILL.md`](../../../review/skills/pr-triage/SKILL.md)) can detect a `read/specs/{bidder}/latest.yaml` and load it as `prior_spec`, allowing reviewer skills to flag behavioral regressions on PR diffs (e.g., "PR adds `text/template` import — `endpoint_resolution.kind` moves from `static` to `template-macro`. Was this intentional?"). This composition is opt-in; review/ continues to work without read/.

The orchestrator does NOT call write/ or port-go2java/; it ONLY produces the spec they read.

## Edge cases the orchestrator handles

| Edge case | Handling |
|---|---|
| **Alias short-circuit** | Step 4 detects `aliasOf:` in YAML; emits minimal alias spec; skips code/params readers. |
| **Disabled bidder** | `bidder_info.disabled: true` → `meta.disabled: true` + `disabled-bidder-read` warning; spec still valid. |
| **Module major drift** | `go.mod` declares non-`v4` module path → `module-major-drift` warning; readers proceed but heuristics may be stale. |
| **Missing files** | Required file missing → hard R1 error. Optional file missing → field nulled + `incomplete-classification` quirk. |
| **Bidder constant mismatch** | `params_test.go` references wrong bidder constant (kobler `BidderKargo`/`BidderKrushmedia` real bug) → `bidder-constant-mismatch` warning. |
| **YAML field-name typo** | `endpointCompression` (camelCase) vs canonical `endpoint-compression` (kebab-case) → `yaml-field-name-typo` warning + `bidder_info.yaml_field_name_quirks[]` entry. |
| **Package/directory mismatch** | `33across` package mismatch (directory `33across`, package `ttx`) → `code.package_directory_mismatch: true` + `package-directory-mismatch` warning. |
| **Multi-file layout** | When `adapters/<bidder>/` has more than one non-test `.go` file, emit `code.file_layout.kind: multi-file` + `code.file_layout.files[].role` per file. Concrete file counts vary per bidder; consult the bidder's golden at `read/test-fixtures/<bidder>.golden.spec.yaml` (the `code.file_layout.files[]` array) for authoritative counts at the pinned commit. |
| **Legacy test-directory naming** | msft uses `test/` + `test-extrainfo/` (NOT canonical `msfttest/`) → `tests.go_directory_naming: legacy-test` (or `custom` for the dual-directory case + paired quirk). |
| **Custom request/response body** | mediasquare uses non-OpenRTB body → `code.make_requests.request_body.kind: custom` + `quirks[]` entry referencing the field. |
| **Custom UnmarshalJSON** | appnexus keywords field branches at runtime on JSON shape → `ext_pojo_construction.custom_unmarshal.kind: go-unmarshaljson` + `where_branched: type-method`. |
| **JSON Schema combinator usage** | rubicon uses `oneOf` for `accountId` → `params.schema_interpretation.combinators_used: [oneOf]`. |
| **Endpoint placeholder unresolved** | `{{.XYZ}}` not in canonical macro list → `endpoint-placeholder-unresolved` warning. |
| **Reader fragment partial failure** | Reader produces null field + paired `incomplete-classification` quirk + warning; orchestrator never aborts the whole read. |
| **PR ref against deleted bidder** | PR removes `adapters/{bidder}/`; orchestrator detects status=removed in tree and emits `bidder-removal-detected` (informational); no spec is produced. |
| **Concurrent v3 → v4 sweep aftermath** | Adapter file imports `prebid-server/v3/...` while master is v4 → reader records the import as-is; the `module-major-drift` warning fires only if `go.mod` itself is non-v4. |

## Verification

The skill is verified against the two Phase A acceptance-gate goldens:

1. **`optidigital`** (clean baseline) — single-file, banner-only, hardcoded BidTypeBanner. Smoke test:
   ```
   read-adapter-orchestrator --bidder=optidigital --source-mode=local --format=yaml | yq '.code.make_bids.bid_type_resolution.method_chain'
   ```
   Expected: `[{ method: hardcoded, hardcoded_value: BidTypeBanner, fallback_action: return-default }]`.
   Compare full output against [`../../test-fixtures/optidigital.golden.spec.yaml`](../../test-fixtures/optidigital.golden.spec.yaml).
2. **`kobler`** (port pair Go #3904 → Java #3684, with two real bidder-constant-mismatch bugs) — single-file, currency conversion, dev/prod toggle. Smoke test:
   ```
   read-adapter-orchestrator --bidder=kobler --source-mode=local --format=yaml | yq '.provenance.warnings'
   ```
   Expected: two `bidder-constant-mismatch` entries (kobler_test.go:12 BidderKargo, params_test.go:47 BidderKrushmedia).
   Compare full output against [`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml).

R4 round-trip determinism: re-running on the same `provenance.source.resolved_commit` MUST produce a byte-identical YAML modulo `provenance.read.timestamp_utc` and `provenance.read.operator`. Diff with `diff <(spec1.yaml) <(spec2.yaml)` and accept only the two excluded lines.

R5 cross-language structural parity: for any bidder also in `prebid-server-java`, the Go and Java specs MUST agree on `bidder_params_sha256`, `bidder_info.capabilities`, `bidder_info.maintainer.email`, `bidder_info.geoscope`, `bidder_info.gvl_vendor_id`, and `params.schema_interpretation`. The kobler dual-spec assertion at `cross-language-pairs/kobler.dual-spec-assertions.yaml` is the canonical round-trip test.

## Sources

- The plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` — Phase B Go orchestrator section, "Per-skill workflows" outline, edge-case catalog (17 Go cases captured by `code.*`/`bidder_info.*`/`tests.*` fields), validation rules R1–R10.
- Spec schema: [`../shared/adapter-spec.md`](../shared/adapter-spec.md) — canonical Adapter Specification format, validation rules, worked Kobler example.
- Behavior taxonomy: [`../shared/behavior-taxonomy.md`](../shared/behavior-taxonomy.md) — enumerated values for all behavioral fields plus the closed `quirks[].edge_case_taxon` registry.
- Port translation rules: [`../shared/port-translation-rules.md`](../shared/port-translation-rules.md) — 46 cross-language Go↔Java translation rules consumed by the future port-go2java skill.
- Golden specs: [`../../test-fixtures/optidigital.golden.spec.yaml`](../../test-fixtures/optidigital.golden.spec.yaml), [`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) — Phase A acceptance gate goldens.
- Framework utilities (Go): [`../../../review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md) — canonical helpers, error types, `EndpointTemplateParams` 18-field list, module-path major-version reference.
- Existing source-mode dispatch reused: [`../../../review/skills/pr-triage/SKILL.md`](../../../review/skills/pr-triage/SKILL.md) — Steps 1c (gh-cli + curl), 2 (drift checks), 3 (file categorization).
- Existing file→domain mapping mirrored: [`../../../review/skills/pr-triage/references/routing-rules.md`](../../../review/skills/pr-triage/references/routing-rules.md) — file-to-skill routing table, priority rules for `params_test.go`, shared file resolution for `openrtb_ext/bidders.go`.
- Suite README: [`../README.md`](../README.md) — directory layout, status of Phase A/B/C, what's NOT in scope.
- prebid-server master: commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (v4.1.0, 2026-04-27).
