# ADR-010: Rules 47/48/49 + effective-value emission doctrine (rtbstack green-field canary)

**Date**: 2026-07-06
**Status**: Accepted (executed in the same PR)

## Context

The rtbstack green-field canary (run-id `2026-07-06T1908Z-79b6`) was the first full Teal-flow execution in the Go→Java direction — read → port (`port-go2java` v0.5.0) → 6-reviewer gauntlet → upstream submission (`prebid/prebid-server-java#4552`, source Go PR #4685) — and the validation canary the SKILL's own status block required for v1.0.0 promotion. Trace: [`docs/runs/f6-rtbstack-greenfield-canary-2026-07-06.md`](../runs/f6-rtbstack-greenfield-canary-2026-07-06.md).

Three defect classes surfaced that the rule corpus (v0.2.0, 46 rules) could not express:

1. **Opposite-framework-default config keys (the gauntlet's headline catch).** The emitted `bidder-config/rtbstack.yaml` omitted `modifying-vast-xml-allowed`. Go's absent-key semantics: plain `bool`, effective **false** (`config/bidderinfo.go:35`). Java's: `adapter-defaults` back-fill, effective **true** (`application.yaml:101` + `BidderConfigurationProperties.init()` `defaultIfNull`; consumed at `VastModifier.java:82`). The omission silently flipped vendor-owned behavior on a video adapter. Two root causes, independently verified:
   - `bidder-config.yaml.j2` had the arm **inverted** — `{% if ctx.modifying_vast_xml %}...true{% endif %}` emits the key only when true (redundant against Java's default) and omits it exactly when declaration is behavioral (F-new-105). The arm was written against Go's opt-in polarity and transplanted.
   - Step 4 carried the source value verbatim into the dest spec and Step 6 compared spec-vs-spec, so `r5_check` reported `pass` (`R5_STRICT_KEYS` `deep_eq` on `bidder_info.modifying_vast_xml_allowed`) while the deployed artifacts diverged — the comparator is value-blind to framework back-fill (F-new-106).
   - **Corpus audit (2026-07-06)**: this class is systemic, not theoretical. Of the 7 Go↔Java pairs checked, adkernelAdn, adverxo, and thetradedesk are divergent in the live upstream repos TODAY (Go yaml absent → effective false; Java yaml absent → effective true; all three video-capable), and all pass R5 spec-strict because both readers record the raw file value. aax and vungle carry explicit `true` on both sides (matched); kobler is banner-only (flag moot); rtbstack ships explicit `false` via #4552.

2. **Grouped-by-key batching had a taxon but no rule and no Go→Java template arm** (F-new-107). The taxonomy's `grouped-by-key` batching kind (canonical: huaweiads, 33across) predates the port skills; `port-java2go` gained a per-key arm in F2 (F-new-7 EXT-A), but `port-go2java`'s `bidder.java.j2` fell through to the `UnsupportedOperationException` TODO. rtbstack's route grouping (Go map + first-seen order slice ↔ Java `LinkedHashMap`) was hand-filled on the canary.

3. **Param-derived endpoint macros had neither taxon nor rule** (F-new-109). rtbstack derives all four endpoint macros (`{{Region}}/{{SspID}}/{{ZoneID}}/{{PartnerId}}`) by parsing a publisher-supplied route URL — hostname-label region against a `{us, eu, sg}` allow-list, required `client`/`endpoint`/`ssp` query params — a mechanism distinct from Rule 11 (direct field substitution) and Rule 14 (region from request geo context). Phase 1 classified it as `runtime-region-selection` + a NEW-TAXON quirk.

A fourth, smaller gap: the `by-bid-mtype` template arm only expressed abort-all error semantics (`throw PreBidException`), while rtbstack/zentotem-class sources accumulate a per-bid error and continue (`errs = append(...); continue`) — a fidelity-relevant tolerance distinction the template forced the operator to hand-restore (F-new-108).

## Options considered

**For the config-key contract (defect 1):**
- (a) *Emit only on divergence* (key declared only when source-effective ≠ target-default) — leanest output; but leaves the true-case implicit, and the live corpus precedent for explicit true (aax, vungle) shows upstream prefers self-documenting declarations on this flag.
- (b) *Always-explicit emission* (declare the key in both polarities with the source-effective value) — deterministic, self-documenting, one template arm, honors both live precedents (explicit true: aax/vungle; explicit false: apacdex, bliink, bmtm, generic, now rtbstack).
- (c) *Reader-side fix only* (Java reader emits effective values, letting R5 catch the divergence) — correct long-term, but changing read semantics re-baselines the golden corpus and every dual-spec assertion, and does nothing to stop the port emitting the divergence in the first place.

**For rule placement:** extend existing rules (16-18 / 11-15 / 34) vs mint new numbered rules. Existing-rule extension would bury cross-language contracts inside unrelated worked examples; the corpus convention (Rules 44-46 via ADRs 003-005) is one rule per distinct translation contract.

## Decision

1. **Rule 49 — Opposite-framework-default config keys (effective-value emission).** The rule floor is MUST-declare-on-divergence: compute the source-EFFECTIVE value (declared value, else source-framework absent-key default), compare against the target adapter-default, and declare the key explicitly when they differ. The template implements option (b) — `bidder-config.yaml.j2` now emits `modifying-vast-xml-allowed` explicitly in BOTH polarities (F-new-105 fix; render + e2e tests updated). The spec-authoring corollary rides in the port SKILL: Step 4 carries effective values; Step 6 re-derives adapter-default-backed fields from the EMITTED artifact + the target default table before the R5 comparison. Option (c) — effective-value emission in the Java READ suite plus a pair-corpus re-audit (which will surface the three live divergent pairs as R5 findings, correctly) — is DEFERRED as a tracked follow-up (ROADMAP Phase E list); it is a read-semantics change with corpus-wide golden impact and deserves its own change, not a rider.
2. **Rule 47 — Grouped-by-key imp batching.** New rule in the Multi-imp grouping section; `port-go2java` `bidder.java.j2` gains a `grouped-by-key` arm driven by `ctx.batching_per_key={key_field}` (schema name symmetric to port-java2go's F2 field), emitting the `LinkedHashMap` first-seen-order grouping with two-level (per-imp / per-group) `badInput` isolation. Master sample: rtbstack.
3. **Rule 48 — Param-derived endpoint macros.** New rule in the Endpoint resolution section + new taxon `param-derived-endpoint-macros` (code-side `endpoint_resolution.kind` row + quirk-taxa registry entry; taxonomy 1.0.0 → 1.1.0 MINOR — the schema's `endpoint_resolution` object is open, so no schema bump). Deliberately NOT template-mapped: the parse/validate/substitute helper is vendor-specific by construction; the SKILL routes it through `unresolved_translations[]: novel-pattern` with the rule's worked example as the porting contract.
4. **`by-bid-mtype` tolerance variant.** `ctx.bid_type_error_tolerance ∈ {abort-all (default), per-bid-skip}` on `bidder.java.j2`, selected from the SOURCE's bid-loop error semantics (never taste); render-guarded to `by-bid-mtype` only. The spec cannot currently express this distinction (`method_chain[].fallback_action` has no accumulate-and-skip value) — recorded as a taxonomy follow-up candidate rather than a schema change here.
5. Rules corpus 0.2.0 → **0.3.0** (MINOR, additive; per `schema-versioning.md` a port skill authored against 0.2.0 "may not know how to apply Rule 47 (when added)" — the SKILL bumps its pin in the same PR).

**Execution note — first live exercise of ADR-009's disposition ladder in this direction.** The gauntlet's split verdict (V7/V8) applied the tie-breaker exactly as written: the reuse half (hand-rolled host extraction → `HttpUtil.getHostFromUrl`) was a target style norm and was adopted; the semantic half (raw-page `site.domain` fallback, pinned by a dedicated Go EXEMPLARY fixture) was vendor-owned behavior and was KEPT under the no-auto-promote guard — one sibling adapter's different choice (beachfront's null-on-failure) is not a repo norm. Target-conformance beats source-fidelity on style; fidelity governs vendor-owned behavior.

## Consequences

- Every future Go→Java emission declares `modifying-vast-xml-allowed` explicitly; new ports cannot silently reproduce the flip. The pre-0.3.0 D2.8 canary outputs carry the latent omission but were never submitted upstream (rtbstack is the only upstream submission from this skill, and it ships the fix).
- The three live upstream divergences (adkernelAdn, adverxo, thetradedesk) are DOCUMENTED, not auto-filed — whether Java should flip to Go's effective false (or the Go configs should opt in) is a per-vendor maintainer judgment; filing it upstream is a follow-up requiring its own authorization (trace §follow-ups).
- `r5_check.py` and the golden/pair corpus are intentionally untouched in this PR; until the deferred reader-side fix lands, R5 remains blind to this class at read time — the port SKILL's Step-4/6 contract is the active mitigation.
- Rule count 46 → 49; taxonomy gains one kind + one quirk taxon; templates gain two arms with render-test coverage (80/80 template+e2e tests pass).

## References

- Canary trace: `docs/runs/f6-rtbstack-greenfield-canary-2026-07-06.md` (F-new-105..114 catalogue, gauntlet ledger summary, corpus audit).
- Upstream: `prebid/prebid-server-java#4552` (Java port, explicit false), `prebid/prebid-server#4685` (Go source), `prebid/prebid-server-java` `application.yaml:101`, `BidderConfigurationProperties.init()`, `VastModifier.java:82`; `prebid/prebid-server` `config/bidderinfo.go:35`.
- Related ADRs: ADR-009 (lean-conformance doctrine — tie-breaker + no-auto-promote guard exercised here), ADR-003/004/005 (the one-rule-per-contract convention), ADR-007 (novel-pattern → taxonomy MINOR precedent).
- Rules corpus: `prebid-server-go/read/skills/shared/port-translation-rules.yaml` v0.3.0 (Rules 47/48/49 bodies carry the verbatim worked examples).
