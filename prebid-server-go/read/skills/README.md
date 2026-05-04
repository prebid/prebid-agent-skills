# Read-skill suite (prebid-server-go)

This suite extracts a structured Adapter Specification from any Go bid adapter in `prebid/prebid-server`. The output is a language-neutral YAML document consumed by future `write/`, `port-go2java/`, and (composed with) `review/` skills. The four read skills (`read-adapter-orchestrator`, `read-adapter-code`, `read-bidder-info`, `read-bidder-params`) each own one slice of the spec and dispatch through the orchestrator.

## Suite purpose

An Adapter Specification is a YAML document that captures everything needed to reconstruct or analyze an adapter without re-parsing source: provenance, YAML metadata, the bidder-params JSON schema (verbatim + interpreted), code-level behavior (batching rules, mutation strategies, endpoint resolution, bid-type resolution), test fixture inventory, quirks, and cross-language port concerns. The schema is canonical at [`shared/adapter-spec.md`](shared/adapter-spec.md) and is shared with the Java-side suite — Go and Java readers MUST emit byte-identical `bidder_params_json`/SHA, identical `params.schema_interpretation`, and identical `bidder_info.capabilities` for the same bidder.

The dual representation matters: `bidder_params_json` is the cross-language byte-identical contract (a porter consumes the verbatim bytes); `params.schema_interpretation` is the normalized view (a write skill consumes the typed properties list). The `code.make_requests.batching.rules[]` and `code.make_bids.bid_type_resolution.method_chain[]` are ordered lists, not scalar enums — Appnexus emits `[max-imps-per-request: 10, pod-grouping]`; Aax emits a 3-step bid-type chain. Provenance (`resolved_commit`, `fetch_method`, `warnings[]`) is load-bearing — the spec is frozen at a specific commit and round-trip determinism (R4) is enforced via test-fixture goldens.

In scope on the Go side: discovery, fetch, parse, dispatch, assembly. Out of scope: writing new adapters from a spec (future `write/`), porting Go-source spec to Java artifacts (future `port-go2java/`), and the symmetric inverse (`port-java2go/`). The 4 review skills at `prebid-server-go/review/skills/` produce review findings; the read suite produces structured specs they could compare against.

## Directory layout

```
prebid-server-go/read/skills/
├── README.md                                  ← you are here
├── shared/                                    Cross-skill canonical references
│   ├── adapter-spec.md                        Schema for the Adapter Specification format
│   ├── behavior-taxonomy.md                   Enumerated values for behavioral fields
│   ├── port-translation-rules.md              46 cross-language Go↔Java translation rules
│   ├── cross-skill-integration.md             How read/, review/, write/, port-* compose
│   └── review-pattern-transfer-policy.md      Why review-skill findings do NOT cross languages
├── read-adapter-orchestrator/                 Entry-point skill: discovery, fetch, dispatch, assembly
│   └── references/
├── read-adapter-code/                         Parses adapters/{bidder}/*.go + test fixtures
│   └── references/
├── read-bidder-info/                          Parses static/bidder-info/{bidder}.yaml
│   └── references/
└── read-bidder-params/                        Parses static/bidder-params/{bidder}.json + openrtb_ext/imp_{bidder}.go + params_test.go
    └── references/
```

## How to read a spec (for human reviewers)

Top-to-bottom guidance for a reviewer reading an adapter spec YAML. Use the Optidigital golden at `read/test-fixtures/optidigital.golden.spec.yaml` as a worked example.

1. **`provenance`** — where the spec came from. `resolved_commit` pins the spec to a specific upstream SHA; `fetch_method` (`github-raw` / `local-checkout` / `gh-cli`) records how the orchestrator pulled the source. `warnings[]` carries non-blocking anomalies surfaced at read time (`bidder-constant-mismatch`, `yaml-field-name-typo`, `module-major-drift`).
2. **`meta`** — what bidder this is. `bidder_name`, `is_alias` + `alias_of` (Go child→parent semantics), `parent_aliases[]`, `module_path_major` (currently `v4`).
3. **`bidder_info`** — the YAML metadata: `endpoint`, `endpoint_construction.kind`, `endpoint_compression`, `maintainer`, `capabilities.{site,app,dooh}.mediaTypes`, `geoscope`, `gvl_vendor_id`, `user_sync` (verbatim subtree).
4. **`bidder_params_json` + `bidder_params_sha256`** — the cross-language byte-identical contract. The exact bytes of `static/bidder-params/{bidder}.json`. Go and Java SHAs MUST match for the same bidder; a diff is a port-fidelity violation.
5. **`params`** — schema interpretation (`properties[]`, `required_fields`, `combinators_used[]`) plus the language-specific ext struct (Go: `openrtb_ext.ExtImp{Bidder}` in `openrtb_ext/imp_{bidder}.go`).
6. **`code`** — the heaviest section. `file_layout` (single-file vs multi-file with role tags), `adapter_struct`, `builder` signature, `make_requests` (with `batching.rules[]` ordered list, `mutation.entity_strategies` per-entity map, `imp_ext_unmarshal`, `endpoint_resolution`), `make_bids` (with `bid_type_resolution.method_chain[]`, `http_status_handling.kind`, `currency_overwrite_safety`).
7. **`tests`** — fixture inventory (`exemplary/`, `supplemental/`, `amp/`, `video/`, `videosupplemental/`), `test_root_directory` (canonical `<bidder>test/`), `uses_canonical_harness` (`RunJSONBidderTest`).
8. **`quirks[]`** — free-text edge cases with optional `edge_case_taxon` from the closed registry in `behavior-taxonomy.md`. A `custom` value in any enumerated field REQUIRES a paired quirks entry.
9. **`cross_language`** — port concerns (`aliases_inverted`, `yaml_unification`, `mutation_idiom_divergence`), `port_lineage` (source/destination PR numbers), `reviewer_cohort` (Go vs Java active humans, with `bretg` as cross-language coordinator).

## Test fixtures

Golden specs at `read/test-fixtures/{bidder}.golden.spec.yaml`. 10 fixtures pinned to commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e`: `152media, 33across, adkernel, adtonos, appnexus, bidstack, kobler, mediasquare, msft, optidigital`. The Phase A acceptance-gate fixtures are `optidigital` (clean baseline) and `kobler` (cross-language port pair — its sibling lives at `prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml`). Round-trip determinism (R4) is enforced via these — re-running the orchestrator on the same `provenance.source.resolved_commit` produces a spec idempotent under `yaml.safe_load → safe_dump` (the test asserts dump2 == dump3). Byte-identical reproduction modulo `provenance.read.timestamp_utc` and `provenance.read.operator` is the orchestrator's TARGET, not what R4 verifies. See `read/test-fixtures/README.md` for per-fixture edge cases.

## What's NOT in scope

- The `write/` skill: generates new adapters from a spec. Future work.
- The `port-go2java/` skill: translates a Go-source spec to Java artifacts. Future work; consumes `shared/port-translation-rules.md`.
- The `port-java2go/` skill: symmetric inverse.
- The `read-java/` suite: lives at `prebid-server-java/read/skills/` (parallel structure).

## Cross-references

- The 4 review skills at `prebid-server-go/review/skills/` consume the same `framework-utilities.md` reference and produce review findings; the read suite produces the structured spec they could compare against.
- The Java parallel suite at `prebid-server-java/read/skills/` shares the canonical `adapter-spec.md` and `port-translation-rules.md` (single source of truth on the Go side; Java side links to the Go-side files until divergence requires a Java-specific schema).
- `prebid-server-go/references/new-bid-adapter-prs.md` — 92 reference PRs (44 currently tagged with `Patterns Demonstrated`), used as ground truth for behavioral taxonomy and port-translation rule discovery.

## Status

- `shared/adapter-spec.md` (~920 lines) — canonical schema with worked Kobler example
- `shared/behavior-taxonomy.md` (~440 lines) — closed enumerations
- `shared/port-translation-rules.md` (~1594 lines, auto-generated from `port-translation-rules.yaml`) — 46 cross-language rules
- `shared/cross-skill-integration.md` (~345 lines) — read/review/write/port composition
- `shared/review-pattern-transfer-policy.md` (~191 lines) — review-pattern transfer ban
- 10 goldens at `read/test-fixtures/` (Phase A `optidigital` + `kobler` plus 8 corpus fixtures)
- All 4 per-skill SKILL.md files authored (`read-adapter-orchestrator`, `read-adapter-code`, `read-bidder-info`, `read-bidder-params`) with `references/` populated
- Phase B Go read suite complete; see [`ROADMAP.md`](../../../ROADMAP.md) for next milestones
