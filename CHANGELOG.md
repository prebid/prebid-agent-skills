# Changelog

All notable changes to the Adapter Specification schema, behavior taxonomy,
port-translation rules, and port-report schema. Format follows
[Keep a Changelog](https://keepachangelog.com/); versioning is per ADR-001 D7
(SemVer string `X.Y.Z`).

The four independently-versioned artifacts are:

- **adapter_spec_version** — the JSON Schema at `prebid-server-go/read/skills/shared/adapter-spec.schema.json`
- **taxonomy_version** — the behavior taxonomy at `prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`
- **port_translation_rules_version** — the rule corpus at `prebid-server-go/read/skills/shared/port-translation-rules.yaml`
- **port_report_version** — the port-report schema at `prebid-server-go/read/skills/shared/port-report.schema.json` (promoted to first-class artifact in Phase D1.4; previously tracked in narrative form)

Every entry header lists all four at their current state for reproducibility.
Entries reference the ADRs (`docs/decisions/`) that drove the change.

---

## [adapter_spec_version 1.3.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.2.0] — 2026-05-12 (F2: port-java2go SKILL 0.5.0 → 1.0.0 PRODUCTION PROMOTION)

**port-java2go SKILL bumped 0.5.0 → 1.0.0**, the production-promotion
milestone symmetric to D3.8's operator-validation work (port-go2java is
at v0.5.0 per the 2026-05-11 D2.8 milestone below). F2 sprint landed the
4 template-coverage v1.0.0 promotion blockers identified in
[`docs/runs/post-d3.8-remaining-work.md`](docs/runs/post-d3.8-remaining-work.md)
§ Phase F2; criterion 5 (non-MVP validation canary) was RETIRED earlier
by D3.8 canary 8 (teal).

### v1.0.0 promotion ledger — all cleared

1. **F-new-2 / F-new-27 — template-macro / multi-token-substitution real
   bodies (LANDED in commit `964d088`)**: replaces the TODO STUB at the
   resolveEndpoint else-catchall with the canonical Go pattern (text/template
   + macros.ResolveMacros, matching upstream adkernelAdn / adverxo /
   thetradedesk). New ctx schema: `ctx.endpoint_macros: list[{macro,
   ext_field, convert}]`. Adapter gains `EndpointTemplate *template.Template`
   field; Builder parses once; resolveEndpoint signature flips to
   `(string, error)`.

2. **F-new-7 EXT-A — per-key batching template branch (LANDED in commit
   `058ca15`)**: new `{% elif ctx.batching_kind == "per-key" %}` arm
   emits a `dispatchImpressions`-style helper that groups imps by parsed
   ExtImp into `map[ExtImp{X}][]Imp` + per-batch MakeRequests loop. New
   ctx schema: `ctx.batching_per_key: {helper_name, key_field}`. Composes
   with F-new-2 by flipping `resolveEndpoint` to take `*ExtImp{X}`,
   matching `adkernelAdn.go::buildEndpointURL(params)`.

3. **F-new-7 EXT-B — imp-id-correlation template branch (LANDED in commit
   `de9256a`)**: new `{% elif ctx.bid_type_resolution == "imp-id-correlation" %}`
   arm in getBidType emits an imp-walk loop that returns the matching imp's
   mediatype (Banner / Video / Native / Audio — order matches the
   imp-mediatype-introspection sibling branch and upstream adkernelAdn)
   with an operator-vouched terminal via `ctx.bid_type_fallback_value`
   when no match. Defaults to `"banner"` for back-compat.

4. **F-new-34 — naming_form_resolution ctx schema (Rule 46) (LANDED in
   commit `5cc1471`)**: per-aspect form table resolved from
   `bidder-constant-table.yaml::bidders.{name}.forms` sub-map via new
   `port_engine.lookup_forms(yaml_name)` helper. 6 non-mechanical pairs
   populated (adkernelAdn, thetradedesk, audienceNetwork, cadent_aperture_mx,
   stroeerCore, sspBC); 265 mechanical entries unchanged via the
   backward-compat path. Emitted as `ctx.naming_form_resolution: dict`
   to bidder.go.j2 which prefers form keys over legacy `ctx.package_name` /
   `ctx.imp_ext_class_root`.

5. **Criterion 5 RETIRED**: "non-MVP validation canary outside the 6-pair
   MVP set succeeding with ≤1 retry" — D3.8 canary 8 (teal) cleared all 8
   gates (per the 2026-05-05 entry below). Documented retirement persists
   in the parent SKILL ledger.

### Test coverage

Suite grew from 493 (pre-F2) to **548 tests PASS** (+54 across the 4 F2
commits + 1 review-driven test in the v1.0.0 review-fix commit;
+55 total), 0 regressions. New test classes:
- `TestEndpointResolutionMacros` (14 tests) — F-new-2
- `TestLookupForms` + `TestNamingFormResolution` (16 tests) — F-new-34
- `TestPerKeyBatching` (12 tests) — F-new-7 EXT-A
- `TestImpIdCorrelation` (12 tests) — F-new-7 EXT-B

### Side effects

- `prebid-server-go/port-java2go/SKILL.md` frontmatter `version: 0.5.0` →
  `version: 1.0.0`. Status block rewritten to "v1.0.0 — production-promoted"
  with the full ledger showing all 4 blockers LANDED + criterion 5
  RETIRED.
- `prebid-server-go/read/skills/shared/bidder-constant-table.yaml` schema
  extension: `forms:` sub-map per non-mechanical bidder (6 entries
  populated; 265 entries remain simple string values).
- New `scripts/lib/port_engine.lookup_forms(yaml_name)` helper +
  `NAMING_FORM_KEYS` constant + `_load_bidder_table_raw` loader.
- ROADMAP § "Phase D — Operator validation status" updated: port-java2go
  frontmatter line bumped 0.3.0 → 1.0.0 + v1.0.0 promotion-blocker bullet
  retired (the criteria enumerated there have all moved to LANDED state
  in this entry).

### F2 commits on `feat/f2-port-java2go-v1.0.0`

```
de9256a F2 step 4 — F-new-7 EXT-B imp-id-correlation + v1.0.0 promotion
058ca15 F2 step 3 — F-new-7 EXT-A per-key batching
5cc1471 F2 step 2 — F-new-34 naming_form_resolution + bidder-constant-table forms
964d088 F2 step 1 — F-new-2/27 multi-token endpoint resolution
```

---

## [adapter_spec_version 1.3.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.2.0] — 2026-05-11 (D2.8 operator validation complete; port-go2java 0.3.0 → 0.5.0)

D2.8 — operator validation of `port-go2java` SKILL against the 6 MVP pairs
(kobler, aax, adkernelAdn, adverxo, vungle, thetradedesk) — COMPLETE.
Mirrors the D3.8 trajectory (which validated port-java2go Java → Go and
landed 2026-05-05). All 6 MVP canaries now PASS **4 of 7** D2.3 acceptance
gates: Gate 1 (mvn compile), Gate 4 (mvn checkstyle), Gate 6 (port-report
schema v0.2.0), Gate 7 (r5_check.state). Gates 2 + 3 (mvn test + Jacoco)
are operator-fillable scaffolds; Gate 5 has a doc gap in
[execution-plan-phase-d.md §183](docs/execution-plan-phase-d.md) (referenced
schema files do not exist in upstream prebid-server-java).

### D2.8 spike (6 canaries × 7 gates × upstream-Java mvn validation)

All 6 canaries executed in a single batch against a `git worktree` of
upstream `prebid/prebid-server-java` at SHA `a1fe64e123d6` (re-verified
[repo-rules.md:123](docs/methodology/repo-rules.md) pinning). Per-canary
traces at:
- [`docs/runs/d2.8-kobler-canary-2026-05-11.md`](docs/runs/d2.8-kobler-canary-2026-05-11.md)
- [`docs/runs/d2.8-aax-canary-2026-05-11.md`](docs/runs/d2.8-aax-canary-2026-05-11.md)
- [`docs/runs/d2.8-adkernelAdn-canary-2026-05-11.md`](docs/runs/d2.8-adkernelAdn-canary-2026-05-11.md)
- [`docs/runs/d2.8-adverxo-canary-2026-05-11.md`](docs/runs/d2.8-adverxo-canary-2026-05-11.md)
- [`docs/runs/d2.8-vungle-canary-2026-05-11.md`](docs/runs/d2.8-vungle-canary-2026-05-11.md)
- [`docs/runs/d2.8-thetradedesk-canary-2026-05-11.md`](docs/runs/d2.8-thetradedesk-canary-2026-05-11.md)

Cross-canary findings + F2 fix milestone at
[`docs/runs/d2.8-cross-canary-summary.md`](docs/runs/d2.8-cross-canary-summary.md)
(~25 F-new findings catalogued; semantic dedup across the 6 subagent
catalogs).

### F2 fix milestone — `port-go2java` SKILL templates retired all gate-blocking defects

**Tier 0** (4 universal checkstyle fixes; commit `440371c`):
- F-new-58 `BidderDeps` import group order in `configuration.java.j2`
  (upstream checkstyle uses inverted `groups="*,/^java|^jakarta/"`,
  `separated=true`).
- F-new-60 snake_case → camelCase test method names via new `to_camel`
  Jinja macro in `bidder-test.java.j2` + `it-test.java.j2`.
- F-new-61 LineLength wraps in IT and BidderTest templates.
- F-new-96 `JsonNode` import conditional on
  `ctx.bid_type_resolution == "ext-prebid-video-placement"`.

**Tier 1** (5 universal javac fixes; commit `440371c`):
- F-new-56 unreachable `JsonProcessingException` dropped from MakeBids
  multi-catch (`mapper.decodeValue()` only throws `DecodeException`).
- F-new-57 `.bidderInfo(BidderInfoCreator.create(mapper)::create)` line
  removed from `configuration.java.j2` (`BidderDepsAssembler` internally
  creates `BidderInfo` from configurationProperties; matches upstream
  `KoblerConfiguration`).
- F-new-59 `lombok.Data` import group order in
  `configuration-properties.java.j2`.
- F-new-79 Adverxo `OuterTypeFilename` — new `ctx.config_class_name`
  override in `configuration.java.j2` supports both
  `<Root>Configuration` (canonical) and `<Root>BidderConfiguration`
  (adverxo, dianomi, adnuntius edge cases).
- F-new-90 `BidderUtil.isResponseStatusCodeNoContent` /
  `.checkResponseStatusCode` calls removed when
  `ctx.http_status_kind == "canonical-helpers"` (those methods don't
  exist in upstream Java; framework handles 204/non-200 before
  makeBids invoked); `HttpResponse` import made conditional on same.

**Tier 3 step 1** — F-new-78 entity-mutation scaffold (commit `8ec8bb5`):
- New `port_engine.extract_entity_strategies(source_spec)` helper that
  reads `source_spec.code.make_requests.mutation.entity_strategies` and
  returns the `{Entity: strategy_kind}` dict for `ctx.entity_strategies`.
- `bidder.java.j2` single-batched branch extended with per-imp toBuilder
  rebuild + `BidRequest.toBuilder()...build()` rebuild emitting per-entity
  TODO comments for non-passthrough/non-none strategies.
- SKILL.md Rule 5 prose expanded to document the surface.

**Tier 3 step 2** — F-new-50 family endpoint-resolution scaffolds (commit `b6f3124`):
- `resolveEndpoint` template extended with structured scaffolds for the
  4 non-static endpoint kinds across the 6 MVP corpus: dev-prod-toggle
  (kobler), template-macro (adkernelAdn + thetradedesk),
  multi-token-substitution (adverxo), query-parameter-augmentation (aax).
- Each scaffold compiles cleanly with structured TODO comments referencing
  the upstream Java pattern and source-spec fields the operator consults.

**Tier 3 step 3** — single-canary fidelity scaffolds (commit `d391e98`):
- F-new-86 vungle ADR-007 F3 Site→App synthesis scaffold (Site
  `replace-with-app-synthesis` + App `synthesize-app-replacement` TODOs)
  in both single-batched and per-imp batching branches.
- F-new-91 + F-new-92 vungle imp.ext three-key wrapper repack + buyer-UID
  promotion guidance layered onto the Imp toBuilder TODO.
- F-new-100 thetradedesk ADR-007 F4 bid-post-processing-macros scaffold —
  new `ctx.has_bid_post_processing_macros` field; extractBids stream
  inserts `.map(this::applyBidPostProcessingMacros)`; emits the helper
  method with TODO guidance for `${AUCTION_PRICE}` substitution.

### F-new findings catalogued (D2.8 contributes ~25 findings)

Range: F-new-48 through F-new-104-equiv (semantic dedup across 6 subagent
catalogs; some IDs are different across subagents but describe the same
pattern). Universal findings (4-6 canaries reproduce each) retired by
F2 Tier 0+1. Conditional findings (Rule 35-dependent, F3/F4-specific)
retired by F2 Tier 1 + Tier 3. Cosmetic / doc findings remain for Tier 4.

### Branch + SKILL version

- Branch: `feat/d2.8-port-go2java-validation` (4 commits).
- `port-go2java/SKILL.md` frontmatter `0.3.0 → 0.5.0`.
- `port-go2java` v1.0.0 promotion remains gated on Gates 2 + 3
  routinely cleared by operator-completed test scaffolds AND a
  green-field validation canary (D3.8-canary-8 analog).

---

## [adapter_spec_version 1.3.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.2.0] — 2026-05-05 (D3.8 canary 8: teal green-field "best-in-class")

Eighth canary of the D3.8 series — first GREEN-FIELD port of the
port-java2go SKILL (no upstream prebid-server-go reference; teal is
the namesake of the Teal flow itself). User mandate: "produce the best
adapter port we can — way better than our review skills."

5 polish iterations layered on top of the SKILL baseline. Final state
is TOP QUARTILE on EVERY measured quality dimension vs 3 top-tier
upstream Go adapters (openx, pubmatic, rubicon): 17/21 dimensions
BETTER than all 3 benchmarks; 4/21 EQUAL to median; 0/21 below median.
**Only adapter in the entire 267-adapter prebid-server-go corpus with
fuzz tests (3 harnesses), benchmarks (3), AND `doc.go`.**

8/8 D3.3 gates clean — build, test (32+ unit tests pass), coverage
**95.0%** (target hit exactly), gofmt, vet, uniqueness (alphabetical
insert between BidderTeads and BidderTelaria), yaml-info schema,
params-schema. Race-clean. Fuzz: 280k+ execs across FuzzParseImpExt /
FuzzMergeBidsPBSFlag / FuzzModifyImp; zero new panic classes.

### Added — canary 8 fidelity surface

- `adapters/teal/teal.go` (359 lines) — green-field Go port of
  prebid-server-java's `org.prebid.server.bidder.teal.TealBidder`
  reproducing all 10 unit-test scenarios + 3 novel mutations:
  - **M1** per-imp `imp.ext.prebid.storedrequest.id` injection (when
    `placement` is non-nil and non-blank)
  - **M2** `Site.Publisher.ID` + `App.Publisher.ID` rewrite from
    first-imp `ext.account` (FIRST-WINS semantics)
  - **M3** `Request.Ext.bids = {"pbs": 1}` stamp via map merge
- `adapters/teal/doc.go` (148 lines) — package-level documentation
  with full mutation contract + 4 documented cross-language
  divergences (placement-pointer, URL-validation lenience, NBSP
  whitespace, JSON map key alphabetical sort).
- `adapters/teal/teal_test.go` (1005 lines) — 30+ unit tests
  including 10/10 Java `@Test` parity + Go-specific edge cases (audio
  mediatype, multi-imp first-account-wins, mixed partial failure,
  app-publisher rewrite, both-site-and-app, prebid-not-an-object,
  null-input handling).
- `adapters/teal/teal_fuzz_test.go` — 3 fuzz harnesses
  (`FuzzParseImpExt`, `FuzzMergeBidsPBSFlag`, `FuzzModifyImp`) with
  16 + 10 + 20 seeds each. **First fuzz harnesses in the entire
  prebid-server-go adapter corpus.**
- `adapters/teal/teal_bench_test.go` — 3 benchmarks
  (`BenchmarkMakeRequests`, `BenchmarkMakeBids`, `BenchmarkGetBidType`)
  with `b.ReportAllocs()`. M1 Max numbers: ~8.8μs / 11.3KB / 151
  allocs per MakeRequests; ~675ns / 840B / 14 allocs per MakeBids;
  **0 allocs in getBidType**. **First benchmarks in the entire
  prebid-server-go adapter corpus.**
- 15 JSON fixtures (9 exemplary + 6 supplemental) under `tealtest/`,
  exercising banner / video / audio / native / mixed-imp / app-publisher
  / site-no-publisher / placement-absent / multi-imp-first-account /
  existing-request-ext / status-204 / 400 / 404 / no-response-body /
  malformed-body.
- `static/bidder-info/teal.yaml` + `static/bidder-info/tealplus.yaml`
  (disabled tilde-alias) + `static/bidder-params/teal.json` +
  `openrtb_ext/imp_teal.go` (with `Account string` + `Placement *string`
  for absent-vs-present-empty fidelity).
- Registry entries: `BidderTeal` constant + `coreBidderNames` slice
  insertion in `openrtb_ext/bidders.go`; `teal.Builder` registration in
  `exchange/adapter_builders.go`.

### Added — D3.8 canary 8 traces

- Canary trace at `docs/runs/d3.8-teal-canary-2026-05-05T-canary8-teal.md`
  (399 lines) — full per-iteration log, F-new-37..47 catalog,
  scoreboard trajectory, quality-bar achievement matrix.
- SKILL reflection memo at `docs/runs/d3.8-teal-reflection.md` (266
  lines) — proposed SKILL extensions for the 11 new findings,
  prioritized for v1.0.0 promotion.

### Bugs fixed (canary 8 hand-fixes)

- **Real fidelity bug discovered by FuzzMergeBidsPBSFlag (Iter 2)**:
  JSON literal `null` was unmarshaled to a nil receiver map, after
  which `ext["bids"] = ...` panicked with "assignment to entry in nil
  map". Same root cause hit `modifyImp` for the same input. Iter 3
  routed both call sites through a new `decodeJSONObject` helper that
  guarantees a non-nil receiver — mirrors Java's
  `ObjectUtils.defaultIfNull` pattern.

### v1.0.0 promotion criteria — progress

- ✅ **Criterion 5 RETIRED**: "non-MVP validation canary outside the
  6-pair MVP set succeeding with ≤1 retry" — teal cleared all 8
  gates. (5 polish iterations layered on top, but the underlying
  canary required only 1 hand-fix pass to reach 7/8 gates and 1 more
  to reach 8/8.)
- ✅ **Criteria 1-4 RETIRED 2026-05-12** by the F2 sprint (see
  top-of-file 2026-05-12 entry): F-new-2/27 multi-token endpoint
  resolution (`964d088`), F-new-7 EXT-A per-key batching (`058ca15`),
  F-new-7 EXT-B imp-id-correlation (`de9256a`), F-new-34
  naming_form_resolution (`5cc1471`). SKILL bumped 0.5.0 → 1.0.0.

---

## [adapter_spec_version 1.3.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.2.0] — 2026-05-05 (D3.8 operator validation complete)

Phase D3.8 — port-java2go SKILL exercised end-to-end against all 6 MVP
pairs (`kobler`, `aax`, `adkernelAdn`, `adverxo`, `vungle`,
`thetradedesk`) via 7 canary runs. Trajectory: `5 clean / 2 after-fix /
2 FAIL` (canary 1) → 3 consecutive `10 clean / 0 / 0` (canaries 5-7);
final canary cleared D3.3 gate 3's 80% coverage threshold (81.4%). All
6 MVPs demonstrably portable.

`port-java2go` SKILL frontmatter bumped 0.3.0 → **0.5.0** (status
banner updated; v1.0.0 promotion criteria enumerated). NOT YET v1.0.0;
4 HIGH-priority promotion blockers tracked in canary 7 trace.

### Added — port_engine helpers (Phase 1)

- `port_engine.exemplary_fixture_assemble_java_to_go(*, ...)` — assembles
  exemplary-fixture.json.j2 ctx from a Java IT 4-file fixture set;
  absorbs F-new-9 (cur fallback), F-new-10 (TEST_ENDPOINT constant),
  F-new-11 (expected_bids from bid-response), F-new-13 (passthrough
  body simulator hook). Includes `inject_empty_user_if_missing` opt-in
  for vungle-shaped User-deref bidders (F-new-22).
- `port_engine.simulate_makerequests_mutations(bid_request, mutations)` —
  applies sequence of MakeRequests mutation ops; 15 op kinds covering
  Device/User/Imp/Site/App rewrite patterns observed across the corpus
  (kobler IP/UA/User zeroing, vungle Site→App synthesis, adkernelAdn
  publisher-null + format-fill, etc.).
- `port_engine.imp_ext_shape_transform_java_to_go(fixture_dict,
  java_bidder_name)` — Rule 36 inverse imp.ext slot rewrite (F4 from
  canary 1).
- `port_engine.TEST_ENDPOINT` constant — single source of truth for
  bidder-test.go.j2's Builder URI + expectedRequest.uri across renderer
  + tests.

### Added — port-java2go template extensions (Stage A + B + Phase 2)

- `bidder.go.j2` — unified `getBidType` body (B1: 4 new branches —
  constant-{banner,video,audio,native}, by-bid-mtype, by-bid-ext-typed-field
  single-step, method-chain-fallback). Currency-conversion helper
  emission gated on `uses_currency_conversion` (B2). Custom-headers
  list-driven via `custom_headers` ctx (B3). `imp_ext_unmarshal_kind=none`
  branch skips parseImpExt entirely (F-new-1; aax+optidigital pattern).
  `legacy_raw_status_handlers` schema for per-status error emission
  (F-new-14; aax shape).
- `bidder-info.yaml.j2` — `gvlVendorID` omitted when 0 (F9; matches Go
  upstream convention).
- `bidder-test.go.j2` — hardcoded `TestJsonSamples` function name (F10;
  100% of merged Go adapter PRs).
- `exemplary-fixture.json.j2` — `expectedRequest.impIDs` emit (F-new-12;
  required by adapterstest framework).
- `supplemental-fixture.json.j2` (NEW) — kobler-shape-agnostic
  supplemental-fixture template with 5 scenario kinds (status-204,
  status-400, status-404, no-response-body, malformed-body); gated on
  `http_status_kind` for canonical-helpers vs legacy-raw-go behavior
  (F-new-23).

### Fixed — reviewer follow-ups

- `port_engine._apply_device_zero_fields` uses `del` (mirroring Go's
  omitempty wire form) instead of `=""` (which would emit empty-string
  keys diverging from upstream Go's marshal output; reviewer H4).
- `port_engine._apply_imp_tagid_from_ext` accepts explicit `slot_name`
  param to disambiguate when imp-ext-rewrap installs duplicate content
  under multiple slots (reviewer H5; back-compat first-match heuristic
  preserved).
- Kobler IT 4-file fixture set committed to
  `scripts/tests/fixtures/kobler-it/` so the canary regression test
  (`test_kobler_shape_passthrough`) actually runs in CI rather than
  silent-skipping (reviewer H1). `PREBID_SERVER_JAVA_CLONE` env var
  opts into reading from a live Java clone.
- `bidder.go.j2` method-chain branch emits a terminal catchall return
  after the chain unconditionally (reviewer H2; previously
  non-terminating Go function for all-`next` chains). Mid-chain
  `fallback_action: throw` no longer emits unreachable terminating
  return — only the LAST step's fallback emits (reviewer H3).
- `bidder.go.j2` docstring `bid_type_resolution` enum no longer lists
  `ext-prebid-video-placement` — orphan value with no template branch
  and no audit-pair usage (reviewer H6).

### Added — D3.8 traces

- 7 canary findings docs at `docs/runs/d3.8-*-canary-*.md`
- Cross-language pairs corpus audit at
  `docs/runs/d3.8-template-coverage-audit.md`
- Pre-canary spike at `docs/runs/d3.8-mvp-pairs-spike-2026-05-05.md`

Test suite: 346 → 480+ passing across the D3.8 series (~134 new tests
including 18 fixture-assemble + 33 mutation-simulator + 9 supplemental-
fixture + 13 unified-getBidType + render tests for B2/B3/F-new-1/F-new-14
plus reviewer regression tests for H2/H3/H4/H5).

---

## [adapter_spec_version 1.3.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.2.0] — 2026-05-04 (engineering complete)

Phase D engineering layer complete. D0 + D1 set up the port-skill
prerequisites (R5 lib, port-engine helpers, schemas, emission refs);
D2 + D3 ship the SKILL pipeline prose and all 17 Jinja templates
across both directions (Go→Java and Java→Go); D4 lands the CI
integration (port-side R4 round-trip framework, coverage-report
extension, mvn checkstyle dry-run helper). Operator-side validation
against the 6 MVP pairs (D2.8 / D3.8) and the beachfront ADR-007 F1
master fixture (D4.4) remain.

### Added — port skill engineering layer (D0-D4)

- `scripts/lib/r5_check.py` — comparator-neutral R5 comparator
  (`compare_pair`, `aggregate_state`, `R5Diagnostic`, `R5Result`,
  `SpecView` protocol). Harness re-exports preserve test_round_trip_ci.py
  imports.
- `scripts/lib/port_engine.py` — 10 mechanical helpers consumed by both
  port skills: `byte_copy`, `normalize_bidder_name`, `alias_graph_invert`,
  `iab_table_translate`, `r5_check_at_port_time`, `port_report_emit`,
  `alphabetical_insert`, `prefix_uniqueness_check`, `gofmt_post_process`,
  `mvn_checkstyle_dry_run`.
- Two skill directories with full pipeline prose:
  `prebid-server-java/port-go2java/SKILL.md` (Go→Java; v0.3.0) and
  `prebid-server-go/port-java2go/SKILL.md` (Java→Go; v0.3.0).
- 11 Java-target Jinja templates at
  `prebid-server-java/port-go2java/templates/`: bidder-config.yaml,
  ext-imp-pojo.java, configuration.java, configuration-properties.java,
  bidder.java, bidder-test.java, it-test.java, plus 4 IT fixture JSONs.
- 6 Go-target Jinja templates at
  `prebid-server-go/port-java2go/templates/`: bidder-info.yaml,
  imp-ext-pojo.go, bidder-test.go, params-test.go, exemplary-fixture.json,
  bidder.go.
- 11 emission reference docs across both port skills'
  `references/` directories + a shared
  `prebid-server-go/read/skills/shared/bidder-constant-table.yaml`
  (271 entries; 84 non-mechanical) refreshed to v4 module path post
  upstream PR #4710 (resolved_commit `2fae16f31693`).

### Added — schema bumps + CI extensions

- **adapter_spec_version 1.3.0** (additive): optional
  `cross_language.java_artifacts.bidder_params_path` for the rare
  bidders whose Java upstream filename diverges from the lowercase
  bidder name (adkerneladn → adkernelAdn.json camelCase; emxdigital →
  emx_digital.json snake_case).
- **port_report_version 0.2.0** (additive): PR-shape automation
  (5 fields including `companion_docs_pr_draft` and `pre_submit_rebase`
  with declarative if/then constraint), source provenance (3 fields),
  fidelity tracking (`re_authored_paragraphs[]`),
  `r5_check.state` enum extended 4 → 6 values (warn-target-strengthens-
  source, fail-source-omits-target-constraint).
- `port_report_version` promoted to first-class versioned artifact
  (4th alongside the original three) per
  `docs/methodology/schema-versioning.md` revision.
- `scripts/round-trip-ci.py` R11 port-side round-trip determinism gate
  (consults `port-translation-rules.yaml` Round-Trip Safety table for
  lossy-direction filtering).
- `scripts/coverage-report.py` §7b per-rule applied-count from
  port-report.json archives.
- **Beachfront cross-language pair fixture** (D4.4) at
  `prebid-server-{go,java}/read/test-fixtures/beachfront.golden.spec.yaml`
  + `cross-language-pairs/beachfront.dual-spec-assertions.yaml`. Master
  sample for THREE load-bearing patterns: ADR-007 F1
  multi-endpoint-by-mediatype (banner endpoint vs video endpoint per
  mediatype), Rule 35 typed-config-subclass (Java
  `BeachfrontConfigurationProperties` with `@NotBlank private String
  videoEndpoint` vs Go opaque `ExtraAdapterInfo` JSON string), and
  Rule 9 parameterized-request-type (Java `Bidder<Void>` + custom
  request bodies). Dual-spec assertions document 2 expected R5 WARNs
  (bidder-params byte-only-whitespace divergence; endpoint_construction
  encoding divergence by ADR-007 F1 design); no port-fidelity FAILs.
  Corpus expanded 40 → 42 goldens; 16 → 17 dual-specs.

### Added — review iteration scaffolding

- `scripts/tests/test_port_e2e_fixtures.py` — fixture-driven render
  tests using real `kobler.golden.spec.yaml` source rather than
  hand-rolled synthetic contexts; closes the gap where per-template
  tests proved "template renders given pre-cooked ctx" but not
  "SKILL → context → template is consistent".
- `TestPortReportV020Invariants` in test_schema_jsonschema.py — 8
  cases pinning the M-D schema tightenings (if/then constraint, SHA
  pattern, six-state enum) so they can't regress silently.
- `TestModuleVersionTableSync` cross-checks the test-suite
  `GO_MODULE_VERSION` constant against the bidder-constant-table's
  `module_version` pin so a future v5 bump fires a test until the
  test constant updates accordingly.

### Driving ADRs / methodology

- `docs/methodology/port-skills-design.md` §3-§7 — pipeline contract.
- `docs/execution-plan-phase-d.md` — D0-D4 sub-phase breakdown +
  per-pair acceptance gates.
- `docs/methodology/end-to-end-flow.md` — Teal flow handoff convention.
- `docs/methodology/repo-rules.md` — upstream snapshot pin
  re-verified 2026-05-04 (Go HEAD `2fae16f31693`, Java HEAD
  `a1fe64e123d6`); in-flight upstream PR #4126 tracked.

---

## [adapter_spec_version 1.3.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.2.0] — 2026-05-04 (initial)

Phase D scaffolding — port skill prerequisites land. D0 lifted the R5
cross-language equivalence comparator to `scripts/lib/r5_check.py` so
the upcoming `port-go2java` / `port-java2go` skills can compute R5 from
the same source of truth as the harness; D0.2 cleared 16 of 17
sync-from-upstream drifts (single false-positive remains as data-only
WARN); D1.4 bumps the port-report contract to 0.2.0 with PR-shape
automation, source provenance, and fidelity tracking. All existing
goldens and 0.1.0-shape port reports continue to validate.

### `adapter_spec_version` 1.2.0 → 1.3.0 (MINOR; additive)

`cross_language.java_artifacts.bidder_params_path` (string|null,
optional) — overrides the upstream bidder-params JSON path when the
Java filename diverges from the lowercase bidder name. Two known
divergences populated:

- `adkerneladn` → `adkernelAdn.json` (camelCase; lowercase variant 404s)
- `emxdigital` → `emx_digital.json` (snake_case)

Goldens without the override fall through to the default lowercase path
construction. `scripts/sync-from-upstream.py compare_bidder_java()`
honors the override.

### `port_report_version` 0.1.0 → 0.2.0 (MINOR; additive)

PR-shape automation cluster (5 fields):
- `recommended_pr_title` — Java-target convention `Port {Bidder}: New Adapter` per upstream porting-guide; Go-target convention `New Adapter: {Bidder}` per real-PR audit (capital A).
- `target_pr_label_recommendations[]` — Java-target default `["do not port"]`; Go-target default `[]`.
- `companion_docs_pr_draft` — draft `prebid/prebid.github.io` adapter-docs page (maintainer-mandatory for Java-target; expected-for-parity on Go-target).
- `pre_submit_rebase` — captures the rebase outcome (master HEAD at emit vs at submit, conflicts detected/summary) so Phase F can correlate post-merge surprises with upstream framework drift.
- `upstream_bugs_to_file[]` — Connatix-style "found a bug while porting" (target_repo, summary, severity ∈ {fidelity-violation, schema-mismatch, documentation-gap, other}, evidence_path).

Source provenance cluster (3 fields):
- `source_pr_url` — GitHub URL of the upstream PR that landed the source-side adapter.
- `source_pr_merged_commit_sha` — 40-hex of the merge commit (anchors port to a specific upstream snapshot for cross-version replay).
- `source_discussion_anchors[]` — load-bearing review-comment / commit / issue links that informed port decisions (per Wave-5 review-pattern audit).

Fidelity tracking (1 field):
- `re_authored_paragraphs[]` — sections re-authored as semantic-coverage parity rather than 1:1 byte-translation (Rule 36 reframing).

`r5_check.state` enum extended (4 → 6 values):
- `warn-target-strengthens-source` — target carries a constraint absent in source (Connatix-style: Java has minimum/maximum that Go lacks; port preserves the constraint).
- `fail-source-omits-target-constraint` — source lacks a constraint the target language requires; port cannot emit a valid target without operator intervention (aax-style; surfaces in `human_todos[]` for upstream confirmation).

`human_todos[].category` enum extended: `style-violation` admitted (for D4.3 pre-submit checkstyle dry-run findings).

### Added (Phase D scaffolding outside the schemas)

- `scripts/lib/r5_check.py` (533 lines) — comparator-neutral R5 library exposed via `compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result` and `aggregate_state(diagnostics, pair_present) -> (state, byte_equal, warn, fail)`. Duck-typed `SpecView` so existing harness `Spec` is untouched; `R5Diagnostic` is comparator-neutral so callers wrap to `Finding` (harness) or schema dict (port skill). The harness re-exports `R5_STRICT_KEYS`, `R5_FORM_DIVERGENT_KEYS`, `R5_ADVISORY_DIVERGENT_KEYS`, `deep_eq`, `_list_set_eq`, `_maintainer_eq`, `normalize_endpoint_macros` for backward-compatibility with `scripts/tests/test_round_trip_ci.py`.
- `scripts/tests/test_r5_check.py` (357 lines, 34 tests) — lib-level callable contract tests covering pass / warn / fail scenarios, `SpecView` duck typing, helper edge cases, and the four-state `aggregate_state` reduction.

### Updated (drift detector + repo-rules snapshot)

- `scripts/sync-from-upstream.py` — `userSync` admitted in known-keys allowlist; `bidder_config_missing` is now alias-aware; `bidder_params_path` override honored. Drift output went 17 fail / 1 warn → 0 fail / 1 warn (real adkernel `endpoint_compression` data-only drift parked for operator ack).
- `docs/methodology/repo-rules.md` — re-verified dates bumped to 2026-05-04. Two new subsections: "In-flight upstream changes" (currently tracking `prebid/prebid-server-java#4126` URL validation, OPEN; D2/D3 pre-submit rebase MUST verify post-rebase emission still compiles) and "Known data-only drifts" (`adkernel` `endpoint_compression`).

### Driving ADRs / methodology

- `docs/methodology/port-skills-design.md` §7 — R5-strict check at port time consumes `scripts/lib/r5_check.compare_pair`; updated to reflect the now-completed D0.1 refactor.
- `docs/decisions/004-rule-45-disabled-by-default-java-alias.md` — `R5_DIVERGENT_KEYS` reference path corrected to `scripts/lib/r5_check.py`.
- `docs/methodology/schema-versioning.md` MINOR criteria — both bumps satisfy: additive only, no new required fields, no enum value removals (only additions), no type changes on existing fields.

---

## [adapter_spec_version 1.2.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.1.0] — 2026-05-03

Wave 11b / Phase 2.8 — schema closure + gate enforcement reality alignment.
Closes 17 accidentally-open `additionalProperties: true` sites that were
Phase 2.0/2.4/2.7 punts; lifts 4 top-level open-maps to structured `$defs`;
closes 8 round-2 sweep sites under `code.*` and `cross_language.*`;
tightens R5/R8/R3/Rule-33 enforcement; deletes redundant Rule 38 lint
check; replaces the leaf-key phantom-path escape with path-aware
vocabulary lookup.

All 40 existing goldens continue to validate against the tightened schema.
Per `docs/methodology/schema-versioning.md` MINOR criteria (clarified in
this wave to explicitly cover closure-as-MINOR), no MAJOR bump required.

### Added (schema $defs — Wave 11b B3 + B3+)

22 new `$defs` total. Top-level lift-to-$defs replacing Tier C open-maps:

- `SpringConfig` (was top-level `spring_config` open-map; declares
  factory_class, factory_method, property_source_path,
  bidder_creator_lambda, configuration_properties_class, bean_dependencies,
  factory_class_package, notes).
- `BidderClass` (was top-level `bidder_class`; declares name, parameterized
  request/response types, override_methods, constructor, static_fields,
  helper_classes_co_located/in_proto/in_model, notes).
- `CodeNaming` (was top-level `code_naming`; declares class_name_root,
  yaml_name, preserves_acronym_case, identifier_workaround, package_name,
  notes).
- `Lifecycle` (was top-level `lifecycle`; restructured per round-1 finding
  that 14 keys nest under `lifecycle.rename`, not at lifecycle top-level).
- Plus nested children: `ConfigurationPropertiesClass`,
  `ConfigurationPropertyField`, `ConfigurationPropertyNestedClass`,
  `ConfigurationPropertyNestedClassField`, `BeanDependency`,
  `BidderClassConstructor`, `BidderClassConstructorParameter`,
  `BidderClassStaticField`, `LifecycleRename`, `LifecycleMove`.

Round-2 sweep additions (B3+) under `code.*` and `cross_language.*`:

- `CodeImports` (4 keys: has_currency_helper, has_jsonutil,
  has_template_engine, third_party).
- `AdapterStruct` (3 keys + nested fields[] items).
- `CodeBuilder` (4 keys + errors_returned[] items as oneOf string|object).
- `MakeRequests` (6 sub-objects + helpers[] with name/signature item shape).
- `MakeBids` (8 universal + notes_currency + helpers[] for parity).
- `GoArtifacts` (3 universal + 9 per-bidder file-path artifacts).
- `JavaArtifacts` (5 universal + declared_in for huaweiads).
- `PortConcerns` (6 universal booleans).

### Changed (schema closures — Wave 11b B1 + B2)

Tier A (B1) — flipped `additionalProperties: true → false` at 6
zero-extra sites: `Code`, `code.file_layout.files[]` items,
`headers_constructed.custom_headers[]` items, `aliases[].test_assets`,
`aliases[].test_application_properties_entries[]` items, `CrossLanguage`
top-level. `Code` description updated to past-tense closure note.

Tier B (B2) — additive closures at 9 sites with property additions:
`code.file_layout` (+ file_count_total, notes from huaweiads), `Tests`
(+ test_application_properties_keys), `IabCategoryStorage` (+ notes),
`ExtPojoConstruction.custom_unmarshal` (+ notes), `HeadersConstructed`
(+ authentication_algorithm, authentication_output_encoding, notes),
`DeployTimeToken` (+ file, line, on_alias as STRING [plan corrected
from "boolean"], notes as oneOf string|array per dual emitter shape),
`Quirk` (+ line). Plus Provenance.warnings/items + language_stamped_headers/items
flipped directly.

Plan correction: `on_alias` is `string-or-null` (alias name like
"appStockSSP"), not `boolean-or-null` as plan said. teqblaze's `note:`
also renamed to `notes:` (corpus normalization; both teqblaze and rubicon
prose are golden-author commentary, not upstream Java quotes).

### Tightened (Wave 11b B4)

- `if/then` invariants: Go specs now require `code_naming: null` and
  `registry: null` (in addition to spring_config/bidder_class). Java
  alias specs (`meta.is_alias: true`) now require `spring_config: null`
  and `bidder_class: null` (152media-Java's existing values confirmed).
- Port_lineage shared-genesis invariant DEFERRED to Wave 11c C4
  (freewheelssp-Java's `destination_language: null` is captured as
  ADR-007 F2 contradicted exemplar; tightening would unilaterally
  invalidate that evidence).

### Tightened (Wave 11b B4 — failure-swallow fixes)

- `round-trip-ci.py` R1 network probe: `gh_path_exists` refactored to
  raise `GhApiUnreachable` on auth/rate-limit/network failures (Wave 10
  recipe propagated). Top-level handler in `main()` exits 3 with
  diagnostic. Fixes the same false-FAIL-flood class as audit-golden.py.
- `lint-port-rules.py:discover_pairs`: returns `(pairs, errors)` tuple;
  raises FileNotFoundError on missing fixtures dirs; emits Finding(
  rule_id=0, severity="fail") on YAML/IO load errors instead of
  swallowing or crashing.
- `coverage-report.py:discover_dual_specs`: scoped Exception catch to
  `(OSError, yaml.YAMLError)`; prints WARN to stderr and skips broken
  files instead of inserting `_parse_error` sentinel data.
- Renderer `consumed_keys` assertions: `render-taxonomy.py` and
  `render-port-rules.py` now raise ValueError on unrecognized YAML keys,
  catching the silent-drop class of bug. Each has injection regression
  test.

### R5 split (Wave 11b B4 C1 + B5 #2)

R5 divergent-keys bucket split into:
- `R5_FORM_DIVERGENT_KEYS` — endpoint URLs only. New
  `normalize_endpoint_macros()` canonicalizes Go `{{.X}}`, Java `${X}`,
  Spring EL `#{X}`, raw `{{X}}` to single `{{X}}` form. After
  normalization: deep_eq. Absence of dual-spec assertion when normalized
  values differ → FAIL `assertion_missing` (Wave 11b strictness).
- `R5_ADVISORY_DIVERGENT_KEYS` — endpoint_construction, default_enabled,
  alias_metadata, port_lineage, lifecycle_rename, reviewer_cohort,
  test_fixture_cost (preserved current behavior; documentation-only).

`R5_STRICT_KEYS` refactored from flat (spec_field, dual_key) tuples to
(spec_field, dual_key, comparator) three-tuples with per-key comparator
selection: `_list_set_eq` for 4 LIST-VALUED keys (capabilities, geoscope,
schema_interpretation.{required_fields, combinators_used,
flexible_types}); `_maintainer_eq` for the 1 PROSE-BEARING key
(maintainer.email-only); `deep_eq` for 4 PURE-DATA scalars.

Prerequisite corpus edit: aax dual-spec gained `bidder_info_endpoint`
assertion (severity:warn) documenting Java's
`?src={{PREBID_SERVER_ENDPOINT}}` extension.

### R8 expansion (Wave 11b B5 #7)

R8 endpoint-placeholder walker expanded from single-field
(`bidder_info.endpoint`) to multi-path collector covering user-sync URLs
(iframe/redirect.url + uid_macro + flat forms), `bidder_class.static_fields[*].value`,
plus the original endpoint. New macro registries:

- `USER_SYNC_MACROS` — admitted on user_sync paths. Both Go PascalCase
  and Java snake_case forms (GDPR/gdpr, GDPRConsent/gdpr_consent,
  USPrivacy/us_privacy, GPP/gpp, GPPSID/gpp_sid, RedirectURL/redirect_url,
  BidderName/bidder, UID/uid).
- `OPENRTB_MACROS` — universal. AUCTION_PRICE, AUCTION_BID_ID, etc. per
  OpenRTB 2.5 §4.1.

16 new R8 WARNs surface for bidder-specific identifiers (TokenID,
SourceId, SupplyId, etc.) — legitimate signals for documentation, not
breaking changes.

### Removed (Wave 11b B5 #8)

- `rule_38_bidder_params_byte_fidelity` deleted from `lint-port-rules.py`.
  Redundant with R5's dual-spec-aware byte-divergence reporting; emitted
  13/14 pairs as warn with no actionable distinction. The Rule 38
  PRINCIPLE remains documented in `port-translation-rules.md:45-77` as
  a load-bearing port-translation rule; the runtime gate is R5.

### Promoted (Wave 11b B5 #8)

- Rule 33 (alias-graph inversion) promoted from `warn` to `fail`
  severity. 0 active warns across corpus; promotion turns alias-graph
  inversions into hard CI gates.

### Path-aware phantom detection (Wave 11b B5 #1)

`test_schema_jsonschema.py:test_no_truly_invented_keys_outside_open_maps`
rewritten to use path-aware vocabulary. New module-level helper
`_build_declared_at(schema)` returns `(declared_at, open_maps)`.
Replaces the prior leaf-key escape that admitted ANY key whose name
appeared anywhere in any `$defs.*.properties`. Closes Gap #2 (paths
like `code.builder.request_body` no longer slip through because
`request_body` is declared at `code.make_requests`, not `code.builder`).

### R3 strict-mode flipped default-on (Wave 11b B5 #3)

`--strict-r3` produced 40 PASS / 0 WARN / 0 FAIL across corpus; safe
to default-on. `--lenient-r3` opt-out preserves prior advisory mode for
contributors who deliberately under-document quirks.

### Doc-count regex extension (Wave 11b B5 #5)

`test_doc_count_claims.py` DISCOVERY_REGEX gained
`(?:java\s+)?(?:alias-)?empire\s+parents` alternation; canonical from
`coverage-report.py:INVENTORY_TOTALS["java_empire_parents"]`. Three
plan-recipe phrases ("N goldens", "N reference PRs", "N fixtures")
deferred — corpus uses each ambiguously.

### Counts

- Open-map prefixes: 28 → 11 (4 EXTENSION-SLOTS + 7 LEGITIMATELY-OPEN
  remain by design; Wave 11c may close 3 corpus-coupled sites).
- Accidentally-open sites: 17 → 0 (plus 8 round-2 sweep additions = 25
  total closures landed).
- Schema $defs: +22 new (12 → 34).
- Test count: 115 → 125 (+10 new across 7 commits).
- Wave 11b commits: 16 (1 plan + 15 implementation).

### Goldens posture

40 existing goldens stay at `adapter_spec_version: "1.0.0"`; they all
validate against the 1.2.0-tightened schema. Future fixtures using the
post-closure structure should declare `adapter_spec_version: "1.2.0"`.

### Goldens stock-validator compatibility (post-review fix)

Reviewer feedback flagged that direct JSON Schema validation of the
goldens with a stock validator failed 40/40: `provenance.read.timestamp_utc`
in every golden was an unquoted ISO datetime (YAML auto-parses to a
Python datetime), and the schema declares it as `"type": "string"`.
The CI's prior `_normalize()` step rewrote datetimes to ISO strings
before validation — papering over a real interoperability issue.

Fix: 42 surgical edits across the 40-golden corpus quote the affected
date/datetime values (`provenance.read.timestamp_utc` × 40 +
`lifecycle.rename.merged_at` × 2 elementaltv occurrences). The
`_normalize()` test crutch is removed, hardening the test against
future unquoted-date regressions. New regression test
`test_stock_yaml_load_emits_strings_for_date_fields` asserts every
golden's date fields parse as strings via stock `yaml.safe_load` —
catching the regression before any downstream consumer sees it.

External consumers can now use any stock JSON Schema 2020-12 validator
(jsonschema, ajv, etc.) directly against the goldens without a
preprocessing step.

### Unchanged

`taxonomy_version` stays at `1.0.0` (no behavior-taxonomy changes);
`port_translation_rules_version` stays at `0.2.0` (Rule 38 lint deletion
doesn't change rule taxonomy — Rule 38 the principle is preserved in
the rules YAML).

### Driving ADRs / methodology

- ADR-001 D5 (lifecycle.rename schema)
- ADR-001 D7 (SemVer string format)
- ADR-007 (novel-pattern schema additions; status flipped to "Partially
  implemented in Phase 2.8 / Wave 11b" with port_lineage shared-genesis
  invariant deferred to Wave 11c)
- `docs/methodology/schema-versioning.md` (closure-as-MINOR clarification
  added)

### Wave 11c (FUTURE PR — separate from this one)

Corpus-coupled decisions deferred:
- C1: Alias canonical name field (`bidder_name` vs `name`).
- C2: `tests.fixture_inventory` typed-values closure.
- C3: `registry` migration to `tests.test_application_properties.*`.
- C4: `cross_language.port_lineage` shared-genesis canonical encoding
  (NEW — moved from Wave 11b's B4 C5 to avoid contradicting ADR-007
  F2 freewheelssp exemplar; needs ADR amendment).

---

## [adapter_spec_version 1.1.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.1.0] — 2026-05-03

ADR-007 (novel-pattern schema additions): F1, F3, F4, F5 admitted to the schema
as `$defs`. NOT `$ref`-wired into top-level `Code` yet — adapter_spec_version
1.1.0 admits the new shapes via the existing `Code` / `Code.make_requests` /
`Code.make_bids` open-map permissiveness (`additionalProperties: true`); Phase 2.8
will tighten and wire. ADR-007 status flipped Proposed → Accepted (2026-05-03).
F2 (`language_stamped_headers`) was already shipped; this release rounds out the
remaining four ADR-007 patterns.

### Added (schema)

- `EndpointResolution` `$def` — admits multi-endpoint adapters (F1; master
  sample beachfront with banner + video endpoints). `kind` enum includes the
  pre-existing 9 single-endpoint forms plus the new `multi-endpoint-by-mediatype`
  and `multi-endpoint-by-shape`. New `endpoints[]` array carries
  `{ name, role, value, mechanism }` per dispatch target; ordering is logical
  (declaration), not lex-sorted, per the ADR-007 array ordering policy.
- `EntityStrategy` `$def` — admits the
  `Site=replace-with-app-synthesis` / `App=synthesize-app-replacement` pattern
  (F3; master sample vungle). Each Site/App/User slot independently typed with
  the union of currently-emitted golden values plus the F3 additions
  (`replace-with-app-synthesis`, `synthesize-app-replacement`,
  `synthesize-from-site`).
- `BidPostProcessing` `$def` — admits post-decode macro replacement on bid
  fields (F4; master sample thetradedesk AUCTION_PRICE substitution into
  `bid.NURL`/`bid.AdM`/`bid.BURL`). `macros[]` array carries
  `{ macro, fields[], source, mechanism }` per substitution.
- `ImpExtUnmarshal` `$def` — admits the `strip_post_extraction: bool` flag (F5;
  master sample beintoo zeroes out `imp.Ext` after parsing). `kind` enum
  includes the currently-emitted golden values (`none`, `standard-two-phase`)
  plus forward-looking variants (`shared-prebid-imp`, `custom-typed`,
  `passthrough`) reserved for Phase 2.8.

### Changed (schema prose)

- Top-level `description` updated to reflect post-Phase-5 reality (40 goldens
  validated; was "Phase 2.0 milestone: covers the kobler-Go and kobler-Java
  goldens" + "Phase 2.1 will expand to cover all 22 goldens").
- `adapter_spec_version` field `description` updated to mention the 1.0.0/1.1.0
  semantics and the not-yet-`$ref`-wired posture of the new `$defs` (was
  "all 22 goldens migrated to '1.0.0'").

### Goldens posture

The 40 existing goldens stay at `adapter_spec_version: "1.0.0"`; none reference
the new patterns at the pinned upstream commits. Future fixtures using F1/F3/F4/F5
shapes will declare `adapter_spec_version: "1.1.0"`. Both versions are admitted
because `Code` is an open map; strict per-shape validation is deferred to Phase 2.8
(when `$ref` wiring lands).

### Unchanged

`taxonomy_version` stays at `1.0.0` (no behavior-taxonomy changes); `port_translation_rules_version`
stays at `0.2.0` (no rule additions or semantic changes).

---

## Unreleased — Process / tooling hardening (no version bump) — 2026-05-03

Out-of-SemVer-perimeter changes per `docs/methodology/schema-versioning.md` —
ADR text refinements, Python data-table updates, CI gate hardening, drift
cleanup, doc-count gates, file-role enum alignment, framework-utilities SHA
pin, and ADR status flips. No SemVer bump on schema, taxonomy, or port-rules
artifacts; no migration script required.

Two distinct origins of work in this section:

1. **Phase 5 fixture-authoring empirical evidence** (commits `d9742a7`
   vungle, `3523009` cadent/emxdigital, `f11b2ba` freewheelssp, `ea0a37a`
   thetradedesk) plus follow-up empirical verification of all 7 lifecycle
   pairs — drove the ADR-005/006/007/008 refinements + tooling updates
   below.
2. **PR #1 hardening waves 1, 2, 4, 5, 6, 7, 9a** (commits `859feff` →
   `e91970f`) — drove the CI gates / drift cleanup / Java SKILL alignment /
   cross-language port infrastructure / doc-count gate / ADR status-flip
   sub-sections below.

The Wave 8 forward-looking design landed under a separate Unreleased
section below, since design-only contracts for future phases are a distinct
genre from process/tooling housekeeping.

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

### CI gates (Waves 1 + 6)

- **Wave 1 (`859feff`)** — exit-code wrapper inversion fixed across
  `Makefile:35,38`, `.github/workflows/round-trip-ci.yml:88,96`,
  `.github/workflows/upstream-sync.yml:49`. Prior wrappers used `[ -le 2 ]`
  which silently masked exit-1 (real fail) as success; replaced with
  `[ -eq 0 ] || [ -eq 2 ]`. Plus wrapped previously-unwrapped
  `audit-golden.py` invocations and dropped daily-drift-causing
  `date.today().isoformat()` from `coverage-report.py:427`. Plus R5 design
  fix: decomposed `params.schema_interpretation` from a whole-block
  `deep_eq` strict-key into three runtime-invariant sub-fields
  (`required_fields, combinators_used, flexible_types`) — the prose-bearing
  `properties[].notes`/`description` fields legitimately differ across
  languages and were causing false `stale-pass` FAILs (canonical: thetradedesk).
- **Wave 6 (`aacc8d0`)** — added `scripts/tests/test_doc_count_claims.py`
  drift gate watching live count claims (rule count, enumeration count) in
  5 doc sites, catching the kind of drift that surfaced as "12 enumerated
  behavioral fields" stale claim in `cross-skill-integration.md` (canonical:
  15). Wave 9b generalized this into a discovery-based gate.

### Drift cleanup (Waves 2 + 9a)

- **Wave 2 (`601d917`)** — finished the `iab_category_storage.injection`
  → `delivery_mechanism` rename (Wave 2 ripple-finish for ADR-001 D2):
  `port-translation-rules.yaml` Rule 42 + 5 SKILL/reference sites.
  `cross-skill-integration.md:327` count fix 12 → 15 enumerated fields.
  README rule count 43 → 46. Dropped 146 lines of dead code from
  `test_schema_contract.py` (the `_DEPRECATED_PRE_PHASE_2_3_EXTRAS` block
  + `SCHEMA_REGISTRY_EXTRAS` empty placeholder; both unused since Phase 2.3
  derived the registry from `adapter-spec.schema.json` `$defs`).
- **Wave 9a (`e91970f`)** — pre-review polish pass after comprehensive
  audit. ~25 stale claims and Wave 2/4/7 incomplete ripples corrected:
  ADR README index 8 status flips (Wave 7 missed the meta-table), ADR-001
  D5 `rename_subtype` → `subtype`, ADR-005 "12 verified pairs" → "11"
  (internal contradiction), Java SKILL test-unit/test-it parenthetical
  drops (Wave 4 miss), Go reference doc `injection: static-init` →
  `delivery_mechanism: static-init` (Wave 2 miss),
  `adapter_spec_version: 1` integer-literal → `"1.0.0"` (Java orchestrator
  + pr-triage manifest), 22 → 40 goldens / 7 → 16 pairs / 89-90 → 92 PR
  count corrections, dropped hardcoded "22 taxa" counts, two read SKILLs
  gained ADR-007 F2 (`language_stamped_headers[]`) population
  instructions, test-fixtures READMEs (Go + Java) updated 12/10 → 21/19
  with Phase 5 row additions, cross-language-pairs README updated 7 → 16
  pairs (aax + elementaltv now show "yes" Go fixture per Wave 5).

### Java SKILL alignment (Wave 4)

- **Wave 4 (`41f3a77`)** — fixed a SKILL-vs-goldens contradiction at
  `read-bidder-class/SKILL.md:72`: the documented file-role enum was
  `bidder, configuration, configuration-properties, proto-ext,
  proto-helper, deserializer, test-unit, test-it` (8 values) but ALL 19
  Java goldens emit `implementation, models, parsers, types, utils`
  (5 values, zero overlap). Aligned SKILL to reality. Authored
  `references/file-role-heuristics.md` (Java mirror of Go's heuristics
  doc) + `scripts/lib/lint-java-roles.py` gating the enum at CI
  (`--include-go` flag covers Go's 6-value variant).

### Cross-language port infrastructure (Wave 5)

- **Wave 5 (`efa3de6`)** — re-derived `aax` and `elementaltv` dual-spec
  assertions: `go_spec: null` → real fixture path, dropped obsolete
  `note_on_specs` blocks (Go fixtures DO exist post-2026-05-02). Added
  `prior_source_spec` slot to pr-triage SKILL for cross-language port-
  fidelity comparison (canonical case: Go-PR vs Java-source spec). Added
  `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` convention for the
  one-shot Teal-flow orchestration (gitignored). Pinned
  `framework-utilities.md` 4 sites from `Verified at v4.1.0` to canonical
  Phase 5 SHA `2fae16f31693452b62dd2a0924b78e71bbec43ec`.

### ADR status flips (Wave 7)

- **Wave 7 (`a69812b`)** — flipped 8 ADRs `Proposed` → `Accepted` in their
  per-ADR files (ADR-001 was schema-migration-driven → `adapter_spec_version
  1.0.0` shipped; ADR-002 → Phase 1.4/1.5 corrections applied; ADR-003/4/5
  → Rules 44/45/46 in port-translation-rules.yaml; ADR-006 →
  `lifecycle.rename.subtype` 5-value enum shipped; ADR-008 → Phase 5 corpus
  complete at 9/9). Plus past-tense rewrite of ADR-002's 8 future-tense
  decision-narrative lines. Plus Java aliases mechanism correction in
  `prebid-server-java/references/new-bid-adapter-prs.md:182`
  (`aliasOf:` field claim → `aliases: { <child>: ~ }` parent-side block
  with explicit Go-vs-Java inversion note). The Wave 7 commit missed
  flipping the meta-table at `docs/decisions/README.md`; Wave 9a
  corrected that.

### Acknowledgments

- Per `docs/methodology/rollback.md:54-57`, ADR corrections used in-place
  edits with "Refined 2026-05-03" date stamps (matching ADR-006 line 3's
  existing "audit A5" precedent). Original `Refined 2026-05-02` date stamps
  preserved.
- Per `docs/methodology/schema-versioning.md:18-62`, no SemVer bump
  triggered for any of the work in this section — ADR text refinements,
  Python data-table updates, CI tooling, drift cleanup, ADR status flips,
  and SHA-pin updates are all out of the perimeter.
- Wave 1 surfaced a real R5 design flaw masked by the `[ -le 2 ]` exit-code
  wrapper bug. The R5 prose-key decomposition is the cleanest fix and
  preserved cross-language-pair semantic-equivalence checks intact.

---

## Unreleased — Forward-looking design (Phase D / E / F, no implementation in this PR) — 2026-05-03

Wave 8 (`8d21cfc`) ships design contracts for future phases — they document
the shapes Phase D port skills will emit, Phase F reflection consumes, and
how the Teal flow integrates D + E + F. No phase-D/F implementation lands
in this PR; the design-only artifacts let the next wave of agents start
against a fixed contract instead of a blank canvas.

This is a new genre in this CHANGELOG (prior entries documented shipped
runtime / data / tooling). Future versioned releases that bundle Phase D
implementation will reference these design docs.

### New: port-report.schema.json (Phase D ↔ Phase F contract)

- `prebid-server-go/read/skills/shared/port-report.schema.json` — JSON
  Schema (181 lines, draft 2020-12). Contract: Phase D port skills emit
  port reports against this; Phase F reflection consumes them. Top-level:
  `port_report_version` (SemVer 0.1.0 initial), `port_run.{run_id,
  source_lang, target_lang, source_spec_sha, target_branch}`,
  `rules_consumed[]` (per-rule verdict: applied | skipped-not-applicable
  | skipped-source-side-only | applied-with-warning), `quirks_emitted[]`
  (mirrors `adapter-spec.schema.json` `$defs/Quirk`), `r5_check.{state,
  byte_equal_fields, warn_fields, fail_fields, summary}`, `human_todos[]`
  (8-value category enum), `unresolved_translations[]` (5-value reason
  enum), `port_translation_rules_version` (cross-version replay key).

### New: Phase D / E / F design docs

- `docs/methodology/port-skills-design.md` (234 lines) — Phase D pipeline:
  load → discover family → apply rules → author destination spec → emit
  artifacts → R5-strict check → emit port-report. Conflict resolution
  (Rule 11 vs 35; Rule 38 byte-eq vs language-formatting; ADR-007
  F-pattern handling at adapter_spec_version 1.1.0 via open-map
  permissiveness). Novel-pattern handling. 3 worked examples: kobler clean
  port, vungle ADR-007 F3 port, aax R5-fail-semantic port.
- `docs/methodology/reflection-loop.md` (99 lines) — Phase F design.
  Three triggers (post-port, post-merge, periodic sweep). 9-row triage
  matrix mapping issue type → fix location: novel pattern needing schema
  → ADR-007-style $def addition; existing rule wrong direction → rules.yaml
  body edit OR ADR amendment; rule conflict / ambiguity → tightening; R5
  byte-only → Rule 38 amendment OR upstream PR; R5 semantic → upstream PR
  (NOT this repo); read-skill missed field → SKILL.md amendment; lint
  missed bug → new lint check; ADR drifted from execution → status flip.
  ADR amendment protocol with refinement annotations. Cross-version replay
  mechanic.
- `docs/methodology/end-to-end-flow.md` (158 lines) — Teal flow design,
  ties Phase D + E + F together. CLI: one-shot via orchestrator OR 4
  explicit steps. Run-scoped artifact layout under `.tmp/full-loop/{run-id}/`.
  Five documented failure modes with detection signal + remediation +
  fix-forward path.

### Anti-pattern taxonomy (Option α — minimal renderer change)

- `behavior-taxonomy.yaml` — added `category: anti-pattern` field to 5
  `quirks_taxa` entries (clear DESIGN anti-patterns, not bugs/typos):
  `hardcoded-config-as-anti-pattern`, `legacy-encoding-json-direct-usage`,
  `unguarded-currency-overwrite`, `hardcoded-bid-type`, `redundant-work`.
- `scripts/render-taxonomy.py` — added category-prefix logic: when a taxon
  has `category: <c>`, the rendered description gets a `**[<c>]**` prefix.
  Future categories may be added in future waves; same mechanism surfaces
  them.

### Methodology README updates

- `docs/methodology/README.md` — added the 3 new design docs to the table
  + 2 new "How to use these docs" entries (port-skills-design + Teal-flow
  consultation guidance).

### Wave 9b structural alignment (this commit)

- `ROADMAP.md` rewrite — added Phase F section (was A-E only); rewrote
  Phase E to acknowledge Wave 5 partially-shipped prerequisites
  (`prior_source_spec`, `.tmp/full-loop`); dropped circular "complete in
  PR #1" framing; added comprehensive Phase numbering map reconciling
  A-F + 2.X + 4.X + Wave-N coexisting schemes.
- `README.md` Phase status table — same rewrite (Phase F row added; Phase
  E rephrased; "complete (PR #1)" → "complete").
- `CHANGELOG.md` Unreleased section — split from single
  "ADR corrections" into "Process / tooling hardening" (this section,
  absorbs Waves 1, 2, 4, 5, 6, 7, 9a + the original ADR corrections) and
  "Forward-looking design" (the section you are reading, Wave 8 + Wave 9b
  structural).
- `scripts/tests/test_doc_count_claims.py` — generalized from 5-entry
  enumeration to canonical-phrase regex + source-fn dict (catches future
  drift on goldens count, dual-spec count, taxa count, etc.).
- `scripts/tests/test_schema_jsonschema.py` `TestSchemaSelfValidity`
  parameterized to validate BOTH `adapter-spec.schema.json` AND
  `port-report.schema.json` against the draft 2020-12 meta-schema.
- `prebid-server-go/read/skills/shared/adapter-spec.md` — added a section
  describing the 4 Wave 3 `$defs` (EndpointResolution, EntityStrategy,
  BidPostProcessing, ImpExtUnmarshal) so the companion markdown isn't
  silently incomplete relative to the JSON Schema's $defs enumeration.

---

## [adapter_spec_version 1.0.0] · [taxonomy_version 1.0.0] · [port_translation_rules_version 0.2.0] · [port_report_version 0.1.0] — 2026-05-02

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
- `scripts/tests/test_schema_contract.py` — schema-derived registry validating dotted-path references in SKILL.md prose against the canonical schema (counts evolve with each schema bump; live count surfaced via `python3 scripts/tests/test_schema_contract.py --verbose`).
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
