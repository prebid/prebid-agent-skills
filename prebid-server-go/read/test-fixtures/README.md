# Go test fixtures

21 hand-authored Adapter Specification fixtures for the `prebid-server-go` read suite. Phase A-4 fixtures (12) pin to upstream commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (`prebid/prebid-server` master, 2026-04-27); Phase 5 fixtures (9) pin to `2fae16f31693452b62dd2a0924b78e71bbec43ec` (`prebid/prebid-server` master, 2026-05-02). Per-fixture pin is recorded at `provenance.source.resolved_commit`.

## Fixtures

| Bidder | Edge case |
|---|---|
| `152media` | Alias-only spec (parent: adkernel); cross-language port pair |
| `33across` | `package ttx` directory mismatch; `Bidder33Across` acronym preservation |
| `aax` | Cross-language port pair; Java-side params schema omits `minLength: 1` (R5 fail) |
| `adkernel` | Multi-alias parent (152media, rxnetwork, xapads); composed batching `[grouped-by-key, format-split]` |
| `adkernelAdn` | (Phase 5) Cross-language port pair (Java: `adkerneladn`); Rule 46 master sample (Go camelCase ↔ Java lowercase); macro-form asymmetry (Go template `{{.X}}` ↔ Java plain `{{X}}`) |
| `adtonos` | Currency conversion via `reqInfo.ConvertCurrency` helper |
| `adverxo` | (Phase 5) Cross-language port pair; macro-form asymmetry across multiple URL params |
| `appnexus` | Custom `UnmarshalJSON` for keywords; pod-grouping batching; multi-imp |
| `bidstack` | Bearer-token authentication |
| `cadent_aperture_mx` | (Phase 5) Cross-language port pair (Java: `emxdigital`); ADR-006 dual-core registration (both `cadent_aperture_mx` AND `emx_digital` registered Go-side as fully-enabled core bidders sharing one Builder) |
| `elementaltv` | Lifecycle rename from Adoppler; cross-language port pair |
| `freewheelssp` | (Phase 5) Cross-language port pair; ADR-007 F2 master sample (`language_stamped_headers[]`: `Componentid: prebid-go` ↔ `prebid-java`); `aliasOf:` stub for `freewheel-ssp` is Go-only |
| `kobler` | Phase A acceptance-gate; cross-language port pair; documented R7 bugs (`BidderKargo` in `kobler_test.go:12`, `BidderKrushmedia` in `params_test.go:47`) |
| `limelightDigital` | (Phase 5) Cross-language port pair; alias-empire master (3 children each side) |
| `mediasquare` | Custom request body types (`msqResponse`, `msqParameters`); cross-language port pair |
| `msft` | Bidder-name rebrand (formerly Microsoft); IAB-category data table; dual test root (`test/` + `test-extrainfo/`) |
| `optidigital` | Phase A acceptance-gate (clean baseline); hardcoded dev-endpoint quirk; cross-language port pair |
| `smarthub` | (Phase 5) Cross-language port pair; alias-empire parent-canonical case (Attekmi rebrand; Go-side parent functional) |
| `teqblaze` | (Phase 5) Cross-language port pair; white-label-only-parent case (10 aliases each side; parent non-functional via `whiteLabelOnly: true`) |
| `thetradedesk` | (Phase 5) Cross-language port pair; ADR-007 F4 master sample (`bid_post_processing.macros[]` AUCTION_PRICE replacement in `bid.NURL`/`bid.AdM`/`bid.BURL`) |
| `vungle` | (Phase 5) Cross-language port pair; ADR-007 F3 master sample (`entity_strategies.Site: replace-with-app-synthesis`, `App: synthesize-app-replacement`); bilateral lifecycle rename (liftoff→vungle) |

## Round-trip determinism (R4)

Each fixture should reproduce byte-identically when re-emitted by the read-orchestrator skill against the same `provenance.source.resolved_commit`, modulo `provenance.read.timestamp_utc` and `provenance.read.operator`. The CI harness (`scripts/round-trip-ci.py`) enforces R4 alongside R1–R10 plus the cross-language-pair dual-spec assertions.

## Upstream-signature audit (manual; pre-PR for fixture-touching changes)

`scripts/audit-golden.py` cross-checks each golden's recorded `bidder_params_sha256`, file-inventory paths, and a few other claims against the upstream `prebid/prebid-server` repo at the pinned `provenance.source.resolved_commit`. It uses `gh api` and therefore requires `gh auth login` (or `GH_TOKEN`) — that's why it's NOT part of `make ci` (CI is hermetic).

Run it manually before submitting a fixture-touching PR:

```bash
make audit-goldens          # all fixtures (Go + Java)
python3 scripts/audit-golden.py kobler   # one bidder
```

Exit codes: `0` clean, `1` real failures, `2` warnings only, `3` `gh` API unreachable (auth missing or rate-limited — re-run after `gh auth login`).

## Adding or refreshing a fixture

1. Identify the bidder and the upstream commit to pin against.
2. Run the `read-adapter-orchestrator` skill at that commit. See `prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md`.
3. Save the emitted YAML as `{bidder}.golden.spec.yaml`.
4. Run `python3 scripts/round-trip-ci.py --strict-r3` to verify R1–R10 pass.
5. If the bidder has a Java counterpart, also add `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` (see the README there).
6. Add a row to the table above.

## Regenerating fixtures

Goldens are pinned to a specific upstream commit (`d7f8515b86258688304b0d9b6668c6a0e258bc9e` for this README — see `provenance.source.resolved_commit` on each fixture). When the upstream advances or the schema/taxonomy changes, the goldens need to be regenerated against the new pin.

### When to regenerate

Trigger regeneration when ANY of the following holds:

1. **Upstream commit advance.** Master has moved more than ~3 months since the current pin AND the moved commits touch one of the fixtures' bidder directories. Pure-doc-change moves don't require regeneration.
2. **Schema change.** A new top-level field, a renamed field, or a default-value change in `prebid-server-go/read/skills/shared/adapter-spec.md` that affects any fixture's emitted shape.
3. **Taxonomy extension.** A new enum value or quirk taxon added to `behavior-taxonomy.md` that retroactively applies to one of the fixtures.
4. **Schema fork.** When the fork policy in `prebid-server-go/read/skills/shared/adapter-spec.md` ("Schema fork policy" section) trips and `adapter-spec-java.md` is born, all Java goldens regenerate against the new schema.
5. **Bidder rename or new alias.** A new alias YAML appearing in master, or a rename PR (Adoppler→ElementalTV style) on one of the pinned bidders, requires the corresponding fixture to be re-read.
6. **R-rule fix.** If `scripts/round-trip-ci.py` or `scripts/tests/test_schema_contract.py` flag a phantom or stale field on an existing golden — the fix may be a regeneration rather than a manual edit.

### Step-by-step procedure

The read skill is not directly executable; "regeneration" means having an LLM follow the skill against the new commit and diff-reviewing the output against the current golden.

1. **Choose the new pin.** Identify the upstream commit (`{NEW_COMMIT}`). Use a release tag when possible (e.g., `prebid/prebid-server` at `vX.Y.Z`); otherwise use the shortest-sha that captures the desired change.
2. **Snapshot the current golden.** Save a copy of the existing `{bidder}.golden.spec.yaml` somewhere outside the repo for diff comparison (e.g., `/tmp/{bidder}-old.yaml`). Do NOT delete the committed golden yet.
3. **Run the orchestrator at the new pin.** Invoke `prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md` with the new commit. The skill's `provenance.source.ref` should be set to the new commit; `resolved_commit` will reflect it on output.
4. **Diff-review.** Compare the new emission to the snapshot. Three categories of difference are expected:
   - **Provenance churn.** `provenance.read.timestamp_utc`, `provenance.read.operator`, `provenance.source.resolved_commit` SHOULD change. R4 ignores the first two.
   - **Schema-driven additions.** New optional fields with default values are additive — accept them.
   - **Behavioral shifts.** Changes to behavioral-enum values mean the upstream adapter changed. Verify against the diff between the old and new commits for that adapter's directory.
5. **Run R1–R10 plus the schema-contract test.** From repo root:

   ```bash
   python3 scripts/round-trip-ci.py --strict-r3
   python3 scripts/tests/test_schema_contract.py
   ```

   Both MUST pass before the regenerated golden is committed.
6. **Update pinned commit references.** A regeneration of even one fixture may need to update SEVERAL pinned-commit references — see the table below.
7. **Commit as a single atomic PR.** Title: `regenerate {bidder} golden at {SHORT_NEW_COMMIT}`. Body cites the diff-categories from step 4 and any schema/taxonomy changes that forced the regeneration.

### Handling drift (old schema vs. new commit's adapter)

When a field that exists in the old golden does not match the new commit's adapter:

| Drift kind | Action |
|---|---|
| Field's value changed (e.g., `default_enabled: true` → `false`) | Update the golden to the new value; cite the upstream PR in the regeneration commit body. |
| Field exists in old golden but adapter no longer emits the structural evidence for it | Drop the field from the regenerated golden. Surface in the commit body if the drop crosses a behavioral semantic boundary. |
| Field exists in new commit's adapter but not in the old golden | Add the field to the regenerated golden. If the field is new to the schema, verify it's documented in `adapter-spec.md`; if not, the schema is stale and needs an update first. |
| Field shape changed (e.g., scalar → list) | This is a schema-version bump. Halt regeneration; coordinate the schema change as a separate PR per `## Versioning policy` in `adapter-spec.md`. |

### Where to update pinned commit references

A single regeneration may affect multiple files. Update ALL that apply:

| Reference | Path | Field |
|---|---|---|
| Golden provenance | `prebid-server-go/read/test-fixtures/{bidder}.golden.spec.yaml` | `provenance.source.resolved_commit` |
| Test-fixtures README | `prebid-server-go/read/test-fixtures/README.md` | top-line `pinned to upstream commit ...` |
| Dual-spec assertion (if cross-language pair) | `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` | any commit-pinned field; `bidder_params_sha256` if upstream changed the schema bytes |
| `behavior-taxonomy.md` Sources block | `prebid-server-go/read/skills/shared/behavior-taxonomy.md` | `prebid/prebid-server master at vX.Y.Z (commit ...)` line — only when bumping the canonical pin for the whole suite |
| `adapter-spec.md` Sources block | `prebid-server-go/read/skills/shared/adapter-spec.md` | same canonical pin line |
| `cross-skill-integration.md` Sources | `prebid-server-go/read/skills/shared/cross-skill-integration.md` | same canonical pin line |

When ALL fixtures of a language regenerate together (a "wave"), the canonical pin lines in the three shared docs above all bump in the same PR. When only one or two fixtures regenerate, the per-fixture provenance updates AND the `cross-language-pairs/` entry suffice; the shared docs' pin stays at its current value (capturing the suite's floor, not its ceiling).
