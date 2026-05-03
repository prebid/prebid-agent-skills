# ADR-005: Rule 46 — Naming-Convention Normalization

**Date**: 2026-05-02 (refined 2026-05-02 audit A2 — moved cross-language facts from per-language spec to dual-spec assertion format; refined 2026-05-03 — drop freewheel-ssp/freewheelssp from RULE_46_PAIRS per Phase 5 empirical verification, count 12 → 11)
**Status**: Accepted (Phase 2 executed — Rule 46 lives at `port-translation-rules.yaml`/.md; rendered count 46)
**Context**: Round 3 inventory identified 11 cross-language pairs (refined from 12 after empirical verification — see freewheelssp dual-spec) where Go uses camelCase or snake_case bidder names and Java normalizes to all-lowercase, alphanumeric-only. The pattern is mechanical and was previously conflated with Rule 43 (lifecycle rename). It's not a rename — it's a naming-convention transformation on the resting state. Round 3 lifecycle-naming deep-dive confirmed this should be a separate rule.

## Decision

**Rule 46: Naming-Convention Normalization.** When porting a Go bidder identifier to Java parent-YAML form, apply lowercase + drop non-`[a-z0-9]` characters to derive the Java parent-YAML filename and Spring bean key. Two allow-listed exceptions handle the cases the pure-mechanical rule cannot:

1. **Digit-leading workaround**: digit-leading names spell out the digit for the Java *class root* but the parent-YAML name still drops the digit. Example: `33across → thirtythreeacross.yaml` + `Thirtythree` class root; `152media → 152media` YAML alias under adkernel + `OneFiveTwoMedia` class root.

2. **Brand-acronym preservation**: TitleCase class root preserves brand acronyms; YAML name stays lowercase. Examples: `elementaltv → elementaltv.yaml + ElementalTV` class root; `feedad → feedad.yaml + FeedAd`; `bidscube → bidscube.yaml + BidsCube`.

**Mechanical transformation**:
```python
def go_to_java_parent_yaml_name(go_name: str) -> str:
    """Apply Rule 46 mechanical normalization."""
    return go_name.lower().replace('_', '').replace('-', '')
```

**Spec field drivers** (refined 2026-05-02 audit A2 — cross-language facts live in dual-spec, not per-language spec):

- **Per-language spec**: `meta.bidder_name` (existing) records each side's verbatim name. No new per-language fields. A Go-side orchestrator doesn't know the Java side's name; per-language `cross_language.naming_asymmetry` would always be null-on-write.

- **Per-language quirk** (NEW taxon): `quirks[].edge_case_taxon: naming-convention-normalization` — emitted on Java side when Java name was derived from a Go name via mechanical transformation. Carries the transformation: `lowercase | underscore-drop | hyphen-drop | digit-leading-workaround | brand-acronym-preservation`.

- **Dual-spec assertion file** (NEW block): a new top-level `naming_asymmetry` key alongside `bidder_params_sha256`, `bidder_info_capabilities`, etc.:
  ```yaml
  naming_asymmetry:                             # Optional. Populated when go and java bidder names differ.
    go_name: boldwin_rapid                      # Verbatim Go YAML name.
    java_name: boldwinrapid                     # Verbatim Java parent-YAML name.
    transformation: underscore-drop             # Mechanical rule applied.
    java_class_root: BoldwinRapid               # Java class root (TitleCase) when applicable.
    rule_46_compliant: true                     # Whether the transformation matches Rule 46's mechanical formula.
    severity: pass                              # Pass when rule_46_compliant=true; warn otherwise.
  ```

**Rationale for moving to dual-spec**: A Go-only or Java-only reader can't populate cross-language naming-asymmetry facts. The dual-spec file is the natural cross-language joiner; this matches ADR-004's architecture for Rule 45.

**The 11 verified pairs** (refined 2026-05-03 — `freewheel-ssp/freewheelssp` removed; see "Excluded cases" below):

| Go (raw) | Java (raw) | Transformation |
|---|---|---|
| adkernelAdn | adkerneladn | `lowercase` |
| audienceNetwork | audiencenetwork | `lowercase` |
| boldwin_rapid | boldwinrapid | `underscore-drop` |
| emx_digital | emxdigital | `underscore-drop` (+ also a Rule 43 lifecycle rebrand) |
| e_volution | evolution | `underscore-drop` |
| lm_kiviads | lmkiviads | `underscore-drop` |
| mgidX | mgidx | `lowercase` |
| sa_lunamedia | salunamedia | `underscore-drop` |
| sspBC | sspbc | `lowercase` |
| stroeerCore | stroeercore | `lowercase` |
| triplelift_native | tripleliftnative | `underscore-drop` |

### Excluded cases — `freewheel-ssp/freewheelssp` (Phase 5 empirical correction)

The `freewheel-ssp/freewheelssp` pair was originally listed as a cross-language `hyphen-drop` Rule 46 case, but Phase 5 fixture authoring (commit `f11b2ba`, see `cross-language-pairs/freewheelssp.dual-spec-assertions.yaml`) verified that **both canonical YAMLs use `freewheelssp` (same name)** at the pinned commits:

- Go canonical: `static/bidder-info/freewheelssp.yaml` (sha256 `42f84dcf…`, 510B, full config).
- Java canonical: `src/main/resources/bidder-config/freewheelssp.yaml` (sha256 `82da1671…`).

The hyphenated `freewheel-ssp.yaml` form is a **Go-only YAML alias-stub** declared via a top-level `aliasOf: freewheelssp` field (sha256 `c5a2bdc5…`, 262B). The hyphen-drop transformation `freewheel-ssp → freewheelssp` IS mechanically valid, but it applies INTRA-Go (alias-stub → canonical), not CROSS-LANGUAGE. Rule 46 as defined is a cross-language contract; the freewheel pair doesn't qualify.

This is the only pair removed; the corpus inventory now stands at **11 cross-language Rule 46 pairs** (previously 12). `INVENTORY_TOTALS["naming_normalization_pairs"]` in `scripts/coverage-report.py:105` is updated to `11`.

## Why separate from Rule 43

Rule 43 (lifecycle rename) is **event-driven** — it captures the lifecycle moment of a rename (DELETE old, CREATE new, alias-back). Rule 46 is **static** — a translation contract on the resting state. The two rules can co-occur (a rename PR may also normalize), but they answer different questions:

- "How does the Java name look right now?" → Rule 46 (mechanical transformation)
- "What happens during a rename?" → Rule 43 (lifecycle event)

Cases that DON'T fit Rule 43 (they belong under Rule 46):
- `33across/thirtythreeacross` — pure naming-normalization, no lifecycle event
- `freewheelssp/fwssp` — sibling alias naming with hyphen-drop (Rule 46)

## Canonical master samples

- **Lowercase**: `audienceNetwork → audiencenetwork` (single transformation, no other variations). Phase 5 master sample: `adkernelAdn/adkerneladn`.
- **Underscore-drop**: `boldwin_rapid → boldwinrapid` (PR `prebid/prebid-server-java#4285`, already tagged `snake-case-bidder-name`).
- **Hyphen-drop**: NO empirical cross-language master sample at the pinned commits. The previously-cited `freewheel-ssp → freewheelssp` was reclassified as a Go-only alias-stub (see "Excluded cases" above). If a future fixture surfaces a true cross-language hyphen-drop pair, this slot can be filled.
- **Digit-leading-workaround**: `152media → 152media + OneFiveTwoMedia class root` (PR `prebid/prebid-server-java#3829`, already tagged `digit-leading-bidder-class-workaround-OneFiveTwoMedia`).
- **Brand-acronym-preservation**: `elementaltv → ElementalTV class root` (PR `prebid/prebid-server-java#4326`, already tagged `acronym-case-preservation`).

## Mechanizability

**Fully mechanical** for the lowercase/underscore-drop/hyphen-drop sub-flavors. Phase 4.6 `lint-port-rules.py` can verify: given a Go YAML name, the corresponding Java YAML name MUST equal `name.lower().replace('_','').replace('-','')` UNLESS the bidder is in the allow-list (digit-leading or brand-acronym).

## Consequences

- Phase 2 adds Rule 46 to `port-translation-rules.yaml`
- Phase 2 adds `naming_asymmetry` block to **dual-spec assertion file format** (NOT to per-language schema)
- Phase 2 adds the new `naming-convention-normalization` taxon to `behavior-taxonomy.yaml`
- Phase 5 includes adkernelAdn/adkerneladn pair as Rule 46 master sample fixture (see ADR-008)
- Existing Java references' Pattern Index already has `snake-case-bidder-name` and `digit-leading-bidder-class-workaround-OneFiveTwoMedia` tags — Phase 2 expands these with explicit Rule 46 cross-references
- Rule 43 wording is tightened (does NOT cover `33across/thirtythreeacross`, etc. — those are Rule 46 per ADR-006)
- Phase 2 mechanizable lint: `lint-port-rules.py` for Rule 46 reads both per-language specs from a dual-spec entry and verifies `name.lower().replace('_','').replace('-','')` matches; flags allow-list exceptions
- All 7 existing dual-spec assertion files updated where `naming_asymmetry` applies (1 of 7 currently — appnexus has no naming asymmetry; kobler/optidigital/aax/elementaltv/mediasquare/152media don't either; only future fixtures will populate the field)

## References

- Round 3 lifecycle-naming deep-dive (this conversation): "Naming-convention findings" section
- 12 verified pairs from inventory analysis
- PR refs: Java #4285 (boldwinrapid canonical), #3829 (152media digit-leading), #4326 (elementaltv acronym), #4361 (360playvid digit-leading-yaml-only); Go #4211 (underscore-allowed), #4376 (package-name-lowercase)
- Existing taxa: `tilde-alias-syntax` (`behavior-taxonomy.md:417`), `acronym-case-preservation` (already tagged)
- Related: `prebid-server-go/read/skills/read-bidder-params/references/schema-interpretation.md:393-413` (TitleCase rule for `BidderName` constants — separate from Rule 46 since `BidderName` constants are case-rich on Go)
