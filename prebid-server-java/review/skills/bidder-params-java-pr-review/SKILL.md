---
name: bidder-params-java-pr-review
description: Reviews changes to `prebid/prebid-server-java` JSON schema (`static/bidder-params/{x}.json`), imp-ext POJO (`ExtImp{X}.java` + helper protos), and IT fixture set (`it/openrtb2/{x}/test-*.json` — the 4-file Rule 36 set). USE WHEN pr-triage-java's routing manifest routes any file matching `src/main/resources/static/bidder-params/{x}.json`, `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java`, or `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` to this skill. Do NOT use without a routing manifest from pr-triage-java; do NOT use for Go-side bidder-params review (that's `bidder-params-pr-review` in the prebid-server-go tree).
version: 0.1.0-stub
---

# bidder-params-java-pr-review

## Status

**STUB — full SKILL prose lands in a future F4 session per audit item 19.**

This file is a placeholder so that:
- `pr-triage-java`'s routing manifest can resolve references to this skill's path
- The Java review-skill suite's file tree is consistent
- Future cross-skill-reference links between skills don't dangle

The full skill prose (Step 1 receive triage data, Step 2 extract changes from diff, Step 3 schema validation, Step 4 schema ↔ Java POJO alignment, Step 5 schema ↔ Go-side byte-fidelity (Rule 38) check, IT fixture parity workflow, custom Jackson deserializer workflow, helper-proto co-location workflow) authors when F4 audit item 19 is taken up. See [`../../../../docs/methodology/java-review-skill-design.md`](../../../../docs/methodology/java-review-skill-design.md) for the design contract this skill will implement.

## Activation

This skill activates when `pr-triage-java`'s routing manifest routes ≥1 file in any of the following patterns to `bidder-params-java-pr-review`:

- `src/main/resources/static/bidder-params/{x}.json` — the draft-04 JSON Schema
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{x}/*.java` — Lombok `@Value @Builder` POJO `ExtImp{X}.java` plus any helper protos co-located in the same package (e.g., `ExtImp{X}BidExt.java`, `ExtImp{X}Params.java`)
- `src/test/resources/org/prebid/server/it/openrtb2/{x}/*.json` — IT fixture set (the 4-file Rule 36 split: test-{name}-{request,response,auction-request,auction-response}.json)

It does NOT activate on its own — `pr-triage-java` runs first and routes files here.

## Cross-Skill References

- `pr-triage-java/SKILL.md` — the orchestrator that emits the routing manifest this skill consumes
- `bidder-class-pr-review/SKILL.md` — for `{X}Bidder.java`'s usage of `ExtImp{X}` fields (this skill READS to verify every declared field is consumed by adapter code; orphans are dead-code)
- `bidder-class-pr-review/SKILL.md` — for the IT class' `@Test` methods (this skill READS to verify fixture filenames are referenced by the canonical 4-file pattern)
- `bidder-config-pr-review/SKILL.md` — for `bidder-config/{x}.yaml` `endpoint:` template-token usage (this skill READS to verify template tokens like `{{adUnitId}}` map to schema-declared params)
- `../../../read/skills/shared/framework-utilities-java.md` — Lombok `@Value @Builder` conventions, JacksonMapper deserialization patterns, draft-04 schema interpretation
- `../../../../docs/methodology/java-review-skill-design.md` — design contract (file ownership map, byte-fidelity Rule 38 + dual-spec assertion link)
