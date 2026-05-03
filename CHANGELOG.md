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

## Unreleased — ADR corrections (no version bump) — 2026-05-03

ADR amendments and reference-data corrections from Phase 5 fixture-authoring
empirical evidence (commits `d9742a7` vungle, `3523009` cadent/emxdigital,
`f11b2ba` freewheelssp, `ea0a37a` thetradedesk) plus follow-up empirical
verification of all 7 lifecycle pairs. **No SemVer bump on schema, taxonomy,
or port-rules artifacts** per `docs/methodology/schema-versioning.md` —
ADR text refinements and Python data-table updates are out of the SemVer
perimeter. No migration script required.

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

### Acknowledgments

- Per `docs/methodology/rollback.md:54-57`, ADR corrections used in-place
  edits with "Refined 2026-05-03" date stamps (matching ADR-006 line 3's
  existing "audit A5" precedent). Original `Refined 2026-05-02` date stamps
  preserved.
- Per `docs/methodology/schema-versioning.md:18-62`, no SemVer bump
  triggered — ADR text refinements and Python data-table updates are out
  of the perimeter.

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
