# ADR-008: Phase 5 Expanded Pair Fixtures

**Date**: 2026-05-02 (refined 2026-05-02 audit B1 — empire-parent goldens use existing flat `parent_aliases` listing, not 9-15 separate alias-child specs; effort revised down 2 days; refined 2026-05-03 — vungle pair reclassified `go-leads` → `bilateral` per Phase 5 empirical evidence; cadent pair carries dual-core-registration nuance note; freewheelssp F2 master claim confirmed empirically)
**Status**: Accepted (Phase 5 executed — corpus complete at 9/9 as of commit `ea0a37a`; all pair fixtures shipped with cross-language assertions)

**Note on empire-parent fixture structure**: A Java empire parent's golden does NOT spec each alias child individually. It carries a single bidder spec with a flat `parent_aliases: [child1, child2, ...]` listing of alias names + the parent's own behavior fields. This matches the existing kobler/optidigital pattern (which list `parent_aliases` as a name list). The dual-spec assertion file's `cross_language_alias_graph` block (NEW) captures cross-language alias-graph alignment per-empire. Per-alias detailed coverage happens incrementally as future fixtures (post-Phase-5) target individual alias children.
**Context**: The original plan had Phase 5 add 3 Java goldens (adkernel, adtonos, bidstack). Round 3 inventory analysis revealed that's insufficient to pressure-test the 3 newly-proposed rules (44, 45, 46) and the Rule 43 sub-categorization. Phase 5 should add 7 pair fixtures (with 2 stretch) to provide master samples for each new rule, each sub-categorization branch, and the empire-coverage gap.

## Decision

**Phase 5 expands from 3 to 7 pair fixtures** (with 2 optional stretch pairs):

| # | Pair | Rule coverage | Effort (revised) | Priority |
|---|---|---|---|---|
| 1 | **smarthub-Go + smarthub-Java** (with Attekmi rebrand evidence) | Rule 44 canonical (`white-label-saas` flavor); Rule 45 disabled-by-default empire children; ADR-006 `bilateral` rebrand sub-type via the SmartHub→Attekmi event | 1.5 days | **P1** |
| 2 | **teqblaze-Go + teqblaze-Java** | Rule 44 (`white-label-saas` flavor); ADR-008 `alias-reparent` evidence (ProgX migration); 9-alias empire | 1.5 days | **P1** |
| 3 | **adverxo-Go + adverxo-Java** | Rule 44 (`registration-only` flavor); cleanest small empire; canonical `port-from-go` exemplar | 1 day | **P1** |
| 4 | **limelightDigital-Go + limelightDigital-Java** | Rule 44 (`endpoint-macro-substitution` flavor) — biggest empire (15 aliases); pressure tests at scale | 1.5 days | P2 |
| 5 | **vungle-Go + vungle-Java** (same-name canonical, refined 2026-05-03 from `liftoff-Go + vungle-Java` cross-name) | Rule 43 `bilateral` master sample (phantom-rename refined from `go-leads` per Phase 5 empirical verification — both sides canonical at `vungle`; backward-compat for `liftoff` via Go removed-bidder warning + Java tilde-inherit alias); ADR-007 F3 `synthesize-app-replacement` master sample (vungle's Site→App rewrite) | 1.5 days | P2 |
| 6 | **cadent_aperture_mx-Go + emxdigital-Java** (cross-name) | Rule 43 `java-leads` master sample (defensible label, but Go has dual-core registration of BOTH `cadent_aperture_mx` AND `emx_digital` as core sibling bidders sharing one Builder — topology more nuanced than simple `java-leads`); Rule 46 `underscore-drop` evidence (intra-Java `emx_digital` ↔ `emxdigital`, NOT cross-language) | 1.5 days | P2 |
| 7 | **adkernelAdn-Go + adkerneladn-Java** (naming-normalized) | Rule 46 `lowercase` master sample; cleanest naming-asymmetry pair | 1 day | P3 |
| 8 (stretch) | **freewheelssp-Go + freewheelssp-Java** | ADR-007 F2 `language-stamped-header-divergence` master sample (`Componentid: prebid-go` vs `prebid-java`); **PR refs to verify via `gh pr view` before citing** | 1.5 days | Stretch |
| 9 (stretch) | **thetradedesk-Go + thetradedesk-Java** | ADR-007 F4 `bid-post-processing-macro` master sample (`AUCTION_PRICE` replacement) | 1.5 days | Stretch |

**Total**: 9.5 days (P1 + P2 + P3, revised) or 12.5 days (with stretch). Effort revised down from initial 11.5/14.5 estimates after audit B1 — empire parents use flat `parent_aliases` listings, not per-alias-child specs.

## Per-pair deliverables

Each pair produces:
1. `prebid-server-go/read/test-fixtures/<bidder>.golden.spec.yaml` (Go side)
2. `prebid-server-java/read/test-fixtures/<bidder>.golden.spec.yaml` (Java side; for cross-name pairs, this uses the Java-canonical name)
3. `cross-language-pairs/<bidder>.dual-spec-assertions.yaml` (using the canonical name; cross-name pairs need a `note_on_cross_name_alignment` block)
4. Updates to:
   - `prebid-server-go/read/test-fixtures/README.md` (table row)
   - `prebid-server-java/read/test-fixtures/README.md` (table row)
   - `cross-language-pairs/README.md` (table row)
   - Existing references' Pattern Index (PR refs added)

## Per-pair specification sketch

### Pair 1 — smarthub/Attekmi (P1)

**Go upstream** (commit `d7f8515b…`):
- `static/bidder-info/smarthub.yaml` — parent
- `adapters/smarthub/smarthub.go` (single-file)
- `static/bidder-params/smarthub.json`
- `openrtb_ext/imp_smarthub.go`
- 9 aliases via `aliasOf: smarthub` YAMLs (markapp, jdpmedia, tredio, felixads, jambojar, adinify, artechnology, addigi, radianfusion)

**Java upstream** (commit `69b1993c…`):
- `src/main/resources/bidder-config/smarthub.yaml` — parent (post Attekmi rebrand)
- `src/main/java/org/prebid/server/bidder/smarthub/SmarthubBidder.java`
- `src/main/java/org/prebid/server/spring/config/bidder/SmarthubConfiguration.java`
- 9 aliases declared in parent's `aliases:` block

**Spec content highlights**:
- Go side: `meta.is_alias: false`, `meta.empire_canonical_master: true`, `meta.empire_parent_flavor: white-label-saas`, `parent_aliases: [markapp, jdpmedia, tredio, felixads, jambojar, adinify, artechnology, addigi, radianfusion]`
- Java side: same, plus `code_naming.notes: "SmartHub class root preserved post-Attekmi rebrand for backward-compat"`, `lifecycle.rename: { old_name: smarthub, new_name: attekmi, subtype: bilateral, alias_back: true, alias_back_form: tilde_inherit, merged_at: 2025-02-05, release: v3.21.0 }` (the parent rebrand event)
- Both: `code.make_requests.batching.rules: [single-batched]` (single HTTP per BidRequest, uses first imp), `endpoint_resolution.kind: template-macro` with `macros_used: [Host, AccountID, SourceId]`
- Java parent's `aliases[].relationship_flavor: white-label-saas` (per ADR-003 audit B6)

**Dual-spec assertions** (cross-language-pairs/smarthub.dual-spec-assertions.yaml):
- `bidder_params_sha256` — likely byte-divergent
- `bidder_info_capabilities` — equivalent (both site/app, banner/video)
- `params_schema_interpretation` — equivalent (`partnerName, seat, token`)
- `port_lineage: { direction: go-to-java, source_pr: prebid/prebid-server#1932, destination_pr: prebid/prebid-server-java#1442, parent_lifecycle: { kind: parent-rebrand, evidence_pr: prebid/prebid-server-java#3699 } }`
- `note_on_alias_status: SmartHub is the empire-parent; aliases shipped as separate Go YAMLs and Java alias-block entries; this fixture covers ONLY the parent. Aliases are tracked via the existing `prebid-server-java/references/new-bid-adapter-prs.md` Lifecycle Events section.`

### Pair 2 — teqblaze (P1)

Similar structure to smarthub with these differences:
- `meta.empire_parent_flavor: white-label-saas` + Java parent's `aliases[].relationship_flavor: white-label-saas`; quirk on Java side: `quirks[].edge_case_taxon: alias-reparent-evidence` referencing `prebid/prebid-server-java#4356, prebid/prebid-server#4352`
- `lifecycle` block null on parent (no rebrand)
- Includes the `whitelabel-only-parent` taxon (Java parent ships with `whiteLabelOnly: true`-style indicator)

### Pair 3 — adverxo (P1)

Smallest clean empire. Already partially covered via #3705 (Adverxo Java multi-alias-bundle). New goldens add:
- Both sides: parent + 3 aliases (adport, bidsmind, harrenmedia)
- `meta.empire_parent_flavor: registration-only` + Java parent's `aliases[].relationship_flavor: registration-only`
- `port_lineage: { direction: go-to-java, source_pr: prebid/prebid-server#4018, destination_pr: prebid/prebid-server-java#3705 }`
- Demonstrates `port-from-go` + `multi-alias-bundle` Pattern Index tags

### Pair 4 — limelightDigital (P2)

Stress-tests Rule 44 at scale:
- Go side has 1 primary file + 15 alias YAMLs
- Java side has 1 parent class + 15 aliases in `aliases:` block
- `meta.empire_parent_flavor: endpoint-macro-substitution` + Java parent's `aliases[].relationship_flavor: endpoint-macro-substitution`
- `code.make_requests.endpoint_resolution: { kind: template-macro, macros_used: [Host, PublisherID], macro_syntax: go-template }`

**Note**: limelightDigital establish PRs (Java #2228, Go #2539) predate the references' 2025 window. The fixture cites them in `port_lineage` but doesn't add them as standalone reference entries.

### Pair 5 — vungle (P2, refined 2026-05-03)

**Empirical pair structure** (refined 2026-05-03 from cross-name `liftoff/vungle` to same-name `vungle/vungle`):

Both Go and Java goldens use canonical name `vungle` at the pinned commits. The pair is a `bilateral` phantom-rename, not a `go-leads` rebrand. Liftoff acquired Vungle in 2021 — a parent-company-name change that did NOT translate into a code-level bidder rename. The SSP product remained `Vungle Exchange`. Some operators configured `liftoff` based on the acquisition news; both prebid servers handle this with backward-compat surfaces:

- **Go side**: `exchange/adapter_util.go::GetDisabledBidderWarningMessages` carries a removed-bidder warning entry redirecting `liftoff` → `vungle`. NO `static/bidder-info/liftoff.yaml` exists. The bidder name was never actually renamed in Go code; the legacy operator name `liftoff` is rejected with a redirect message.
- **Java side**: `aliases.liftoff: { enabled: false }` tilde-inherit under `vungle.yaml`. The legacy operator name routes to the vungle adapter through the alias resolution layer (default-disabled — operators must opt in).

Go fixture filename = `vungle.golden.spec.yaml`; Java fixture filename = `vungle.golden.spec.yaml`. Dual-spec filename = `vungle.dual-spec-assertions.yaml` (already authored at commit `d9742a7`).

The dual-spec assertion file carries a `lifecycle.rename` block recording the empirical state:

```yaml
lifecycle:
  rename:
    old_name: liftoff
    new_name: vungle
    subtype: bilateral                      # Empirical correction from 'go-leads' (ADR-006 refined 2026-05-03)
    go_alias_back: removed-bidder-warning-map
    java_alias_back: tilde_inherit
```

Per ADR-007 F3, this fixture is the canonical `synthesize-app-replacement` master (vungle's Site→App rewrite). F3 master claim is independent of the lifecycle reclassification.

### Pair 6 — cadent_aperture_mx (Go) / emxdigital (Java) cross-name (P2, refined 2026-05-03)

Cross-name pair: Go YAML = `cadent_aperture_mx.golden.spec.yaml`; Java = `emxdigital.golden.spec.yaml`. Demonstrates Rule 43 `java-leads` (defensible) + Rule 46 `underscore-drop` (intra-Java only).

**Empirical topology nuance** (refined 2026-05-03; see `cross-language-pairs/emxdigital.dual-spec-assertions.yaml`): The `java-leads` label is defensible but more nuanced than a simple "Go fossilizes the legacy name" framing:

- **Java**: parent `emxdigital` (legacy EMX brand) + alias `cadent_aperture_mx` under `emxdigital.yaml` with `enabled: false` and `geoscope: [USA, CAN]`. Java has chosen a single canonical (`emxdigital`).
- **Go**: DUAL-CORE REGISTRATION. BOTH `cadent_aperture_mx` AND `emx_digital` are registered as fully-enabled core sibling bidders in `coreBidderNames`, sharing the same `cadentaperturemx.Builder` function via separate entries in `exchange/adapter_builders.go`. Each Go name has its own `static/bidder-info/<name>.yaml` (byte-identical sha256 `8ee63ad8…`) and its own `static/bidder-params/<name>.json` (semantically equal, byte-different — the `emx_digital.json` description has a copy-paste bug saying "Cadent Aperture MX adapter"). NEITHER Go name is in `GetDisabledBidderWarningMessages`.

Go has NOT consolidated to a single canonical; it carries both names as live core bidders. The "java-leads" label captures Java's parent-canonical choice but the Go-side topology is dual-core, not legacy-fossilized.

Rule 46 `underscore-drop` applies INTRA-Java (BIDDER_NAME constant `emx_digital` ↔ Spring/YAML key `emxdigital`), NOT as a cross-language pair (Java's canonical YAML key `emxdigital` lacks the underscored form).

### Pair 7 — adkernelAdn (Go) / adkerneladn (Java) (P3)

Pure naming-normalization pair (no rename event). Both files exist but with case-different names. Smallest delta. Demonstrates Rule 46 `lowercase` master.

## Sequencing

P1 pairs (1-3) land first (4 days). They cover Rule 44 across all three flavors plus the Attekmi rebrand evidence. After P1, the new rules have functional master samples and Phase 4.3 coverage report can render cleanly.

P2 pairs (4-6) land in parallel with Phase 4 methodology work (~3 weeks of total Phase 4+5 effort if interleaved, 4.5 days for P2). P2 covers Rule 43 sub-types and the highest-leverage novel-pattern master samples.

P3 (pair 7, 1 day) and stretch (pairs 8-9, 1.5 days each) are nice-to-have.

## Consequences

- Phase 5 effort: 4 days P1 → 9.5 days P1+P2+P3 → 12.5 days with stretch (revised down 2 days per audit B1)
- Empire coverage: 5 → 8 of 32 Java empire parents (25%)
- Lifecycle coverage: 1 (elementaltv) → 3 (elementaltv `bilateral` + vungle `bilateral` phantom-rename + cadent_aperture_mx/emxdigital `java-leads` with dual-core nuance) — `bilateral` and `java-leads` covered. `go-leads` has empirical cardinality 0 at the pinned commits (refined 2026-05-03; both originally-classified `go-leads` pairs reclassified). The 5-subtype taxonomy (`bilateral | java-leads | go-leads | mirror-topology | inverted-parent`) is documented in ADR-006 with master samples for 4 of 5 subtypes.
- Naming-asymmetry coverage: 0 → 1 (adkernelAdn/adkerneladn) — Rule 46 has master sample
- Novel-pattern master samples (with stretch): F1 ✗, F2 ✓ (freewheelssp), F3 ✓ (vungle), F4 ✓ (thetradedesk), F5 ✗
- Coverage report at end of Phase 5 lists the remaining 24 uncovered empire parents and 8 uncovered lifecycle pairs as tracked gaps for incremental future work
- Each Phase 5 fixture commit MUST verify cited PR refs via `gh pr view` before authoring (audit C8 — diversity agent's freewheelssp PR refs `#2392`/`#2251` were unverified)

## References

- Round 3 inventory analysis (this conversation): empire/lifecycle/naming gap quantification
- Empire deep-dive (this conversation): all 5 empire parents inspected with PR provenance
- Diversity sample (this conversation): novel patterns identified for ADR-007 master samples
- Rules: ADR-003 (Rule 44), ADR-004 (Rule 45), ADR-005 (Rule 46), ADR-006 (Rule 43 sub-types), ADR-007 (novel patterns)
- Existing canonical: kobler pair (Phase A acceptance gate); the new pairs follow the kobler structural template
- References integration: `prebid-server-java/references/new-bid-adapter-prs.md` "Parent Lifecycle Events" section + Pattern Index tags `alias-empire`, `alias-add`, `alias-reparent`, `parent-rebrand`, `parent-evolve`, `white-label-saas`, etc.
