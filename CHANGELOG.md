# Changelog

All notable changes to the Adapter Specification schema, behavior taxonomy, and
port-translation rules. Format follows [Keep a Changelog](https://keepachangelog.com/);
versioning is per ADR-001 D7 (SemVer string `X.Y.Z`).

The three independently-versioned artifacts are:

- **adapter_spec_version** — the JSON Schema at `prebid-server-go/read/skills/shared/adapter-spec.schema.json`
- **taxonomy_version** — the behavior taxonomy at `prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`
- **port_translation_rules_version** — the rule corpus at `prebid-server-go/read/skills/shared/port-translation-rules.yaml`

Every entry references the ADRs (`docs/decisions/`) that drove the change.

---

## [adapter_spec_version 1.2.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] — 2026-05-03

Wave 11b / Phase 2.8 — schema closure + gate enforcement reality alignment.
Closes 17 accidentally-open `additionalProperties: true` sites that were
Phase 2.0/2.4/2.7 punts; lifts 4 top-level open-maps to structured `$defs`;
closes 8 round-2 sweep sites under `code.*` and `cross_language.*`;
tightens R5/R8/R3/Rule-33 enforcement; deletes redundant Rule 38 lint
check; replaces the leaf-key phantom-path escape with path-aware
vocabulary lookup.

All 40 existing goldens continue to validate against the tightened schema.
Per `docs/methodology/schema-versioning.md` MINOR criteria (clarified in
this wave to explicitly cover closure-as-MINOR), no MAJOR bump required.

### Added (schema $defs — Wave 11b B3 + B3+)

22 new `$defs` total. Top-level lift-to-$defs replacing Tier C open-maps:

- `SpringConfig` (was top-level `spring_config` open-map; declares
  factory_class, factory_method, property_source_path,
  bidder_creator_lambda, configuration_properties_class, bean_dependencies,
  factory_class_package, notes).
- `BidderClass` (was top-level `bidder_class`; declares name, parameterized
  request/response types, override_methods, constructor, static_fields,
  helper_classes_co_located/in_proto/in_model, notes).
- `CodeNaming` (was top-level `code_naming`; declares class_name_root,
  yaml_name, preserves_acronym_case, identifier_workaround, package_name,
  notes).
- `Lifecycle` (was top-level `lifecycle`; restructured per round-1 finding
  that 14 keys nest under `lifecycle.rename`, not at lifecycle top-level).
- Plus nested children: `ConfigurationPropertiesClass`,
  `ConfigurationPropertyField`, `ConfigurationPropertyNestedClass`,
  `ConfigurationPropertyNestedClassField`, `BeanDependency`,
  `BidderClassConstructor`, `BidderClassConstructorParameter`,
  `BidderClassStaticField`, `LifecycleRename`, `LifecycleMove`.

Round-2 sweep additions (B3+) under `code.*` and `cross_language.*`:

- `CodeImports` (4 keys: has_currency_helper, has_jsonutil,
  has_template_engine, third_party).
- `AdapterStruct` (3 keys + nested fields[] items).
- `CodeBuilder` (4 keys + errors_returned[] items as oneOf string|object).
- `MakeRequests` (6 sub-objects + helpers[] with name/signature item shape).
- `MakeBids` (8 universal + notes_currency + helpers[] for parity).
- `GoArtifacts` (3 universal + 9 per-bidder file-path artifacts).
- `JavaArtifacts` (5 universal + declared_in for huaweiads).
- `PortConcerns` (6 universal booleans).

### Changed (schema closures — Wave 11b B1 + B2)

Tier A (B1) — flipped `additionalProperties: true → false` at 6
zero-extra sites: `Code`, `code.file_layout.files[]` items,
`headers_constructed.custom_headers[]` items, `aliases[].test_assets`,
`aliases[].test_application_properties_entries[]` items, `CrossLanguage`
top-level. `Code` description updated to past-tense closure note.

Tier B (B2) — additive closures at 9 sites with property additions:
`code.file_layout` (+ file_count_total, notes from huaweiads), `Tests`
(+ test_application_properties_keys), `IabCategoryStorage` (+ notes),
`ExtPojoConstruction.custom_unmarshal` (+ notes), `HeadersConstructed`
(+ authentication_algorithm, authentication_output_encoding, notes),
`DeployTimeToken` (+ file, line, on_alias as STRING [plan corrected
from "boolean"], notes as oneOf string|array per dual emitter shape),
`Quirk` (+ line). Plus Provenance.warnings/items + language_stamped_headers/items
flipped directly.

Plan correction: `on_alias` is `string-or-null` (alias name like
"appStockSSP"), not `boolean-or-null` as plan said. teqblaze's `note:`
also renamed to `notes:` (corpus normalization; both teqblaze and rubicon
prose are golden-author commentary, not upstream Java quotes).

### Tightened (Wave 11b B4)

- `if/then` invariants: Go specs now require `code_naming: null` and
  `registry: null` (in addition to spring_config/bidder_class). Java
  alias specs (`meta.is_alias: true`) now require `spring_config: null`
  and `bidder_class: null` (152media-Java's existing values confirmed).
- Port_lineage shared-genesis invariant DEFERRED to Wave 11c C4
  (freewheelssp-Java's `destination_language: null` is captured as
  ADR-007 F2 contradicted exemplar; tightening would unilaterally
  invalidate that evidence).

### Tightened (Wave 11b B4 — failure-swallow fixes)

- `round-trip-ci.py` R1 network probe: `gh_path_exists` refactored to
  raise `GhApiUnreachable` on auth/rate-limit/network failures (Wave 10
  recipe propagated). Top-level handler in `main()` exits 3 with
  diagnostic. Fixes the same false-FAIL-flood class as audit-golden.py.
- `lint-port-rules.py:discover_pairs`: returns `(pairs, errors)` tuple;
  raises FileNotFoundError on missing fixtures dirs; emits Finding(
  rule_id=0, severity="fail") on YAML/IO load errors instead of
  swallowing or crashing.
- `coverage-report.py:discover_dual_specs`: scoped Exception catch to
  `(OSError, yaml.YAMLError)`; prints WARN to stderr and skips broken
  files instead of inserting `_parse_error` sentinel data.
- Renderer `consumed_keys` assertions: `render-taxonomy.py` and
  `render-port-rules.py` now raise ValueError on unrecognized YAML keys,
  catching the silent-drop class of bug. Each has injection regression
  test.

### R5 split (Wave 11b B4 C1 + B5 #2)

R5 divergent-keys bucket split into:
- `R5_FORM_DIVERGENT_KEYS` — endpoint URLs only. New
  `normalize_endpoint_macros()` canonicalizes Go `{{.X}}`, Java `${X}`,
  Spring EL `#{X}`, raw `{{X}}` to single `{{X}}` form. After
  normalization: deep_eq. Absence of dual-spec assertion when normalized
  values differ → FAIL `assertion_missing` (Wave 11b strictness).
- `R5_ADVISORY_DIVERGENT_KEYS` — endpoint_construction, default_enabled,
  alias_metadata, port_lineage, lifecycle_rename, reviewer_cohort,
  test_fixture_cost (preserved current behavior; documentation-only).

`R5_STRICT_KEYS` refactored from flat (spec_field, dual_key) tuples to
(spec_field, dual_key, comparator) three-tuples with per-key comparator
selection: `_list_set_eq` for 4 LIST-VALUED keys (capabilities, geoscope,
schema_interpretation.{required_fields, combinators_used,
flexible_types}); `_maintainer_eq` for the 1 PROSE-BEARING key
(maintainer.email-only); `deep_eq` for 4 PURE-DATA scalars.

Prerequisite corpus edit: aax dual-spec gained `bidder_info_endpoint`
assertion (severity:warn) documenting Java's
`?src={{PREBID_SERVER_ENDPOINT}}` extension.

### R8 expansion (Wave 11b B5 #7)

R8 endpoint-placeholder walker expanded from single-field
(`bidder_info.endpoint`) to multi-path collector covering user-sync URLs
(iframe/redirect.url + uid_macro + flat forms), `bidder_class.static_fields[*].value`,
plus the original endpoint. New macro registries:

- `USER_SYNC_MACROS` — admitted on user_sync paths. Both Go PascalCase
  and Java snake_case forms (GDPR/gdpr, GDPRConsent/gdpr_consent,
  USPrivacy/us_privacy, GPP/gpp, GPPSID/gpp_sid, RedirectURL/redirect_url,
  BidderName/bidder, UID/uid).
- `OPENRTB_MACROS` — universal. AUCTION_PRICE, AUCTION_BID_ID, etc. per
  OpenRTB 2.5 §4.1.

16 new R8 WARNs surface for bidder-specific identifiers (TokenID,
SourceId, SupplyId, etc.) — legitimate signals for documentation, not
breaking changes.

### Removed (Wave 11b B5 #8)

- `rule_38_bidder_params_byte_fidelity` deleted from `lint-port-rules.py`.
  Redundant with R5's dual-spec-aware byte-divergence reporting; emitted
  13/14 pairs as warn with no actionable distinction. The Rule 38
  PRINCIPLE remains documented in `port-translation-rules.md:45-77` as
  a load-bearing port-translation rule; the runtime gate is R5.

### Promoted (Wave 11b B5 #8)

- Rule 33 (alias-graph inversion) promoted from `warn` to `fail`
  severity. 0 active warns across corpus; promotion turns alias-graph
  inversions into hard CI gates.

### Path-aware phantom detection (Wave 11b B5 #1)

`test_schema_jsonschema.py:test_no_truly_invented_keys_outside_open_maps`
rewritten to use path-aware vocabulary. New module-level helper
`_build_declared_at(schema)` returns `(declared_at, open_maps)`.
Replaces the prior leaf-key escape that admitted ANY key whose name
appeared anywhere in any `$defs.*.properties`. Closes Gap #2 (paths
like `code.builder.request_body` no longer slip through because
`request_body` is declared at `code.make_requests`, not `code.builder`).

### R3 strict-mode flipped default-on (Wave 11b B5 #3)

`--strict-r3` produced 40 PASS / 0 WARN / 0 FAIL across corpus; safe
to default-on. `--lenient-r3` opt-out preserves prior advisory mode for
contributors who deliberately under-document quirks.

### Doc-count regex extension (Wave 11b B5 #5)

`test_doc_count_claims.py` DISCOVERY_REGEX gained
`(?:java\s+)?(?:alias-)?empire\s+parents` alternation; canonical from
`coverage-report.py:INVENTORY_TOTALS["java_empire_parents"]`. Three
plan-recipe phrases ("N goldens", "N reference PRs", "N fixtures")
deferred — corpus uses each ambiguously.

### Counts

- Open-map prefixes: 28 → 11 (4 EXTENSION-SLOTS + 7 LEGITIMATELY-OPEN
  remain by design; Wave 11c may close 3 corpus-coupled sites).
- Accidentally-open sites: 17 → 0 (plus 8 round-2 sweep additions = 25
  total closures landed).
- Schema $defs: +22 new (12 → 34).
- Test count: 115 → 125 (+10 new across 7 commits).
- Wave 11b commits: 16 (1 plan + 15 implementation).

### Goldens posture

40 existing goldens stay at `adapter_spec_version: "1.0.0"`; they all
validate against the 1.2.0-tightened schema. Future fixtures using the
post-closure structure should declare `adapter_spec_version: "1.2.0"`.

### Goldens stock-validator compatibility (post-review fix)

Reviewer feedback flagged that direct JSON Schema validation of the
goldens with a stock validator failed 40/40: `provenance.read.timestamp_utc`
in every golden was an unquoted ISO datetime (YAML auto-parses to a
Python datetime), and the schema declares it as `"type": "string"`.
The CI's prior `_normalize()` step rewrote datetimes to ISO strings
before validation — papering over a real interoperability issue.

Fix: 42 surgical edits across the 40-golden corpus quote the affected
date/datetime values (`provenance.read.timestamp_utc` × 40 +
`lifecycle.rename.merged_at` × 2 elementaltv occurrences). The
`_normalize()` test crutch is removed, hardening the test against
future unquoted-date regressions. New regression test
`test_stock_yaml_load_emits_strings_for_date_fields` asserts every
golden's date fields parse as strings via stock `yaml.safe_load` —
catching the regression before any downstream consumer sees it.

External consumers can now use any stock JSON Schema 2020-12 validator
(jsonschema, ajv, etc.) directly against the goldens without a
preprocessing step.

### Unchanged

`taxonomy_version` stays at `1.0.0` (no behavior-taxonomy changes);
`port_translation_rules_version` stays at `0.2.0` (Rule 38 lint deletion
doesn't change rule taxonomy — Rule 38 the principle is preserved in
the rules YAML).

### Driving ADRs / methodology

- ADR-001 D5 (lifecycle.rename schema)
- ADR-001 D7 (SemVer string format)
- ADR-007 (novel-pattern schema additions; status flipped to "Partially
  implemented in Phase 2.8 / Wave 11b" with port_lineage shared-genesis
  invariant deferred to Wave 11c)
- `docs/methodology/schema-versioning.md` (closure-as-MINOR clarification
  added)
- Wave 11 plan: (Claude Code planning artifact)

### Wave 11c (FUTURE PR — separate from this one)

Corpus-coupled decisions deferred:
- C1: Alias canonical name field (`bidder_name` vs `name`).
- C2: `tests.fixture_inventory` typed-values closure.
- C3: `registry` migration to `tests.test_application_properties.*`.
- C4: `cross_language.port_lineage` shared-genesis canonical encoding
  (NEW — moved from Wave 11b's B4 C5 to avoid contradicting ADR-007
  F2 freewheelssp exemplar; needs ADR amendment).

---

## [adapter_spec_version 1.1.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] — 2026-05-03

ADR-007 (novel-pattern schema additions): F1, F3, F4, F5 admitted to the schema
as `$defs`. NOT `$ref`-wired into top-level `Code` yet — adapter_spec_version
1.1.0 admits the new shapes via the existing `Code` / `Code.make_requests` /
`Code.make_bids` open-map permissiveness (`additionalProperties: true`); Phase 2.8
will tighten and wire. ADR-007 status flipped Proposed → Accepted (2026-05-03).
F2 (`language_stamped_headers`) was already shipped; this release rounds out the
remaining four ADR-007 patterns.

### Added (schema)

- `EndpointResolution` `$def` — admits multi-endpoint adapters (F1; master
  sample beachfront with banner + video endpoints). `kind` enum includes the
  pre-existing 9 single-endpoint forms plus the new `multi-endpoint-by-mediatype`
  and `multi-endpoint-by-shape`. New `endpoints[]` array carries
  `{ name, role, value, mechanism }` per dispatch target; ordering is logical
  (declaration), not lex-sorted, per the ADR-007 array ordering policy.
- `EntityStrategy` `$def` — admits the
  `Site=replace-with-app-synthesis` / `App=synthesize-app-replacement` pattern
  (F3; master sample vungle). Each Site/App/User slot independently typed with
  the union of currently-emitted golden values plus the F3 additions
  (`replace-with-app-synthesis`, `synthesize-app-replacement`,
  `synthesize-from-site`).
- `BidPostProcessing` `$def` — admits post-decode macro replacement on bid
  fields (F4; master sample thetradedesk AUCTION_PRICE substitution into
  `bid.NURL`/`bid.AdM`/`bid.BURL`). `macros[]` array carries
  `{ macro, fields[], source, mechanism }` per substitution.
- `ImpExtUnmarshal` `$def` — admits the `strip_post_extraction: bool` flag (F5;
  master sample beintoo zeroes out `imp.Ext` after parsing). `kind` enum
  includes the currently-emitted golden values (`none`, `standard-two-phase`)
  plus forward-looking variants (`shared-prebid-imp`, `custom-typed`,
  `passthrough`) reserved for Phase 2.8.

### Changed (schema prose)

- Top-level `description` updated to reflect post-Phase-5 reality (40 goldens
  validated; was "Phase 2.0 milestone: covers the kobler-Go and kobler-Java
  goldens" + "Phase 2.1 will expand to cover all 22 goldens").
- `adapter_spec_version` field `description` updated to mention the 1.0.0/1.1.0
  semantics and the not-yet-`$ref`-wired posture of the new `$defs` (was
  "all 22 goldens migrated to '1.0.0'").

### Goldens posture

The 40 existing goldens stay at `adapter_spec_version: "1.0.0"`; none reference
the new patterns at the pinned upstream commits. Future fixtures using F1/F3/F4/F5
shapes will declare `adapter_spec_version: "1.1.0"`. Both versions are admitted
because `Code` is an open map; strict per-shape validation is deferred to Phase 2.8
(when `$ref` wiring lands).

### Unchanged

`taxonomy_version` stays at `1.0.0` (no behavior-taxonomy changes); `port_translation_rules_version`
stays at `0.2.0` (no rule additions or semantic changes).

---

## Unreleased — Process / tooling hardening (no version bump) — 2026-05-03

Out-of-SemVer-perimeter changes per `docs/methodology/schema-versioning.md` —
ADR text refinements, Python data-table updates, CI gate hardening, drift
cleanup, doc-count gates, file-role enum alignment, framework-utilities SHA
pin, and ADR status flips. No SemVer bump on schema, taxonomy, or port-rules
artifacts; no migration script required.

Two distinct origins of work in this section:

1. **Phase 5 fixture-authoring empirical evidence** (commits `d9742a7`
   vungle, `3523009` cadent/emxdigital, `f11b2ba` freewheelssp, `ea0a37a`
   thetradedesk) plus follow-up empirical verification of all 7 lifecycle
   pairs — drove the ADR-005/006/007/008 refinements + tooling updates
   below.
2. **PR #1 hardening waves 1, 2, 4, 5, 6, 7, 9a** (commits `859feff` →
   `e91970f`) — drove the CI gates / drift cleanup / Java SKILL alignment /
   cross-language port infrastructure / doc-count gate / ADR status-flip
   sub-sections below.

The Wave 8 forward-looking design landed under a separate Unreleased
section below, since design-only contracts for future phases are a distinct
genre from process/tooling housekeeping.

### ADR-005 (Rule 46 — Naming-Convention Normalization)

#### Removed
- `freewheel-ssp/freewheelssp` row from RULE_46_PAIRS (count 12 → 11). Both
  canonical YAMLs use `freewheelssp`; the hyphenated form is a Go-only YAML
  alias-stub via top-level `aliasOf:` field. The hyphen-drop transformation
  applies INTRA-Go (alias-stub → canonical), NOT cross-language. Per Phase 5
  commit `f11b2ba` and ADR-005 "Excluded cases" section.

#### Refined
- Master-samples list — Hyphen-drop slot now empty (no cross-language master
  at the pinned commits). Future fixtures that surface a true cross-language
  hyphen-drop pair can fill this slot.

### ADR-006 (Rule 43 — Lifecycle Subtype Categorization)

#### Added
- Two new sub-types: `mirror-topology` (both sides agree on parent name +
  alias name; defaults inverted; rebrand acknowledged in metadata but neither
  side adopted the new name as canonical) and `inverted-parent` (Go parent ≠
  Java parent; each side picked the OPPOSITE canonical; sub-flavor:
  `+ go-removed` when Go has actively rejected the other name via
  `removed-bidder` warning map).

#### Reclassified
- `liftoff/vungle`: `go-leads` → `bilateral` (phantom-rename; both sides
  canonical at `vungle` at the pinned commits; backward-compat: Go via
  removed-bidder warning, Java via tilde-inherit alias). Per commit
  `d9742a7`.
- `cadent_aperture_mx/emxdigital`: `java-leads` (label kept, defensible) with
  topology nuance — Go has DUAL-CORE REGISTRATION of BOTH `cadent_aperture_mx`
  AND `emx_digital` as core sibling bidders sharing one Builder (not the
  textbook "Go fossilizes" pattern). Per commit `3523009`.
- `conversant/epsilon`: `java-leads` → `inverted-parent`. Go parent =
  `conversant` (canonical-shape YAML); Java parent = `epsilon` (canonical-
  shape YAML). Both sides keep both names alive but with opposite parent
  choices. No removed-bidder warning on either side.
- `magnite/rubicon`: `java-leads` → `mirror-topology`. Both sides have
  `rubicon` as parent + `magnite` as alias. Defaults inverted (Go: parent
  disabled / alias enabled; Java: parent enabled / alias disabled). Merger
  acknowledged in YAML comments but bidder-name structure unchanged.
- `intenze/gothamads`: `java-leads` → `inverted-parent` (with Go-led
  removal). Go parent = `intenze` with `gothamads` in `removed-warn` map;
  Java parent = `gothamads` with intenze disabled-alias. Go LEADS rename in
  the OPPOSITE direction of Java parent choice.
- `equativ/smartadserver`: `go-leads` → `mirror-topology`. Both sides have
  `smartadserver` as parent + `equativ` as alias. Maintainer email is
  `*@equativ.com` (post-rebrand) on both sides — rebrand-aware metadata, but
  bidder-name unchanged. No removed-bidder warning.

#### Distribution
- 7 LIFECYCLE_PAIRS now distribute: **2 bilateral + 1 java-leads +
  0 go-leads + 2 mirror-topology + 2 inverted-parent**. Empirical
  cardinality of `go-leads` = 0 at the pinned commits; the subtype is
  preserved for future corpus expansion.

### ADR-007 (Five New Schema Fields for Novel Patterns)

#### Refined
- F1 (multi-endpoint-by-mediatype, master = `beachfront`): tightened
  Java-side wording — only `videoEndpoint` is added as a custom property
  field; the banner endpoint reuses the inherited `BidderConfigurationProperties.endpoint`.
  Both languages have two effective endpoint slots; the wording previously
  implied two custom Java fields, but `BeachfrontConfigurationProperties`
  declares only `videoEndpoint`.
- F2 (language-stamped-header-divergence, master = `freewheelssp`): added
  footnote distinguishing F2 (cross-language same-header-divergent-values)
  from one-sided header mutations (e.g., `aduptech` Java emits
  `Componentid: prebid-java` but Go aduptech emits no Componentid header).
  F2 requires both languages to emit the same header name with divergent
  values.

#### Empirically re-affirmed
- F1 master = `beachfront`: empirical cardinality at the pinned commits is
  exactly 1 (no other corpus bidder uses multi-endpoint-by-mediatype YAML
  shape).
- F2 master = `freewheelssp`: empirically validated. The "F2 contradicted"
  framing in the freewheelssp dual-spec narrative was a label-collision
  artifact in `scripts/coverage-report.py:58` (mis-labeling F2 as
  "multi-endpoint-by-mediatype"). The label was corrected; F2's
  master-sample claim itself stands.

### ADR-008 (Phase 5 Pair Fixtures)

#### Refined
- Pair 5 row: `liftoff-Go + vungle-Java` (cross-name) → `vungle-Go +
  vungle-Java` (same-name canonical). Subtype: `go-leads` → `bilateral`
  phantom-rename.
- Pair 6 row (`cadent_aperture_mx/emxdigital`): added topology nuance note
  about Go dual-core registration.

### Tooling

- `scripts/coverage-report.py:58`: relabeled freewheelssp PHASE_5_PAIRS
  summary from "ADR-007 F2 master (multi-endpoint-by-mediatype)" to
  "ADR-007 F2 master (language-stamped-header-divergence — refined
  2026-05-03 from multi-endpoint-by-mediatype label-collision)".
- `scripts/coverage-report.py:55,56`: updated vungle and emxdigital
  PHASE_5_PAIRS summaries per the lifecycle reclassifications.
- `scripts/coverage-report.py:69`: dropped freewheel-ssp tuple from
  RULE_46_PAIRS.
- `scripts/coverage-report.py:80-86`: rewrote LIFECYCLE_PAIRS — 5 of 7
  tuples reclassified per the empirical 7-pair table.
- `scripts/coverage-report.py:105`: INVENTORY_TOTALS["naming_normalization_pairs"]
  12 → 11.
- `scripts/tests/test_coverage_report.py:56`: renamed
  `test_rule_46_pairs_count_is_12` → `_is_11`; updated assertion + message.
- `scripts/tests/test_coverage_report.py:62`: updated subtype tally comment
  in `test_lifecycle_pairs_count_is_7` (count stays 7).
- `scripts/tests/test_render_port_rules.py:96-110`: extended
  `test_rule_43_sub_types_documented` to assert all 5 subtypes (added
  `mirror-topology` and `inverted-parent`).

### Documentation (auto-regenerated)

- `docs/coverage-report.md`: regenerated via `scripts/coverage-report.py`.
- `prebid-server-go/read/skills/shared/port-translation-rules.md`:
  regenerated via `scripts/render-port-rules.py`. Rule 46 table 12 → 11
  rows; Rule 43 sub-types table 3 → 5 rows.
- `prebid-server-go/read/skills/shared/behavior-taxonomy.md`: regenerated
  via `scripts/render-taxonomy.py`. `naming-convention-normalization` taxon
  description: 12 → 11 cases.

### Dual-spec narrative refinements

- `cross-language-pairs/{vungle,emxdigital,freewheelssp,thetradedesk,adkernelAdn}.dual-spec-assertions.yaml`:
  replaced "queued/deferred to future commit" markers with citations to
  this corrections commit. Empirical evidence sections preserved verbatim
  as the source-of-truth.

### CI gates (Waves 1 + 6)

- **Wave 1 (`859feff`)** — exit-code wrapper inversion fixed across
  `Makefile:35,38`, `.github/workflows/round-trip-ci.yml:88,96`,
  `.github/workflows/upstream-sync.yml:49`. Prior wrappers used `[ -le 2 ]`
  which silently masked exit-1 (real fail) as success; replaced with
  `[ -eq 0 ] || [ -eq 2 ]`. Plus wrapped previously-unwrapped
  `audit-golden.py` invocations and dropped daily-drift-causing
  `date.today().isoformat()` from `coverage-report.py:427`. Plus R5 design
  fix: decomposed `params.schema_interpretation` from a whole-block
  `deep_eq` strict-key into three runtime-invariant sub-fields
  (`required_fields, combinators_used, flexible_types`) — the prose-bearing
  `properties[].notes`/`description` fields legitimately differ across
  languages and were causing false `stale-pass` FAILs (canonical: thetradedesk).
- **Wave 6 (`aacc8d0`)** — added `scripts/tests/test_doc_count_claims.py`
  drift gate watching live count claims (rule count, enumeration count) in
  5 doc sites, catching the kind of drift that surfaced as "12 enumerated
  behavioral fields" stale claim in `cross-skill-integration.md` (canonical:
  15). Wave 9b generalized this into a discovery-based gate.

### Drift cleanup (Waves 2 + 9a)

- **Wave 2 (`601d917`)** — finished the `iab_category_storage.injection`
  → `delivery_mechanism` rename (Wave 2 ripple-finish for ADR-001 D2):
  `port-translation-rules.yaml` Rule 42 + 5 SKILL/reference sites.
  `cross-skill-integration.md:327` count fix 12 → 15 enumerated fields.
  README rule count 43 → 46. Dropped 146 lines of dead code from
  `test_schema_contract.py` (the `_DEPRECATED_PRE_PHASE_2_3_EXTRAS` block
  + `SCHEMA_REGISTRY_EXTRAS` empty placeholder; both unused since Phase 2.3
  derived the registry from `adapter-spec.schema.json` `$defs`).
- **Wave 9a (`e91970f`)** — pre-review polish pass after comprehensive
  audit. ~25 stale claims and Wave 2/4/7 incomplete ripples corrected:
  ADR README index 8 status flips (Wave 7 missed the meta-table), ADR-001
  D5 `rename_subtype` → `subtype`, ADR-005 "12 verified pairs" → "11"
  (internal contradiction), Java SKILL test-unit/test-it parenthetical
  drops (Wave 4 miss), Go reference doc `injection: static-init` →
  `delivery_mechanism: static-init` (Wave 2 miss),
  `adapter_spec_version: 1` integer-literal → `"1.0.0"` (Java orchestrator
  + pr-triage manifest), 22 → 40 goldens / 7 → 16 pairs / 89-90 → 92 PR
  count corrections, dropped hardcoded "22 taxa" counts, two read SKILLs
  gained ADR-007 F2 (`language_stamped_headers[]`) population
  instructions, test-fixtures READMEs (Go + Java) updated 12/10 → 21/19
  with Phase 5 row additions, cross-language-pairs README updated 7 → 16
  pairs (aax + elementaltv now show "yes" Go fixture per Wave 5).

### Java SKILL alignment (Wave 4)

- **Wave 4 (`41f3a77`)** — fixed a SKILL-vs-goldens contradiction at
  `read-bidder-class/SKILL.md:72`: the documented file-role enum was
  `bidder, configuration, configuration-properties, proto-ext,
  proto-helper, deserializer, test-unit, test-it` (8 values) but ALL 19
  Java goldens emit `implementation, models, parsers, types, utils`
  (5 values, zero overlap). Aligned SKILL to reality. Authored
  `references/file-role-heuristics.md` (Java mirror of Go's heuristics
  doc) + `scripts/lib/lint-java-roles.py` gating the enum at CI
  (`--include-go` flag covers Go's 6-value variant).

### Cross-language port infrastructure (Wave 5)

- **Wave 5 (`efa3de6`)** — re-derived `aax` and `elementaltv` dual-spec
  assertions: `go_spec: null` → real fixture path, dropped obsolete
  `note_on_specs` blocks (Go fixtures DO exist post-2026-05-02). Added
  `prior_source_spec` slot to pr-triage SKILL for cross-language port-
  fidelity comparison (canonical case: Go-PR vs Java-source spec). Added
  `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` convention for the
  one-shot Teal-flow orchestration (gitignored). Pinned
  `framework-utilities.md` 4 sites from `Verified at v4.1.0` to canonical
  Phase 5 SHA `2fae16f31693452b62dd2a0924b78e71bbec43ec`.

### ADR status flips (Wave 7)

- **Wave 7 (`a69812b`)** — flipped 8 ADRs `Proposed` → `Accepted` in their
  per-ADR files (ADR-001 was schema-migration-driven → `adapter_spec_version
  1.0.0` shipped; ADR-002 → Phase 1.4/1.5 corrections applied; ADR-003/4/5
  → Rules 44/45/46 in port-translation-rules.yaml; ADR-006 →
  `lifecycle.rename.subtype` 5-value enum shipped; ADR-008 → Phase 5 corpus
  complete at 9/9). Plus past-tense rewrite of ADR-002's 8 future-tense
  decision-narrative lines. Plus Java aliases mechanism correction in
  `prebid-server-java/references/new-bid-adapter-prs.md:182`
  (`aliasOf:` field claim → `aliases: { <child>: ~ }` parent-side block
  with explicit Go-vs-Java inversion note). The Wave 7 commit missed
  flipping the meta-table at `docs/decisions/README.md`; Wave 9a
  corrected that.

### Acknowledgments

- Per `docs/methodology/rollback.md:54-57`, ADR corrections used in-place
  edits with "Refined 2026-05-03" date stamps (matching ADR-006 line 3's
  existing "audit A5" precedent). Original `Refined 2026-05-02` date stamps
  preserved.
- Per `docs/methodology/schema-versioning.md:18-62`, no SemVer bump
  triggered for any of the work in this section — ADR text refinements,
  Python data-table updates, CI tooling, drift cleanup, ADR status flips,
  and SHA-pin updates are all out of the perimeter.
- Wave 1 surfaced a real R5 design flaw masked by the `[ -le 2 ]` exit-code
  wrapper bug. The R5 prose-key decomposition is the cleanest fix and
  preserved cross-language-pair semantic-equivalence checks intact.

---

## Unreleased — Forward-looking design (Phase D / E / F, no implementation in this PR) — 2026-05-03

Wave 8 (`8d21cfc`) ships design contracts for future phases — they document
the shapes Phase D port skills will emit, Phase F reflection consumes, and
how the Teal flow integrates D + E + F. No phase-D/F implementation lands
in this PR; the design-only artifacts let the next wave of agents start
against a fixed contract instead of a blank canvas.

This is a new genre in this CHANGELOG (prior entries documented shipped
runtime / data / tooling). Future versioned releases that bundle Phase D
implementation will reference these design docs.

### New: port-report.schema.json (Phase D ↔ Phase F contract)

- `prebid-server-go/read/skills/shared/port-report.schema.json` — JSON
  Schema (181 lines, draft 2020-12). Contract: Phase D port skills emit
  port reports against this; Phase F reflection consumes them. Top-level:
  `port_report_version` (SemVer 0.1.0 initial), `port_run.{run_id,
  source_lang, target_lang, source_spec_sha, target_branch}`,
  `rules_consumed[]` (per-rule verdict: applied | skipped-not-applicable
  | skipped-source-side-only | applied-with-warning), `quirks_emitted[]`
  (mirrors `adapter-spec.schema.json` `$defs/Quirk`), `r5_check.{state,
  byte_equal_fields, warn_fields, fail_fields, summary}`, `human_todos[]`
  (8-value category enum), `unresolved_translations[]` (5-value reason
  enum), `port_translation_rules_version` (cross-version replay key).

### New: Phase D / E / F design docs

- `docs/methodology/port-skills-design.md` (234 lines) — Phase D pipeline:
  load → discover family → apply rules → author destination spec → emit
  artifacts → R5-strict check → emit port-report. Conflict resolution
  (Rule 11 vs 35; Rule 38 byte-eq vs language-formatting; ADR-007
  F-pattern handling at adapter_spec_version 1.1.0 via open-map
  permissiveness). Novel-pattern handling. 3 worked examples: kobler clean
  port, vungle ADR-007 F3 port, aax R5-fail-semantic port.
- `docs/methodology/reflection-loop.md` (99 lines) — Phase F design.
  Three triggers (post-port, post-merge, periodic sweep). 9-row triage
  matrix mapping issue type → fix location: novel pattern needing schema
  → ADR-007-style $def addition; existing rule wrong direction → rules.yaml
  body edit OR ADR amendment; rule conflict / ambiguity → tightening; R5
  byte-only → Rule 38 amendment OR upstream PR; R5 semantic → upstream PR
  (NOT this repo); read-skill missed field → SKILL.md amendment; lint
  missed bug → new lint check; ADR drifted from execution → status flip.
  ADR amendment protocol with refinement annotations. Cross-version replay
  mechanic.
- `docs/methodology/end-to-end-flow.md` (158 lines) — Teal flow design,
  ties Phase D + E + F together. CLI: one-shot via orchestrator OR 4
  explicit steps. Run-scoped artifact layout under `.tmp/full-loop/{run-id}/`.
  Five documented failure modes with detection signal + remediation +
  fix-forward path.

### Anti-pattern taxonomy (Option α — minimal renderer change)

- `behavior-taxonomy.yaml` — added `category: anti-pattern` field to 5
  `quirks_taxa` entries (clear DESIGN anti-patterns, not bugs/typos):
  `hardcoded-config-as-anti-pattern`, `legacy-encoding-json-direct-usage`,
  `unguarded-currency-overwrite`, `hardcoded-bid-type`, `redundant-work`.
- `scripts/render-taxonomy.py` — added category-prefix logic: when a taxon
  has `category: <c>`, the rendered description gets a `**[<c>]**` prefix.
  Future categories may be added in future waves; same mechanism surfaces
  them.

### Methodology README updates

- `docs/methodology/README.md` — added the 3 new design docs to the table
  + 2 new "How to use these docs" entries (port-skills-design + Teal-flow
  consultation guidance).

### Wave 9b structural alignment (this commit)

- `ROADMAP.md` rewrite — added Phase F section (was A-E only); rewrote
  Phase E to acknowledge Wave 5 partially-shipped prerequisites
  (`prior_source_spec`, `.tmp/full-loop`); dropped circular "complete in
  PR #1" framing; added comprehensive Phase numbering map reconciling
  A-F + 2.X + 4.X + Wave-N coexisting schemes.
- `README.md` Phase status table — same rewrite (Phase F row added; Phase
  E rephrased; "complete (PR #1)" → "complete").
- `CHANGELOG.md` Unreleased section — split from single
  "ADR corrections" into "Process / tooling hardening" (this section,
  absorbs Waves 1, 2, 4, 5, 6, 7, 9a + the original ADR corrections) and
  "Forward-looking design" (the section you are reading, Wave 8 + Wave 9b
  structural).
- `scripts/tests/test_doc_count_claims.py` — generalized from 5-entry
  enumeration to canonical-phrase regex + source-fn dict (catches future
  drift on goldens count, dual-spec count, taxa count, etc.).
- `scripts/tests/test_schema_jsonschema.py` `TestSchemaSelfValidity`
  parameterized to validate BOTH `adapter-spec.schema.json` AND
  `port-report.schema.json` against the draft 2020-12 meta-schema.
- `prebid-server-go/read/skills/shared/adapter-spec.md` — added a section
  describing the 4 Wave 3 `$defs` (EndpointResolution, EntityStrategy,
  BidPostProcessing, ImpExtUnmarshal) so the companion markdown isn't
  silently incomplete relative to the JSON Schema's $defs enumeration.

---

## [adapter_spec_version 1.0.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] — 2026-05-02

First official versioned release. Cuts the schema spine and the data-driven
taxonomy + rule corpus loose from the legacy hand-authored Markdown.

### Schema (`adapter-spec.schema.json`)

**Added** (per ADR-001):

- D1 — `code_naming.*` as a top-level Java-only block (was nested `code.naming` on huaweiads-Java).
- D3 — `cross_language.port_lineage.source_language` enum gains `shared-genesis` (rubicon's pre-Go/pre-Java root lineage).
- D4 — `code.make_requests.mutation.schain_movement.{from, to, helper, notes}` structured field for OpenRTB 2.5→2.6 schain repositioning (master sample: appnexus-Go).
- D5 — `lifecycle.rename` sub-fields including `subtype` (`bilateral` | `java-leads` | `go-leads`, ADR-006), `package_moves[]`, `fixture_dir_moves[]`.
- D6 — 22 phantom-path resolutions (open-map declarations for `tests.unit_test_breakdown`, `aliases[].test_application_properties_entries`, `spring_config.configuration_properties_class.nested_classes[].fields`, etc.).
- D7 — SemVer string format (`X.Y.Z`) for `adapter_spec_version` and `taxonomy_version`. Phase 2.7 dropped the legacy integer form.
- ADR-007 F1–F5 — novel pattern fields (multi-endpoint-by-mediatype, language-stamped headers, mediatype-context-rewrite, bid-post-processing macros, imp-ext strip).
- `if/then/else` source_language discrimination — Go-source specs MUST null `spring_config` and `bidder_class`; Java-source non-alias specs MUST populate them.
- ADR-003/004 fields for Rule 44/45 — `meta.empire_canonical_master`, `meta.empire_parent_flavor`, `aliases[].relationship_flavor`.

**Renamed** (per ADR-001 D2):

- `iab_category_storage.injection` → `iab_category_storage.delivery_mechanism`. Disambiguates from `currency_conversion.injection` (different scope, different enum). Phase 2.7 migrated 22 goldens; the legacy `injection` field is removed from the schema.

**Removed**:

- Legacy integer form of `adapter_spec_version` (was `1`; now must be SemVer string `"1.0.0"`).
- `iab_category_storage.injection` (replaced by `delivery_mechanism`).

### Behavior taxonomy (`behavior-taxonomy.yaml`)

**Added** (8 new taxa per ADRs):

- ADR-007 — `multi-endpoint-by-mediatype`, `language-stamped-header-divergence`, `mediatype-context-rewrite-site-to-app`, `bid-post-processing-macro`, `imp-ext-strip-post-extraction`.
- ADR-004 — `disabled-by-default-empire-alias`, `default-enabled-go-disabled-justified` (paired Rule 45 taxa).
- ADR-005 — `naming-convention-normalization`.

**Migrated** — `behavior-taxonomy.md` is now AUTO-GENERATED from `behavior-taxonomy.yaml` via `scripts/render-taxonomy.py`. Drift gated by `scripts/tests/test_render_taxonomy.py`.

### Port-translation rules (`port-translation-rules.yaml`)

Bumped to **46 rules** (was 43).

**Added**:

- Rule 44 — Java alias-empire consolidation (ADR-003).
- Rule 45 — Disabled-by-default Java alias (ADR-004).
- Rule 46 — Naming-convention normalization (ADR-005).

**Refined**:

- Rule 43 (Bidder-rename three-step lifecycle) gains three sub-types per ADR-006: `bilateral`, `java-leads`, `go-leads`. Captured in `lifecycle.rename.subtype`. Note: originally drafted as `synchronized`; renamed to `bilateral` because the canonical Adoppler→ElementalTV master sample has the two languages renaming ~52 days apart (NOT lockstep).
- Rule 37 — fixed cross-reference (was "Rule 26 quirk: 152media → OneFiveTwoMediaTest"; corrected to "Rule 46 digit-leading-workaround").

**Migrated** — `port-translation-rules.md` is now AUTO-GENERATED from `port-translation-rules.yaml` via `scripts/render-port-rules.py`. Drift gated by `scripts/tests/test_render_port_rules.py`.

### Goldens

22 goldens migrated:

- `adapter_spec_version: 1` (int) → `adapter_spec_version: "1.0.0"` (string).
- Added `taxonomy_version: "1.0.0"`.
- Renamed `iab_category_storage.injection` → `iab_category_storage.delivery_mechanism`.
- huaweiads-Java: moved nested `code.naming.*` block to top-level `code_naming.*`.
- elementaltv-Go + elementaltv-Java: added `lifecycle.rename.subtype: bilateral`.

### Tooling

**Added**:

- `scripts/lib/lint-port-rules.py` — mechanizable lints for Rules 5, 9, 33, 36, 38, 44, 46 (Phase 2.6).
- `scripts/render-taxonomy.py` (Phase 2.4), `scripts/render-port-rules.py` (Phase 2.5).
- `scripts/audit-golden.py` — Phase 1.5 golden-vs-upstream audit (5 checks, all 22 goldens pass).
- `scripts/tests/test_schema_jsonschema.py` — meta-schema validity + per-golden + Go/Java discrimination tests.
- `scripts/tests/test_schema_contract.py` — schema-derived registry covering 254 paths / 641 dotted paths.
- `scripts/tests/test_render_taxonomy.py`, `scripts/tests/test_render_port_rules.py`, `scripts/tests/test_lint_port_rules.py`.
- `Makefile` with targets `make ci`, `make test`, `make audit-goldens`, `make audit-pr`, `make coverage`, `make render-taxonomy`, `make render-port-rules`, `make lint-port-rules`.
- `.github/workflows/round-trip-ci.yml`, `.github/known-broken-pairs.txt`.
- `requirements.txt` — `PyYAML`, `jsonschema>=4.18`.

### Documentation

- 8 ADRs (`docs/decisions/001-*.md` through `008-*.md`) capturing schema, rule, and Phase 5 fixture decisions.
- Execution plan (`docs/execution-plan.md`) — Phase 0–5 master plan with audit corrections (A1-C10).
- Phase 1.5 audit report (`docs/audits/golden-audit-2026-05-02.md`).
- `adapter-spec.md` reduced from 1115 to 188 lines (Phase 2.2); JSON Schema is now the source of truth, `.md` is the human reading layer pointing at it.

### Breaking changes

For any external consumer (none today; Phase D port skills are not yet started):

- `adapter_spec_version` is now `"1.0.0"` (string), not `1` (integer).
- `iab_category_storage.injection` no longer exists; use `delivery_mechanism` (same enum: `constructor-arg | static-init | null`).
- huaweiads-Java's `code.naming.*` block moved to top-level `code_naming.*`.

### Acknowledgments

Phase 2 work is grounded in:

- Round 3 cross-language inventory: 358 Go bidders + 350 Java bidders; 32 Java alias-empire parents (95 children); 78 disabled-asymmetric pairs; 12 naming-convention pairs; 8 lifecycle-rename pairs.
- Pre-execution audit corrections (A1–C10) — restructured the per-language vs dual-spec assertion split for Rules 45/46.
- Phase 1.5 golden audit — verified all 22 goldens against upstream prebid-server / prebid-server-java repos.

---

## Earlier

Pre-1.0 work happened on the `feat/read-skills` branch as Phase 0 (read skills),
Phase 1 (PR review fixes), and Phase 1.5 (golden audit). It is not versioned —
those phases bootstrapped the artifacts that this 1.0.0 release officially
versions.

The earlier history is available in the git log; see in particular:

- Phase 1 commits — `c6282f8 fix(shared): align rule count from 37 to 43`,
  `592b7bb fix(provenance-warnings): replace PascalCase derivation`,
  `ab4ce02 fix(spring-config-patterns): correct kobler bean_dependencies`,
  and the rest of the `fix(...)` series before Phase 2 began.
- Phase 2.0–2.6 commits — `be8ae24` through `e7c68e6`, leading up to this
  Phase 2.7 release.
