# Schema versioning policy

How the four independently-versioned artifacts evolve over time and how
consumers handle the transition.

## The four versioned artifacts

| Artifact | File | Field that records it |
|---|---|---|
| Adapter Specification schema | `prebid-server-go/read/skills/shared/adapter-spec.schema.json` | `adapter_spec_version` (top-level, REQUIRED on every spec) |
| Behavior taxonomy | `prebid-server-go/read/skills/shared/behavior-taxonomy.yaml` | `taxonomy_version` (top-level on goldens) |
| Port-translation rules | `prebid-server-go/read/skills/shared/port-translation-rules.yaml` | `rules_version` (top-level in the YAML; not stamped on goldens) |
| Port-report schema | `prebid-server-go/read/skills/shared/port-report.schema.json` | `port_report_version` (top-level, REQUIRED on every port report; consumed by Phase F reflection loop) |

Each artifact follows **SemVer string format** `X.Y.Z` per ADR-001 D7.
Phase 2.7 dropped the legacy integer form (`adapter_spec_version: 1`); the
current minimum is `"1.0.0"`. Phase D1.4 promoted `port_report_version`
to a first-class versioned artifact alongside the original three —
previously tracked in narrative form within CHANGELOG entries, now
declared explicitly with the same MAJOR / MINOR / PATCH increment
rules below. The CHANGELOG entry header convention is the four-element
form `[adapter_spec_version X.Y.Z] · [taxonomy_version X.Y.Z] ·
[port_translation_rules_version X.Y.Z] · [port_report_version X.Y.Z] —
date`; entries that don't bump every artifact still list each at its
current version for reproducibility.

## Increment rules

For each artifact, the version components mean:

- **MAJOR** — breaking change. Consumers MUST migrate. Goldens MUST be
  re-validated against the new schema, possibly with a migration script.
- **MINOR** — additive change. Old goldens still validate; new fields
  are optional; new enum values are accepted but not required.
- **PATCH** — non-semantic change. Comment edits, description tightening,
  rendered-MD touch-ups. Old artifacts validate without modification.

### What counts as breaking (MAJOR bump)

The judgment call is "would a Go-source spec written against version `X.Y.Z`
fail validation against `X+1.0.0`?" If yes, MAJOR.

- Removing a field from the schema (e.g., dropping `iab_category_storage.injection` in Phase 2.7).
- Renaming a field (`injection` → `delivery_mechanism`).
- Changing a field's type (e.g., `adapter_spec_version: integer` → `string`).
- Removing a value from an `enum` (consumers downstream may still emit it).
- Tightening a `pattern` regex such that previously-valid strings fail.
- Promoting an optional field to `required`.
- Changing the meaning of an existing enum value (preserves the symbol but breaks consumers).

### What counts as additive (MINOR bump)

- Adding a new optional field (current goldens still validate).
- Adding a new enum value (existing values stay valid; consumers can emit either).
- Loosening a `pattern` regex.
- Adding a new `$def` referenced from new optional fields.
- Adding new validation rules (R-numbered) that warn-only.
- **Wave 11b clarification — closing accidentally-open
  `additionalProperties: true` to `false`**: MINOR if all currently-validating
  goldens continue to validate (the declared property set absorbs the
  previously-undeclared corpus emissions). Wave 11b closed 17 such sites
  (B1/B2/B3) plus 8 round-2 sweep sites without breaking any of the 40
  goldens. The closure is MAJOR only when a closure refuses an existing
  corpus emission AND the fix is a schema concession rather than a
  corpus edit (i.e., the corpus emits a real key the schema then drops).

For port-translation rules: adding a new rule (Rule 44/45/46 in Phase 2.5)
is MINOR. Existing rules' contracts unchanged.

For taxonomy: adding a new taxon (`disabled-by-default-empire-alias` etc.)
is MINOR. Existing taxa stay registered.

### What counts as patch (PATCH bump)

- Editing `description` text on a schema property.
- Fixing a typo in a rule's `notes` paragraph.
- Re-rendering an auto-generated `.md` from its `.yaml` source.
- Adjusting comments/whitespace.

## Migration scripts

Breaking changes ship a migration script at `scripts/migrate/` named
`<from>-to-<to>.py` (e.g., `0.1.0-to-1.0.0.py`). Each migration:

1. Reads each affected golden, applies the transformation, writes back.
2. Is idempotent — re-running produces no further changes.
3. Lives long enough that consumers behind the curve can catch up;
   delete after one MINOR or two PATCH bumps once all known consumers
   have migrated.

The Phase 2.7 migration was authored as a one-off scratch script
(`_scratch_migrate_goldens.py`, deleted after use) because it ran once
in this repo. For external consumers who track this schema, future
breaking changes will ship under `scripts/migrate/` for as long as they
remain useful.

Migration scripts MUST NOT modify the schema or rules YAMLs themselves —
they only touch goldens and downstream consumer artifacts. Schema/rule
changes ride in the breaking-change commit.

## CHANGELOG protocol

Every version bump appears in `CHANGELOG.md`. The entry MUST:

- Use the exact form `[adapter_spec_version X.Y.Z] · [taxonomy_version A.B.C] · [port_translation_rules_version M.N.P] — YYYY-MM-DD`.
- Include subsections **Added**, **Renamed**, **Removed**, **Breaking changes** as applicable.
- Reference every ADR (`docs/decisions/`) that drove the change.
- For breaking changes: include a "Migration" sub-section pointing at the migration script.

Phase 2.7's `[1.0.0] · [1.0.0] · [0.2.0] — 2026-05-02` entry is the
canonical first example.

## Independence of the three versions

The three versions are **independent** — bumping one does not require
bumping the others.

- Schema MAJOR can ship without taxonomy or rules changes (e.g., dropping
  the legacy `injection` field is a schema-only MAJOR).
- Rules MINOR can ship without schema changes (Rule 44/45/46 in Phase 2.5
  added new rules but the schema was already populated with the fields
  via Phase 2.0/2.1; Phase 2.5's `rules_version: 0.2.0` is a rules-only
  bump).
- Taxonomy MINOR ships when new taxa are added (Phase 2.4's 8 new taxa).

The only correlation: the dual-spec assertion file format AND the rules
YAML BOTH reference taxa names. Adding a new taxon (taxonomy MINOR) AND
referencing it from rules YAML (rules MINOR) ride in one commit but stay
on independent version numbers.

## Where consumers SHOULD pin

- Read skills produce specs against `adapter_spec_version: "1.0.0"` today.
  When the schema bumps to `"2.0.0"`, every read-skill emit changes — this
  is when pinning matters most.
- The Adapter Specification's `provenance.read.skill_versions` map records
  which read-skill version produced each block. This is independent of
  `adapter_spec_version`; the skill_versions evolve faster than the schema
  and let consumers detect "this spec was emitted by an older skill build."
- Port skills (Phase D, future) MUST declare a `port_translation_rules_version`
  they were authored against. A port skill against `0.2.0` may not know how
  to apply Rule 47 (when added).

## Deprecation lifecycle

A deprecated field (slated for removal in the next MAJOR) carries:

- A `description` note: "DEPRECATED — replaced by `<new_field>` (Phase X.Y).
  Will be removed in `<artifact>` MAJOR version."
- An entry in CHANGELOG's most recent release announcing the deprecation.
- A test that flags any new golden using the deprecated field (warn-only).

Phase 2.7 deprecated nothing this way — it was a hard cut from `injection`
to `delivery_mechanism` because no external consumers existed yet. Future
breaking changes ship a deprecation lifecycle when external consumers
exist.

## Sources

- ADR-001 (D7): SemVer string format mandate.
- ADR-007: novel pattern fields F1–F5 (added as MINOR in Phase 2.0/2.1).
- CHANGELOG.md: version-by-version history.
