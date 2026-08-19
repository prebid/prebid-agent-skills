# Read-skill suite (prebid-server-java)

This suite extracts a structured Adapter Specification from any Java bid adapter in `prebid/prebid-server-java`. The output is a language-neutral YAML document consumed by future `write/`, `port-java2go/`, and (composed with) review skills. The four read skills (`read-bidder-orchestrator`, `read-bidder-class`, `read-bidder-config`, `read-bidder-params-java`) each own one slice of the spec and dispatch through the orchestrator.

## Suite purpose

An Adapter Specification is a YAML document that captures everything needed to reconstruct or analyze an adapter without re-parsing source: provenance, YAML metadata, the bidder-params JSON schema (verbatim + interpreted), code-level behavior (batching rules, mutation idioms, endpoint resolution, bid-type resolution), Spring DI structure (`spring_config` block), test fixture inventory, quirks, and cross-language port concerns. The Go-side suite shares the same schema — Java and Go readers MUST emit an identical `bidder_params_ref` digest (`sha256` + `bytes`), identical `params.schema_interpretation`, and identical `bidder_info.capabilities` for the same bidder.

Java specs include sections that are null on the Go side: `spring_config` (factory class, `@Bean` method, `bidder_creator_lambda`, `BidderConfigurationProperties` subclass with `extra_fields`, `bean_dependencies` like `currencyConversionService` and `JacksonMapper`); `bidder_class` (Lombok-annotated class hierarchy, parameterized `Bidder<T>`, `static_fields[]`, `helper_classes_co_located[]` and `helper_classes_in_proto[]`); and Java-specific test idioms (per-alias IT class with 4-file split fixtures, hand-written JUnit `@Test` methods, `test-application.properties` registry append). Java specs also leave `code.adapter_struct` and `code.builder` null (Java construction lives in `spring_config.bidder_creator_lambda`).

In scope on the Java side: discovery, fetch, parse, dispatch, assembly. Out of scope: writing new adapters from a spec (future `write/`), porting Java-source spec to Go artifacts (future `port-java2go/`), and the symmetric inverse (`port-go2java/`).

## Directory layout

```
prebid-server-java/read/skills/
├── README.md                                  ← you are here
├── shared/                                    Empty by design — links Go-side canonical files
├── read-bidder-orchestrator/                  Entry-point skill: discovery, fetch, dispatch, assembly
│   └── references/
├── read-bidder-class/                         Parses src/main/java/org/prebid/server/bidder/{xyz}/*.java + JUnit tests
│   └── references/
├── read-bidder-config/                        Parses src/main/resources/bidder-config/{xyz}.yaml + Spring @Configuration class
│   └── references/
└── read-bidder-params-java/                   Parses src/main/resources/static/bidder-params/{xyz}.json + ExtImp{Xyz}.java
    └── references/
```

> **Shared references**: The canonical schema lives on the Go side at [`prebid-server-go/read/skills/shared/adapter-spec.md`](../../../prebid-server-go/read/skills/shared/adapter-spec.md). Java-side readers consume the same schema; if a future divergence requires a Java-specific schema, that lives here as `shared/adapter-spec-java.md`. Likewise for [`behavior-taxonomy.md`](../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md) and [`port-translation-rules.md`](../../../prebid-server-go/read/skills/shared/port-translation-rules.md) — single source of truth on the Go side.

## How to read a spec (for human reviewers)

Top-to-bottom guidance for a reviewer reading a Java-source adapter spec YAML. Use the Kobler golden at `read/test-fixtures/kobler.golden.spec.yaml` as a worked example.

1. **`provenance`** — where the spec came from. `resolved_commit` pins to a specific Java upstream SHA. `warnings[]` carries non-blocking anomalies (`yaml-field-name-typo`, `package-directory-mismatch`, `legacy-test-helpers-imported`).
2. **`meta`** — `bidder_name`, `is_alias`, `parent_aliases[]` (Java parent declares aliases on itself, inverse of Go), `java_artifact_version` (e.g., `3.41.0`).
3. **`bidder_info`** — the unified YAML metadata. `endpoint`, `endpoint_compression` (kebab-case `endpoint-compression` on Java vs camelCase on Go), `ortb_version` (Java-only quoted string `"2.6"`), `default_enabled`, `modifying_vast_xml_allowed`, `maintainer`, `capabilities`, `geoscope`, `gvl_vendor_id`, `yaml_extra_fields` (e.g., `dev-endpoint`).
4. **`bidder_params_ref`** — the cross-language byte-identical contract: `{ path, resolved_commit, sha256, bytes }` with the bytes staged at `read/test-fixtures/blobs/<sha256>`, both numbers taken from the fetch pipe rather than from a hash of the spec's own text (V1/V2 in [`adapter-spec.md`](../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)). Go and Java digests MUST match. The inline `bidder_params_json` / `bidder_params_sha256` pair remains schema-valid but is deprecated.
5. **`params`** — schema interpretation plus the Lombok-annotated POJO (`@Value @Builder` / `@Value(staticConstructor=of)`).
6. **`code`** — `file_layout`, `make_requests` (with `batching.rules[]`, `mutation.entity_strategies` typically `immutable-rebuild` with `java_idiom: lombok-tobuilder`, `imp_ext_unmarshal.mechanism_java: typeref-extprebid`), `make_bids` (with `bid_type_resolution.method_chain[]`, `http_status_handling.kind: framework-default` or `framework-default-plus-empty-seatbid-shortcircuit`).
7. **`tests`** — Java's 4-file split per integration test case (request, response, auction-request, auction-response). `integration_test.pattern: 4-file-split`. `unit_test_methods_count` populated; per-alias IT class required (Adverxo's `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`).
8. **`spring_config`** — Java-only block. `factory_class`, `factory_method`, `property_source_path`, `bidder_creator_lambda` (verbatim for round-trip fidelity), `configuration_properties_class` (subclass with `@NotBlank` / `@NotNull` validations on `extra_fields[]`), `bean_dependencies[]` (`currencyConversionService`, `mapper`, `@Value(${external-url})`).
9. **`bidder_class`** — Java-only block. `name`, `parameterized_request_type` (`BidRequest` default; non-default for Mediasquare's `Bidder<MediasquareRequest>`), `constructor.parameters[]` with `source` (`config-field`/`framework-injected`) and `role`, `static_fields[]` (TypeReferences, default-currency strings), `helper_classes_co_located[]` vs `helper_classes_in_proto[]`.
10. **`quirks[]`** — free-text edge cases with `edge_case_taxon`. A `custom` value REQUIRES a paired quirks entry.
11. **`cross_language`** — port concerns (`aliases_inverted`, `yaml_unification`, `mutation_idiom_divergence`), `port_lineage` (source/destination PR numbers). `reviewer_cohort` was removed at `adapter_spec_version` 2.0.0 — no skill may key a check on reviewer identity, so the field had nothing to do.

## Test fixtures

Golden specs at `read/test-fixtures/{bidder}.golden.spec.yaml`. 10 fixtures pinned to commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a`: `152media, aax, appnexus, elementaltv, generic, huaweiads, kobler, mediasquare, optidigital, rubicon`. The Phase A acceptance-gate fixture is `kobler` (cross-language port pair — its Go sibling lives at `prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`). Round-trip determinism (R4) is enforced — re-running the orchestrator on the same `provenance.source.resolved_commit` MUST produce a byte-identical spec modulo `provenance.read.timestamp_utc` and `provenance.read.operator`. See `read/test-fixtures/README.md` for per-fixture edge cases.

## What's NOT in scope

- The `write/` skill: generates new adapters from a spec. Future work.
- The `port-java2go/` skill: translates a Java-source spec to Go artifacts. Future work; consumes `shared/port-translation-rules.md` (Go-side canonical).
- The `port-go2java/` skill: symmetric inverse.
- The `read-go/` suite: lives at `prebid-server-go/read/skills/` (parallel structure).

## Cross-references

- The Go parallel suite at `prebid-server-go/read/skills/` is the source of truth for `adapter-spec.md`, `behavior-taxonomy.md`, and `port-translation-rules.md`.
- [`prebid-server-java/references/new-bid-adapter-prs.md`](../../references/new-bid-adapter-prs.md) — 49 Java reference PRs (39 currently tagged with `Patterns Demonstrated`), used as ground truth for Java behavioral taxonomy and port-translation rule discovery.

## Status

- 10 goldens at `read/test-fixtures/` (Phase A `kobler` plus 9 corpus fixtures)
- `shared/` empty by design (links to Go-side canonical schema); divergence-trigger files would land at `shared/adapter-spec-java.md` if Java-specific schema becomes necessary
- All 4 per-skill SKILL.md files authored (`read-bidder-orchestrator`, `read-bidder-class`, `read-bidder-config`, `read-bidder-params-java`) with `references/` populated
- Phase C Java read suite complete; see [`ROADMAP.md`](../../../ROADMAP.md) for next milestones
