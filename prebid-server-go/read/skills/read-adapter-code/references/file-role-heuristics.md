# File Role Heuristics

Deterministic mapping rules from `adapters/{xyz}/*.go` filename to the `code.file_layout.files[].role` enum value. Consumed by `read-adapter-code/SKILL.md` Steps 1–2.

The role enum (from [../../shared/adapter-spec.md](../../shared/adapter-spec.md)): `implementation, tests, types, parsers, utils, models, data-table, params-tests, usersync`.

---

## Rule order (deterministic)

For each `.go` file under `adapters/{xyz}/` (excluding subdirectories — those are test fixtures), apply these rules in order. The FIRST matching rule wins.

| # | Pattern | Role | Notes |
|---|---|---|---|
| 1 | `params_test.go` | `params-tests` | Excluded by orchestrator; this skill skips it silently if encountered. Owned by `read-bidder-params`. |
| 2 | `usersync.go` | `usersync` | Legacy file from pre-v3 era. Most modern adapters do NOT have this file (user-sync URL is in YAML). When present, mark `usersync` and emit a `legacy-go-pattern-pre-1.22` INFO-level quirk. |
| 3 | `iab_categories.go` (or `*_categories.go`) | `data-table` | Static lookup table (canonical: msft). Triggers `code.iab_category_storage.{storage_kind: go-data-table, go_data_file: <path>, table_size: <count>}`. |
| 4 | `models.go` OR `structs.go` OR `types.go` OR `proto.go` | `types` | Type declarations for custom request/response payloads. Canonical: mediasquare `structs.go` (defines `msqParameters`, `msqResponse`, etc.). |
| 5 | `parsers.go` OR `parse.go` | `parsers` | Bidder-specific parsing helpers (rare). |
| 6 | `utils.go` OR `helpers.go` | `utils` | Generic helpers split out for organization (rare). |
| 7 | `*_test.go` (any suffix, excluding `params_test.go`) | `tests` | Includes `{xyz}_test.go` (the JSON harness runner) and any non-canonical `_test.go` files (e.g., `{xyz}_relay_test.go`). |
| 8 | `{xyz}.go` (matches the directory name) | `implementation` | The main adapter file. Always present. Holds `Builder`, `MakeRequests`, `MakeBids`, and the adapter struct. |
| 9 | Any other `.go` file | `implementation` | Multi-file adapter splits an additional implementation file. Mark as `implementation` and increment a multi-file counter. |

**Tie-breaking**: the first matching rule wins. Rules 1–8 are exclusive; rule 9 is a catch-all for adapters that introduce a new file matching no other rule (rare in current corpus — most multi-file adapters use canonical names like `iab_categories.go` or `models.go` that are caught by rules 3–6).

---

## LOC counting

`loc` is a computed value under V4 in [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4): it is the stdout of one command run against the bytes at `provenance.source.resolved_commit`.

```bash
<fetch> | wc -l
```

Blank lines, comments, and import blocks all count. `wc -l` counts `\n` occurrences, so a file with no terminal newline reports one less than its visible line count — record what the command prints; the terminal-newline question is answered separately by the `bytes` witness on that file's reference. Do not add a correction term, and do not read the number off an editor's gutter. Record as `code.file_layout.files[].loc`. Examples (each reproducible with the command above):

- `adapters/kobler/kobler.go:177` (kobler golden spec).
- `adapters/optidigital/optidigital.go:71` (optidigital golden spec).

---

## Multi-file detection

A multi-file adapter is one with more than one non-test `.go` file. Specifically, count files where role is one of: `implementation, types, parsers, utils, models, data-table, usersync`. Excluded from the count: `tests, params-tests`.

| Adapter | Files (with roles) | `file_layout.kind` | Notes |
|---|---|---|---|
| kobler | `kobler.go (implementation), kobler_test.go (tests), params_test.go (params-tests)` | `single-file` | Only `kobler.go` counts toward multi-file detection. |
| optidigital | `optidigital.go (implementation), optidigital_test.go (tests), params_test.go (params-tests)` | `single-file` | Same reasoning. |
| msft | `msft.go (implementation), models.go (types), iab_categories.go (data-table), msft_test.go (tests), params_test.go (params-tests)` | `multi-file` | Three non-test files. |
| mediasquare | `mediasquare.go (implementation), structs.go (types), parsers.go (parsers), utils.go (utils), mediasquare_test.go (tests), params_test.go (params-tests)` | `multi-file` | Custom request body type (`msqParameters`) lives in `structs.go`; bidder-specific helpers split across `parsers.go` and `utils.go`. |
| appnexus | `appnexus.go (implementation), models.go (types), iab_categories.go (data-table), appnexus_test.go (tests), params_test.go (params-tests)` | `multi-file` | Multi-file justified by the inlined IAB-category data table and custom types — emit a `multi-file-layout-justified` quirk. |
| 33across | `33across.go (implementation), 33across_test.go (tests), params_test.go (params-tests)` | `single-file` | Note the package-directory mismatch (directory `33across`, package `ttx`); see the next section. |

When `multi-file`, set `cross_language.port_concerns.multi_file_layout: true`. The Java port may or may not preserve the multi-file split; this flag tells the porter to expect it.

---

## Package vs directory mismatch detection

The Go `package` clause of the implementation file SHOULD match the directory name. When it does not, this is a documented edge case (Plan edge case 1).

**Detection algorithm**:

1. Locate the file with role=`implementation` whose filename (without `.go`) matches the directory name. If none matches (e.g., directory `33across` has no file named `33across.go` because Go disallows leading digits in identifiers), use the implementation file with the bidder-name-prefixed identifier or the only `implementation`-role file.
2. Parse the `package <name>` clause.
3. Set `code.package_or_class: <name>`.
4. Set `code.directory_name: <dir>`.
5. Set `code.package_directory_mismatch: <name> != <dir>`.

**Canonical examples**:

| Directory | Implementation file | Package clause | `package_directory_mismatch` |
|---|---|---|---|
| `adapters/kobler/` | `kobler.go` | `package kobler` | `false` |
| `adapters/optidigital/` | `optidigital.go` | `package optidigital` | `false` |
| `adapters/33across/` | `33across.go` | `package ttx` | `true` (canonical mismatch — Go disallows leading digits in identifiers) |
| `adapters/adkernel/` | `adkernel.go` | `package adkernel` | `false` (the struct identifier `adkernelAdapter` is the variation, not the package; see [adapter-code-patterns.md](adapter-code-patterns.md#adapter-struct-shapes)) |
| `adapters/cadent_aperture_mx/` | `cadent.go` | `package cadent_aperture_mx` | `false` (filename does not match dir, but package does — only the package matters for this flag) |

When `package_directory_mismatch: true`, the orchestrator additionally emits a `package-directory-mismatch` warning under `provenance.warnings` per Validation Rule R6 in [../../shared/adapter-spec.md](../../shared/adapter-spec.md#validation-rules-r1-r10).

---

## Test directory naming detection

Test fixtures live under `adapters/{xyz}/{xyz}test/` (canonical), `adapters/{xyz}/test/` (legacy: msft), or other paths.

**`tests.test_root_directory`**: the directory name (last segment of the test fixture path's parent) verbatim.

**`tests.go_directory_naming`** rules:

| Value | Detection cue |
|---|---|
| `canonical` | Test root is `{xyz}test` with NO separator (e.g., `koblertest`, `optidigitaltest`). The default for new adapters. |
| `legacy-test` | Test root is `{xyz}/test` (separator). Older convention. Canonical: `adapters/msft/test/`. |
| `custom` | Anything else. REQUIRES a quirk entry. Canonical: `adapters/msft/test-extrainfo/` co-existing with `test/` (msft has TWO test trees because of distinct ExtraAdapterInfo configurations). |

When `custom`, emit a quirk like:

```yaml
- id: msft-dual-test-tree
  file: adapters/msft/
  summary: "msft uses both test/ and test-extrainfo/ — two test trees for distinct ExtraAdapterInfo configurations."
  edge_case_taxon: incomplete-classification
```

The orchestrator may downgrade this to a `provenance.warnings` entry rather than a quirk if it has more global context. The orchestrator handles dispatch decisions; this skill records observations.

---

## Per-file-role implications for `code.*` extraction

Each role drives specific spec-field extraction:

| Role | Extract from this file |
|---|---|
| `implementation` | `code.adapter_struct.*`, `code.builder.*`, `code.make_requests.*`, `code.make_bids.*`, `code.imports.*`. |
| `tests` | `tests.uses_canonical_harness`, test-runner `bidder-constant-mismatch` warnings, `tests.fixture_inventory.*` (via subdirectory walk). |
| `types` | The names of custom request/response types — populates `code.make_requests.request_body.custom_body_type`, `code.make_bids.custom_response_type` when present. Emit a `multi-file-layout-justified` quirk citing the file. |
| `data-table` | `code.iab_category_storage.{go_data_file, table_size}` if the file contains an IAB-category map. |
| `parsers`, `utils` | Helpers go into `code.make_requests.helpers[]` or `code.make_bids.helpers[]` depending on caller. Emit a `multi-file-layout-justified` quirk if the split is non-trivial. |
| `usersync` | Legacy-only. Emit a `legacy-go-pattern-pre-1.22` INFO quirk citing the file. The user-sync URL data lives in YAML and is owned by `read-bidder-info`. |

---

## Edge-case priority table (when multiple rules might match)

For deterministic outputs:

1. `params_test.go` is ALWAYS `params-tests` regardless of any other heuristic.
2. `*_test.go` (any other) is ALWAYS `tests`.
3. Special filenames (`models.go, structs.go, types.go, parsers.go, utils.go, helpers.go, iab_categories.go, usersync.go`) win over the generic `{xyz}.go` rule.
4. The `{xyz}.go` filename match wins over rule 9 (catch-all `implementation`).
5. Any other `.go` file falls through to rule 9 (catch-all `implementation`).

Examples:

- `adapters/mediasquare/structs.go` — rule 4 matches → `types`.
- `adapters/msft/iab_categories.go` — rule 3 matches → `data-table`.
- `adapters/mediasquare/parsers.go` — rule 5 matches → `parsers`.

---

## Sources

- `prebid/prebid-server` master at v4.1.0 (commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` as of 2026-04-27):
  - `adapters/kobler/` — single-file canonical (`kobler.go`).
  - `adapters/optidigital/` — single-file canonical (`optidigital.go`).
  - `adapters/33across/` — package-directory mismatch (`package ttx` in `33across/` directory).
  - `adapters/adkernel/` — bidder-name-prefixed unexported struct identifier `adkernelAdapter`.
  - `adapters/mediasquare/` — multi-file with `structs.go` (custom types `msqParameters`, `msqResponse`), `parsers.go`, `utils.go`.
  - `adapters/msft/` — multi-file with `iab_categories.go` data table and `models.go` types; legacy test directories `test/` and `test-extrainfo/`.
  - `adapters/appnexus/` — multi-file with `iab_categories.go` (data-table) and `models.go` (types).
- Schema: [../../shared/adapter-spec.md](../../shared/adapter-spec.md).
- Behavior taxonomy: [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md).
- Companion classification: [adapter-code-patterns.md](adapter-code-patterns.md).
- Companion quirk emission rules: [quirk-catalog.md](quirk-catalog.md).
- Review-time test directory naming rule: [../../../../review/skills/adapter-code-pr-review/SKILL.md#workflow-test-runner-changed](../../../../review/skills/adapter-code-pr-review/SKILL.md#workflow-test-runner-changed).
