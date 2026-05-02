# ADR-003: Rule 44 — Java Alias-Empire Consolidation

**Date**: 2026-05-02
**Status**: Proposed (Phase 2 execution adds to `port-translation-rules.md` / `port-translation-rules.yaml`)
**Context**: Round 3 inventory revealed that Java consolidates 95 of its 350 bidders as aliases under 32 parent "alias-empires", while Go keeps most of them as standalone primary bidders. This is a systematic cross-language pattern that no current rule captures. Empire deep-dive on 5 parents (limelightDigital, teqblaze, smarthub/Attekmi, adtelligent, nexx360) confirms a single mechanism with three observational sub-flavors.

## Decision

**Rule 44: Alias-Empire Consolidation.** When Java registers N siblings under a shared parent's `aliases:` block (re-using the parent's `Bidder<T>` instance via `BidderDepsAssembler.aliasesDeps()`) while Go registers them as YAMLs with `aliasOf: <parent>` against a single `adapters/<parent>/` package, treat the empire as one logical adapter family in both servers.

Three sub-flavors (observational, not separate rules):

| Sub-flavor | Mechanism | Master sample |
|---|---|---|
| `endpoint-macro-substitution` | One `Bidder<T>` class; alias differentiates via `imp.ext.bidder.host` filling endpoint macros (`{{Host}}`, `{{PublisherID}}`) | limelightDigital (15 aliases) |
| `white-label-saas` | One `Bidder<T>` class; alias differentiates via per-alias `endpoint:` override pointing at the alias's SaaS host | smarthub/Attekmi (9 aliases), teqblaze (9 aliases) |
| `registration-only` | One `Bidder<T>` class; alias is purely a name registration with no behavioral override; parent endpoint serves all | nexx360 (4 aliases), adverxo (3 aliases) |

**Mechanism invariant** (across all three flavors):
- Java: parent's `*Configuration.java` registers `BidderConfigurationProperties` for the parent; `aliases:` block in `bidder-config/<parent>.yaml` lists children with optional per-alias YAML-merge overrides; `BidderDepsAssembler.aliasesDeps()` auto-iterates aliases and reuses the parent's `bidderCreator` lambda for each
- Go: each alias has its own `static/bidder-info/<alias>.yaml` with `aliasOf: <parent>`; routes to the parent's `adapters/<parent>/` package at request time

**Spec field drivers** (refined 2026-05-02 audit, B6 — uses existing fields rather than adding redundant `cross_language.empire` block):

- `meta.is_alias`, `meta.alias_of` (Go-side child specs) — already exists
- `aliases[]` block (Java-side parent specs) — already exists; per-alias override metadata
- `meta.empire_canonical_master: bool` (NEW) — flag on a parent or single representative spec marking it as the canonical Rule 44 master sample
- `meta.empire_parent_flavor: endpoint-macro-substitution | white-label-saas | registration-only | null` (NEW) — set on child specs to mirror their parent's empire flavor; null when not part of an empire
- `aliases[].relationship_flavor: endpoint-macro-substitution | white-label-saas | registration-only` (NEW) — set on parent's `aliases[]` entries to declare each child's empire flavor relationship

**Rationale for using existing fields**: A standalone `cross_language.empire` block would duplicate `meta.alias_of` (Go-side) and `aliases[]` (Java-side). The empire-flavor tag is the ONLY new fact and naturally hangs off existing alias structures. Single-language readers can populate these fields from their own side; cross-language verification (parent existence, flavor coherence) lives in the dual-spec assertion file.

**Mechanizable**: yes (Phase 4.6 lint-port-rules.py can verify). For each Go-side `aliasOf:` entry, assert that the corresponding Java side declares the alias under the same parent's `aliases:` block (or accept divergence with a `cross_language.alias_graph_divergence` quirk).

## Canonical master sample

**smarthub/Attekmi** is the canonical Rule 44 master:
- Cleanest empire shape (single HTTP request, three macro placeholders, white-label hosts)
- Enough aliases (9) to be representative
- Includes a parent-rebrand event (SmartHub→Attekmi, see ADR-006)
- Tight Go-coherence (no `aliasOf` mismatches)

**adverxo** is the smallest clean canonical (3 aliases, simple).
**limelightDigital** is the complexity-high reference (15 aliases, `endpoint-macro-substitution` flavor).

## Round-trip considerations

- Empire-to-empire round-trip is lossless: both languages encode the same parent + child relationship.
- Go-to-Java port involving a Go-primary that should be Java-aliased: porter consults `cross_language.empire.parent` (if known) or falls back to declaring as a standalone Java bidder.
- Empire migrations (`alias-reparent`) require updating the parent reference on BOTH sides; Phase 4.2 PR audit can detect partial migrations.

## Consequences

- Phase 2 adds Rule 44 to `port-translation-rules.yaml` with 5 master samples
- Phase 2 adds `meta.empire_canonical_master`, `meta.empire_parent_flavor`, `aliases[].relationship_flavor` to schema (no new top-level block; uses existing `meta` and `aliases[]` structures)
- Phase 4.3 coverage report tracks: 5 of 32 Java empire parents currently have goldens; 27 uncovered. Each new empire pair fixture (Phase 5 + future) closes one gap.
- Phase 5 prioritizes 3 empire pairs (smarthub, teqblaze, limelightDigital) to bring coverage to 8/32 (25%) — see ADR-008
- New Pattern Index tags already added to references (commit `2026-05-02`): `alias-empire`, `alias-add`, `alias-reparent`, `cross-empire-migration`, `parent-rebrand`, `parent-evolve`, `registration-only-alias`, `white-label-saas`, `endpoint-macro-substitution-empire`
- Cross-language alias-graph alignment (parent existence, flavor coherence) is verified by Phase 2.6 mechanizable lint reading both per-language specs + the dual-spec assertion file

## References

- Round 3 inventory analysis: 32 Java parents, 95 Java aliases, 17 cross-language coherent + 79 asymmetric alias relationships
- Empire deep-dive (this conversation): 5 parents inspected with PR provenance
- PR refs (Java): #2228 (limelightDigital establish, pre-window), #4053 (Nexx360 establish), #4161 (TeqBlaze establish), #3705 (Adverxo establish), #1442 (SmartHub establish, pre-window)
- PR refs (Go): #4480 (TeqBlaze), #4286 (Nexx360), #2539 (LimeLightDigital, pre-window), #1932 (SmartHub, pre-window)
- Empire-evolution PRs: Java #4356 (alias-reparent), #3699 (parent-rebrand), #4359 (parent-evolve), #4467 + #4473 (alias-add)
- Code reference: `BidderDepsAssembler.aliasesDeps()` in `src/main/java/org/prebid/server/spring/config/bidder/util/BidderDepsAssembler.java`
- Mechanism doc: `prebid-server-java/references/new-bid-adapter-prs.md` "Parent Lifecycle Events" section + Pattern Index `alias-empire` tag
