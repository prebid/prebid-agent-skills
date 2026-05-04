# Rollback policy

Each Phase 2 commit is individually revertible. Phase 3 + 4 commits are
sub-ordered such that a partial-revert at any point leaves the repository
in a consistent state. This document codifies what that means and what
the rollback drill looks like in practice.

## Revert-safety guarantees

### Phase 2 commits (the schema spine)

The seven Phase 2 commits each delivered an independent migration:

| Commit | What it landed | Revert effect |
|---|---|---|
| `feat(phase-2.0)` | JSON Schema covering kobler goldens | Reverting drops the schema; goldens still parse but lose machine-readable validation. |
| `feat(phase-2.1)` | JSON Schema covers all 22 goldens + source_language discrimination | Reverting tightens kobler-only coverage back. |
| `feat(phase-2.2)` | adapter-spec.md reduced to 188 lines | Reverting restores the 1115-line MD. JSON Schema unaffected. |
| `feat(phase-2.3)` | goldens validate via schema-derived registry | Reverting reactivates the 180-entry hand-curated registry. Schema unaffected. |
| `feat(phase-2.4)` | behavior-taxonomy.md auto-generated from .yaml | Reverting restores hand-authored MD; YAML stays as a sibling reference. |
| `feat(phase-2.5)` | port-translation-rules.md auto-generated; +Rules 44/45/46 | Reverting drops Rules 44–46 and the `bilateral` sub-type renaming. Goldens with `lifecycle.rename.subtype: bilateral` remain valid against the prior schema (unknown field passthrough via open-map). |
| `feat(phase-2.6)` | mechanizable port-rule lints | Reverting drops scripts/lib/lint-port-rules.py; CI exit codes shrink to round-trip-only. |
| `feat(phase-2.7)` | migrate goldens to schema 1.0.0 + tighten schema + CHANGELOG | This is the only Phase 2 commit that touches goldens. Reverting requires the inverse migration (string `"1.0.0"` → integer `1`, `delivery_mechanism` → `injection`, etc.). The pre-migration scratch script is deleted; reconstruct via `git revert` followed by re-running the inverse transformations on goldens. |

The Phase 2.7 migration is the trickiest to revert because it both
tightened the schema AND migrated 22 goldens. A `git revert` of `b1b6886`
brings back the legacy schema fields, but the goldens still carry the
new field shapes — they'll need a counter-migration to roll back to
integer `adapter_spec_version` + `injection` + nested `code.naming`. In
practice, "rolling back" Phase 2.7 means re-running the inverse of the
migration. Because that's expensive, prefer to fix-forward (cut a Phase
2.8 with the corrective change).

### Phase 3 commits (conciseness)

Phase 3.2 (`0841291`) and Phase 3.3 (`bcb9c8a`) are pure prose deletions
+ catalog consolidation. Reverting either restores the deleted prose and
removes the single-source-of-truth move. No schema impact; goldens
unaffected.

### Phase 4 commits (methodology)

Phase 4.0 (`eec9757`) and Phase 4.3 (`82b3ea0`) are additive — templates,
scripts, and docs. Reverting drops the artifacts; nothing else regresses.

## Fix-forward vs revert

Default to **fix-forward** for any change that survived `make ci` and was
merged. The `git revert` knob is reserved for:

1. A merged commit that broke `make ci` (caught in main-branch CI, not
   PR-time). Revert restores green.
2. A merged commit that introduced an undocumented schema break (e.g.,
   removed an enum value the consumer-side port skills depended on).
   Revert + a Phase X+1 fix-forward commit.
3. An ADR that turned out to be wrong. The ADR commit gets a revert; a
   replacement ADR ships with a status note ("supersedes ADR-NNN").

Fix-forward is preferred because each Phase commit's CHANGELOG entry
references ADRs and other commits — reverts create dangling references.

## CI smoke job

A revert MUST pass `make ci` exit 0. The CI smoke job
(`.github/workflows/round-trip-ci.yml` per Phase 4.7) runs on every push;
a revert commit triggers the same gates as a regular commit. If the
revert exposes a latent inconsistency (e.g., a downstream test that
implicitly relied on the reverted change), the test gets marked broken
and a follow-up fix-forward commit lands.

## Schema-version rollback

If `adapter_spec_version: "2.0.0"` ships and is later rolled back to
`"1.0.0"`:

1. Revert the schema-tightening commit.
2. Run the inverse migration script (`scripts/migrate/2.0.0-to-1.0.0.py`,
   if one was authored).
3. Update `CHANGELOG.md` with a "Rollback" entry referencing the
   reverted commit and explaining the rationale.
4. Bump `adapter_spec_version` on goldens back to `"1.0.0"`.

The migration scripts at `scripts/migrate/` MUST ship with both
forward (`X-to-Y.py`) and inverse (`Y-to-X.py`) transformations when the
schema MAJOR is bumped.

## Goldens revertibility

Each golden MUST individually round-trip through `make audit-goldens`
without error at every Phase commit. Phase 2.7's migration touched all
22 goldens in one commit because the rename was global; partial reverts
of the goldens are not supported (the schema would reject a half-migrated
golden with `delivery_mechanism` AND `injection` simultaneously). For
fine-grained rollback, the unit is the entire migration commit.

## Provenance preservation

Reverts MUST preserve commit provenance (don't `git commit --amend` a
revert; let it stand as its own commit). The `git log` history is the
audit trail for what was attempted, what was rolled back, and why. The
ADR system (`docs/decisions/`) is the rationale layer; git history is
the temporal layer. Both are load-bearing.

## Sources

- Phase 2 commits: see `git log --grep='feat(phase-2'`.
- CHANGELOG.md: version-bump history with breaking-change call-outs.
- `docs/methodology/schema-versioning.md`: SemVer increment rules.
- ADR index: `docs/decisions/README.md`.
