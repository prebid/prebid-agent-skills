# Output Format (Java)

How the Java orchestrator emits its spec + summary. Identical shape to the Go orchestrator's output rules — the spec schema is language-neutral, so the emission rules are too.

## Default emission (stdout)

When neither `--out` nor `--persist` is provided, output goes to stdout in the form:

```
--- yaml ---
adapter_spec_version: 1
spec_kind: prebid-server-adapter
source_language: java
... (full YAML spec) ...

--- markdown ---
# Adapter spec: <bidder> (java, <shortsha>)

## Identity
... (full Markdown summary) ...
```

The two delimiter lines `--- yaml ---` and `--- markdown ---` are emitted exactly as shown so downstream tools can split the stream.

When `--format=yaml` only or `--format=md` only is passed, only the requested delimiter+section is emitted.

## `--out=<path>` mode

When `--out` is provided, the orchestrator writes to disk instead of stdout. Filename convention:

```
{bidder}-{shortsha}.spec.yaml
{bidder}-{shortsha}.spec.md
```

Where `{shortsha}` is the first 7 chars of `provenance.source.resolved_commit`. Example: `kobler-69b1993.spec.yaml`.

If `--out` is a directory path, both files are written into it with the conventional names. If `--out` is a file path, the orchestrator strips any extension and appends `.yaml` and `.md` per `--format`.

## `--persist` mode (opt-in)

`--persist` writes to a deterministic location:

```
prebid-server-java/read/specs/{bidder}/{shortsha}.yaml
prebid-server-java/read/specs/{bidder}/{shortsha}.md
prebid-server-java/read/specs/{bidder}/latest.yaml -> {shortsha}.yaml   (symlink)
prebid-server-java/read/specs/{bidder}/latest.md   -> {shortsha}.md     (symlink)
```

The `read/specs/` directory is `.gitignore`'d by default (see `prebid-server-java/read/.gitignore`). Users opt into checking specs in if they want diff-comparison workflows or git-based regression tracking.

The `latest.{yaml,md}` symlink always points at the most recent persist for that bidder. Reading `latest.yaml` is the convention used by `pr-triage`'s prior-spec comparison hook.

If `{shortsha}.yaml` already exists, `--persist` overwrites it (re-running on the same commit is idempotent per R4).

## `--format` modes

| Value | Emits |
|---|---|
| `yaml,md` (default) | both YAML spec and Markdown summary |
| `yaml` | YAML spec only |
| `md` | Markdown summary only |

Comma-separated list, no spaces. Order doesn't matter (always YAML first, Markdown second).

## `--fixture-mode` modes

Controls how `tests.fixture_inventory[]` entries are populated. The default keeps specs compact; `summary` and `verbatim` are for deeper analysis.

| Mode | What's emitted per fixture |
|---|---|
| `count` (default) | `{ filename, sha256, bytes, role }` (e.g., role: `bidder-bid-request`, `auction-response`) |
| `summary` | + extracted top-level media types (banner/video/native/audio counts), imp count, seatbid count |
| `verbatim` | + the full JSON body inlined under `body:` (BIG — only useful for offline analysis) |

`role` is a Java-specific addition for the 4-file split:

- `bidder-bid-request` — the outbound HTTP request body sent to the bidder (matches `test-{name}-bid-request.json`).
- `bidder-bid-response` — the mock response from the bidder (matches `test-{name}-bid-response.json`).
- `auction-request` — the inbound auction request to PBS (matches `test-auction-{name}-request.json`).
- `auction-response` — the expected outbound auction response from PBS (matches `test-auction-{name}-response.json`).

The orchestrator emits these 4 in the listed order per test case.

## Markdown summary structure

The Markdown output is language-neutral in shape. Both Go and Java specs produce the SAME section structure; only the populated content differs (a Java spec describes Spring DI under `## Construction`, a Go spec describes the `Builder()` function).

Sections (in this order):

```markdown
# Adapter spec: {bidder} ({language}, {shortsha})

## Identity
- Bidder name, alias status, language, repo, commit, fetch method
- Maintainer, GVL vendor ID, geoscope
- Capabilities (site/app/dooh × banner/video/native/audio)

## Endpoint
- URL, construction kind, macros used, mechanism (per language)
- endpoint compression, ortb_version, modifying_vast_xml_allowed
- deploy-time tokens (if any)

## Construction
- (Java) Spring config: factory class + method, property source, lambda body, configuration_properties_class extras, bean dependencies
- (Go) Builder function: signature, errors returned, template parsed at build

## Bidder class / struct
- (Java) bidder_class.{name, parameterized_request_type, override_methods, constructor.parameters, static_fields, helper_classes_*}
- (Go) code.adapter_struct.{type_name, type_visibility, fields[]}

## Request building
- batching.rules[] (each rule kind + parameters)
- request_body.kind
- mutation.entity_strategies (per-entity) + java_idiom/go_idiom
- imp_ext_unmarshal.kind + mechanism
- endpoint_resolution.kind + mechanism
- helpers (with signatures)

## Response building
- response_type, custom_response_type
- http_status_handling.kind
- application_status_handling (if not none)
- bid_type_resolution.method_chain[] + default_value + multi_format_detection
- bid_pointer_pattern (+ go_sibling on Go specs)
- currency_overwrite_safety

## Params (cross-language)
- bidder_params_sha256
- schema_interpretation: properties, required_fields, flexible_types, combinators_used
- ext_struct: file, type_name, fields, custom_unmarshal
- params_test: file, valid/invalid case counts (Go) or unit test method count (Java)

## Tests
- (Java) test_root_directory, java_it_folder_naming, integration_test_class, integration_test_pattern
- (Java) unit_test_methods_count, unit_test_loc, hand_written_test_methods[]
- (Java) test_application_properties_entries_added
- (Go) test_root_directory, go_directory_naming
- fixture_inventory (count by role)
- uses_canonical_harness

## Currency conversion
- used, helper signatures (both languages noted with the source-language one populated)
- injection mechanism, bid_request_passed_for_context

## Headers
- pre_built_in_constructor, per_request_dynamic
- custom_headers
- authentication_kind + authentication_input

## IAB category storage
- storage_kind, yaml_field / go_data_file, table_size, injection

## Quirks
- Each quirk: id, file, summary, edge_case_taxon

## Cross-language
- go_artifacts (path stubs only on Java spec)
- java_artifacts (full)
- port_concerns (5 booleans)
- port_lineage (when port pair)
- reviewer_cohort (per-language disjoint cohorts + cross_language_coordinator)
- {go,java}_specific_concerns[] (free-text — dense on source-language side)

## Provenance
- read.skill_versions, timestamp_utc, operator
- warnings[] table: type, file, line, summary
```

The Markdown is plain prose with embedded YAML snippets where helpful. It is NOT a strict transformation of the YAML — the Markdown summarizes for human review while the YAML is the machine-readable source of truth.

## Round-trip determinism (R4)

Two reads at the same commit MUST produce byte-identical output modulo:

- `provenance.read.timestamp_utc`
- `provenance.read.operator`

YAML key order is enforced by the orchestrator (writes use a fixed key order matching `adapter-spec.md`'s top-level structure). Multi-line strings use the literal-block scalar (`|`) for `bidder_params_json` and `spring_config.bidder_creator_lambda` to preserve byte content exactly.

Numbers are emitted without quotes; strings always quoted (avoids YAML's `1.10` → `1.1` rounding regression). UTF-8 encoding throughout; no BOM.

## Sources

- Master plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` (Output and persistence section).
- Canonical schema: `../../../../../prebid-server-go/read/skills/shared/adapter-spec.md` (Validation rules R1–R10, including R4 round-trip determinism).
- Sibling Go output rules: `../../../../../prebid-server-go/read/skills/read-adapter-orchestrator/references/output-format.md` (when authored — same content shape; this file is the Java-side mirror).
