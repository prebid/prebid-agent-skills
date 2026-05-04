# Adapter Specification (canonical schema)

The canonical YAML schema for prebid-server adapter specifications. Language-neutral at the behavioral level with explicit per-language sub-blocks for divergences. Consumed by all read skills (Go and Java), the future `write/` skill, and the future `port-go2java` / `port-java2go` skills. Two specs for the same bidder produced from each language MUST agree on cross-language fields (`bidder_params_json` byte-identical, `bidder_info.capabilities`, `params.schema_interpretation`) and MAY differ only on language-specific blocks.

> **Phase 2 status (2026-05-02)**: the structural contract (every field, type, required marker, enum) lives in [`adapter-spec.schema.json`](adapter-spec.schema.json) (JSON Schema 2020-12). This Markdown file is the human-readable wrapper documenting policy, rules, and pointers — the JSON Schema is the source of truth for validation.

---

## Versioning policy

`adapter_spec_version` is a SemVer string `X.Y.Z` (per ADR-001 D7). Goldens declare it explicitly. Bump policy:

- **Patch** (`1.0.0 → 1.0.1`): bug fix in a worked example, prose-only schema documentation change, no behavioral or shape change
- **Minor** (`1.0.0 → 1.1.0`): additive — new optional field, new enum value with `custom` already covering the gap
- **Major** (`1.0.0 → 2.0.0`): breaking — field renamed, default value changed, required field added, enum value removed

A reader skill MUST emit the version it produced. A consumer (write, port) MUST refuse a version higher than its own and SHOULD warn on a lower version.

The legacy form `adapter_spec_version: 1` (integer) is accepted by the schema during the Phase 2 migration window; Phase 2.7 migrates all goldens to the SemVer string form.

---

## Schema fork policy (when to introduce `adapter-spec-java.md`)

This shared schema serves Go and Java readers via per-language sibling fields (`mechanism_go` / `mechanism_java`, `go_idiom` / `java_idiom`, etc.) and conditionally-present blocks (`spring_config`, `bidder_class`, `aliases[]`, `lifecycle`, `code_naming` — Java-only; `code.adapter_struct`, `code.builder` — Go-only). The shared form is preferred — it lets cross-language consumers (`port-go2java/`, `port-java2go/`, dual-spec assertions) work against a single canonical contract. A Java-side fork at `prebid-server-java/read/skills/shared/adapter-spec-java.md` is justified ONLY when ALL of the following gates trip together.

### Quantitative gates (necessary)

1. **Top-level field count.** The Java-specific top-level field count exceeds `N = 6` (currently 5: `spring_config`, `bidder_class`, `aliases[]`, `lifecycle`, `code_naming`). Adding a sixth Java-only top-level field without a Go peer trips the count, but ONLY counts toward the gate when gate 2 also fails.
2. **Per-field null-marker density.** A single shared schema requires more than `M = 3` `null when source_language=java` (or `go`) markers on any one top-level field. The current schema has 0–2 such markers per field. Crossing 3 means the field's shape is no longer cross-language; sibling-key naming has been exhausted.
3. **Behavioral-field divergence count.** More than `K = 4` enumerated behavioral fields in `behavior-taxonomy.md` need a per-language enum subset (e.g., `mechanism_go` values that have no Java counterpart and would never appear on a Java spec). The current count is 3 (`endpoint_resolution.mechanism_go|java`, `mutation.go_idiom|java_idiom`, `bid_pointer_go_sibling`).

### Qualitative gates (necessary)

4. **Conceptual mismatch unresolvable by sibling naming.** The mismatch is structural — not just nomenclature. If the Go spec's `code.builder.signature_canonical: bool` could be expressed as a Java sibling (e.g., `code.factory_method.signature_canonical: bool`) by renaming, sibling naming wins. Fork only when the field's *meaning* differs across languages, not its name.
5. **Downstream consumer loss is acceptable.** Forking breaks two contracts: (a) the dual-spec assertion suite at `cross-language-pairs/*` can no longer compare across schemas without a mapping shim; (b) the port-translation rules in `port-translation-rules.md` reference fields by canonical paths that must now disambiguate Go vs. Java. The fork author MUST accept these costs and propose a mitigation (e.g., a shim in `cross-language-pairs/README.md` documenting the bridged field names).

### Anti-criteria (DON'T fork for)

- **Cosmetic differences.** YAML kebab-case vs. camelCase keys (Java `endpoint-compression`; Go `endpointCompression`) — handled by `bidder_info.yaml_field_name_quirks[]`. Field-name style is a rendering concern, not a schema concern.
- **Per-language idiom values.** Adding a new `mechanism_java` value (e.g., `vertx-webclient`) is an enum extension, not a fork — update `behavior-taxonomy.md` instead.
- **Single-bidder edge cases.** A new top-level field needed by exactly one Java adapter (e.g., huaweiads's HMAC nonce formatting) belongs in `quirks[]` paired with an `edge_case_taxon`, not a fork.

### What changes hands when the fork lands

If gates 1–5 all trip, forking is a coordinated change-set:

| Artifact | Action |
|---|---|
| `prebid-server-java/read/skills/shared/adapter-spec-java.md` | NEW file. Diverges from this schema only on the gated fields; everything else is a verbatim copy with a header note pointing back here as the historical ancestor. |
| `prebid-server-java/read/test-fixtures/*.golden.spec.yaml` | All Java goldens regenerate against the forked schema. |
| `cross-language-pairs/*.dual-spec-assertions.yaml` | Each entry gains a `schema_bridge:` block declaring how forked-Java fields map to shared-Go fields for comparison. |
| `scripts/round-trip-ci.py` | R3, R5, R9 grow per-language code paths. |
| `scripts/tests/test_schema_contract.py` and `test_schema_jsonschema.py` | Load BOTH schemas; phantom-path detection runs per-language with the appropriate schema as ground truth. |
| `prebid-server-go/read/skills/shared/cross-skill-integration.md` | Section 1 overview diagram updates (two canonical schemas, not one). |
| `prebid-server-go/read/skills/shared/port-translation-rules.md` | Each rule that references a forked field gains a `Go field → Java field` resolution table. |
| `prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md` and Java sub-skills | "Source of truth" pointers swap from this file to the new fork. |

The fork PR MUST update every artifact above atomically. Stragglers (e.g., a SKILL.md still pointing at the Go schema for a now-Java-only field) defeat the fork's purpose: making the Java contract independent.

### Review checklist (use when the fork PR lands)

- [ ] Gates 1–5 each cited with current counts.
- [ ] Sibling-key naming explicitly ruled out, with the proposed sibling and the reason it doesn't work.
- [ ] Bridge mapping in `cross-language-pairs/README.md` for every affected dual-spec assertion.
- [ ] No SKILL.md continues to reference the Go schema for a field now defined only in the Java fork.
- [ ] CI rules R1–R10 still pass on both shapes.

---

## Schema (machine-readable)

The structural contract is in [`adapter-spec.schema.json`](adapter-spec.schema.json) — a JSON Schema 2020-12 document with `$defs` for each top-level block:

- **Top-level `$ref`-wired**: `Provenance`, `Meta`, `BidderInfo`, `Params`, `Code`, `Tests`, `IabCategoryStorage`, `ExtPojoConstruction`, `CurrencyConversion`, `HeadersConstructed`, `DeployTimeToken`, `Alias`, `Quirk`, `CrossLanguage` — these are the canonical 14 top-level structural blocks. The schema's `properties` block points each `$ref` at the matching `$def`.
- **Code sub-block `$defs`** (added at `adapter_spec_version 1.1.0` per ADR-007): `EndpointResolution` (F1), `EntityStrategy` (F3), `BidPostProcessing` (F4), `ImpExtUnmarshal` (F5). Wave 11b B3+ closed `Code` itself (`additionalProperties: false`) and added structured `$defs` for the four sub-blocks: `CodeImports`, `AdapterStruct`, `CodeBuilder`, `MakeRequests`, `MakeBids`. The F1/F3/F4/F5 `$defs` themselves are STILL not `$ref`-wired into the corresponding positions inside MakeRequests/MakeBids — those sub-objects are typed `object|null` (implicit-open) within their parent $def. Per-pattern `$ref`-wiring is deferred to a future wave. F2 (`headers_constructed.language_stamped_headers[]`) shipped earlier and IS already wired into `HeadersConstructed`.

Every required field, allowed enum value, and nullability marker is encoded there.

**Validate a spec**:

```python
import json, yaml, datetime
from jsonschema import Draft202012Validator

def normalize(node):
    if isinstance(node, dict): return {k: normalize(v) for k, v in node.items()}
    if isinstance(node, list): return [normalize(v) for v in node]
    if isinstance(node, (datetime.datetime, datetime.date)): return node.isoformat()
    return node

schema = json.load(open("prebid-server-go/read/skills/shared/adapter-spec.schema.json"))
spec = normalize(yaml.safe_load(open("prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml")))
errors = list(Draft202012Validator(schema).iter_errors(spec))
assert errors == [], f"Validation errors: {errors}"
```

CI runs this against every golden on every PR via `scripts/tests/test_schema_jsonschema.py`.

### Per-language invariants (`source_language` discrimination)

The schema uses JSON Schema 2020-12 `if/then/else` keyed on `source_language` `const`-value (per ADR-001 audit A3 — NOT OpenAPI's `discriminator` keyword) to enforce per-language invariants:

- **Go-source specs** (`source_language: go`) MUST null `spring_config` and `bidder_class` (Java-only structural blocks)
- **Java-source non-alias specs** (`source_language: java` AND `meta.is_alias: false`) MUST emit non-null `spring_config` and `bidder_class`
- **Java-source alias specs** (`meta.is_alias: true`) MAY null `spring_config` and `bidder_class` (alias inherits from parent)
- **Bilateral blocks** — `lifecycle.rename` and `code_naming` are present on either language when relevant (e.g., elementaltv-Go records the Adoppler→ElementalTV rename in `lifecycle.rename`)

### Schema evolution

Non-trivial schema decisions are documented as ADRs in [`docs/decisions/`](../../../../docs/decisions/):

- [ADR-001](../../../../docs/decisions/001-phase-2-schema-field-additions.md) — Phase 2 schema field additions (`code_naming` top-level, `injection`→`delivery_mechanism` rename, `shared-genesis` source_language, `mutation.schain_movement`, `lifecycle.rename` sub-fields, 22 phantom-path resolutions, SemVer version format)
- [ADR-007](../../../../docs/decisions/007-novel-pattern-schema-additions.md) — Five novel-pattern schema additions (multi-endpoint, language-stamped headers, mediatype-context-rewrite, bid-post-processing macros, imp-ext strip)

When adding or changing a field:

1. Edit `adapter-spec.schema.json` (the authoritative contract)
2. If goldens need to change, edit them and verify with `make audit-goldens`
3. Run `make ci` to confirm `test_schema_jsonschema.py` passes for all 40 goldens (21 Go + 19 Java post-Phase-5)
4. Document significant changes in `CHANGELOG.md` (Phase 2.7+)
5. If the change is breaking, write an ADR and bump the schema version per the policy above

---

## Worked example: Kobler (canonical port pair)

Phase 2.0 milestone fixture. The full Go and Java specs live in the goldens directory:

- Go-source spec: [`prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../../test-fixtures/kobler.golden.spec.yaml)
- Java-source spec: [`prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml)
- Cross-language assertions: [`cross-language-pairs/kobler.dual-spec-assertions.yaml`](../../../../cross-language-pairs/kobler.dual-spec-assertions.yaml)

Notable Kobler-pair properties demonstrated:

- **Byte-equal `bidder_params_json`**: both sides hash to `125fef34c3c83c63342e94c74b7ac9f98d026ada4e6a0112157387d787c7b685` (Rule R5-strict pass)
- **Cross-language port lineage**: `source_pr: prebid/prebid-server#3904`, `destination_pr: prebid/prebid-server-java#3684`
- **Currency-conversion idiom divergence (Rule 32)**: Go uses `function-arg` injection (`reqInfo.ConvertCurrency`); Java uses `dependency` injection (`CurrencyConversionService`) — captured via `currency_conversion.injection`
- **R7 documented bug**: kobler `params_test.go:47` calls `validator.Validate(openrtb_ext.BidderKrushmedia, ...)` (copy-paste artifact) — surfaces as `bidder-constant-mismatch` warning
- **Dev-prod toggle**: `bidder_info.endpoint_construction.kind: dev-prod-toggle` driven by `imp.ext.bidder.test` flag of the FIRST imp only

For other canonical examples covering the diversity of the corpus, see:

| Bidder | Demonstrates |
|---|---|
| 152media | Alias-only spec (parent: adkernel); cross-language port pair |
| elementaltv | `lifecycle.rename` from Adoppler (Rule 43 `bilateral` sub-type) |
| huaweiads | Java-only `parameterized_request_type: Bidder<HuaweiAdsRequest>`, IAB-category go-data-table-equivalent storage, HMAC auth |
| appnexus | `mutation.schain_movement` (OpenRTB 2.5→2.6 rebrand), custom `UnmarshalJSON`, yaml-inlined IAB-category data table |
| rubicon | `cross_language.port_lineage.source_language: shared-genesis` (predates Go-Java pair convention) |
| msft | Bidder-rename (formerly Microsoft); IAB-category data table; dual test root (`test/` + `test-extrainfo/`) |
| optidigital | Phase A acceptance-gate (clean baseline); hardcoded dev-endpoint quirk; canonical `default_enabled` asymmetry (Rule 45) |

The cross-language-pairs dual-spec assertions live at `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` (16 pairs post-Phase-5; see `cross-language-pairs/README.md`).

---

## Validation rules (R1-R10)

The orchestrator enforces these rules at read time. Failures are emitted under `provenance.warnings` (non-blocking) or surface as hard errors that abort the read. The CI harness at `scripts/round-trip-ci.py` runs each rule against every golden on PR-time + post-merge.

| Rule | Description | Enforcement |
|---|---|---|
| R1 | Spec must reference only files reachable at `provenance.source.resolved_commit`. A reference to a file that doesn't exist at that commit is a hard error. | Hard error |
| R2 | `bidder_params_sha256` must match `sha256(bidder_params_json)`. The Go and Java reader for the same bidder MUST produce identical SHA. | Hard error |
| R3 | No invented fields. Every behavioral field has either a default flag (with structural evidence affirmatively matching the default) or a regex/AST/JSON-parse evidence pointer. A `custom` value REQUIRES a matching `quirks` entry. | Hard error |
| R4 | Round-trip determinism. Re-running the read on the same commit produces a spec idempotent under `yaml.safe_load → safe_dump` (the test asserts dump2 == dump3). The orchestrator targets byte-identical reproduction modulo `provenance.read.timestamp_utc` and `provenance.read.operator`; R4 enforces idempotency rather than raw-byte equality against a stored golden. | Hard error in CI; warning interactively |
| R5-strict | Cross-language structural parity for port pairs — STRICT fields. For any bidder present in both repos, the following MUST be byte-identical (after canonical normalization): `bidder_params_sha256`, `bidder_info.capabilities`, `params.schema_interpretation`, `bidder_info.gvl_vendor_id`, `bidder_info.maintainer.email`, `bidder_info.geoscope`. Divergence is a hard FAIL (port-fidelity violation). | Hard FAIL in dual-spec-assertion suite |
| R5-divergent | Cross-language structural parity for port pairs — LEGITIMATE-DIVERGENCE fields. The following fields MAY diverge between Go and Java specs as a matter of language idiom; CI normalizes for comparison rather than failing: `bidder_info.user_sync` (Go camelCase keys vs Java kebab-case keys — semantically equivalent), `bidder_info.endpoint` (deploy-time tokens, dev-prod toggles, and per-language template syntax allowed), `bidder_info.endpoint_compression` (Java specs sometimes omit when the framework default applies), `bidder_info.ortb_version` (Java-only quoted-string `"2.6"`; Go always emits null). Divergence on these fields surfaces as INFO-level only — never a fail. | INFO-level dual-spec-assertion note |
| R6 | `meta.bidder_name == cross_language.go_artifacts.package_name` AND `meta.bidder_name.toLowerCase() == directory_name(cross_language.java_artifacts.bidder_dir)`. Mismatch is a `package-directory-mismatch` warning. **Alias suppression** (Phase 1 commit `340d2a5`): when `meta.is_alias=true`, R6 compares against `meta.alias_of` (parent), not the alias's own bidder name. | `provenance.warnings` |
| R7 | If `params.params_test.bidder_constant_referenced` does not match the constant declared in `openrtb_ext/bidders.go` for this bidder name (Go), or doesn't match the Java equivalent, emit `bidder-constant-mismatch` warning with `file:line`. **Important** (Phase 1 commit `592b7bb`): the canonical constant is looked up in `bidders.go`, NOT derived by PascalCase — 84 of 271 upstream constants don't match a mechanical PascalCase. | `provenance.warnings` |
| R8 | If `bidder_info.endpoint` contains a `{{.XYZ}}` macro and `XYZ` is not in `macros.EndpointTemplateParams` (Go) or the Java macro list, emit `endpoint-placeholder-unresolved` warning. | `provenance.warnings` |
| R9 | If `code.imports.has_jsonutil == false` AND any `Marshal` or `Unmarshal` call appears in the adapter code (Go), emit `legacy-encoding-json-direct-usage` warning (recommended migration to `jsonutil`). | `provenance.warnings` |
| R10 | If `tests.uses_canonical_harness == false` (Go: `RunJSONBidderTest` not called; Java: `VertxTest` not extended), emit `legacy-test-helpers-imported` warning. | `provenance.warnings` |

Validation rule R7 is load-bearing: Phase 2 found two real source-code bugs in `kobler_test.go` and `params_test.go` (BidderKargo and BidderKrushmedia copy-paste artifacts) that pass tests because the validator/builder don't cross-check the constant. The spec's read-time validation surfaces these.

A dual-spec assertion FAIL is a port-fidelity violation that surfaces in the cross-language test harness (per `cross-language-pairs/README.md`).

---

## Sources

- Phase 2 reconnaissance findings (this PR): the 17+17 edge-case enumeration across both languages, plus the broader 9-adapter Java behavior taxonomy stress-test.
- `prebid/prebid-server` master — Phase A-4 fixtures pin to `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (v4.1.0, 2026-04-27); Phase 5 fixtures pin to `2fae16f31693452b62dd2a0924b78e71bbec43ec` (master, 2026-05-02).
- `prebid/prebid-server-java` master — Phase A-4 fixtures pin to `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` (v3.41.0, 2026-04-22); Phase 5 fixtures pin to `a1fe64e1...` (master, 2026-05-02).
- [`prebid-server-go/references/new-bid-adapter-prs.md`](../../../references/new-bid-adapter-prs.md) — 92 reference PRs (44 currently tagged with `Patterns Demonstrated`).
- [`prebid-server-java/references/new-bid-adapter-prs.md`](../../../../prebid-server-java/references/new-bid-adapter-prs.md) — 49 reference PRs.
- Sibling shared file: [`prebid-server-go/review/skills/shared/framework-utilities.md`](../../../review/skills/shared/framework-utilities.md).
- Sibling shared file: [`behavior-taxonomy.md`](behavior-taxonomy.md).
- Sibling shared file: [`port-translation-rules.md`](port-translation-rules.md) — 46 cross-language Go↔Java translation rules (auto-generated from `port-translation-rules.yaml`; Rules 44/45/46 added in Phase 2.5 per ADR-003/004/005; Rule 43 sub-types `bilateral`/`java-leads`/`go-leads`/`mirror-topology`/`inverted-parent` per ADR-006, 5 subtypes refined 2026-05-03 from 3).
- Sibling machine-readable schema: [`adapter-spec.schema.json`](adapter-spec.schema.json) — JSON Schema 2020-12 (Phase 2.0/2.1).
- ADR index: [`docs/decisions/`](../../../../docs/decisions/).
