# ADR-006: Rule 43 Sub-Categorization

**Date**: 2026-05-02 (refined 2026-05-02 audit A5 — renamed `synchronized` to `bilateral`; refined 2026-05-03 — added 2 new subtypes `mirror-topology` and `inverted-parent`; reclassified 5 of 7 lifecycle pairs per Phase 5 empirical verification)
**Status**: Proposed (Phase 2 execution updates `port-translation-rules.md`)

**Note on terminology**: The `bilateral` sub-type was originally drafted as `synchronized` but renamed during the pre-execution audit. The Adoppler→ElementalTV canonical example shows the two languages renaming **52 days apart** (Java 2026-01-12, Go 2026-03-04). That's bilateral cooperation but NOT lockstep timing. `bilateral` accurately describes "both sides eventually rename"; `synchronized` would falsely imply simultaneity.

**Note on 2026-05-03 refinement**: Phase 5 fixture authoring (commits `d9742a7` vungle, `3523009` cadent/emx) plus follow-up empirical verification of all 7 lifecycle pairs surfaced that the original 3-subtype taxonomy (`bilateral | java-leads | go-leads`) is insufficient — only 2 of 7 pairs cleanly fit those labels. The remaining 5 fall into two new patterns: `mirror-topology` (both sides agree on parent name + alias name; defaults inverted) and `inverted-parent` (Go and Java each chose the OPPOSITE name as canonical). Reclassifications and verbatim upstream evidence live in the dual-spec assertion files (`cross-language-pairs/{vungle,emxdigital}.dual-spec-assertions.yaml`).

**Context**: Round 3 lifecycle-naming deep-dive verified 8 pairs that exhibit Rule 43 (bidder-rename three-step lifecycle); 7 of them landed in `LIFECYCLE_PAIRS` (the 8th was inventory-only, bidirectional). Phase 5 empirical re-verification of all 7 pairs against pinned upstream commits (Go `2fae16f3`, Java `a1fe64e1`) showed that the 3-subtype taxonomy was too narrow. The current ADR-006 captures the FIVE structurally distinct sub-types observed in upstream code; treating them uniformly would mislead a porter.

## Decision

**Rule 43 grows FIVE sub-types** captured as `lifecycle.rename.subtype` field (refined 2026-05-03 from the original three):

```yaml
lifecycle:
  rename:
    old_name: <name>
    new_name: <name>
    subtype: bilateral | java-leads | go-leads | mirror-topology | inverted-parent
    # ... existing fields (alias_back, alias_back_form, package_moves, fixture_dir_moves)
```

The 7 LIFECYCLE_PAIRS distribute as **2 bilateral + 1 java-leads + 0 go-leads + 2 mirror-topology + 2 inverted-parent**.

### Subtype 1: `bilateral` — both sides eventually rename

Both Go and Java settle on the SAME new canonical name; both retain backward-compat for the old name (Go via removed-bidder warning map; Java via `aliases: { <old>: ~ }` tilde-back, which may or may not be `enabled: false`). NOT lockstep — the two renames are independent PRs in independent repos. The backward-compat surfaces are typically asymmetric (Go warns and rejects; Java keeps the alias alive).

**Master samples** (2):
- **`adoppler → elementaltv`** (canonical): Java rename `prebid/prebid-server-java#4326` (2026-01-12, v3.38.0); Go rename `prebid/prebid-server#4639` (2026-03-04, v4.0.0; ~2 months later). Go has `adoppler` in `removed`-warn map; Java has `aliases.adoppler: ~` tilde-stub.
- **`liftoff → vungle`** (phantom-rename, refined 2026-05-03 from `go-leads`): Both sides canonical at `vungle` at the pinned commits. Liftoff acquired Vungle in 2021 — a parent-company-name change, NOT a code-level rename. The SSP product remained `Vungle Exchange`. Some operators configured `liftoff` based on the acquisition news; both prebid servers handle this with backward-compat: Go via removed-bidder warning map (`liftoff` → `vungle`); Java via `aliases.liftoff: { enabled: false }` tilde-inherit. See `cross-language-pairs/vungle.dual-spec-assertions.yaml` for verbatim evidence.

### Subtype 2: `java-leads` — Java post-rebrand, Go pre-rebrand

Java adopts the post-rebrand canonical name; Go fossilizes the pre-rebrand legacy name. Backward-compat exists ONLY on Java (via tilde-alias). Go-side never renames; the legacy name remains the Go canonical.

**Master sample** (1, refined 2026-05-03 from 4):
- **`cadent_aperture_mx (Go) ↔ emxdigital (Java)`** — Cadent acquired EMX. Java parent is `emxdigital` (legacy EMX brand); the new Cadent brand `cadent_aperture_mx` lives only as a disabled+geo-restricted alias under emxdigital.yaml. **Topology nuance**: Go does NOT cleanly fossilize the legacy name — it has DUAL-CORE REGISTRATION of BOTH `cadent_aperture_mx` AND `emx_digital` as fully-enabled core sibling bidders sharing one Builder (`cadentaperturemx.Builder`). Each Go name has its own bidder-info YAML (byte-identical sha256 `8ee63ad8…`) and its own bidder-params JSON (semantically equal, byte-different). Neither Go name appears in `GetDisabledBidderWarningMessages`. The `java-leads` label is defensible under the parent-canonical interpretation (Java has chosen a canonical name; Go has not consolidated), but the topology is more nuanced than a simple "Go fossilizes" framing. See `cross-language-pairs/emxdigital.dual-spec-assertions.yaml` for verbatim evidence.

**Reclassified out** (3 pairs originally listed as java-leads no longer fit):
- `conversant/epsilon` → `inverted-parent` (see Subtype 5).
- `magnite/rubicon` → `mirror-topology` (see Subtype 4).
- `intenze/gothamads` → `inverted-parent` with Go-led removal (see Subtype 5).

**Implication for porter** (when subtype=java-leads): When porting Go→Java, do not rename. The Java side already has the post-rebrand name; emit a `cross_language.lifecycle.subtype: java-leads` quirk on the spec.

### Subtype 3: `go-leads` — Go post-rebrand, Java pre-rebrand

Inverse of subtype 2. Go adopts the post-rebrand name; Java retains pre-rebrand. Backward-compat exists ONLY on Go (via removed-bidder warning map).

**Master samples** (0, refined 2026-05-03 from 2): NONE at the pinned commits. Both pairs originally classified `go-leads` were reclassified after empirical verification:
- `liftoff/vungle` → `bilateral` (phantom-rename; both sides at `vungle`).
- `equativ/smartadserver` → `mirror-topology` (both sides parent=`smartadserver`, alias=`equativ`).

The subtype is preserved in the taxonomy for future corpus expansion. **Empirical cardinality at SHAs `2fae16f3` (Go) / `a1fe64e1` (Java) = 0**. If a future fixture surfaces a true `go-leads` pair (Go canonical = post-rebrand new name; Java parent = pre-rebrand legacy name; Java alias-back via tilde), this slot can be filled.

**Implication for porter** (when subtype=go-leads): When porting Java→Go, do not rename. Go already has the post-rebrand name; emit a `cross_language.lifecycle.subtype: go-leads` quirk.

### Subtype 4: `mirror-topology` — both sides agree on parent name + alias name; defaults inverted (NEW 2026-05-03)

**Both Go and Java agree on the parent name AND the alias name**, but the enable-default flags are inverted: one side enables the alias by default while the other disables it. Maintainer email or other metadata may be rebrand-aware on both sides, but **neither side has actually adopted the new name as the canonical bidder name**. The "rebrand" is acknowledged in surface metadata while the bidder-name structure stays unchanged.

**Master samples** (2, NEW 2026-05-03):
- **`magnite/rubicon`**: Both sides have `rubicon` as parent and `magnite` as alias. Go: parent `rubicon` is `disabled: true` by default + alias `magnite` is enabled-by-default (`aliasOf: rubicon`). Java: parent `rubicon` is enabled-by-default + alias `magnite` is `enabled: false`. The Magnite/Rubicon merger is acknowledged in YAML comments ("Contact global-support@magnite.com to ask about enabling a connection to the Magnite (formerly Rubicon) exchange") but the bidder-name structure stays at `rubicon` parent on both sides. No removed-bidder warning on either side.
- **`equativ/smartadserver`**: Both sides have `smartadserver` as parent and `equativ` as alias. Go: parent `smartadserver` enabled + alias `equativ` enabled (`aliasOf: smartadserver`). Java: parent `smartadserver` enabled + alias `equativ` is `enabled: false`. Maintainer email is `*@equativ.com` (post-rebrand) on both sides — rebrand-aware metadata. No removed-bidder warning on either side.

**Implication for porter** (when subtype=mirror-topology): The pair is in a "rebrand acknowledged but not adopted" state. No rename is required when porting; both sides genuinely agree on the parent name. Carry the alias declaration; flip the enable-default if the destination convention prefers the inverse.

### Subtype 5: `inverted-parent` — Go parent ≠ Java parent; each side picked the opposite canonical (NEW 2026-05-03)

**Go and Java each chose a DIFFERENT name as the canonical parent**. Both names live on both sides via `aliasOf:` (Go) or `aliases:` (Java) blocks, but the parent-alias roles are reversed. May or may not have a removed-bidder warning on the Go side (orthogonal sub-flavor: `inverted-parent + go-removed`).

**Master samples** (2, NEW 2026-05-03):
- **`conversant/epsilon`**: Go parent = `conversant` (canonical-shape YAML, no aliasOf); Java parent = `epsilon` (canonical-shape YAML). Go has `epsilon.yaml` with `aliasOf: conversant`. Java has `aliases.conversant: { usersync.cookie-family-name: conversant }` under epsilon — rich alias with cookie-family override. NO removed-bidder warning on Go. Both sides keep both names alive but with opposite parent choices. Maintainer email is `PublisherIntegration@epsilon.com` on Go side — rebrand-aware metadata under the legacy parent name.
- **`intenze/gothamads`** (sub-flavor: `inverted-parent + go-removed`): Go parent = `intenze` (canonical-shape YAML); Java parent = `gothamads` (canonical-shape YAML). Go has REMOVED `gothamads` via `exchange/adapter_util.go::GetDisabledBidderWarningMessages` map: `"gothamads": ... please rename it to "intenze"`. Java has `aliases.intenze: { enabled: false, endpoint: ..., meta-info.maintainer-email: ... }` — disabled-with-overrides. Go LEADS the rename in the OPPOSITE direction of the Java parent choice. Java package has a typo (`org.prebid.server.bidder.gotthamads` with double-t) — unrelated implementation quirk.

**Implication for porter** (when subtype=inverted-parent): The two sides have NOT agreed on which name is canonical. Porting requires a deliberate choice about which canonical to follow on the destination side. Document the topology asymmetry in the per-language spec's `meta.bidder_name` (each side records its own canonical) and emit a `cross_language.lifecycle.subtype: inverted-parent` quirk. If `go-removed` sub-flavor applies, also note that Go has actively rejected one of the names.

## What does NOT belong under Rule 43

- `33across (Go) ↔ thirtythreeacross (Java)` — pure naming-normalization, no lifecycle event. This is **Rule 46** (see ADR-005).
- `freewheel-ssp/freewheelssp` — Go-only YAML alias-stub via `aliasOf:`; both canonical YAMLs use `freewheelssp`. Not Rule 46 cross-language and not Rule 43 lifecycle (refined 2026-05-03; see ADR-005).
- `mediafuse (Go alias) ↔ appnexus (Java parent declaring mediafuse alias)` — alias-graph divergence, no rename. This is **Rule 33** (alias inversion).

## Mechanizability

**Partially mechanizable**. Phase 4.6 `lint-port-rules.py` can verify:
- For each `lifecycle.rename` block, `subtype` MUST be one of the 5 enum values (`bilateral | java-leads | go-leads | mirror-topology | inverted-parent`).
- For `bilateral`, both sides must have either a removed-bidder warning entry OR an alias-back entry referencing the legacy name.
- For `java-leads`, Java must have the alias-back referencing the legacy Go-side canonical; Go bidder's `meta.bidder_name` matches the legacy name.
- For `go-leads`, the inverse (Go has removed-bidder warning entry; Java's `meta.bidder_name` matches the legacy name).
- For `mirror-topology`, BOTH sides have the parent name + the alias name; the enable-default values may differ (lint warns when defaults match).
- For `inverted-parent`, Go's `meta.bidder_name` ≠ Java's `meta.bidder_name`; both sides have the other's name as an `aliasOf:` (Go) or `aliases:` (Java) entry.

## Consequences

- Phase 2 updates Rule 43 in `port-translation-rules.yaml` to include the `subtype` enum (refined 2026-05-03 from 3 to 5 values).
- Phase 2 adds `lifecycle.rename.subtype` field to schema (per ADR-001 D5). Field is unconstrained string in the schema; the 5-value taxonomy lives in this ADR + `port-translation-rules.yaml`.
- Phase 5 includes vungle (`bilateral` master, refined 2026-05-03 from `go-leads`) and emxdigital/cadent_aperture_mx (`java-leads` master, with dual-core-registration nuance) pair fixtures (see ADR-008).
- Existing elementaltv golden gets `lifecycle.rename.subtype: bilateral` added during Phase 2 migration.
- New Pattern Index tags (Phase 2): `lifecycle-subtype-go-leads`, `lifecycle-subtype-java-leads`, `lifecycle-subtype-mirror-topology`, `lifecycle-subtype-inverted-parent` (paired with existing `bidder-rename-major-version`).
- `LIFECYCLE_PAIRS` table in `scripts/coverage-report.py:80-86` is updated per the 7-pair empirical reclassification.
- `INVENTORY_TOTALS["lifecycle_rename_pairs"]` in `scripts/coverage-report.py:106` stays at `8` (the 8th is the inventory-only bidirectional pair from Round 3, not in `LIFECYCLE_PAIRS`).

## References

- Round 3 lifecycle-naming deep-dive (this conversation): "Final synthesis — Rule 43 expansion" section
- Current Rule 43 wording: `port-translation-rules.md:1297-` (lifecycle rules section)
- PR refs: bilateral — Go #4639, Java #4326; java-leads — predates window (cadent acquisition pre-2025, conversant rebrand pre-2025); go-leads — predates window (Liftoff acquisition 2021, Equativ rebrand 2022)
- Worked example: `adapter-spec.md` Adoppler→ElementalTV (bilateral)
- Schema additions: see ADR-001 D5
