# ADR-010: Rules 47/48/49 + effective-value emission doctrine

**Date**: 2026-08-19
**Status**: Accepted (rules landed 2026-08-19; templates and SKILL contract landed in the same branch)

## Context

Three defect classes surfaced from the rtbstack Go→Java port (`prebid/prebid-server#4685` → `prebid/prebid-server-java#4552`) that the rules corpus could not express. Each is now a numbered rule; this ADR records why, what was verified, and what the first cut of Rule 48 got wrong.

### 1. Opposite-framework-default config keys

The emitted `bidder-config/rtbstack.yaml` omitted `modifying-vast-xml-allowed`. Absent means the opposite thing on each side, verified at `prebid/prebid-server` `0ba35231` and `prebid/prebid-server-java` `e3ffd57db`:

| | declaration | absent key means |
|---|---|---|
| Go | `config/bidderinfo.go:35` — `ModifyingVastXmlAllowed bool` | effective **false** |
| Java | `application.yaml:102` under `adapter-defaults`, back-filled by `BidderConfigurationProperties.init():67-68` via `ObjectUtils.defaultIfNull` | effective **true** |

The flag is consumed at `VastModifier.java:82` — `if (!bidderCatalog.isModifyingVastXmlAllowed(bidder)) { return bidAdm; }` — so a flipped default changes wire behavior on every video bid.

Two independent root causes:

- `bidder-config.yaml.j2` had the arm inverted. `{% if ctx.modifying_vast_xml %}…true{% endif %}` declares the key only where Java's default already agrees, and omits it in exactly the case where declaration is behavioral (F-new-105). The arm expresses Go's opt-in polarity and was transplanted to a Java emission.
- Step 4 carried the source value verbatim and Step 6 compared spec-to-spec, so `r5_check` reported `pass` (`R5_STRICT_KEYS` runs `deep_eq` on `bidder_info.modifying_vast_xml_allowed`) while the artifacts diverged. The comparator reads recorded values and cannot see a back-fill that happens at Spring startup (F-new-106).

**Corpus measurement (2026-08-19).** The class is systemic, and the reason the three known-divergent pairs pass R5 is not the one previously recorded. Of the 20 Java goldens carrying the field, `git show <resolved_commit>:<bidder-config path>` on the pinned commit shows:

- 4 declare `true` (aax, freewheelssp, mediasquare, vungle) — golden matches the file.
- 1 declares `false` (generic) — golden matches the file.
- **14 have no key at all, and the golden records `false`.**

`false` is neither the file's value nor the Java-effective value. It comes from the Java reader's own documented default at `prebid-server-java/read/skills/read-bidder-config/references/yaml-unification-rules.md`, which says "Default `false` when absent" — a statement about the framework that `application.yaml:102` contradicts. So the adkernelAdn / adverxo / thetradedesk pairs pass R5 spec-strict because the Java reader computes a wrong default, not because both readers record the raw file value. The observable outcome is the same; the mechanism is not, and the fix differs by mechanism — recording raw `null` would make R5 fail on a type mismatch, while recording the effective `true` would make R5 correctly report a real upstream divergence.

### 2. Grouped-by-key batching had a taxon but no rule and no Go→Java arm

The taxonomy's `grouped-by-key` batching kind (canonical: huaweiads token grouping, 33across accountId grouping) predates the port skills. `port-java2go` gained a per-key arm in F2 (F-new-7 EXT-A); `port-go2java`'s `bidder.java.j2` fell through to the `UnsupportedOperationException` TODO, so rtbstack's route grouping was hand-filled (F-new-107).

### 3. Param-derived endpoint macros had neither taxon nor rule

rtbstack derives all four endpoint macros by parsing one publisher-supplied route URL — hostname-label region against a `{us, eu, sg}` allow-list, required `client`/`endpoint`/`ssp` query params. That is neither Rule 11 (direct field substitution) nor Rule 14 (region from request geo context) (F-new-109).

A fourth, smaller gap: the `by-bid-mtype` arm expressed only abort-all error semantics (`throw PreBidException`), while sources that accumulate a per-bid error and continue forced the operator to hand-restore the tolerance (F-new-108).

## Options considered

For the config-key contract:

- **(a) Emit only on divergence** — leanest output, but leaves the true case implicit, and the live corpus shows upstream declaring this flag explicitly in both polarities.
- **(b) Always-explicit emission** — declare the key in both polarities with the source-effective value. Deterministic, self-documenting, one template arm, and matched by live precedent on both sides (explicit true: aax, freewheelssp, mediasquare, vungle; explicit false: generic, and rtbstack via #4552).
- **(c) Reader-side fix** — have the Java reader record effective values and let R5 catch the divergence. Correct in the long run, but it re-baselines 14 goldens and every dual-spec assertion that reads the field, and it does nothing to stop a port emitting the divergence in the first place.

For rule placement: extending Rules 16-18 / 11-15 / 34 would bury cross-language contracts inside unrelated worked examples. The corpus convention (Rules 44-46 via ADRs 003-005) is one rule per distinct translation contract.

## Decision

1. **Rule 49 — opposite-framework-default config keys.** The floor is MUST-declare-on-divergence: compute the source-effective value (declared value, else the source framework's absent-key default), compare against the target adapter-default, declare explicitly when they differ. The template implements option (b): `bidder-config.yaml.j2` emits `modifying-vast-xml-allowed` in both polarities, and a ctx that omits the key fails at render rather than guessing `false`. The spec-authoring corollary rides in the port SKILL — Step 4 carries effective values, Step 6 re-derives adapter-default-backed fields from the emitted artifact before the R5 comparison.

   Option (c) is **deferred, not rejected**, and the deferral now has a measured cost: 14 goldens carry a value that is neither raw nor effective, and the reader reference that produces it states a framework default the framework contradicts. Whether the field should hold raw `null` or the effective value is a corpus-wide read-semantics decision with its own migration, and it will surface the live divergent pairs as R5 findings — correctly. Recorded as a follow-up rather than a rider.

2. **Rule 47 — grouped-by-key imp batching.** New rule in the multi-imp grouping section. `bidder.java.j2` gains a `grouped-by-key` arm driven by `ctx.batching_per_key={key_field}`, emitting the `LinkedHashMap` first-seen-order grouping with two-level (per-imp / per-group) `badInput` isolation. Two render guards: a missing `key_field` fails rather than defaulting, and a `key_field` that is not a lower-camelCase Java identifier fails rather than emitting a getter that will not compile. `ctx.batching_kind` takes the spec driver's value `"grouped-by-key"`; `port-java2go` spells the same kind `"per-key"`, and that asymmetry is documented in the template header rather than resolved by renaming a shipped v1.0.0 ctx.

3. **Rule 48 — param-derived endpoint macros.** New rule in the endpoint resolution section, plus the `param-derived-endpoint-macros` taxon (an `endpoint_resolution.kind` row, a quirk-taxa entry, and the matching `EndpointResolution.kind` enum value in `adapter-spec.schema.json`, without which a spec using the rule's own driver would fail validation). Deliberately not template-mapped: the parse/validate/substitute helper is vendor-specific by construction, so the SKILL routes it through `unresolved_translations[]: novel-pattern` with the rule's worked example as the porting contract.

   **The first cut of this rule taught the pattern upstream review rejected.** It was minted from the canary and carried the canary's own Java code: chained `String.replace` with a per-parameter `HttpUtil.encodeUrl` on each value. On that same PR, upstream review raised exactly that as a FAIL — hand-substituted macros with per-parameter `HttpUtil.encodeUrl` double-encode once `Uri.java` is used, and the target repo builds bidder URIs through `Uri`. The rule now carries `endpointUrl.replaceMacro(NAME, value)…expand()` with bare-name macro constants against single-brace placeholders, keeps the original inline with the rejection quoted, and states the encoding asymmetry as the review's mechanism rather than as a measured character mapping. `Uri.expand()` delegates to Vert.x `UriTemplate` with `Variables` (`org/prebid/server/util/Uri.java`); the character-level behaviour of that expansion was not measured, so the rule tells the porter to read it off a run.

   The general lesson, which is the reason this paragraph is in an ADR rather than a commit message: **a rule minted from a canary is only as validated as that canary's upstream review.** A canary that compiles, passes a local gate, and clears an internal review gauntlet has not yet been reviewed by the people whose merge bar the rule exists to encode. The gauntlet that cleared this emission did not catch what upstream then rejected.

4. **`by-bid-mtype` tolerance variant.** `ctx.bid_type_error_tolerance ∈ {abort-all (default), per-bid-skip}` on `bidder.java.j2`, selected from the source's bid-loop error semantics and never from taste, render-guarded to `by-bid-mtype` only — no other resolution arm has the null-means-skip contract. Target-repo shape verified at `e3ffd57db`: `ZentotemBidder.java:60-105` is this exact structure, 68 adapters take an errors list into `extractBids`, and 34 use `case null, default ->`. The spec cannot currently express the distinction (`method_chain[].fallback_action` has no accumulate-and-skip value); recorded as a taxonomy follow-up rather than a schema change here.

5. **Versions.** Rules corpus → `0.4.0`, behavior taxonomy → `1.2.0`, both MINOR and additive. Per `schema-versioning.md` a port skill authored against an earlier corpus "may not know how to apply Rule 47 (when added)", so both port SKILLs bump their `port_translation_rules_version` pin in the same change.

## Consequences

- Every future Go→Java emission declares `modifying-vast-xml-allowed` explicitly, and a ctx that forgets the field fails at render. New ports cannot silently reproduce the flip.
- The three live upstream divergences (adkernelAdn, adverxo, thetradedesk) are documented, not auto-filed. Whether Java should flip to Go's effective false, or the Go configs should opt in, is a per-vendor maintainer judgment, and filing it upstream needs its own authorization.
- `r5_check.py` and the golden corpus are untouched here. Until the deferred reader-side decision lands, R5 stays blind to this class at read time and the port SKILL's Step 4/6 contract is the only active mitigation. The 14 goldens recording `false` for an absent key are a known, measured inaccuracy, not a passing state.
- A new gate connects a rule's claim about a template to that template: a rule naming a port skill alongside a `ctx.X` variable or a `.j2` file must resolve against that skill's templates directory. Rules 47 and 49 shipped with claims their templates did not satisfy, and nothing caught it.

## References

- Upstream, Java at `e3ffd57db`: `src/main/resources/application.yaml:102`; `BidderConfigurationProperties.init():67-68`; `vast/VastModifier.java:82`; `bidder/zentotem/ZentotemBidder.java:60-105`; `bidder/model/Result.java:11`; `util/BidderUtil.java:29`; `util/Uri.java`; `src/test/resources/org/prebid/server/it/test-application.properties`.
- Upstream, Go at `0ba35231`: `config/bidderinfo.go:35`.
- Upstream PRs: `prebid/prebid-server-java#4552` (Java port, explicit false), `prebid/prebid-server#4685` (Go source).
- Review evidence for the Rule 48 correction: `review-evals/fixtures/prebid-server-java-4552/`.
- Related ADRs: ADR-009 (lean-conformance doctrine — target-conformance beats source-fidelity on style, fidelity governs vendor-owned behavior), ADR-003/004/005 (the one-rule-per-contract convention), ADR-007 (novel-pattern → taxonomy MINOR precedent).
- Rules corpus: `prebid-server-go/read/skills/shared/port-translation-rules.yaml` at `0.4.0`; Rules 47/48/49 bodies carry the worked examples.
