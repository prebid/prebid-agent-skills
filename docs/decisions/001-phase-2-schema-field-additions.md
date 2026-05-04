# ADR-001: Phase 2 Schema Field Additions

**Date**: 2026-05-02 (refined 2026-05-02 with pre-execution audit corrections: A4 added D6 phantom-path completion; A3/C6 use JSON Schema terminology; B4 SemVer string format)
**Status**: Accepted (Phase 2 executed — schema migration landed; goldens migrated; CHANGELOG records the version bumps)
**Context**: Round 3 verification surfaced five schema-decision forks that were ambiguous in earlier rounds. Each one needs a concrete answer before Phase 2 (schema migration) so we don't fragment the migration commits.

**Note on JSON Schema terminology**: This ADR (and ADR-007) reference Java-only blocks needing a discriminated polymorphism. JSON Schema 2020-12 expresses this via `if/then/else` keyed on `source_language` `const`-value, NOT via OpenAPI's `discriminator` keyword. All references to "discriminator" elsewhere in the plan refer to this `if/then/else` shape.

**Note on null handling**: New nullable fields use the canonical JSON Schema 2020-12 form `{"type": ["string", "null"]}`. Avoid OpenAPI's `nullable: true` (not part of JSON Schema).

## Decisions

### D1 — `code_naming` location: top-level

**Context**: The schema declared `code_naming.*` as a top-level property (in `adapter-spec.md` and now in `adapter-spec.schema.json` `$defs/Code` siblings), but the huaweiads-java golden carried a nested `code.naming.*` block. The contradiction surfaced as H1 during the review.

**Options**:
1. Top-level `code_naming.*` (matches `spring_config`, `bidder_class`, `lifecycle` Java-only top-level pattern)
2. Nested `code.naming.*` (groups with other `code.*` fields)

**Decision**: **Top-level** `code_naming.*`. Migrate huaweiads-java golden's nested block to top-level during Phase 2.

**Rationale**: Java-only blocks already use the top-level convention (`spring_config`, `bidder_class`, `lifecycle`); nesting `code_naming` under `code` would break that convention. Discriminator on `source_language: java` cleanly handles the Java-only-ness.

### D2 — `injection` field rename: `delivery_mechanism`

**Context**: Pre-rename the schema declared both `iab_category_storage.injection: constructor-arg | static-init | null` AND `currency_conversion.injection: dependency | function-arg`. Same field name, different scopes, different enums — schema-internal name collision surfaced in Round 3.

**Options**:
1. Rename `iab_category_storage.injection` → `iab_category_storage.delivery_mechanism`
2. Rename `currency_conversion.injection` → `currency_conversion.injection_mechanism`
3. Leave both; rely on path-disambiguation in JSON Schema

**Decision**: **Rename `iab_category_storage.injection` → `iab_category_storage.delivery_mechanism`** during Phase 2 migration.

**Rationale**: `injection` is more idiomatic for `currency_conversion` (DI-pattern naming) than for `iab_category_storage` (which is really about how the category table is delivered to the adapter — constructor-arg vs static-init). The rename clarifies intent. Migrated all 40 goldens' `iab_category_storage.injection` → `delivery_mechanism` in Phase 2.7. Final value distribution: 37 × `null`, 2 × `static-init` (Go appnexus, Go msft), 1 × `constructor-arg` (Java appnexus). (Original ADR projected 22 goldens; Phase 5 fixture authoring added more pairs before Phase 2.7 ran.)

### D3 — `port_lineage.source_language: shared-genesis`

**Context**: rubicon-java golden line 1091 emits `source_language: shared-genesis` under `cross_language.port_lineage`. Schema declares enum `[go, java]` (2 values). Rubicon predates Go-Java pair convention.

**Options**:
1. Add `shared-genesis` to the schema enum
2. Replace with one of the existing values (forced choice)
3. Leave undocumented divergence

**Decision**: **Add `shared-genesis` to the schema enum** during Phase 2.

**Rationale**: Rubicon is a real outlier — it predates the Go-Java pair convention. `shared-genesis` accurately describes its lineage (forked from a common pre-Go/pre-Java root). Forcing it into `go` or `java` would lie about historical fact. Schema admits a third value with master sample = rubicon.

### D4 — `mutation.schain_movement` schema field

**Context**: appnexus-go golden lines 443-460 emit `mutation.schain_movement.{from, to, helper, notes}` block. Not in schema. Surfaced as a "phantom field" during Round 3.

**Options**:
1. Promote to first-class schema field with structured sub-fields
2. Remove from golden; replace with a `quirks[]` entry under taxon `schain-movement-old-to-new-ortb`
3. Leave undocumented

**Decision**: **Promote to first-class schema field** during Phase 2. Structure:

```yaml
mutation:
  schain_movement:                              # Optional. Captures OpenRTB 2.5→2.6 schain repositioning.
    from: <field-path>                          # E.g., request.Source.Ext.schain
    to: <field-path>                            # E.g., request.Ext.schain
    helper: <function-name>                     # E.g., moveSupplyChain
    notes: [...]                                # Free-text observations
```

**Rationale**: schain repositioning is a recurring port concern (appnexus is a master sample, but other adapters likely do similar moves). A structured field lets a porter recognize and apply the move; a free-text quirk would lose the from/to specificity. Pairs naturally with Rule 6 (Source schain manipulation).

### D5 — `lifecycle.rename` sub-fields

**Context**: elementaltv-java golden uses undocumented `lifecycle.rename.{fixture_dir_moves, package_moves}.{from, to}` blocks. Round 3 phantom-field analysis flagged these.

**Options**:
1. Add to schema as structured sub-fields under `lifecycle.rename`
2. Replace with `quirks[]` entries
3. Leave undocumented

**Decision**: **Add to schema** under `lifecycle.rename`:

```yaml
lifecycle:
  rename:
    old_name: <name>
    new_name: <name>
    alias_back: bool
    alias_back_form: tilde_inherit | full_block
    package_moves:                              # Optional. Java package directory moves.
      - { from: <path>, to: <path> }
    fixture_dir_moves:                          # Optional. JUnit IT/test fixture directory moves.
      - { from: <path>, to: <path> }
    yaml_deletes: []
    yaml_adds: []
    subtype: bilateral | java-leads | go-leads | mirror-topology | inverted-parent   # ADR-006 (refined 2026-05-03 from 3 to 5 subtypes; was synchronized | java-leads | go-leads — `synchronized` renamed to `bilateral` in audit A5; `mirror-topology` and `inverted-parent` added per Phase 5 empirical evidence). Goldens emit at `lifecycle.rename.subtype:` (verified across the 7 lifecycle pairs).
    merged_at: <date>
    release: <version>
```

**Rationale**: Lifecycle renames are first-class events with structured operational consequences (package paths change, fixtures move, properties files update). Capturing them as data lets the port skill mechanically apply the changes; quirks would lose the structure.

### D6 — Remaining 22 phantom paths (added 2026-05-02 audit)

**Context**: Round 3 phantom-field analysis found 36 truly-undocumented paths. D1/D4/D5 above resolve ~14 of them. The remaining ~22 paths need explicit decisions for Phase 2.3 to consume.

**Decisions per group**:

| Phantom path group | Resolution | Schema change |
|---|---|---|
| `aliases.test_assets.naming_asymmetry.{fixture_dir_uses_yaml_name, it_class_uses_workaround, rationale}` | Add to schema as Java IT-class naming workaround sub-fields | `aliases[].test_assets.naming_asymmetry: { fixture_dir_uses_yaml_name: bool, it_class_uses_workaround: bool, rationale: string }` |
| `aliases.test_application_properties_entries.{key, line, value}` | Add to schema as list-of-objects | `aliases[].test_application_properties_entries: [{ key: string, line: int, value: string }]` |
| `spring_config.configuration_properties_class.nested_classes.fields.{name, type, validations}` | Add to schema (the nested class fields the subclass introduces) | `spring_config.configuration_properties_class.nested_classes[].fields: [{ name: string, type: string, validations: [string] }]` |
| `tests.unit_test_breakdown.<TestClassName>` (10 paths, huaweiads-Java) | Declare as OPEN_MAP — keys are arbitrary test-class names, values are method counts | `tests.unit_test_breakdown: { type: object, additionalProperties: { type: integer } }` |
| `registry.test_application_properties.*` (4 paths, huaweiads-Java) | **Rename** to canonical `tests.test_application_properties.*` (consolidates the huaweiads invention under existing `tests` block) | Schema change + golden migration of huaweiads-Java |
| Miscellaneous (~4 paths) | Phase 2.3 triages each on case-by-case basis; default = drop or rename to canonical sibling | Phase 2.3 task |

**Rationale**: Most of these are real schema fields that Round 1 missed because the regex extractor doesn't walk into list-element keys or open-map sub-paths. Adding them codifies what goldens already do; the registry rename addresses the only genuine invention.

## D7 — Versioning string format (added 2026-05-02 audit)

**Decision**: All `*_version` fields use SemVer string format `"X.Y.Z"`. Schema validation: `{"type": "string", "pattern": "^[0-9]+\\.[0-9]+\\.[0-9]+$"}`.

Affected fields: `adapter_spec_version`, `taxonomy_version`, `port_translation_rules_version`. Goldens migrate to declare `"1.0.0"` during Phase 2.7. SKILL frontmatter `version` already follows this format.

**Rationale**: Eliminates ambiguity between `1`, `1.0`, `1.0.0`, and date-based formats. SemVer is the standard.

## Consequences

- Phase 2 schema migration: 5 field additions/renames + ~22 phantom-path resolutions; ~22 golden migrations for D2; ~1 golden migration for D1; ~1 golden migration for `registry.*` rename in D6
- JSON Schema `if/then/else` keyed on `source_language` cleanly handles Java-only blocks
- The `code_naming` decision aligns Java-only blocks; future schema additions follow the same pattern
- The `injection` rename creates a `CHANGELOG.md` entry; no downstream porters affected (Phase D not yet started)
- The 22 phantom-path additions close the H6 root cause; Phase 2.3 validation runs cleanly post-migration

## References

- Round 3 verification (this conversation): H1, M-injection-collision, rubicon source_language, schain_movement scope analysis
- Round 3 phantom-field decomposition (this conversation): 36 unique undocumented paths across 22 goldens; D1/D4/D5/D6 collectively resolve all 36
- Pre-execution audit (this conversation): A3 JSON Schema terminology, A4 phantom-path completeness, B4 SemVer string, C6 null syntax
- Schema: `prebid-server-go/read/skills/shared/adapter-spec.md` (current), `adapter-spec.schema.json` (planned)
- Affected goldens at original ADR-001 authoring: `huaweiads.golden.spec.yaml` (Java, code_naming + registry rename + unit_test_breakdown), `appnexus.golden.spec.yaml` (Go, schain_movement), `elementaltv.golden.spec.yaml` (Java, lifecycle.rename), `rubicon.golden.spec.yaml` (Java, shared-genesis). Phase 5 added 9 Go + 9 Java pair fixtures (smarthub, teqblaze, adverxo, limelightDigital, vungle, cadent_aperture_mx/emxdigital, adkernelAdn/adkerneladn, freewheelssp, thetradedesk) — all conformed to the post-D2 `delivery_mechanism` field name on initial authoring.
- All 40 goldens (post-Phase-5 count): `iab_category_storage.injection` rename + `adapter_spec_version`/`taxonomy_version` SemVer additions
