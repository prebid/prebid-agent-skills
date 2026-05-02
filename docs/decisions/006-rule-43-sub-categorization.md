# ADR-006: Rule 43 Sub-Categorization

**Date**: 2026-05-02 (refined 2026-05-02 audit A5 — renamed `synchronized` to `bilateral`)
**Status**: Proposed (Phase 2 execution updates `port-translation-rules.md`)

**Note on terminology**: The `bilateral` sub-type was originally drafted as `synchronized` but renamed during the pre-execution audit. The Adoppler→ElementalTV canonical example shows the two languages renaming **52 days apart** (Java 2026-01-12, Go 2026-03-04). That's bilateral cooperation but NOT lockstep timing. `bilateral` accurately describes "both sides eventually rename"; `synchronized` would falsely imply simultaneity.
**Context**: Round 3 lifecycle-naming deep-dive verified 8 pairs that exhibit Rule 43 (bidder-rename three-step lifecycle), but they cleave into three structurally distinct sub-types that the current Rule 43 wording doesn't differentiate. The current canonical example (Adoppler→ElementalTV) covers only one sub-type; treating the others uniformly would mislead a porter.

## Decision

**Rule 43 grows three sub-types** captured as `lifecycle.rename.subtype` field:

```yaml
lifecycle:
  rename:
    old_name: <name>
    new_name: <name>
    subtype: bilateral | java-leads | go-leads
    # ... existing fields (alias_back, alias_back_form, package_moves, fixture_dir_moves)
```

### Subtype 1: `bilateral` — both sides eventually rename

Both Go and Java rename within a small number of months of each other (typically <6 months apart); both adopt the new canonical name; both retain backward-compat for the old name (Go via removed-bidder warning map; Java via `aliases: { <old>: ~ }` tilde-back). NOT lockstep — the two renames are independent PRs in independent repos.

**Master sample**: `adoppler → elementaltv` (current canonical):
- Java rename: PR `prebid/prebid-server-java#4326` (2026-01-12, v3.38.0)
- Go rename: PR `prebid/prebid-server#4639` (2026-03-04, v4.0.0; ~2 months later)

This is the cleanest sub-type and is what the existing Rule 43 example describes.

### Subtype 2: `java-leads` — Java post-rebrand, Go pre-rebrand

Java adopts the post-rebrand canonical name; Go fossilizes the pre-rebrand legacy name. Backward-compat exists ONLY on Java (via tilde-alias). Go-side never renames; the legacy name remains the Go canonical.

**Master samples**:
- `cadent_aperture_mx (Go) ↔ emxdigital (Java)` — Cadent acquired EMX; Java tracks new ownership, Go retains pre-acquisition name
- `conversant (Go) ↔ epsilon (Java)` — Publicis Epsilon acquired Conversant
- `magnite (Go) ↔ rubicon (Java)` — Magnite/Rubicon merger
- `intenze (Go) ↔ gothamads (Java)` — acquisition

**Implication for porter**: When porting Go→Java, do not rename. The Java side already has the post-rebrand name; emit a `cross_language.lifecycle.subtype: java-leads` quirk on the spec.

### Subtype 3: `go-leads` — Go post-rebrand, Java pre-rebrand

Inverse of subtype 2. Go adopts the post-rebrand name; Java retains pre-rebrand. Backward-compat exists ONLY on Go (via removed-bidder warning map).

**Master samples**:
- `liftoff (Go) ↔ vungle (Java)` — Liftoff acquired Vungle in 2021; Go adopted post-acquisition name; Java retained pre-acquisition
- `equativ (Go) ↔ smartadserver (Java)` — Smart AdServer rebranded to Equativ in 2022; Go adopted post-rebrand

**Implication for porter**: When porting Java→Go, do not rename. Go already has the post-rebrand name; emit a `cross_language.lifecycle.subtype: go-leads` quirk.

## What does NOT belong under Rule 43

- `33across (Go) ↔ thirtythreeacross (Java)` — pure naming-normalization, no lifecycle event. This is **Rule 46** (see ADR-005).
- `mediafuse (Go alias) ↔ appnexus (Java parent declaring mediafuse alias)` — alias-graph divergence, no rename. This is **Rule 33** (alias inversion).

## Mechanizability

**Partially mechanizable**. Phase 4.6 `lint-port-rules.py` can verify:
- For each `lifecycle.rename` block, `subtype` MUST be one of the 3 enum values
- For `bilateral`, both sides must have parallel rename evidence (Go removed-bidder + Java alias-back)
- For `java-leads`, Java must have the alias-back; Go side has no rename evidence; the Go bidder's `meta.bidder_name` is the legacy name
- For `go-leads`, the inverse

## Consequences

- Phase 2 updates Rule 43 in `port-translation-rules.yaml` to include the `subtype` enum
- Phase 2 adds `lifecycle.rename.subtype` field to schema (per ADR-001 D5)
- Phase 5 includes vungle/liftoff (`go-leads` master) and emxdigital/cadent_aperture_mx (`java-leads` master) pair fixtures (see ADR-008)
- Existing elementaltv golden gets `lifecycle.rename.subtype: bilateral` added during Phase 2 migration
- New Pattern Index tag (Phase 2): `lifecycle-subtype-go-leads`, `lifecycle-subtype-java-leads` (paired with existing `bidder-rename-major-version`)

## References

- Round 3 lifecycle-naming deep-dive (this conversation): "Final synthesis — Rule 43 expansion" section
- Current Rule 43 wording: `port-translation-rules.md:1297-` (lifecycle rules section)
- PR refs: bilateral — Go #4639, Java #4326; java-leads — predates window (cadent acquisition pre-2025, conversant rebrand pre-2025); go-leads — predates window (Liftoff acquisition 2021, Equativ rebrand 2022)
- Worked example: `adapter-spec.md` Adoppler→ElementalTV (bilateral)
- Schema additions: see ADR-001 D5
