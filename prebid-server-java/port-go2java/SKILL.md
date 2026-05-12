---
name: port-go2java
description: Translates a Go-source Adapter Spec (prebid-server-go/read/specs/{bidder}/latest.yaml or .tmp/full-loop/{run-id}/go/{bidder}.yaml) into Java artifacts under prebid-server-java/src/main/java/org/prebid/server/bidder/{bidder}/ plus paired YAML, bidder-params, IT fixtures, and Spring config. USE WHEN porting a new (or existing) Go bid adapter to the Java codebase. Walks the 46 port-translation rules, applies the 7-step pipeline, emits port-report.json.
version: 0.5.0
---

# port-go2java (Go → Java)

> **Status: D2.8 operator validation complete (2026-05-11).** All 6 MVP pairs (`kobler`, `aax`, `adkernelAdn`, `adverxo`, `vungle`, `thetradedesk`) demonstrably portable Go → Java end-to-end via a 6-canary batch run (`feat/d2.8-port-go2java-validation`). Final state: **4/7 D2.3 gates green for every MVP pair** (Gate 1 mvn compile, Gate 4 mvn checkstyle:check, Gate 6 port-report.json schema v0.2.0, Gate 7 r5_check.state matches per-pair expectation). Gates 2 (mvn test) + 3 (Jacoco ≥ 90%) blocked on operator-fillable test scaffolds; Gate 5 has a doc gap in execution-plan-phase-d.md §183 (referenced schema files don't exist in upstream Java; F-new-62). Pipeline prose (D2.1); 11 Jinja templates (D2.1-D2.7); F2 SKILL fixes landed Tier 0 (universal checkstyle), Tier 1 (universal javac), Tier 3 (entity-mutation scaffold per Rule 5 + 4 endpoint-resolution scaffolds per Rule 11/12/13 + F3/F4/imp.ext single-canary scaffolds); `extract_entity_strategies` port_engine helper. Traces under `docs/runs/d2.8-*-canary-2026-05-11.md`; cross-canary findings at `docs/runs/d2.8-cross-canary-summary.md`. Frontmatter bumps to 1.0.0 once Gates 2 + 3 are routinely cleared by operator-completed scaffolds AND a green-field validation canary lands (D3.8-canary-8 analog).

## What this skill does

Takes a structured Go-source Adapter Spec (read by `prebid-server-go/read/skills/read-adapter-orchestrator`) and emits the Java artifacts that satisfy R5-strict cross-language equivalence at port time. Applies the 46 port-translation rules from `../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`. Emits a `port-report.json` documenting what was applied, what was novel, and what needs human review.

**Source** (this skill consumes): `prebid-server-go/read/specs/{bidder}/latest.yaml`, or transient at `.tmp/full-loop/{run-id}/go/{bidder}.yaml` when running under the Teal flow.

**Target** (this skill emits): Java artifacts at the canonical paths per `references/java-artifact-shapes.md` (D1.3 deliverable):

- `src/main/java/org/prebid/server/bidder/{bidder}/{Bidder}Bidder.java`
- `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}Configuration.java`
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java`
- `src/main/resources/bidder-config/{bidder}.yaml`
- `src/main/resources/static/bidder-params/{bidder}.json` (byte-copy from Go per Rule 38)
- `src/test/java/org/prebid/server/bidder/{bidder}/{Bidder}BidderTest.java`
- `src/test/java/org/prebid/server/it/{Bidder}Test.java`
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-auction-{bidder}-{request,response}.json`
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-{bidder}-bid-{request,response}.json`
- `src/test/resources/org/prebid/server/it/test-application.properties` (append two lines)

**Out of scope** (handled elsewhere or future): writing a Java adapter from scratch (`write/`, future); reviewing post-merge (`review/`, future composition); analytics modules / RTD modules / general modules / delta-ports (deferred per execution-plan-phase-d.md "Out of scope").

## Invocation

```bash
# One-shot Teal flow (read → port → review):
$ orchestrator port \
    --source-lang=go \
    --target-lang=java \
    --bidder={bidder} \
    --source-spec=prebid-server-go/read/specs/{bidder}/latest.yaml \
    --target-branch=feat/{bidder}-java-port \
    --run-id=2026-05-04T1430Z-a3f9

# Direct invocation (when the source spec is persisted):
$ /port-go2java --bidder={bidder} --target-branch=feat/{bidder}-java-port

# Spec-only port (no Java code emitted; useful for design review):
$ /port-go2java --bidder={bidder} --dry-run
```

Pre- and post-conditions per `../../docs/methodology/port-skills-design.md` §2.

## Pipeline (7 steps)

Per design doc `../../docs/methodology/port-skills-design.md` §3. Phase D2 (this commit) fills each step's body. The SKILL is a prose-driven document the LLM follows in order; mechanical helpers from `scripts/lib/port_engine.py` are invoked via `Bash` tool calls; templates at `templates/*.j2` are rendered via Python's Jinja2 (operator may use `python3 -c 'import jinja2; ...'` from a Bash tool call, or the SKILL invokes a thin renderer script).

### Step 1 — Load + validate source spec

**Inputs.** Source spec YAML, located by precedence:

1. `--source-spec=<path>` flag (operator override).
2. `${FULL_LOOP_RUN_ID}` env var set OR `--run-id=<id>` flag → load `.tmp/full-loop/{run-id}/go/{bidder}.yaml`.
3. `--bidder=<name>` flag (no run-id) → load `prebid-server-go/read/specs/{bidder}/latest.yaml` (the persisted golden).

If multiple sources are present and they disagree, abort with `ERROR: source spec resolution conflict — use exactly one of --source-spec, --run-id, or --bidder`.

**Validation.** Load the YAML via `yaml.safe_load`. Validate against `../../prebid-server-go/read/skills/shared/adapter-spec.schema.json` using the `jsonschema` library. On a validation error, abort with the violation path + JSON-Path expression so the operator can repair the source spec. Never proceed past Step 1 with a malformed spec — Steps 2-5 assume schema-valid input and behave undefined otherwise.

**Direction gate.** Confirm `source_language == "go"`. If `source_language == "java"`, abort with `ERROR: this skill ports Go → Java; for Java → Go use port-java2go (lives at prebid-server-go/port-java2go/)`. Other values (`null`, missing, `"js"`) abort with `ERROR: source_language must be "go"`.

**Loaded state.** After Step 1, the SKILL holds:

- `source_spec: dict` — the parsed Go-source spec, schema-valid.
- `bidder_name_go: str` — `source_spec.meta.bidder_name`, the Go YAML name (lowercase or camelCase).
- `bidder_constant_go: str` — `source_spec.cross_language.go_artifacts.bidder_constant`, the `openrtb_ext.Bidder{X}` form.
- `run_id: str` — explicit `--run-id` value OR `${FULL_LOOP_RUN_ID}` OR a freshly-generated ISO-like timestamp `YYYY-MM-DDTHHMMZ-{6-hex}`.
- `output_root: Path` — `.tmp/full-loop/{run-id}/java/` (transient) OR `prebid-server-java/port-go2java/output/{bidder}/` (persisted via `--persist`).

### Step 2 — Discover the bidder family

**Family classification.** Read `source_spec.meta.is_alias`, `source_spec.meta.parent_aliases`, `source_spec.aliases`, `source_spec.meta.empire_parent_flavor`. Classify into one of four shapes:

| Shape | Condition | Examples |
|---|---|---|
| `primary` | `meta.is_alias == false` AND no aliases declared | kobler, vungle, thetradedesk |
| `alias-child` | `meta.is_alias == true` AND `aliasOf` declares a parent | 152media (alias of adkernel) |
| `empire-parent` | `meta.is_alias == false` AND `aliases[]` declares N children | adverxo (3 children: adport, bidsmind, mobupps); smarthub (10 children) |
| `empire-child` | `meta.is_alias == true` AND `meta.empire_parent_flavor != null` | individual smarthub aliases |

Rule 44's "alias-empire flavor coherence" classifies whether all empire children share the parent's flavor (same `bidder_info.endpoint_construction.kind`, same Site/App capabilities, etc.) — Step 3 walks Rule 44 explicitly.

**Auxiliary spec loading.** For empire-parent shapes, the SKILL also loads each child's spec at `prebid-server-go/read/specs/{child}/latest.yaml` so Rule 33 (alias-graph invert) has the full per-child bidder_info. If a child spec is missing, abort with `ERROR: empire-parent {bidder} declares aliases [...] but child spec at {path} is missing — re-run read-orchestrator on the child first`.

For alias-child shapes, the SKILL loads the parent spec (the alias inherits parent behavior; the Java emission consolidates into the parent's bidder-config rather than emitting a separate Java adapter for the child).

**Loaded state addition.** After Step 2, the SKILL also holds:

- `family_shape: str` — one of `primary | alias-child | empire-parent | empire-child`.
- `aux_specs: dict[str, dict]` — child specs (for empire-parent) or parent spec (for alias-child); empty for primary.

### Step 3 — Apply rules (Go → Java direction)

**Rule walk algorithm.** Iterate `../../prebid-server-go/read/skills/shared/port-translation-rules.yaml::rules[]` in declared order. For each rule:

1. Read `rule.spec_field_driver` (a dotted path like `bidder_info.endpoint`). If the driver field is absent / null on `source_spec`, emit `verdict: skipped-not-applicable` with `summary: "spec_field_driver={path} is null/absent"` and continue.
2. Otherwise check `rule.applies_when` (when present): a YAML predicate over the spec. If the predicate is false, emit `verdict: skipped-not-applicable` and continue.
3. Check `rule.directionality`: some rules are source-language-only (e.g., a Go-specific quirk that has no Java analog). If `directionality: go-source-only`, emit `verdict: skipped-source-side-only` and continue.
4. Otherwise apply the rule. The application path differs for mechanical-ready rules (priority list below) versus prose-driven rules (the remaining 36).

**Mechanical-ready rules (10 of 46).** Each has a port_engine helper that performs the transformation. The SKILL invokes the helper, captures the output, and updates the working state.

| # | Rule | Helper | Output |
|---|---|---|---|
| 1 | Rule 38 — bidder-params byte-fidelity | `port_engine.byte_copy(source_path, dest_path)` | Java `static/bidder-params/{bidder}.json` is byte-identical to Go's. SHA-256 verified post-copy. |
| 2 | Rule 46 — naming-convention normalization | `port_engine.normalize_bidder_name(go_name, target_lang='java')` | Java YAML name (lowercase + drop non-`[a-z0-9]`); allow-list overrides for rebrands like `cadent_aperture_mx → emxdigital`. Stored at `dest_spec.meta.bidder_name`. |
| 3 | Rule 33 — alias-graph invert | `port_engine.alias_graph_invert(parent_spec, alias_specs, direction='go-to-java')` | Java `aliases:` block content for the parent's bidder-config YAML. Per-child overrides for diverging fields only. |
| 4 | Rule 44 — alias-empire flavor coherence | inline check (no helper) | Verify each empire child's `bidder_info` flavor matches parent's. Divergences emit `quirks[]: alias-empire-flavor-divergence`. |
| 5 | Rule 36 — fixture-inventory parity → semantic-coverage parity | inline + Jinja template | Re-author Java IT 4-file split from Go's flat fixtures. Document unreachable-error-paths exclusions per the porting guide. |
| 6 | Rule 42 — IAB-cat storage translation | `port_engine.iab_table_translate(direction='go-to-java', source_artifact=<go_iab_file_contents>)` | Java YAML `adapters.{bidder}.iab-cat-mapping` dict. Only invoked when `source_spec.iab_category_storage.storage_kind == "go-data-table"`. |
| 7 | Rule 35 — config-properties subclass scaffolding | inline + Jinja template | Emit `{Bidder}BidderConfigurationProperties` Java class when source has `cross_language.go_specific_concerns[]: hardcoded-dev-endpoint` (Kobler-style). The class promotes Go's hardcoded constant to a Spring-config typed field. |
| 8 | Rule 39 — derived-view | no-op | The rule is read-side-only — no port-side action. Always emits `verdict: skipped-source-side-only`. |
| 9 | Rule 19 — standard headers (`HttpUtil.headers()` collapse) | inline | When source's `headers_constructed.has_only_standard_headers == true`, the Java template uses `HttpUtil.headers()` shorthand instead of explicit `MultiMap.add(...)` calls. |
| 10 | Rule 30 — canonical Go status helpers ↔ Java framework default | inline | Source's `code.make_bids.http_status_handling.kind` ∈ {`canonical-go-helpers`, `legacy-raw-go`} maps to Java's framework-default behavior (no explicit status-check code in `MakeBids`). Quirk emitted if source uses `legacy-raw-go` (suggests upstream-Go cleanup opportunity). |

**Prose-driven rules (36 of 46).** For each, walk the rule's prose `description` and `worked_examples[]` and apply the translation inline. Capture artifact-level outputs (e.g., new fields on the destination spec, new lines on the dest YAML) in the working state. Examples:

- **Rule 1 — Imp.ext two-phase unmarshal**: emit `static final TypeReference<ExtPrebid<?, ExtImp{Bidder}>> {BIDDER}_EXT_TYPE_REFERENCE` + `mapper.mapper().convertValue(imp.getExt(), {BIDDER}_EXT_TYPE_REFERENCE).getBidder()` in `{Bidder}Bidder.java`'s parsing helper.
- **Rule 5 — mutation strategy pairing**: source `entity_strategies.{Imp,Device,User,Site,App,Cur,Banner}.kind` translates to Java's `lombok-tobuilder` immutable-rebuild pattern in the corresponding `make_requests` template path. The full `entity_strategies` dict from `source_spec.code.make_requests.mutation.entity_strategies` is extracted via [`port_engine.extract_entity_strategies(source_spec)`](../../scripts/lib/port_engine.py) and passed as `ctx.entity_strategies` to `bidder.java.j2`. The template's makeHttpRequests body emits a `BidRequest.toBuilder()...build()` scaffold with per-entity TODO comments for non-passthrough/non-none strategies (operator fills the specific mutation logic). Strategy-specific guidance is layered onto the TODOs: F-new-86 (Site `replace-with-app-synthesis` / App `synthesize-app-replacement`, vungle ADR-007 F3 master sample) and F-new-91/F-new-92 (Imp `imp.ext` three-key wrapper repack + buyer-UID promotion) call out their distinctive emit patterns inline.

- **ADR-007 F4 / F-new-100 — bid-post-processing-macro substitution**: when source spec carries a `bid-post-processing-macro` edge-case taxon in `quirks_emitted[]` (thetradedesk is the master sample), the subagent sets `ctx.has_bid_post_processing_macros=true`. `bidder.java.j2` then inserts a `.map(this::applyBidPostProcessingMacros)` step in the extractBids stream and emits an `applyBidPostProcessingMacros(Bid)` helper scaffold with TODO guidance for `${AUCTION_PRICE}` substitution into `bid.nurl/adm/burl`. Operator wires the actual substitution per source spec helpers (e.g., thetradedesk's `resolveAuctionPriceMacros` using `bid.getPrice().toPlainString()`).
- **Rule 11 — multi-token-substitution endpoint**: emit a `String.format(...)` or Spring EL `#{...}` substitution depending on the macro count (`> 2` → Spring EL via `BidderConfigurationProperties`; `≤ 1` → simple `String.replace`).
- **Rule 30 — canonical-helpers status handling maps to Java framework-default**: source `code.make_bids.http_status_handling.kind ∈ {canonical-go-helpers, legacy-raw-go}` translates to **no explicit status-check code** in Java's `MakeBids`. Java's HTTP layer handles 204 NO_CONTENT and non-200 codes before `makeBids` is invoked (matches upstream `KoblerBidder` pattern). When `ctx.http_status_kind == "canonical-helpers"`, `bidder.java.j2` emits a 3-line Java `//` comment explaining the rule application (so reviewers of the emitted code understand why there's no status check) and skips the `HttpResponse response = httpCall.getResponse()` extraction. The `HttpResponse` import is made conditional on the same predicate. F-new-90 retired the non-existent `BidderUtil.isResponseStatusCodeNoContent` / `.checkResponseStatusCode` calls our template had previously emitted under the canonical-helpers branch.

#### Filename ↔ class-name pairing for Configuration.java (`ctx.config_class_name`)

Upstream prebid-server-java uses two conventions for the Spring DI configuration class: most bidders use `<Root>Configuration.java` (the canonical form — `KoblerConfiguration`, `AaxConfiguration`, etc.), but a minority use `<Root>BidderConfiguration.java` (`AdverxoBidderConfiguration`, `DianomiBidderConfiguration`, `AdnuntiusBidderConfiguration`). Since a public Java class name must match its file name, the SKILL's pipeline driver must keep both in sync.

The `configuration.java.j2` template accepts `ctx.config_class_name` to set the internal class name (defaults to `<ctx.bidder_class_root>Configuration` when absent). The Step 5 file-emission path must pair the chosen class name with the matching filename — both `<ctx.config_class_name>.java` (e.g., `AdverxoBidderConfiguration.java`) is required when `ctx.config_class_name` is set; failing to pair the two yields a `checkstyle:OuterTypeFilename` violation (F-new-79). The canary 4 driver (`adverxo`) demonstrates the canonical pairing: it sets `cfg_ctx["config_class_name"] = f"{class_root}BidderConfiguration"` AND writes the artifact to `src/main/java/.../{class_root}BidderConfiguration.java`. For default `<Root>Configuration` cases, omit `ctx.config_class_name` and emit to `<Root>Configuration.java`.

The SKILL must NOT skip a prose-driven rule silently. If the rule's `spec_field_driver` is non-null but the SKILL cannot determine how to apply the rule (e.g., a novel pattern), emit `verdict: applied-with-warning` AND populate `unresolved_translations[]` with `reason: ambiguous-rule-match` so Phase F can triage.

**Composition (per design §5.1).** When two rules apply to overlapping artifacts, lower-id wins on artifact placement; higher-id transforms the lower-id's output. Example: Rule 11 emits the endpoint URL, Rule 35 emits a typed-config field; Rule 35 runs FIRST (creates the config field), then Rule 11 substitutes the field's value into the URL. The SKILL records both rule applications in `rules_consumed[]` independently.

**Conflict (per design §5.3).** Genuine winner-take-all conflicts are rare (none in the current rule corpus). When detected (two rules emitting mutually-exclusive artifacts at the same path), apply the lower-id rule and record the higher-id loser in `unresolved_translations[]` with `reason: conflicting-rules` and `ambiguous_rule_ids: [lower, higher]`.

**Loaded state addition.** After Step 3, the SKILL holds:

- `rules_consumed: list[dict]` — one entry per rule walked; populates `port-report.json::rules_consumed[]`.
- `dest_spec_partial: dict` — destination Java spec, partially constructed (the rules add to it incrementally).
- `quirks_emitted: list[dict]` — quirks the rule walk surfaced (e.g., `hardcoded-config-as-anti-pattern` when Rule 35 promotes a Go const).
- `unresolved_translations: list[dict]` — ambiguous / conflicting / novel patterns for Phase F triage.

### Step 4 — Author the destination spec

**R5-strict-shared field carry-over.** These fields appear in both Go and Java specs with identical semantics; copy verbatim from `source_spec` to `dest_spec`:

- `bidder_info.capabilities`
- `bidder_info.gvl_vendor_id`
- `bidder_info.endpoint_compression`
- `bidder_info.geoscope`
- `bidder_info.maintainer`
- `bidder_info.modifying_vast_xml_allowed`
- `bidder_info.endpoint` (form-divergent per language; Step 3 Rule 11 already normalized)
- `params.schema_interpretation.{required_fields, combinators_used, flexible_types}`
- `bidder_params_json` (verbatim string)

**Java-specific construction.** Build the Java-only spec blocks:

- `spring_config.factory_method`: `{bidder}BidderDeps` (Spring DI bean factory naming convention).
- `spring_config.property_source_path`: `classpath:/bidder-config/{bidder}.yaml`.
- `spring_config.bidder_creator_lambda`: `config -> new {Bidder}Bidder(config.getEndpoint(), mapper)` (or with `currencyConversionService` arg when `currency_conversion.used == true`).
- `spring_config.configuration_properties_class`: present iff Rule 35 was applied; the typed-config subclass.
- `bidder_class.name`: `{Bidder}Bidder` (PascalCase from Rule 46 + brand-acronym table).
- `bidder_class.package`: `org.prebid.server.bidder.{bidder}`.
- `bidder_class.constructor.parameters`: derived from Rule 9 (request-type) + Rule 28 (currency).
- `code_naming.identifier_workaround`: `digit-leading-rename` when source `meta.bidder_name` starts with a digit (Java edge case #26 — `33across` → Java class root `ThirtyThreeAcross`).

**Cross-language metadata.** Set `dest_spec.cross_language.java_artifacts.{bidder_class, bidder_dir, config_class, proto_dir, yaml_path}` to the canonical paths. Set `dest_spec.cross_language.port_lineage`:

```yaml
port_lineage:
  source_language: go
  source_pr: <source_spec.provenance.source.pr_url or null>
  destination_language: java
  destination_pr: null   # not yet opened; Step 7 emits PR draft
  port_translation_rules_version: <from rules YAML>
  port_skill_version: <from this SKILL.md frontmatter>
  fidelity_review_themes:
    - port-fidelity
    - <one entry per applied prose-driven rule, e.g., 'rule-46-naming-normalization'>
```

**bidder_params_sha256 re-compute.** SHA-256 of `dest_spec.bidder_params_json`. Since Rule 38's byte-copy produced byte-identical JSON, this MUST equal `source_spec.bidder_params_sha256`. If they differ, the SKILL has bug; abort with `ERROR: bidder_params_sha256 mismatch — Rule 38 byte-copy invariant violated`.

**Provenance pinning.** `dest_spec.provenance.source.resolved_commit = source_spec.provenance.source.resolved_commit` — the Java port is point-in-time relative to the source. `dest_spec.provenance.read.timestamp_utc` is fresh (the moment the Step ran).

**Loaded state addition.** After Step 4, the SKILL holds:

- `dest_spec: dict` — the complete Java-source destination spec, schema-valid against `adapter-spec.schema.json`.

### Step 5 — Emit Java artifacts

**Output directory.** All emitted files land under `output_root/` (Step 1 set this to `.tmp/full-loop/{run-id}/java/` or `prebid-server-java/port-go2java/output/{bidder}/`). The directory is created if missing. Existing files at the same paths are overwritten (the port is idempotent on re-run).

**Per-file template invocation.** Each Java artifact is rendered from a Jinja2 template under `templates/`. Template inputs are a `context` dict assembled from `dest_spec` plus the applied `rules_consumed` list (so templates can branch on rule-specific knowledge — e.g., the `bidder.java.j2` template checks if Rule 35 fired and includes the typed-config import accordingly).

| File | Template | Notes |
|---|---|---|
| `src/main/resources/bidder-config/{bidder}.yaml` | `bidder-config.yaml.j2` | Kebab-case YAML keys per `references/java-artifact-shapes.md` §11. |
| `src/main/resources/static/bidder-params/{bidder}.json` | `byte_copy` (no template) | Byte-identical to Go's per Rule 38; SHA-256 verified. |
| `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java` | `ext-imp-pojo.java.j2` | Lombok @Builder + @Value + @JsonProperty annotations. |
| `src/main/java/org/prebid/server/bidder/{bidder}/{Bidder}Bidder.java` | `bidder.java.j2` | Implements `Bidder<BidRequest>`; Rule-specific control flow per `rules_consumed`. |
| `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}Configuration.java` | `configuration.java.j2` | Spring DI; `BidderDepsAssembler` factory bean. |
| `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}BidderConfigurationProperties.java` | `configuration-properties.java.j2` | Rule 35 only; emitted when typed-config promotion applies. |
| `src/test/java/org/prebid/server/bidder/{bidder}/{Bidder}BidderTest.java` | `bidder-test.java.j2` | JUnit 5; ≥90% line-coverage target. |
| `src/test/java/org/prebid/server/it/{Bidder}Test.java` | `it-test.java.j2` | IT class; one `@Test` per fixture pair. |
| `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-auction-{bidder}-{request,response}.json` | `it-fixture-auction-{request,response}.json.j2` | Per-call fixtures; populated from `tests.fixture_inventory.exemplary[]`. |
| `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-{bidder}-bid-{request,response}.json` | `it-fixture-bid-{request,response}.json.j2` | Per Rule 36. |
| `src/test/resources/org/prebid/server/it/test-application.properties` | NO TEMPLATE — append two lines | `adapters.{bidder}.enabled=true\nadapters.{bidder}.endpoint=http://localhost:8090/{bidder}-exchange\n` appended at end-of-file. |

Templates emit checkstyle-compliant code by construction (ImportOrder strict 3-group, EmptyLineSeparator, LineLength≤120 — see `references/java-artifact-shapes.md` §4-6). The SKILL renders each template, writes to disk, and records the file path on `port_run.emitted_files[]`.

**PR-shape automation outputs.** Build the four port-report fields per `references/pr-template-mapping.md`:

- `recommended_pr_title`: `"Port {Bidder}: New Adapter"` for new-adapter ports; `"Port {AliasName}: New alias for {ParentName}"` for alias-only ports.
- `target_pr_label_recommendations`: `["do not port"]` (mandatory per upstream porting guide).
- `companion_docs_pr_draft`: emit `target_repo: prebid/prebid.github.io`, `file_path: dev-docs/bidders/{bidder}.md`, `body_markdown:` populated from `source_spec.bidder_info` + `params` + `meta`.
- `pre_submit_rebase`: see below.

**Pre-submit rebase.** The SKILL invokes (via Bash) `git -C {prebid-server-java-clone} fetch origin master && git rebase origin/master` against the operator's local prebid-server-java clone (path passed via `--target-clone=<path>`). On clean rebase, set `pre_submit_rebase.conflicts_detected = false`. On conflicts, set `conflicts_detected = true` AND `conflicts_summary` to a description of which files conflicted; the SKILL aborts before opening the PR with `ERROR: rebase conflicts; manual resolution required (see port-report.json::pre_submit_rebase)`.

If `--target-clone` is not provided, the SKILL skips the rebase step and emits `pre_submit_rebase: null` in the port-report. The operator MUST run the rebase manually before submitting.

**Pre-submit checkstyle dry-run (D4.3).** When `--target-clone=<path>` is provided AND `mvn` is on PATH, the SKILL invokes `port_engine.mvn_checkstyle_dry_run(target_clone)` (which shells out to `mvn -B checkstyle:check --file extra/pom.xml` from the clone directory, with a 300-second timeout). Each parsed violation surfaces as a `human_todos[]` entry with `category: style-violation`, populated `evidence_path: {file}:{line}`, and `summary: {message} [{rule}]`. When `mvn` is unavailable OR `--target-clone` is omitted OR the run times out, the SKILL emits one `human_todos[]: { category: style-violation, summary: "checkstyle dry-run skipped — {reason}" }` and proceeds.

> **First-run operator note (D4.3).** The helper recognizes two `maven-checkstyle-plugin` output formats: the legacy `[ERROR] /path/Foo.java:42:5: msg [Rule]` form AND the 3.x default `[ERROR] /path/Foo.java:[42,5] (group) Rule: msg` form. Both regexes are exercised in the unit-test suite via synthetic input. On the FIRST real run against the operator's local prebid-server-java clone, sanity-check the parsed violation count vs the raw mvn output — if mvn reports N violations but the helper's `human_todos[]` shows zero, the upstream plugin likely emits a third format we haven't accounted for. File the format upstream as a port-engine improvement and pass `runner=` to the helper to bypass parsing meanwhile.

The helper is hermetic (dependency-injected runner for tests); see `scripts/tests/test_port_engine.py::TestMvnCheckstyleDryRun` for exercised cases.

### Step 6 — R5-strict check at port time

**Re-read the destination spec.** Step 5 emitted the Java artifacts. To verify R5, the SKILL re-reads them as if it were a fresh read (using `prebid-server-java/read/skills/read-bidder-orchestrator` semantics, but invoked in-memory rather than re-running the orchestrator skill — the helper at `port_engine.r5_check_at_port_time(source_spec, dest_spec)` operates directly on the in-memory dicts).

**Comparator invocation.** Call `port_engine.r5_check_at_port_time(source_spec=source_spec, dest_spec=dest_spec)`. The helper routes through `r5_check.compare_pair(go_spec, java_spec, assertions=None, overall=None)` (no dual-spec assertions — the pair file may not exist for a new bidder). The result is an `R5Result` containing `diagnostics: list[R5Diagnostic]` and `state: str`.

**Direction-aware extension.** The helper returns one of four harness states (`pass | warn-byte-only-divergence | fail-semantic-divergence | skipped-no-pair-fixture`). The SKILL extends to six schema states by inspecting `dest_spec` vs `source_spec` for direction-specific asymmetries:

- If a `fail-semantic-divergence` diagnostic comes from a strict-key field where `source_spec` has a constraint but `dest_spec` lacks it → upgrade state to `fail-source-omits-target-constraint` (aax-style: Go-source enforces `minLength:1`; emitted Java would lack it; the port emits the constraint anyway and surfaces a `human_todos[]: upstream-confirmation` entry advising the operator to file a port-fidelity bug against upstream Go if it's stricter than the rest of the corpus).
- If a `warn-byte-only-divergence` diagnostic comes from a strict-key field where `dest_spec` carries an EXTRA constraint absent in `source_spec` → upgrade state to `warn-target-strengthens-source` (Connatix-style: Java has `minimum:0`/`maximum:1` that Go lacks; the port preserves the constraint).

**Port-time R5 fail is NOT a CI failure.** The port still ships its artifacts; the operator decides whether to merge. A `fail-*` state populates `human_todos[]` with category `byte-divergence-warning` (for `fail-source-omits-target-constraint`) or `upstream-confirmation` (for `fail-semantic-divergence`). The decision to merge is human review; the port skill never aborts on R5 fail at this step.

**Loaded state addition.** After Step 6, the SKILL holds:

- `r5_result: dict` — `{ state, byte_equal_fields, warn_fields, fail_fields, summary }` ready for `port-report.json::r5_check`.

### Step 7 — Emit port-report.json

**Assemble the port-report dict.** Build a Python dict matching `../../prebid-server-go/read/skills/shared/port-report.schema.json` v0.2.0:

```python
report = {
    "port_report_version": "0.2.0",
    "port_run": {
        "run_id": run_id,
        "source_lang": "go",
        "target_lang": "java",
        "source_spec_sha": sha256(source_spec_yaml_bytes),
        "target_branch": target_branch_or_null,
    },
    "rules_consumed": rules_consumed,           # from Step 3
    "quirks_emitted": quirks_emitted,           # from Step 3 + 4
    "r5_check": r5_result,                      # from Step 6
    "source_pr_url": source_spec.provenance.source.pr_url_or_null,
    "source_pr_merged_commit_sha": source_spec.provenance.source.resolved_commit,
    "source_discussion_anchors": [],            # populate if read-skill captured any
    "re_authored_paragraphs": [...],            # one entry per Rule 36-style re-authoring
    "recommended_pr_title": "Port {Bidder}: New Adapter",
    "target_pr_label_recommendations": ["do not port"],
    "upstream_bugs_to_file": upstream_bugs,     # from Step 6 fail-state analysis
    "companion_docs_pr_draft": {...},           # from Step 5
    "pre_submit_rebase": pre_submit_rebase_result_or_null,
    "human_todos": human_todos,                 # accumulated across Steps 3, 5, 6
    "unresolved_translations": unresolved_translations,
    "port_translation_rules_version": "0.2.0",
}
```

**Schema-validated write.** Call `port_engine.port_report_emit(report, path=output_root / "port-report.json")`. The helper validates against the schema and writes to disk. On validation failure, abort with `ERROR: port-report assembly violates v0.2.0 schema — {path}: {message}`. This is a SKILL bug (Step 7 should never produce an invalid report given valid Steps 1-6 outputs); operator should file an issue.

**Operator handoff.** Emit a final operator message summarizing:

- Files emitted at `output_root` (count + tree).
- `r5_check.state` and brief summary.
- `human_todos` count + brief list.
- `unresolved_translations` count + brief list.
- Next operator steps: review emission, run mvn locally if not done, open PR with `recommended_pr_title` + label `do not port`, submit companion docs PR.

The SKILL exits 0 on success regardless of `r5_check.state` — fail states are surfaced to the operator, not blocked. Exit non-zero only on hard failures (Step 1 schema violation, Step 4 SHA mismatch, Step 7 schema violation).

## Rule application order

Per design doc §4. Rules applied in declaration order from `port-translation-rules.yaml`. Two port runs of the same source spec at the same `port_translation_rules_version` produce byte-identical destination artifacts (R4 round-trip determinism). When two rules conflict, lower-id wins; conflict recorded in `unresolved_translations[]`.

## R5-strict check at port time

Per design doc §7. The skill consumes `scripts/lib/r5_check.compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result`. The four harness states map to the schema's six-state enum; the two extended states (`warn-target-strengthens-source`, `fail-source-omits-target-constraint`) are emitted when the port skill detects direction-specific source-vs-target asymmetries beyond what the harness compares.

A port-time R5 fail is a `human_todos[]` entry, not a CI failure. The port still ships; humans decide whether to merge.

## Quality bar (D2 acceptance gates)

D2 considers the skill production-ready only when, for each MVP pair:

1. Emitted Java compiles cleanly via `mvn -B compile --file extra/pom.xml`.
2. Emitted unit tests pass via `mvn -B test -Dtest={Bidder}BidderTest`.
3. Jacoco line-coverage on the new `{Bidder}Bidder.java` ≥ 90%.
4. `mvn -B checkstyle:check` exits 0.
5. Runtime validation via Java's `BidderParamValidator.java` accepts the emitted bidder-params JSON. NOTE: the literal schema files `bidder-info-schema.json` and `static/bidder-params/_schema.json` referenced in earlier drafts of `docs/execution-plan-phase-d.md` §183 do NOT exist in upstream `prebid-server-java`; Java validates via runtime code, not JSON schema files. Tracked as F-new-62 (LOW; doc gap, not a SKILL defect). For D2.8 this gate is N/A pending an execution-plan rewrite to invoke `BidderParamValidator` at mvn-test time.
6. `port-report.json` schema-validates against `port-report.schema.json` v0.2.0.
7. `r5_check.state` matches the per-pair expectation in `docs/execution-plan-phase-d.md` §D2.3.

## References

- **Design doc**: [`../../docs/methodology/port-skills-design.md`](../../docs/methodology/port-skills-design.md) — 7-step pipeline + conflict resolution + novel-pattern handling.
- **Execution plan**: [`../../docs/execution-plan-phase-d.md`](../../docs/execution-plan-phase-d.md) — D2 acceptance criteria + per-pair expectations.
- **Rules corpus**: [`../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) — 46 rules at v0.2.0; the SKILL pins to this version.
- **Output schema**: [`../../prebid-server-go/read/skills/shared/port-report.schema.json`](../../prebid-server-go/read/skills/shared/port-report.schema.json) — port-report contract (v0.2.0).
- **Source-spec schema**: [`../../prebid-server-go/read/skills/shared/adapter-spec.schema.json`](../../prebid-server-go/read/skills/shared/adapter-spec.schema.json) — what the source spec must satisfy.
- **R5 lib**: [`../../scripts/lib/r5_check.py`](../../scripts/lib/r5_check.py) — R5 comparator (Phase D0.1).
- **Port engine**: `../../scripts/lib/port_engine.py` — 9 mechanical helpers (D1.2 deliverable).
- **Upstream porting guide**: `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` — maintainer-authored spec the SKILL version-pins to.
- **Reflection loop**: [`../../docs/methodology/reflection-loop.md`](../../docs/methodology/reflection-loop.md) — Phase F consumes `port-report.json::human_todos[]` and `unresolved_translations[]`.

### Per-skill subdirectories

- [`references/`](references/) — Java-target emission references (D1.3 fills): `java-artifact-shapes.md`, `pr-template-mapping.md`, `registration-rules.md`, `porting-guide.md` (pinned to upstream SHA).
- [`templates/`](templates/) — Jinja templates for Java artifact emission (D2 fills): `configuration-properties.java.j2`, `bidder.java.j2`, `bidder-test.java.j2`, etc.
