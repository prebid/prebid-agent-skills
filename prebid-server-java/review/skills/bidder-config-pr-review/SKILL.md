---
name: bidder-config-pr-review
description: Reviews changes to `prebid/prebid-server-java` unified bidder-config YAML, Spring DI `@Configuration` factory, and the Rule 35 typed `BidderConfigurationProperties` subclass. USE WHEN pr-triage-java's routing manifest routes any file matching `src/main/resources/bidder-config/{x}.yaml`, `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java`, `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java`, or `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` to this skill. Do NOT use without a routing manifest from pr-triage-java; do NOT use for Go-side bidder-info review (that's `bidder-info-pr-review` in the prebid-server-go tree).
version: 0.1.0-stub
---

# bidder-config-pr-review (Java)

## Status

**STUB — full SKILL prose lands in a future F4 session per audit item 19.**

This file is a placeholder so that:
- `pr-triage-java`'s routing manifest can resolve references to this skill's path
- The Java review-skill suite's file tree is consistent
- Future cross-skill-reference links between skills don't dangle

The full skill prose (Step 1 receive triage data, Step 2 extract changes from diff, Step 3 verify @Configuration ↔ YAML alignment, Step 4 alias-block consistency check, white-label policy compliance workflow, Rule 35 typed-subclass workflow, maintainer-email verification gate workflow, capabilities + media-type alignment workflow) authors when F4 audit item 19 is taken up. See [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) for the design contract this skill will implement.

The Java-side equivalent of Go's `bidder-info-pr-review` is folded into this skill because Java's YAML is unified (bidder-info + endpoint + aliases together) and the Spring DI files cannot be reviewed without the YAML context.

## Activation

This skill activates when `pr-triage-java`'s routing manifest routes ≥1 file in any of the following patterns to `bidder-config-pr-review`:

- `src/main/resources/bidder-config/{x}.yaml` — the unified config (bidder-info + endpoint + aliases + usersync)
- `src/main/java/org/prebid/server/spring/config/bidder/{X}Configuration.java` — Spring `@Configuration` factory
- `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfiguration.java` — same role, alternate naming form (both forms exist upstream)
- `src/main/java/org/prebid/server/spring/config/bidder/{X}BidderConfigurationProperties.java` — Rule 35 typed-config subclass (only when present)

It does NOT activate on its own — `pr-triage-java` runs first and routes files here.

## Cross-Skill References

- `pr-triage-java/SKILL.md` — the orchestrator that emits the routing manifest this skill consumes
- `bidder-class-pr-review/SKILL.md` — for `{X}Bidder.java`'s constructor signature (this skill READS the constructor to verify the Spring factory's `bidderCreator` lambda arg list matches; F-new-57 trap)
- `bidder-params-java-pr-review/SKILL.md` — for `bidder-params/{x}.json` capability alignment (read-only)
- `../../../read/skills/shared/framework-utilities-java.md` — Spring DI conventions, alias inversion semantics, white-label policy quotes
- `../../../../docs/methodology/java-review-skill-design.md` — design contract (file ownership map, conventions, open questions including Q2 typed-subclass ownership and Q4 alias-only detection heuristic)
