---
name: port-java2go
description: Translates a Java-source Adapter Spec (prebid-server-java/read/specs/{bidder}/latest.yaml or .tmp/full-loop/{run-id}/java/{bidder}.yaml) into Go artifacts under prebid-server-go/adapters/{bidder}/ plus paired YAML, bidder-params, exemplary fixtures, and registry entries. USE WHEN porting a new (or existing) Java bid adapter to the Go codebase. Walks the 46 port-translation rules, applies the 7-step pipeline, emits port-report.json.
version: 0.5.0
---

# port-java2go (Java → Go)

> **Status: D3.8 operator validation complete.** All 6 MVP pairs (`kobler`, `aax`, `adkernelAdn`, `adverxo`, `vungle`, `thetradedesk`) demonstrably portable end-to-end via 7 canaries; trajectory `5 clean / 2 after-fix / 2 FAIL` → 3 consecutive `10 clean / 0 / 0`; final canary cleared D3.3 gate 3's 80% coverage threshold. Pipeline prose authored (D3.1); 7 Go-side templates shipped (D3.2 + D3.8 supplemental-fixture); 2 port_engine helpers added (`exemplary_fixture_assemble_java_to_go`, `simulate_makerequests_mutations`); 8 template-body extensions landed (B1 unified `getBidType` / B2 currency-conversion / B3 custom-headers / F-new-1 imp_ext=none / F-new-14 legacy-raw-go status branching / F-new-12 impIDs / F-new-22 inject_empty_user / F-new-23 supplemental gating).
>
> **Production-ready for canary porting** with 1-2 hour operator hand-fill per pair (workarounds documented in each canary trace under `docs/runs/d3.8-*-canary-*.md`). NOT YET v1.0.0. Promotion to v1.0.0 needs:
>
> 1. ~~Template-macro / multi-token-substitution real bodies (F-new-2, F-new-27 — confirmed in 2/5 canaries; currently TODO stubs)~~ **LANDED** — `feat/f2-port-java2go-v1.0.0` (resolveEndpoint flips to `(string, error)`; emits `text/template` + `macros.ResolveMacros` per upstream adkernelAdn/adverxo/thetradedesk; new `ctx.endpoint_macros` schema documented in template header + Step 4 prose below).
> 2. ~~Per-key batching template branch (F-new-7 EXT-A — adkernelAdn)~~ **LANDED** — `feat/f2-port-java2go-v1.0.0` (new `{% elif ctx.batching_kind == "per-key" %}` branch emits a `dispatchImpressions`-style helper that groups imps by parsed `ExtImp{X}` value into `map[ExtImp{X}][]Imp`, plus a MakeRequests per-batch loop emitting one `adapters.RequestData` per group; composes with F-new-2 by flipping `resolveEndpoint` to `func (*ExtImp{X}) (string, error)` matching upstream adkernelAdn.go::buildEndpointURL; new `ctx.batching_per_key: {helper_name, key_field}` schema documented in template header + Step 4 prose below).
> 3. imp-id-correlation template branch (F-new-7 EXT-B — adkernelAdn)
> 4. ~~`naming_form_resolution` ctx schema (F-new-34 Rule 46 master-sample)~~ **LANDED** — `feat/f2-port-java2go-v1.0.0` (per-aspect form table now resolved from `bidder-constant-table.yaml::bidders.{name}.forms` sub-map via new `scripts.lib.port_engine.lookup_forms(yaml_name)` helper; emitted as `ctx.naming_form_resolution: dict` to `bidder.go.j2` which prefers form keys over legacy `ctx.package_name` / `ctx.imp_ext_class_root`; 6 non-mechanical pairs populated: adkernelAdn, thetradedesk, audienceNetwork, cadent_aperture_mx, stroeerCore, sspBC — backward-compat preserved for the other 265 mechanical entries; schema doc in Step 4 prose below).
> 5. A non-MVP validation canary (fresh adapter outside the 6-pair MVP set) succeeding with ≤1 retry
>
> Audit + spike: `docs/runs/d3.8-template-coverage-audit.md`, `docs/runs/d3.8-mvp-pairs-spike-2026-05-05.md`. 7 canary traces under `docs/runs/d3.8-*-canary-*.md`. ~33 distinct findings across the series (full enumeration in canary 7 trace).

## What this skill does

Takes a structured Java-source Adapter Spec (read by `prebid-server-java/read/skills/read-bidder-orchestrator`) and emits the Go artifacts that satisfy R5-strict cross-language equivalence at port time. Applies the 46 port-translation rules from `../read/skills/shared/port-translation-rules.yaml` in **inverse direction** (Java → Go). Emits a `port-report.json` documenting what was applied, what was novel, and what needs human review.

**Source** (this skill consumes): `prebid-server-java/read/specs/{bidder}/latest.yaml`, or transient at `.tmp/full-loop/{run-id}/java/{bidder}.yaml` when running under the Teal flow.

**Target** (this skill emits): Go artifacts at the canonical paths per `references/go-artifact-shapes.md` (D1.3 deliverable):

- `adapters/{bidder}/{bidder}.go` (Builder + MakeRequests + MakeBids)
- `adapters/{bidder}/{bidder}_test.go` (thin `RunJSONBidderTest` wrapper)
- `adapters/{bidder}/{bidder}test/exemplary/*.json` (re-authored from Java IT 4-file fixtures into Go's flat shape)
- `adapters/{bidder}/{bidder}test/supplemental/*.json` (error-path fixtures; preserve those reachable in Go)
- `adapters/{bidder}/params_test.go` (validates schema)
- `openrtb_ext/imp_{bidder}.go` (struct emitted from Java's `ExtImp{Bidder}.java` + Lombok annotations stripped)
- `openrtb_ext/bidders.go` constant addition + `coreBidderNames` slice entry (alphabetical, lower-first)
- `exchange/adapter_builders.go` import + map entry (alphabetical)
- `static/bidder-info/{bidder}.yaml` (camelCase keys; converted from Java's kebab-case)
- `static/bidder-params/{bidder}.json` (byte-copy from Java per Rule 38)

**Out of scope** (handled elsewhere or future): writing a Go adapter from scratch (`write/`, future); reviewing post-merge (`review/`, future composition); analytics modules / RTD modules / general modules / delta-ports (deferred per execution-plan-phase-d.md "Out of scope").

## Invocation

```bash
# One-shot Teal flow (read → port → review):
$ orchestrator port \
    --source-lang=java \
    --target-lang=go \
    --bidder={bidder} \
    --source-spec=prebid-server-java/read/specs/{bidder}/latest.yaml \
    --target-branch=feat/{bidder}-go-port \
    --run-id=2026-05-04T1430Z-a3f9

# Direct invocation (when the source spec is persisted):
$ /port-java2go --bidder={bidder} --target-branch=feat/{bidder}-go-port

# Spec-only port (no Go code emitted; useful for design review):
$ /port-java2go --bidder={bidder} --dry-run
```

Pre- and post-conditions per `../../docs/methodology/port-skills-design.md` §2.

## Pipeline (7 steps)

Per design doc `../../docs/methodology/port-skills-design.md` §3. Phase D3 (this commit) fills each step's body. The SKILL is a prose-driven document the LLM follows in order; mechanical helpers from `scripts/lib/port_engine.py` are invoked via `Bash` tool calls; templates at `templates/*.j2` are rendered via Python's Jinja2 (operator may use `python3 -c 'import jinja2; ...'` from a Bash tool call, or the SKILL invokes a thin renderer script).

### Step 1 — Load + validate source spec

**Inputs.** Source spec YAML, located by precedence:

1. `--source-spec=<path>` flag (operator override).
2. `${FULL_LOOP_RUN_ID}` env var set OR `--run-id=<id>` flag → load `.tmp/full-loop/{run-id}/java/{bidder}.yaml`.
3. `--bidder=<name>` flag (no run-id) → load `prebid-server-java/read/specs/{bidder}/latest.yaml` (the persisted golden).

If multiple sources are present and they disagree, abort with `ERROR: source spec resolution conflict — use exactly one of --source-spec, --run-id, or --bidder`.

**Validation.** Load the YAML via `yaml.safe_load`. Validate against `../read/skills/shared/adapter-spec.schema.json` using the `jsonschema` library. On a validation error, abort with the violation path + JSON-Path expression.

**Direction gate.** Confirm `source_language == "java"`. If `source_language == "go"`, abort with `ERROR: this skill ports Java → Go; for Go → Java use port-go2java (lives at prebid-server-java/port-go2java/)`.

**Loaded state.** After Step 1, the SKILL holds:

- `source_spec: dict` — the parsed Java-source spec, schema-valid.
- `bidder_name_java: str` — `source_spec.meta.bidder_name`, the Java YAML name (lowercase + drop non-`[a-z0-9]`).
- `run_id: str` — explicit `--run-id` value OR `${FULL_LOOP_RUN_ID}` OR a freshly-generated ISO-like timestamp.
- `output_root: Path` — `.tmp/full-loop/{run-id}/go/` (transient) OR `prebid-server-go/port-java2go/output/{bidder}/` (persisted via `--persist`).
- `bidder_constant_lookup: dict[str,str]` — loaded from `../read/skills/shared/bidder-constant-table.yaml`; used in Step 4 to resolve the Go-side `Bidder{X}` constant name (the Rule 46 inverse is not fully mechanical — Java lowercase `adkerneladn` could map to Go `adkernel`, `adkernelAdn`, or other camelCase forms; the lookup table is the source of truth).

### Step 2 — Discover the bidder family

**Family classification.** Read `source_spec.meta.is_alias`, `source_spec.meta.parent_aliases`, `source_spec.aliases`, `source_spec.meta.empire_parent_flavor`. Java consolidates aliases on the parent's bidder-config YAML (the inverse of Go's per-child YAML model). Classify into one of four shapes:

| Shape | Condition | Examples |
|---|---|---|
| `primary` | `meta.is_alias == false` AND `aliases:` block empty | kobler, vungle, thetradedesk |
| `alias-child` | `meta.is_alias == true` AND `meta.parent_aliases[0]` populated | rare on Java side; usually accessed via parent's `aliases:` block |
| `empire-parent` | `meta.is_alias == false` AND `aliases:` block has N entries | adverxo (3 children), smarthub (10) |
| `empire-child` | implicit child entry in another bidder's `aliases:` block | accessed by walking the parent's spec |

**Aliases-block decomposition.** For empire-parent specs, the Java parent's `aliases: { child_a: {overrides}, child_b: ~ }` block must be SPLIT into N separate Go child YAMLs at `static/bidder-info/{child}.yaml` each declaring `aliasOf: parent` (Rule 33 inverse). Step 5 emits these per-alias YAMLs; Step 2 just records the children list on the working state.

**Loaded state addition.** After Step 2, the SKILL holds:

- `family_shape: str` — one of `primary | alias-child | empire-parent | empire-child`.
- `aux_alias_overrides: dict[str, dict]` — for empire-parent: per-child override dicts from the parent's aliases block.

### Step 3 — Apply rules (Java → Go inverse direction)

**Rule walk algorithm.** Iterate `../read/skills/shared/port-translation-rules.yaml::rules[]` in declared order. For each rule, check `rule.spec_field_driver` against `source_spec`; emit `verdict: applied | skipped-not-applicable | skipped-source-side-only | applied-with-warning`. Walk-loop logic mirrors D2 §Step 3 — the difference is direction-specific application (lossy-direction quirks emitted; Go-target idiom translation rather than Java-target).

D3's mechanical-ready rules (priority order; same 10 as D2 in inverse direction):

1. Rule 38 — bidder-params byte-fidelity (`byte_copy` Java → Go)
2. Rule 46 inverse — name-normalization reversal (Java lowercase `adkerneladn` → Go camelCase `adkernelAdn`); requires the dual-spec assertion lookup since not fully mechanical in this direction
3. Rule 33 inverse — Java parent → child YAML decomposes into Go child → parent YAMLs
4. Rule 44 inverse — alias-empire flavor coherence (parent flavor inferred from Java aliases block, projected into Go child-yamls + alias entries)
5. Rule 36 inverse — Java IT 4-file split + JUnit class collapses to Go's flat `{bidder}test/exemplary/*.json` + `{bidder}_test.go` thin runner (semantic-coverage parity, not 1:1)
6. Rule 42 inverse — Java YAML-inlined IAB cats convert to Go data-table `iab_categories.go` with static-init `delivery_mechanism`
7. Rule 35 inverse (lossy-direction) — Java typed `BidderConfigurationProperties` subclass demotes to Go's `ExtraAdapterInfo` opaque JSON string (per Round-Trip Safety section pre-declaration). Emit `quirks[]: hardcoded-config-as-anti-pattern` if the Java subclass has fields the Go side won't structurally enforce.
8. Rule 39 — derived-view (no-op on porter)
9. Rule 19 inverse — Java `HttpUtil.headers()` collapse expands to explicit Go `http.Header` `Add()` calls
10. Rule 30 inverse — Java framework-default HTTP status handling expands to explicit Go `adapters.IsResponseStatusCodeNoContent` + `adapters.CheckResponseStatusCodeForErrors` helper calls

The remaining 36 rules are handled prose-driven (the SKILL walks the rule's prose body and applies the inverse translation in-line). Conflict resolution per design doc §5: lower-id rule wins on artifact placement; record `unresolved_translations[]` with reason `conflicting-rules` for the reflection loop.

**Lossy-direction safety**: Rule 35 inverse, Rule 19 inverse, Rule 30 inverse, Rule 8 (Java helper collapses → Go explicit expansions) are pre-declared lossy in `port-translation-rules.yaml` Round-Trip Safety section. The SKILL preserves source-side semantic information by emitting explicit `quirks[]` entries on the Go destination spec capturing what was lossy, so a future Go→Java re-port retains traceability. Each lossy emission MUST add a `human_todos[]` entry with category `byte-divergence-warning` so the operator confirms the lossiness is acceptable for the target.

**Loaded state addition.** After Step 3, the SKILL holds: `rules_consumed: list[dict]`, `dest_spec_partial: dict`, `quirks_emitted: list[dict]`, `unresolved_translations: list[dict]` — same shape as D2.

### Step 4 — Author the destination spec

**R5-strict-shared field carry-over.** Same nine fields as D2 §Step 4 carry verbatim from `source_spec` to `dest_spec` (the cross-language R5-strict invariant is symmetric).

**Go-specific construction.** Build the Go-only spec blocks:

- `code.package_or_class`: typically `bidder_name_java` (lowercase). Exceptions: when the bidder-constant-table indicates a non-mechanical mapping, use the Go-side package name from there.
- `code.directory_name`: same as `package_or_class` in 99% of cases. Mismatch is rare (cadent_aperture_mx Go side has package `cadentaperturemx` in dir `cadent_aperture_mx`); handled by Rule 7.
- `code.adapter_struct.type_name`: `"adapter"` (canonical Go convention).
- `code.adapter_struct.fields`: at minimum `{name: endpoint, type: string}`. When source's typed config has extra fields, demote to `{name: extraInfo, type: extraInfo}` per Rule 35 inverse + emit `quirks[]: hardcoded-config-as-anti-pattern`.
- `code.builder.signature_canonical: true` (always for ports — the Builder signature follows the canonical 3-arg form).
- `code.imports.has_currency_helper: bool` — set from `source_spec.currency_conversion.used`.
- `code.imports.has_jsonutil`: true (every adapter parses `imp.ext`).
- `cross_language.go_artifacts.{bidder_dir, package_name, bidder_constant}`: from `bidder_constant_lookup`.
- `cross_language.go_artifacts.alias_yaml_path`: when family_shape ∈ `{empire-child, alias-child}`, set to `static/bidder-info/{alias_name}.yaml`.

**Headers / status / unmarshal demotion.** The Java framework provides several behaviors implicitly that Go requires explicit code for. Per Rule 19/30/8 inverse:

- Java `BidderUtil.defaultRequest` → Go explicit `headers := http.Header{}; headers.Add("Content-Type", "application/json;charset=utf-8"); headers.Add("Accept", "application/json"); return &adapters.RequestData{Method: "POST", Uri: ..., Body: bodyBytes, Headers: headers}`.
- Java framework-default 204/4xx handling → Go explicit `adapters.IsResponseStatusCodeNoContent(responseData)` + `adapters.CheckResponseStatusCodeForErrors(responseData)`.
- Java `ImpUtil.parseImpExt(imp, mapper, ExtImpFoo.class)` → Go explicit `var bidderExt openrtb_ext.ExtBidder; if err := jsonutil.Unmarshal(imp.Ext, &bidderExt); err != nil { ... }; var fooExt openrtb_ext.ExtImpFoo; if err := jsonutil.Unmarshal(bidderExt.Bidder, &fooExt); err != nil { ... }`.

These expansions are documented in `references/porting-guide.md` (the inverse porting guide) and emitted in the Go-side templates.

**Endpoint-macros resolution (Rule 11/12 — F-new-2 / F-new-27).** When `source_spec.code.make_requests.endpoint_resolution.kind` ∈ `{template-macro, multi-token-substitution}`, the template emits the canonical Go `text/template` + `macros.ResolveMacros` pattern instead of the previous TODO-stub `return a.endpoint` catchall. Concretely the destination spec carries two new ctx fields the renderer wires through to `bidder.go.j2`:

- `ctx.endpoint_resolution_kind`: pass through `template-macro` or `multi-token-substitution` (no transformation needed; the source-side enum maps 1:1).
- `ctx.endpoint_macros: list[{macro, ext_field, convert}]`: one entry per macro the Go endpoint URL references. `macro` is the canonical `macros.EndpointTemplateParams` field name (PublisherID, SupplyId, AdUnit, TokenID, AccountID, …); `ext_field` is the exact PascalCase field on the rendered `openrtb_ext.ExtImp{X}` struct; `convert` is one of `null` (raw string passthrough), `"itoa"` (int → string via `strconv.Itoa`), `"format-int64"` (int64 → string via `strconv.FormatInt(..., 10)`), or a literal Go expression (escape hatch when the conversion isn't itoa/format-int64). When `convert` is `itoa` or `format-int64` the renderer MUST add `"strconv"` to `ctx.imports_extra` (the template assumes the symbol is in-scope).

When this branch fires, the template emits five paired changes (all gated on the same predicate):

1. **Imports**: adds `"text/template"` and `"github.com/prebid/prebid-server/{v}/macros"` to the import block.
2. **Adapter struct**: adds an `EndpointTemplate *template.Template` field (PascalCase per upstream adkernelAdn shape — exported convention preserved even though the field's Go-private use).
3. **Builder**: calls `template.New("{package}EndpointTemplate").Parse(cfg.Endpoint)`, returning `fmt.Errorf("unable to parse endpoint url template: %v", err)` on failure (verbatim upstream error string).
4. **resolveEndpoint** signature flips from `string` to `(string, error)`; the body parses `request.Imp[0]`'s ext via the existing `parseImpExt` helper, builds an `EndpointTemplateParams` literal from `ctx.endpoint_macros`, and returns `macros.ResolveMacros(a.EndpointTemplate, endpointParams)`. The `parseImpExt` local re-parse is the same shape upstream uses in `thetradedesk.go::getExtensionInfo` (walk imps until the macro fields are populated; we shortcut to imp[0] since the per-imp loop in MakeRequests has already validated each).
5. **MakeRequests callsites** (all three batching branches: single-batched, per-imp, max-imps-per-request) bind the error and either return-append-errors (single-batched) or `continue` to the next imp/chunk (per-imp, max-imps).

The previous TODO-stub catchall is retained for the third non-trivial endpoint kind, `query-parameter-augmentation` (separate audit ticket F-new-X), and for any operator-introduced novel kinds. Other kinds (`static`, `dev-prod-toggle`, `single-token-substitution`) are unchanged.

Canonical reference adapters: `adapters/adkernelAdn/adkernelAdn.go::buildEndpointURL` (1 macro, int → itoa); `adapters/thetradedesk/thetradedesk.go::buildEndpointURL` (1 macro, string passthrough); `adapters/adverxo/adverxo.go::buildEndpointURL` (2 macros, mixed int+string).

**Naming-form resolution (Rule 46 — F-new-34).** Most upstream bidders have a single naming form: the lowercase yaml_name passes through unchanged for the Go package + directory + static yaml filename + Java package; PascalCase(yaml_name) gives the Go constant root + Java class root. The 6 corpus bidders where these forms diverge non-mechanically (Go camelCase vs Java lowercase, brand-acronym preservation, rebrands, intra-Go package-vs-directory mismatch) consult `prebid-server-go/read/skills/shared/bidder-constant-table.yaml::bidders.{yaml_name}.forms` — a sub-map of the six per-aspect forms — via the `scripts.lib.port_engine.lookup_forms(yaml_name)` helper.

The helper returns a dict with six string keys (sourced from the table when populated; mechanically derived when absent):

- `go_yaml_name` — `static/bidder-info/{x}.yaml` and adapter directory (the F-new-34 master sample `cadent_aperture_mx` is the one MVP-corpus example where this diverges from `go_package_name`).
- `go_package_name` — the `package X` directive in `adapters/{bidder}/{bidder}.go` and the `template.New("{X}EndpointTemplate")` name prefix.
- `go_constant_root` — `openrtb_ext.Bidder{X}` constant suffix. Used by sibling templates (`params_test.go.j2`, `bidder-test.go.j2`).
- `java_yaml_name` — Java-side `bidder-config/{x}.yaml` filename + Spring property keys. Consumed by `port-go2java` sibling templates; included on the Go-side dict for round-trip / lineage tracking.
- `java_class_root` — Java-side `{X}Bidder` class root (also `{X}Configuration`, `ExtImp{X}`, `{X}Test` roots). Same — sibling-side metadata.
- `java_package` — Java-side `org.prebid.server.bidder.{x}` package.

The dict is passed to `bidder.go.j2` as `ctx.naming_form_resolution` at Step 4 ctx-assembly time. The template prefers these forms over the legacy `ctx.package_name` / `ctx.imp_ext_class_root` keys whenever the dict is provided; when absent, the legacy keys flow through unchanged (backward-compatible with pre-F-new-34 ctx shapes). The legacy `ctx.imp_ext_class_root` continues to win over `naming_form_resolution.go_constant_root` when explicitly set (the rare bidder whose `ExtImp{X}` class root diverges from its bidder-constant root).

The `forms:` sub-map authoring convention (in `bidder-constant-table.yaml`): only populate when at least ONE of the six forms deviates from the mechanical formula (`yaml_name` for Go forms; `re.sub(r"[^a-z0-9]", "", yaml_name.lower())` for Java forms; constant root from the simple-string value). Mechanical bidders retain the historical compact `bidder_name: PascalCaseRoot` shape. Currently 6 entries populate `forms:` (`adkernelAdn`, `thetradedesk`, `audienceNetwork`, `cadent_aperture_mx`, `stroeerCore`, `sspBC`) — the v1.0.0 F-new-34 set. The remaining 265 entries pass through `lookup_forms` mechanically.

**Per-key batching (Rule 11/F-new-7 EXT-A).** When `source_spec.code.make_requests.batching.rules[0].kind == "per-key"` (imps grouped by an `imp.ext.bidder.{field}` value; one outbound HTTP per unique group), the renderer maps to `ctx.batching_kind == "per-key"` and populates a new `ctx.batching_per_key` schema:

- `ctx.batching_per_key.helper_name: str|None` — Go func name for the grouping helper. Defaults to `"dispatchImpressions"` (mirrors upstream `adapters/adkernelAdn/adkernelAdn.go::dispatchImpressions`). Operator overrides for bidders that prefer a different name.
- `ctx.batching_per_key.key_field: str` — documents the `ExtImp{X}` field that drives the grouping (e.g., `"PublisherID"` for adkernelAdn). Informational — used in the emitted helper's doc comment + the port-report rendering. The Go map key is the WHOLE `ExtImp{X}` struct (`map[ExtImp{X}][]openrtb2.Imp`), not just this field, matching upstream's shape; the spec's `batching.rules[0].group_key` value (e.g., `"imp.ext.bidder.pubId"`) reduces to the PascalCase field name on the rendered `openrtb_ext.ExtImp{X}` struct.

When this branch fires, the template emits four paired changes (all gated on `ctx.batching_kind == "per-key"`):

1. **MakeRequests body**: replaces the single-batched / per-imp / max-imps switch arm with a per-batch loop that calls `{helper_name}(request.Imp)` → `map[ExtImp{X}][]openrtb2.Imp + []error`, iterates the map, and emits one `adapters.RequestData` per bucket (each carrying `openrtb_ext.GetImpIDs(perGroup.Imp)`).
2. **parseImpExt helper force-emit**: the grouping helper calls `parseImpExt(&imp)` per imp, so the helper is emitted regardless of `ctx.imp_ext_unmarshal_kind` (parallel to F-new-2's force-emit).
3. **Helper function**: a `{helper_name}(imps []openrtb2.Imp) (map[ExtImp{X}][]openrtb2.Imp, []error)` declaration at the end of the file, parallel to `chunkImps` for `max-imps-per-request`.
4. **resolveEndpoint signature flip (composition with F-new-2)**: when `endpoint_resolution_kind ∈ {template-macro, multi-token-substitution}`, `resolveEndpoint` flips from `(*openrtb2.BidRequest) (string, error)` to `(*openrtb_ext.ExtImp{X}) (string, error)`. The per-batch endpoint is resolved against the parsed grouping-key struct passed by pointer (`a.resolveEndpoint(&batchKey)`), NOT against `request.Imp[0]`. This mirrors upstream `adkernelAdn.go::buildEndpointURL(params)` exactly. When `endpoint_resolution_kind` is `static` / `dev-prod-toggle` / other non-macro kind, the per-batch loop reads `a.endpoint` directly and the `resolveEndpoint` helper is SUPPRESSED (would otherwise be unused — `go vet` would flag it).

Constraint: the rendered `openrtb_ext.ExtImp{X}` struct MUST be Go-comparable (no slice/map/func fields) for the `map[ExtImp{X}]…` usage to compile. The renderer does NOT enforce this; operator vouches at ctx-assembly time. Per the canary 7 trace (`docs/runs/d3.8-adkernelAdn-canary-2026-05-05T1636Z-7686.md`), adkernelAdn is the only confirmed corpus bidder using per-key today; the audit estimates 2-3 corpus-wide pairs.

Canonical reference adapter: `adapters/adkernelAdn/adkernelAdn.go::dispatchImpressions` + `MakeRequests` loop + `buildEndpointURL(params)`.

**Cross-language metadata.** Same as D2 §Step 4 with directions reversed:

```yaml
port_lineage:
  source_language: java
  source_pr: <source_spec.provenance.source.pr_url or null>
  destination_language: go
  destination_pr: null
  port_translation_rules_version: <from rules YAML>
  port_skill_version: <this SKILL.md frontmatter>
  fidelity_review_themes:
    - port-fidelity
    - <one entry per applied prose-driven rule>
```

**bidder_params_sha256 invariant.** SHA-256 of `dest_spec.bidder_params_json`; MUST equal `source_spec.bidder_params_sha256` (Rule 38 byte-copy guarantees this). Mismatch aborts the SKILL.

**Provenance pinning.** `dest_spec.provenance.source.resolved_commit = source_spec.provenance.source.resolved_commit`.

### Step 5 — Emit Go artifacts

**Output directory.** Same conventions as D2 §Step 5 (`output_root` per Step 1).

**Per-file template invocation.**

| File | Template | Notes |
|---|---|---|
| `static/bidder-info/{bidder}.yaml` | `bidder-info.yaml.j2` | camelCase keys per `references/go-artifact-shapes.md` §9. |
| `static/bidder-params/{bidder}.json` | `byte_copy` (no template) | Byte-identical to Java's per Rule 38; SHA-256 verified. |
| `openrtb_ext/imp_{bidder}.go` | `imp-ext-pojo.go.j2` | Cross-package struct; PascalCase fields with `json:"X"` tags. |
| `adapters/{bidder}/{bidder}.go` | `bidder.go.j2` | Builder + MakeRequests + MakeBids per Go canonical pattern. |
| `adapters/{bidder}/{bidder}_test.go` | `bidder-test.go.j2` | Thin `adapters.RunJSONBidderTest` wrapper. |
| `adapters/{bidder}/{bidder}test/exemplary/*.json` | `exemplary-fixture.json.j2` | One file per Java IT scenario, re-authored to Go's flat shape (Rule 36 inverse). |
| `adapters/{bidder}/{bidder}test/supplemental/*.json` | `exemplary-fixture.json.j2` | Same template, error-path scenarios. |
| `adapters/{bidder}/params_test.go` | `params-test.go.j2` | Validates `static/bidder-params/{bidder}.json` against schema. |

**Registry inserts (mechanical via port_engine):**

- `openrtb_ext/bidders.go`: `port_engine.alphabetical_insert` for the const + slice entry. Marker: `r'Bidder\w+\s+BidderName\s*='`. Pre-emit: `port_engine.prefix_uniqueness_check(target_lang='go', bidder_name=bidder_name_java)` MUST return `(True, [])`. Abort with operator notification on collision — `TestBidderUniquenessGatekeeping` would fail otherwise.
- `exchange/adapter_builders.go`: two `alphabetical_insert` calls — one for the import block, one for the dispatch-map entry. Markers per `references/registration-rules.md`.

**Post-emit:**

- `port_engine.gofmt_post_process(file_paths)` — runs `gofmt -s -w` over every emitted `.go` file. On non-zero exit, abort and surface the gofmt diff to the operator.
- (Optional) `go vet ./adapters/{bidder}/...` — when `--target-clone=<path>` is provided. Violations surface as `human_todos[]` with category `style-violation`.

**PR-shape automation outputs.** Per `references/pr-shape.md`:

- `recommended_pr_title`: `"New Adapter: {Bidder}"` (capital A; observed 100% of merged PRs). For alias ports: `"New Alias: {AliasName} (parent: {ParentName})"`.
- `target_pr_label_recommendations`: `[]` (Go has no upstream PR template; no mandatory labels).
- `companion_docs_pr_draft`: same shape as D2 (target_repo prebid/prebid.github.io; less mandatory than Java side but expected for parity).
- `pre_submit_rebase`: rebase target branch onto upstream `prebid/prebid-server` master HEAD; capture outcome.

Emission rules:

- **`gofmt -s -w` post-process**: every emitted `.go` file passes `gofmt -s -w` post-emit (via `scripts/lib/port_engine.gofmt_post_process`). Otherwise upstream Go CI fails on style.
- **`go vet` clean by construction**: templates include explicit error returns + named-result-parameter style only when needed. `go vet` should exit 0.
- **`coreBidderNames` alphabetical insert**: `port_engine.alphabetical_insert` does case-insensitive lower-first insertion into `openrtb_ext/bidders.go` and `exchange/adapter_builders.go`. This matches upstream `TestBidderUniquenessGatekeeping` enforcement.
- **Prefix uniqueness pre-check**: `port_engine.prefix_uniqueness_check(target_lang="go", bidder_name=...)` runs BEFORE emit. If the first 6 letters of the bidder name collide with an existing `coreBidderNames` entry, abort with operator notification — `TestBidderUniquenessGatekeeping` would fail otherwise.
- **PR-shape automation**: emit `recommended_pr_title: "New Adapter: {Bidder}"` (capital A per real-PR audit) and `target_pr_label_recommendations: []` (Go has no upstream PR template; no mandatory labels).
- **Companion docs PR**: emit `companion_docs_pr_draft` with target_repo `prebid/prebid.github.io`, file_path `dev-docs/bidders/{bidder}.md`, body_markdown populated from the source spec. Less maintainer-pressure than Java side, but expected for parity.
- **Pre-submit rebase**: rebase the target branch onto upstream `prebid/prebid-server` `master` HEAD; abort with operator notification on framework conflict; record outcome in `pre_submit_rebase`.

### Step 6 — R5-strict check at port time

**Re-read.** Same in-memory comparator approach as D2 §Step 6: `port_engine.r5_check_at_port_time(source_spec=source_spec, dest_spec=dest_spec)` routes through `r5_check.compare_pair`. The helper's first arg is the Go view; for Java→Go porting, `dest_spec` (the Go-target) is passed as the first arg per the helper's internal language-routing.

**Direction-aware extension (Java→Go specifics).** The four harness states extend to six schema states by inspecting Go-target vs Java-source asymmetries:

- `fail-source-omits-target-constraint`: Java source lacks a constraint Go enforces (aax-style — Java omits `minLength:1` that Go enforces on `cid`/`crid`). Port emits Go bidder-params with the Go-correct constraint AND surfaces a `human_todos[]: upstream-confirmation` entry advising the operator to file a port-fidelity bug against `prebid/prebid-server-java` to add the missing constraint upstream.
- `warn-target-strengthens-source`: Go target carries a constraint absent in Java source (Connatix-style — Go has `minimum:0`/`maximum:1` that Java lacks). The port preserves the Go-side constraint; surfaces a `human_todos[]: byte-divergence-warning` for human review.

These two states are direction-specific — a `fail-source-omits` in one direction is conceptually a `warn-target-strengthens` in the inverse direction (Java→Go aax shows the former; Go→Java shows the latter on the same pair).

**Port-time R5 fail is NOT a CI failure.** Same as D2: human_todos[] populates; the port still ships its artifacts; merge decision is human review.

### Step 7 — Emit port-report.json

**Assemble + write.** Same algorithm as D2 §Step 7. Build the dict per `../read/skills/shared/port-report.schema.json` v0.2.0; flip `port_run.{source_lang: "java", target_lang: "go"}`. Call `port_engine.port_report_emit(report, path=output_root / "port-report.json")` for schema-validated write.

**Canonical shape (kobler, abridged ~30 lines).** Operators repeatedly drift from the schema (D3.8 canary's first emit had 20 schema errors). Use this as the structural reference; `additionalProperties: false` on the top-level + most subobjects, so non-schema fields like `$schema`, `emitted_files`, `pr_shape`, `registry_inserts`, `bidder_params_sha256_match`, `note` (in rules_consumed), `rule_ref` (in human_todos), `rule_id` (in unresolved_translations) MUST NOT be added:

```json
{
  "port_report_version": "0.2.0",
  "port_translation_rules_version": "0.2.0",
  "port_run": {
    "run_id": "2026-05-05T0426Z-9f2a",
    "source_lang": "java",
    "target_lang": "go",
    "source_spec_sha": "2acced97389d03e8b4a8d2b8f5c238a5505815286525b86284dd0ab2144d6ff7",
    "target_branch": "feat/d3.8-kobler-canary"
  },
  "rules_consumed": [
    { "rule_id": 38, "verdict": "applied", "summary": "bidder-params byte-copy Java→Go (sha256 matches)" },
    { "rule_id": 35, "verdict": "applied-with-warning", "summary": "Java config subclass devEndpoint not preserved — operator must hand-fill resolveEndpoint() for dev-prod toggle" }
  ],
  "quirks_emitted": [
    { "id": "dev-endpoint-handling", "summary": "Java typed config subclass `KoblerConfigurationProperties.devEndpoint` must be hand-mapped on Go side.", "edge_case_taxon": "port-fidelity-divergence" }
  ],
  "r5_check": { "state": "pass", "byte_equal_fields": ["bidder_params_sha256"], "warn_fields": [], "fail_fields": [], "summary": "kobler is the canonical R5-pass baseline." },
  "source_pr_url": "https://github.com/prebid/prebid-server-java/pull/3684",
  "source_pr_merged_commit_sha": null,
  "source_discussion_anchors": [],
  "re_authored_paragraphs": [],
  "recommended_pr_title": "New Adapter: Kobler",
  "target_pr_label_recommendations": [],
  "upstream_bugs_to_file": [],
  "companion_docs_pr_draft": null,
  "pre_submit_rebase": null,
  "human_todos": [
    { "category": "byte-divergence-warning", "summary": "devEndpoint not preserved by template; operator must add Go-side dev-prod logic in resolveEndpoint().", "evidence_path": "src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java" }
  ],
  "unresolved_translations": [
    { "pattern_summary": "currency-conversion logic in MakeRequests body has no template branch for has_currency_helper=true.", "reason": "novel-pattern-needs-schema-addition", "candidate_rule_id": null, "evidence_path": "prebid-server-go/port-java2go/templates/bidder.go.j2" }
  ]
}
```

The full canary report at `.tmp/full-loop/2026-05-05T0426Z-9f2a/go/port-report.json` is schema-valid against v0.2.0 and shows representative population of every field.

**Operator handoff.** Final message summarizes: emitted files at `output_root` (count + tree), `r5_check.state`, human_todos count + brief list, unresolved_translations count + brief list, next operator steps (review emission, run `gofmt -s -l + go vet + go test ./adapters/{bidder}/...` locally if not done, run `./scripts/check_coverage.sh`, open PR with `recommended_pr_title`, submit companion docs PR).

The SKILL exits 0 on success regardless of `r5_check.state` — fail states are surfaced to the operator. Exit non-zero only on hard failures (Step 1 schema violation, Step 4 SHA mismatch, Step 5 prefix uniqueness collision, Step 7 schema violation).

## Rule application order

Per design doc §4. Rules applied in declaration order from `port-translation-rules.yaml`. Two port runs of the same source spec at the same `port_translation_rules_version` produce byte-identical destination artifacts (R4 round-trip determinism). When two rules conflict, lower-id wins; conflict recorded in `unresolved_translations[]`.

## R5-strict check at port time

Per design doc §7. The skill consumes `scripts/lib/r5_check.compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result`. The four harness states map to the schema's six-state enum; the two extended states (`warn-target-strengthens-source`, `fail-source-omits-target-constraint`) are emitted when the port skill detects direction-specific source-vs-target asymmetries beyond what the harness compares.

A port-time R5 fail is a `human_todos[]` entry, not a CI failure. The port still ships; humans decide whether to merge.

## Quality bar (D3 acceptance gates)

D3 considers the skill production-ready only when, for each MVP pair:

1. Emitted Go compiles cleanly via `go build ./adapters/{bidder}/...`.
2. Emitted tests pass via `go test ./adapters/{bidder}/...`.
3. Adapter-coverage report (per upstream `./scripts/check_coverage.sh`) ≥ 80% (real-world median; well above the 30% CI minimum).
4. `gofmt -s -l` exits with no diff; `go vet ./adapters/{bidder}/...` exits clean.
5. `TestBidderUniquenessGatekeeping` passes (first-6-letter prefix unique against current `coreBidderNames`).
6. Emitted YAML validates against Go's `static/bidder-info/_schema.json`; emitted JSON validates against the bidder-params schema convention.
7. `port-report.json` schema-validates against `port-report.schema.json` v0.2.0.
8. `r5_check.state` matches the per-pair expectation in `docs/execution-plan-phase-d.md` §D3.3.

## References

- **Design doc**: [`../../docs/methodology/port-skills-design.md`](../../docs/methodology/port-skills-design.md) — 7-step pipeline + conflict resolution + novel-pattern handling.
- **Execution plan**: [`../../docs/execution-plan-phase-d.md`](../../docs/execution-plan-phase-d.md) — D3 acceptance criteria + per-pair expectations.
- **Rules corpus**: [`../read/skills/shared/port-translation-rules.yaml`](../read/skills/shared/port-translation-rules.yaml) — 46 rules at v0.2.0; the SKILL pins to this version. Round-Trip Safety section pre-declares lossy-direction asymmetries.
- **Output schema**: [`../read/skills/shared/port-report.schema.json`](../read/skills/shared/port-report.schema.json) — port-report contract (v0.2.0).
- **Source-spec schema**: [`../read/skills/shared/adapter-spec.schema.json`](../read/skills/shared/adapter-spec.schema.json) — what the source spec must satisfy.
- **R5 lib**: [`../../scripts/lib/r5_check.py`](../../scripts/lib/r5_check.py) — R5 comparator (Phase D0.1).
- **Port engine**: `../../scripts/lib/port_engine.py` — 9 mechanical helpers (D1.2 deliverable).
- **Inverse porting guide**: `references/porting-guide.md` — D1.3 authors this; analogue of upstream Java's `bid-adapter-porting-guide.md` (Go has no upstream equivalent).
- **Reflection loop**: [`../../docs/methodology/reflection-loop.md`](../../docs/methodology/reflection-loop.md) — Phase F consumes `port-report.json::human_todos[]` and `unresolved_translations[]`.

### Per-skill subdirectories

- [`references/`](references/) — Go-target emission references (D1.3 fills): `go-artifact-shapes.md`, `pr-shape.md`, `registration-rules.md`, `porting-guide.md` (internally authored — Go has no upstream equivalent).
- [`templates/`](templates/) — Jinja templates for Go artifact emission (D3 fills): `bidder.go.j2`, `bidder-test.go.j2`, `imp-ext-pojo.go.j2`, `bidder-info.yaml.j2`, etc.
