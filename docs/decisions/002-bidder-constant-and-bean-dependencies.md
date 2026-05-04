# ADR-002: Reverse Round-2 verdicts on bidder_constant_referenced and kobler bean_dependencies

**Date**: 2026-05-02
**Status**: Accepted (Phase 1 corrections applied — `schema-interpretation.md` and `spring-config-patterns.md` edits landed in Phase 1.4 and 1.5)
**Context**: Round 2 verification reached two conclusions that Round 3 (with deeper evidence) reversed. This ADR captures both reversals and their fixes so Phase 1 doesn't re-litigate them.

## Decision A — `bidder_constant_referenced` field captures the BUG, not the canonical intent

**Round 2 verdict**: "Pick the principled rule (TestValidParams primary)" → would update the golden + SKILL to emit `BidderKobler`.

**Round 3 evidence**: The schema's worked example (kobler block in `adapter-spec.md`) literally encoded the bug value:

```yaml
bidder_constant_referenced: openrtb_ext.BidderKrushmedia    # MISMATCH — surfaces in warnings.
```

The schema demonstrates the field captures **what's actually in the code** (last-observed wins), with the warning carrying canonical-vs-actual mismatch.

**Reversed decision**: 
- Field semantics: **last-observed value** (the bug, when there is one)
- The SKILL (`read-bidder-params/SKILL.md`, `bidder_constant_referenced` extraction step) was verified correct — kept as-is
- The golden (`kobler.golden.spec.yaml` carrying `BidderKrushmedia`) was verified correct — kept as-is
- The reference (`schema-interpretation.md` "TestValidParams primary" claim) was wrong — fixed in Phase 1.5

**Fix in Phase 1.5**: edited `schema-interpretation.md` to match the SKILL's "last-observed wins" rule and align with the schema's worked example.

## Decision B — kobler bean_dependencies: golden matches upstream; reference is wrong

**Round 1 Java agent verdict**: "Fix the golden — reference's quoted method signature is canonical."

**Round 2 verification** (text-side only): "Reference is canonical because it's more falsifiable; fix the golden."

**Round 3 verification** (upstream code fetched at the pinned commit): 

Upstream `KoblerConfiguration.java` parameter order:
```java
BidderDeps koblerBidderDeps(KoblerConfigurationProperties config,
                            CurrencyConversionService currencyConversionService,
                            @NotBlank @Value("${external-url}") String externalUrl,
                            JacksonMapper mapper)
```

The **golden** at `kobler.golden.spec.yaml` matched this exactly. The **reference** at `spring-config-patterns.md` (TWO quoted code blocks: pattern definition and worked example) carried the **wrong** order (`externalUrl` in slot 2, `currencyConversionService` in slot 3).

**Reversed decision**:
- The golden was verified correct — kept as-is
- The reference's TWO quoted Java blocks were wrong — fixed in Phase 1.4

**Fix in Phase 1.4**: edited BOTH quoted code blocks in `spring-config-patterns.md` to reflect the upstream order `(config, currencyConversionService, externalUrl, mapper)`.

## Consequences

- Phase 1 commits 1.4 and 1.5 are smaller than originally scoped (just doc edits, no golden changes)
- Round 2's recommendation log carries a "reversed" annotation in the meta-review
- A general lesson: **when a verdict can be settled by upstream fetch, do that before declaring** — both Round 1 and Round 2 made the wrong call here because they didn't have upstream access

## References

- Round 3 verification (this conversation): "Round 2 verdicts" section, H10 area
- Verified upstream: `https://github.com/prebid/prebid-server-java/blob/69b1993c39ed3212ca63012a8c0924fdfa0b5d4a/src/main/java/org/prebid/server/spring/config/bidder/KoblerConfiguration.java`
- Verified upstream: `https://github.com/prebid/prebid-server/blob/d7f8515b86258688304b0d9b6668c6a0e258bc9e/adapters/kobler/params_test.go`
- Worked example: kobler `bidder_constant_referenced` block in `adapter-spec.md`
- Files fixed: `spring-config-patterns.md` (two code blocks); `schema-interpretation.md` (TestValidParams claim)
