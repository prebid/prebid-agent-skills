# Output Format

How the orchestrator emits the assembled Adapter Specification. Covers stdout vs `--out PATH` vs `--persist` semantics, filename conventions, the `--format` and `--fixture-mode` flags, the `latest.yaml` symlink behavior, and the Markdown summary structure.

The contract: the YAML output conforms to [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md) version 1; the Markdown is a derived view that surfaces load-bearing fields. R4 round-trip determinism applies to the YAML — re-running the orchestrator on the same `provenance.source.resolved_commit` MUST produce a byte-identical YAML modulo `provenance.read.timestamp_utc` and `provenance.read.operator`.

---

## Output destinations (precedence)

The orchestrator picks ONE destination per invocation, evaluated in this order:

| Precedence | Trigger | Destination |
|---|---|---|
| 1 | `--persist` set | `prebid-server-go/read/specs/{bidder}/{shortsha}.{yaml,md}` + `latest.yaml` symlink. `--out` is ignored when `--persist` is set. |
| 2 | `--out=<path>` set (no `--persist`) | The given path. If `<path>` is a directory, write `{bidder}-{shortsha}.spec.{yaml,md}` inside it; if `<path>` is a file (or non-existent), write to that exact path (treating it as a YAML or Markdown file based on extension). |
| 3 | (default) | stdout, with delimiters between YAML and Markdown halves. |

`--persist` is the "checked-in spec" workflow (treats `read/specs/` as a versionable archive of read snapshots, opt-in per the user choice during planning). `--out` is the "save this snapshot to a known location" workflow. Stdout is the "interactive read" workflow.

---

## Filename convention

For both `--out` (when `<path>` is a directory) and `--persist`, filenames follow:

```
{bidder}-{shortsha}.spec.yaml
{bidder}-{shortsha}.spec.md
```

- `{bidder}` is the lowercase bidder name (`kobler`, `optidigital`, `33across`).
- `{shortsha}` is the first 7 characters of `provenance.source.resolved_commit` (e.g., `d7f8515`).
- `.spec.yaml` and `.spec.md` are the canonical extensions. The doubled-dot pattern (`.spec.yaml` not `.yaml`) signals to consumers that these are spec artifacts, not generic YAML files.

Example: `kobler-d7f8515.spec.yaml` + `kobler-d7f8515.spec.md`.

For `--persist`, filenames live under `prebid-server-go/read/specs/{bidder}/`:

```
prebid-server-go/read/specs/kobler/d7f8515b.yaml
prebid-server-go/read/specs/kobler/d7f8515b.md
prebid-server-go/read/specs/kobler/latest.yaml -> d7f8515b.yaml      # symlink
prebid-server-go/read/specs/kobler/latest.md   -> d7f8515b.md        # symlink
```

Note: under `--persist`, the file is named `{shortsha}.yaml` (NOT `{bidder}-{shortsha}.spec.yaml`) because the directory already disambiguates by bidder. The `.spec.` infix is dropped to keep the persisted-archive paths shorter.

---

## `--persist` semantics

When `--persist` is set:

1. **Directory creation**: `mkdir -p prebid-server-go/read/specs/{bidder}/`. This is the first write; if the directory cannot be created (permissions, FS read-only), abort with hard error.
2. **File write**: write `{shortsha}.yaml` and `{shortsha}.md` (the latter only if `--format` includes `md`).
3. **Symlink refresh**:
   - If `--format` includes `yaml`: remove existing `latest.yaml` (if any), then create `latest.yaml -> {shortsha}.yaml` as a relative symlink (`ln -sf {shortsha}.yaml prebid-server-go/read/specs/{bidder}/latest.yaml`).
   - If `--format` includes `md`: same for `latest.md`.
4. **Idempotency**: if a file already exists at `{shortsha}.yaml` AND its bytes are identical to what would be written, do NOT rewrite (preserves mtime; helpful for diff-comparison workflows). If bytes differ, rewrite — this indicates an R4 round-trip determinism violation and should be investigated. Emit a `provenance.warnings[]` entry of type `persist-byte-mismatch` and continue.
5. **Gitignore policy**: the `prebid-server-go/read/specs/` directory is `.gitignore`d by default (top-level `/.gitignore` includes `prebid-server-go/read/specs/` and `prebid-server-java/read/specs/`). Users opt into checking specs in by removing the line or adding individual files with `git add -f`. The orchestrator does NOT modify `.gitignore`.

The `latest.yaml` symlink is a convenience for the opt-in pr-triage composition: pr-triage can detect `read/specs/{bidder}/latest.yaml` and load it as `prior_spec` for behavioral regression checks. The symlink ALWAYS points at the most recently persisted spec for that bidder, regardless of which commit it captured. To explicitly compare against a known commit, point at `{shortsha}.yaml` directly.

---

## `--out=<path>` semantics

When `--out=<path>` is set (and `--persist` is NOT):

| `<path>` interpretation | Behavior |
|---|---|
| Existing directory | Write `{bidder}-{shortsha}.spec.yaml` and `{bidder}-{shortsha}.spec.md` into it (per `--format`). |
| Non-existent path with `.yaml` extension | Write YAML to that exact path. Markdown skipped UNLESS `--format=md` is also set, in which case the YAML is suppressed. |
| Non-existent path with `.md` extension | Write Markdown to that exact path. YAML skipped UNLESS `--format=yaml` is also set. |
| Non-existent path with no/other extension | Treat as a directory; create it; write both files inside per `--format`. |
| Existing file | Overwrite (no confirmation). |

Existing parent directory is REQUIRED — the orchestrator does not create parent directories under `--out` (it does under `--persist`, which has a known canonical path). If parent doesn't exist, hard error.

---

## stdout semantics (default)

When neither `--out` nor `--persist` is set, the orchestrator emits to stdout:

```
--- yaml ---
adapter_spec_version: 1
spec_kind: prebid-server-adapter
source_language: go
provenance:
  source:
    repo: prebid/prebid-server
    ...
--- markdown ---
# kobler adapter — d7f8515

**Source**: `prebid/prebid-server` @ `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (branch=master, fetch=local-checkout)
...
```

The `--- yaml ---` and `--- markdown ---` delimiters are LITERAL strings that:

1. Let humans visually separate the two halves.
2. Let tooling split the streams: `awk '/^--- yaml ---$/,/^--- markdown ---$/' | sed '1d;$d' > spec.yaml`.
3. Are NOT part of the YAML spec — the YAML between delimiters is valid standalone YAML.

When `--format=yaml` only, the Markdown half (and its delimiter) is suppressed. When `--format=md` only, the YAML half is suppressed. When both (default), both halves with delimiters are emitted.

---

## `--format` flag

| Value | Meaning |
|---|---|
| `yaml` | Emit only the YAML spec. No Markdown. Suppresses `--- markdown ---` delimiter on stdout. |
| `md` | Emit only the Markdown summary. No YAML. Suppresses `--- yaml ---` delimiter on stdout. |
| `yaml,md` (default) | Emit both. |

The flag is comma-separated AND case-insensitive. `--format=YAML,Md` works. The flag does NOT support arbitrary other formats (no JSON output — convert via `yq -o json` if needed).

---

## `--fixture-mode` flag

Controls how `tests.fixture_inventory.*` is rendered. The fixture inventory can be very large (a single bidder may have 50+ fixtures); this flag tunes the verbosity:

| Value | Per-fixture payload | Use case |
|---|---|---|
| `count` (default) | `{ filename, sha256, bytes }` | Round-trip verification. The sha256 is the durable identifier; bytes is for capacity planning. |
| `summary` | `count` + `media_types: [banner, video]` (extracted from the JSON's `imp.*` keys) | Reviewer dashboards. Knowing each fixture's media type without opening it. |
| `verbatim` | `count` + `body: <full JSON>` inlined | Cross-language porting. The future port-go2java skill needs the full JSON to translate request/response shapes. WARNING: verbatim mode produces very large specs (10-100x bigger). |

The flag applies to ALL fixture subdirectories uniformly (`exemplary`, `supplemental`, `amp`, `video`, `videosupplemental`, and the Java-side `integration`).

---

## Markdown summary structure

The `.spec.md` companion file is structured for human readability. It surfaces the load-bearing fields without expecting the reader to wade through the full YAML.

### Markdown skeleton

```markdown
# {bidder} adapter — {shortsha}

**Source**: `prebid/prebid-server` @ `{full-sha}` (ref: {ref-form}, fetch: {fetch-method})
**Read at**: {timestamp-utc}
**Spec version**: {adapter_spec_version}

## Identity

- Bidder name: `{bidder}`
- Alias: {is_alias=true → "alias of {parent}" | "no"}
- Disabled: {meta.disabled true → "yes — captures last known shape" | "no"}
- Module path major: `{module_path_major}`

## Endpoint

- URL: `{bidder_info.endpoint}`
- Construction: `{bidder_info.endpoint_construction.kind}`{macros if non-empty: " (macros: {list})"}
- Compression: `{bidder_info.endpoint_compression}`

## Capabilities

| Channel | Media types |
|---|---|
| site | {bidder_info.capabilities.site.mediaTypes \| join} |
| app  | {bidder_info.capabilities.app.mediaTypes \| join}  |
| dooh | {bidder_info.capabilities.dooh.mediaTypes \| join} |

- Geoscope: {list or "all"}
- GVL Vendor ID: {gvl_vendor_id}
- Maintainer: {maintainer.email}

## Bidder params

- File: `static/bidder-params/{bidder}.json`
- SHA256: `{bidder_params_sha256}`
- Properties: {N from params.schema_interpretation.properties}; required: {required_fields list}
- Combinators: {combinators_used or "none"}
- Ext struct: `{params.ext_struct.package}.{params.ext_struct.type_name}` ({fields count} fields)
- Params test: {params.params_test.valid_cases_count} valid + {invalid_cases_count} invalid cases
  {if R7 mismatch: ⚠️ Bidder constant mismatch in params_test.go: references `{bidder_constant_referenced}`}

## Code

- File layout: `{kind}` ({len(files)} files)
- Adapter struct: `{adapter_struct.type_name}` ({type_visibility}); fields: {fields list}
- Imports: jsonutil={has_jsonutil}, currency_helper={has_currency_helper}, template_engine={has_template_engine}

### make_requests

- Batching: {batching.rules[].kind \| join " → "}
- Request body: `{request_body.kind}`{custom_body_type if set: " ({custom_body_type})"}
- Mutation: {entity_strategies as table — Site/App/Source/Imp/Banner/Device/User/Cur}; go_idiom: `{go_idiom}`
- imp.ext unmarshal: `{imp_ext_unmarshal.kind}` (target: `{target_type}`)
- Endpoint resolution: `{endpoint_resolution.kind}` ({mechanism_go})

### make_bids

- Response type: `{response_type}`
- HTTP status handling: `{http_status_handling.kind}`
- Application status handling: `{application_status_handling.kind}`{field if not none: " (field: {field})"}
- Bid type resolution:
  - Method chain: {method_chain[].method \| join " → "}
  - Default: `{default_value}`
  - Multi-format detection: `{multi_format_detection}`
- Bid pointer pattern: `{bid_pointer_pattern}` (Go: `{bid_pointer_go_sibling}`)
- Currency overwrite safety: `{currency_overwrite_safety}`

## Tests

- Test root: `{test_root_directory}` ({go_directory_naming})
- Canonical harness: {uses_canonical_harness}
- Fixture counts: exemplary={N}, supplemental={N}, amp={N}, video={N}, videosupplemental={N}

## Quirks ({len(quirks)})

{For each quirks entry:}
- **{id}** ({edge_case_taxon}) — `{file}`
  {summary}

## Cross-language port concerns

| Concern | Value |
|---|---|
| Aliases inverted (Go child→parent vs Java parent→children) | {aliases_inverted} |
| YAML unification (Java unifies bidder-config) | {yaml_unification} |
| Mutation idiom divergence | {mutation_idiom_divergence} |
| Package/directory mismatch | {package_directory_mismatch} |
| Multi-file layout | {multi_file_layout} |
| Custom UnmarshalJSON | {custom_unmarshaljson_present} |

{if port_lineage populated:}
**Port lineage**: {source_language} {source_pr} → {destination_language} {destination_pr}; review themes: {fidelity_review_themes \| join}

**Reviewer cohort**:
- Go: {reviewer_cohort.go \| join}
- Java: {reviewer_cohort.java \| join}
- Cross-language coordinator: {reviewer_cohort.cross_language_coordinator}

## Provenance warnings ({len(warnings)})

{For each warnings entry:}
- ⚠️ **{type}** at `{file}`{:line}: {summary}

{if warnings empty:}
✓ No warnings emitted at read time.

## Full YAML

The complete spec is at the companion `{bidder}-{shortsha}.spec.yaml` file (or the YAML half above the `--- markdown ---` delimiter on stdout).
```

The Markdown is intentionally compact — about 60-100 lines for a typical bidder. It is NOT a replacement for the YAML; it is a dashboard.

### What's NOT in the Markdown

- The verbatim `bidder_params_json` (would be too long; readers consult the YAML or the source file).
- The full `params.schema_interpretation.properties` array beyond a count.
- The full fixture inventory (count only; the YAML has the full list).
- The `cross_language.go_specific_concerns[]` and `java_specific_concerns[]` free-text lists (often paragraph-long; the YAML has them).
- Any field whose value is `null` or empty (compactness).

---

## Header preservation

The YAML output preserves the canonical header order (per [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md)):

```
adapter_spec_version → spec_kind → source_language → provenance → meta → bidder_info → bidder_params_json → bidder_params_sha256 → params → code → tests → spring_config → bidder_class → iab_category_storage → ext_pojo_construction → currency_conversion → headers_constructed → deploy_time_tokens → quirks → cross_language
```

For Go-source specs, `spring_config` and `bidder_class` are emitted as `null` (NOT omitted) to preserve schema completeness. The fixed order ensures byte-identical specs across re-reads (R4).

---

## Encoding details

- **Newlines**: LF (`\n`), not CRLF.
- **YAML quoting**: minimal — strings are unquoted unless they contain special characters (colons, hashes, leading/trailing whitespace) or YAML keywords (`true`, `false`, `null`, `~`, numeric-like). The `bidder_params_json` field uses block-literal (`|`) when the JSON has no terminal-trailing-whitespace nuances; otherwise double-quoted to preserve byte-fidelity (see optidigital golden's note on `\n  \n` trailing-whitespace pattern).
- **Indentation**: 2 spaces. Lists indented 2 spaces under their key.
- **Trailing newline**: the YAML output ends with exactly one `\n`. This is required for byte-identical R4 comparison.
- **Final fixture sort**: fixture lists (`exemplary[]`, `supplemental[]`, etc.) are sorted alphabetically by `filename` for byte-identical spec reproduction.

---

## Sources

- The plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` — "Output and persistence" section: stdout default, `--out PATH`, `--persist` (opt-in per user choice), `--format=yaml,md` flag, `--fixture-mode={count,summary,verbatim}` flag, filename convention `{bidder}-{shortsha}.spec.yaml`, `latest.yaml` symlink behavior, `read/specs/` directory `.gitignore` policy.
- Spec schema: [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md) — top-level YAML structure, section ordering, `tests.fixture_handling: count-only | summary | verbatim` field.
- Behavior taxonomy: [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md) — enumerated values surfaced in the Markdown summary tables.
- Optidigital golden (showing fixture-mode=count): [`../../../test-fixtures/optidigital.golden.spec.yaml`](../../../test-fixtures/optidigital.golden.spec.yaml).
- Kobler golden (showing fixture-mode=count + multiple supplemental fixtures): [`../../../test-fixtures/kobler.golden.spec.yaml`](../../../test-fixtures/kobler.golden.spec.yaml).
- prebid-server master: commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (v4.1.0, 2026-04-27).
