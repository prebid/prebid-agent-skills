---
name: bidder-class-pr-review
description: Reviews changes to `prebid/prebid-server-java` adapter implementation files (`{X}Bidder.java`, helpers in the bidder package, unit tests, and the IT test class). USE WHEN pr-triage-java's routing manifest routes any file under `src/main/java/org/prebid/server/bidder/{x}/`, `src/test/java/org/prebid/server/bidder/{x}/`, or `src/test/java/org/prebid/server/it/{X}Test.java` to this skill. Do NOT use without a routing manifest from pr-triage-java; do NOT use for Go-side adapter review (that's `adapter-code-pr-review` in the prebid-server-go tree).
version: 0.1.0-stub
---

# bidder-class-pr-review (Java)

## Status

**STUB — full SKILL prose lands in a future F4 session per audit item 19.**

This file is a placeholder so that:
- `pr-triage-java`'s routing manifest can resolve references to this skill's path
- The Java review-skill suite's file tree is consistent
- Future cross-skill-reference links between skills don't dangle

The full skill prose (Step 1 receive triage data, Step 2 extract changes from diff, Step 3 build verification task list, workflows for Bidder constructor changes / makeHttpRequests changes / makeBids changes / per-test-method scrutiny / IT-class fixture wiring) authors when F4 audit item 19 is taken up. See [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) for the design contract this skill will implement.

## Activation

This skill activates when `pr-triage-java`'s routing manifest routes ≥1 file in any of the following patterns to `bidder-class-pr-review`:

- `src/main/java/org/prebid/server/bidder/{x}/*.java` — adapter implementation + co-located helpers (request/response DTOs, custom mappers)
- `src/test/java/org/prebid/server/bidder/{x}/*.java` — unit tests (typically `{X}BidderTest.java` plus helper test fixtures)
- `src/test/java/org/prebid/server/it/{X}Test.java` — the IT test class (per-alias IT classes too: `AdportTest.java`, `BidsmindTest.java`, etc.)

It does NOT activate on its own — `pr-triage-java` runs first and routes files here.

When PR type is `alias-only` AND only a per-alias IT class (`it/{Alias}Test.java`) was added (no `bidder/{x}/` files), this skill activates **for the IT class only**. See [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) §8 Q1.

## Cross-Skill References

- `pr-triage-java/SKILL.md` — the orchestrator that emits the routing manifest this skill consumes
- `bidder-config-pr-review/SKILL.md` — for the unified YAML's `endpoint:`, `meta-info.{app,site}-media-types`, `aliases:` (read-only)
- `bidder-params-java-pr-review/SKILL.md` — for the JSON schema, `ExtImp{X}.java` POJO, and IT fixture set (read-only)
- `../../../read/skills/shared/framework-utilities-java.md` — Java framework utilities (Lombok annotations, JacksonMapper, BidderDeps, CurrencyConversionService conventions)
- `../../../../docs/methodology/java-review-skill-design.md` — design contract (file ownership map, conventions, open questions)
