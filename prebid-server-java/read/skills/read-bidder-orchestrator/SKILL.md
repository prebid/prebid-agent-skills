---
name: read-bidder-orchestrator
description: USE WHEN extracting an Adapter Specification from a Java bidder in prebid-server-java (or fork) — discovers files at a commit, dispatches per-domain readers (read-bidder-class, read-bidder-config, read-bidder-params-java), assembles output into the language-neutral spec (source_language=java), and emits YAML+Markdown. Idempotent under round-trip; byte-comparable to Go-side spec on cross-language fields. Mirrors read-adapter-orchestrator with Java specifics (Spring DI, unified bidder-config YAML, inverted aliases, multi-file fixtures, per-alias IT classes).
version: 1.1.0
---

# read-bidder-orchestrator (Java)

## Overview

Extracts a structured Adapter Specification from a single Java bidder in `prebid/prebid-server-java`. Produces:

- A YAML spec following the canonical schema at `../../../../prebid-server-go/read/skills/shared/adapter-spec.md` (the schema is byte-identical between Go and Java suites — only the populated language-specific blocks differ).
- A Markdown summary keyed off the same spec for human review.

The spec carries `source_language: java`. Cross-language fields (`bidder_params_ref.sha256`, `bidder_params_ref.bytes`, `bidder_info.capabilities`, `params.schema_interpretation`, `bidder_info.gvl_vendor_id`) are byte-comparable to the Go-side spec for the same bidder — each side measures its own digest before the comparison. Language-specific fields populate `cross_language.java_specific_concerns[]` (dense) and `cross_language.go_specific_concerns[]` / `cross_language.go_artifacts.*` as path-stub hints only.

Downstream consumers: the future `port-java2go/` skill suite (Phase D), `diff-spec` (deferred), and any review skill that wants prior-spec comparison.

## Inputs

| Flag | Required | Default | Description |
|---|---|---|---|
| `--bidder=<name>` | yes | — | Lowercase YAML name (e.g., `kobler`, `152media`, `feedad`). For the digit-leading workaround case, pass the YAML name (`152media`), not the class root (`OneFiveTwoMedia`). |
| `--ref=<spec>` | no | `branch=master` | One of `branch=<name>`, `commit=<sha>`, `pr=<N>`, `tag=<vX.Y.Z>`. PR resolves to `head.sha`. |
| `--source-mode=<mode>` | no | `auto` | `local`, `github-raw`, `gh-cli`, or `auto`. See [references/source-modes.md](references/source-modes.md). |
| `--persist` | no | off | Write to `prebid-server-java/read/specs/{bidder}/{shortsha}.{yaml,md}` plus `latest.yaml` symlink. |
| `--out=<path>` (synonym `--output=<path>`) | no | stdout | Output file path. Filename convention: `{bidder}-{shortsha}.spec.{yaml,md}`. The `--output` synonym matches the spelling used in [`../../../../docs/methodology/end-to-end-flow.md`](../../../../docs/methodology/end-to-end-flow.md); both names resolve to the same flag. |
| `--run-id=<id>` | no | `${FULL_LOOP_RUN_ID}` env var if set | Teal-flow convention (Phase D1.5). When set (and neither `--persist` nor `--out` is given), output path defaults to `.tmp/full-loop/{run-id}/java/{bidder}.yaml` — the canonical handoff location the upcoming `port-go2java` / `port-java2go` skills look for the source spec. Format: ISO-like timestamp + short hash, e.g., `2026-05-04T1430Z-a3f9`. The `.tmp/` directory is `.gitignore`d (Wave 5). |
| `--format=<set>` | no | `yaml,md` | Comma-separated subset of `yaml,md`. |
| `--fixture-mode=<mode>` | no | `count` | `count`, `summary`, `verbatim`. Every mode records `{ filename, sha256, bytes }` per fixture — `summary` and `verbatim` add to that pair, never replace it — and both numbers come from the fetch pipe, not from an inlined copy (V1/V2 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)). |

See [Output](#output) below for emission rules; the contract is the language-neutral form documented in the Go orchestrator's `## Output` section, with the Java-specific paths swapped in.

## Workflow

The orchestrator runs seven steps in this fixed order. Steps 1–4 are sequential; step 5 dispatches three readers in parallel; steps 6–7 are sequential.

### Step 1: Resolve `--ref` to a 40-char commit SHA

Resolution depends on `--source-mode`:

- `local` — `git -C <java-checkout> rev-parse <ref>`. For `branch=master`, accepts a stale local checkout but warns if `git fetch --dry-run` shows drift. Note: `--source-mode=local` produces `provenance.source.fetch_method: "local-checkout"` in the spec (NOT `local`); the schema enum at `prebid-server-go/read/skills/shared/adapter-spec.schema.json` admits only `{github-raw, local-checkout, gh-cli}`.
- `github-raw` — uses GitHub's `repos/prebid/prebid-server-java/commits/{ref}` API to resolve, then fetches blobs from `raw.githubusercontent.com`.
- `gh-cli` — `gh api repos/prebid/prebid-server-java/commits/{ref} --jq .sha`.

The resolved SHA is recorded in `provenance.source.resolved_commit` and ALL subsequent file reads MUST happen at that exact commit (R1: spec frozen).

For `pr=<N>`, the API resolves to `pulls/{N}.head.sha` (NOT `merge_commit_sha`) so the spec captures the PR's contributor branch state.

### Step 2: Discover Java files for the adapter

Apply the discovery globs documented in [references/discovery-rules.md](references/discovery-rules.md). Java's hierarchy uses TitleCase preserves-acronyms class names with two known workarounds:

- **Identifier rule**: `152media` → `OneFiveTwoMediaTest.java` (digit-leading bidders cannot be Java identifiers).
- **TitleCase preservation**: `ElementalTV`, `FeedAd`, `BidTheatre`, `BidsCube` keep their brand-acronym capitalization.

The orchestrator MUST discover all of:

1. `src/main/java/org/prebid/server/bidder/{xyz}/{Xyz}Bidder.java` (+ optional helpers in same dir)
2. `src/main/java/org/prebid/server/spring/config/bidder/{Xyz}Configuration.java`
3. `src/main/resources/bidder-config/{xyz}.yaml` (UNIFIED — bidder-info + endpoint + aliases together)
4. `src/main/resources/static/bidder-params/{xyz}.json` (byte-identical to Go-side file)
5. `src/main/java/org/prebid/server/proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` plus any helper proto/ DTOs
6. `src/test/java/org/prebid/server/bidder/{xyz}/{Xyz}BidderTest.java` (unit tests, hand-written `@Test` methods)
7. `src/test/java/org/prebid/server/it/{Xyz}Test.java` (integration test class — note: per-alias IT classes also live here; e.g., Adverxo aliases ship `AdportTest.java`, `BidsmindTest.java`, `MobuppsTest.java`)
8. `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/test-{name}-{request,response,auction-request,auction-response}.json` (the 4-file split fixture set; see Rule 36 in `port-translation-rules.md`)
9. `src/test/resources/org/prebid/server/it/test-application.properties` (central registry under the IT package — orchestrator detects appended entries; see warnings)

If file (1) or (2) is missing AND a parent declares `aliases.{bidder}`, take the alias short-circuit in Step 4. Otherwise missing files are recorded as `provenance.warnings` entries with type `missing-expected-file`.

### Step 3: Drift check `pom.xml`

Read `pom.xml` at the repository root; extract the project version:

```xml
<project>
  <artifactId>prebid-server</artifactId>
  <version>3.41.0-SNAPSHOT</version>
</project>
```

Record `meta.java_artifact_version` as the parsed version (e.g., `3.41.0`; SNAPSHOT suffix stripped). If the major version differs from the orchestrator's tested baseline (`3.x`), emit a `module-major-drift` warning. See [references/provenance-warnings.md](references/provenance-warnings.md) for warning schema.

### Step 4: Detect alias short-circuit

Java's alias direction is INVERTED from Go (port translation Rule 33). In Go, the child YAML declares `aliasOf: parent`. In Java, the parent YAML declares `aliases: { child: ~ }` (tilde-syntax for empty inheritance — the child inherits everything from the parent).

Algorithm:

1. List every `bidder-config/*.yaml` reachable at the resolved commit (or use a cache of the parent registry from Step 2).
2. For each parent YAML, parse `adapters.{parent}.aliases` and check whether `--bidder` is a key.
3. If found:
   - Set `meta.is_alias = true`, `meta.alias_of = <parent>`.
   - Read `adapters.{parent}.aliases.{xyz}` — if it's `~` (null) or `{}`, the alias inherits everything; record `aliases[].config_form: tilde_inherit`. If it's a populated block, record `config_form: full_block` and capture the override fields.
   - Emit a MINIMAL spec: full `meta`, full `bidder_info` (resolved by parent's YAML + the alias's overrides), and a `bidder_params_ref` whose `path` is the PARENT's params file (`src/main/resources/static/bidder-params/{parent}.json`) with `sha256` + `bytes` produced by running `read-bidder-params-java` Step 1 against that path — never copied out of the parent's spec (V2 in [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)). AND populate Java-specific alias test assets:
     - `aliases[].test_assets.it_class` (e.g., `AdportTest`)
     - `aliases[].test_assets.fixture_dir` (e.g., `src/test/resources/org/prebid/server/it/openrtb2/adport/`)
     - `aliases[].test_assets.fixture_file_count` (typically 4)
   - Skip Step 5 (no readers needed for an alias-only spec).
   - Continue to Steps 6–7.
4. If NOT found, proceed to Step 5 (full read).

If the bidder's own `{xyz}Bidder.java` exists AND a parent declares it as an alias, that's an inconsistency; emit `alias-resolution-circular` warning and prefer the standalone implementation (the alias entry is dead config).

For Java's bidder-rename three-step refactor (e.g., Adoppler → ElementalTV), the OLD name appears as a tilde alias of the NEW parent — `adapters.elementaltv.aliases.adoppler: ~` — and the old YAML is deleted. Step 4 handles this transparently: the old name resolves as an alias, the new name resolves as a full read.

### Step 5: Dispatch per-domain readers in parallel

Three readers are invoked concurrently. Each reader is its own skill with its own SKILL.md; the orchestrator passes the resolved commit SHA, the discovered file paths, and `--fixture-mode` and consumes the reader's output as a JSON/YAML fragment.

| Reader | Owns | Output fragment |
|---|---|---|
| `read-bidder-class` | `bidder/{xyz}/*.java` (+ `XyzConfiguration.java`, `proto/openrtb/ext/request/{xyz}/*.java`, test classes) | `code.*`, `bidder_class`, `spring_config`, `tests.*`, `iab_category_storage`, `currency_conversion`, `headers_constructed`, `make_requests.*`, `make_bids.*`, language-specific quirks |
| `read-bidder-config` | `bidder-config/{xyz}.yaml` (the unified file) | `bidder_info.*`, alias map (parent specs only), `cross_language.port_concerns.yaml_unification: true` |
| `read-bidder-params-java` | `static/bidder-params/{xyz}.json` (verbatim bytes), `proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java`, `params_test` data extracted from `{Xyz}BidderTest.java` | `bidder_params_json` (verbatim), `bidder_params_sha256`, `params.schema_interpretation`, `params.ext_struct`, `params.params_test`, `ext_pojo_construction.*` |

Each reader's output is independent — no inter-reader coupling. The orchestrator owns assembly.

### Step 6: Assemble fragments into the canonical schema

Assembly steps, in order:

1. Initialize the spec scaffold with `adapter_spec_version: "1.0.0"` (SemVer string per ADR-001 D7; or `"1.1.0"` when emitting ADR-007 F1/F3/F4/F5 patterns), `spec_kind: prebid-server-adapter`, `source_language: java`.
2. Populate `provenance.*` (source, ref, resolved_commit, fetch_method, skill_versions, timestamp_utc, operator).
3. Populate `meta.*` (bidder_name, alias data from Step 4, java_artifact_version from Step 3, module_path_major: null).
4. Merge each reader's fragment under its owned section. Resolve overlaps with reader-of-record precedence (e.g., `read-bidder-class` is the sole writer of `make_requests.mutation`; if `read-bidder-config` accidentally produces `mutation` data, the orchestrator drops it and emits `reader-fragment-collision` warning).
5. Compute `bidder_params_sha256 = sha256(bidder_params_json)` per R2; verify it matches what `read-bidder-params-java` produced.
6. Populate `cross_language.java_artifacts` (dense — reader produced it) and `cross_language.go_artifacts` (path stubs only — `bidder_dir: adapters/{xyz}/`, `package_name: {xyz}`, `bidder_constant: openrtb_ext.Bidder{Xyz}`; the orchestrator does NOT verify the Go side exists).
7. Populate `cross_language.port_concerns`:
   - `aliases_inverted: true` always for Java specs (the inversion is structural).
   - `yaml_unification: true` always for Java specs.
   - `mutation_idiom_divergence: true` if `make_requests.mutation.java_idiom == lombok-tobuilder`.
   - `package_directory_mismatch`, `multi_file_layout`, `custom_unmarshaljson_present` from reader fragments.
8. If port-pair metadata is provided (e.g., via `prebid-server-java/references/new-bid-adapter-prs.md` `port-from-go` tag), populate `cross_language.port_lineage.*`. Otherwise leave null.
9. Run validation rules R1–R10 (defined in `../../../../prebid-server-go/read/skills/shared/adapter-spec.md`):
   - **R1** (referenced files reachable at resolved commit) — hard error.
   - **R2** (sha256 matches verbatim bytes) — hard error.
   - **R3** (no invented fields; `custom` requires `quirks`) — hard error.
   - **R4** (round-trip determinism modulo timestamp/operator) — interactive warning, CI hard error.
   - **R5** (cross-language structural parity) — surfaces as `port_concerns` warning if Go-side spec is also locally available; otherwise no enforcement at read time.
   - **R6** (`bidder_name` matches directory name) — `provenance.warnings` entry of type `package-directory-mismatch`. For Java this captures TitleCase-preservation and identifier-rule-workaround cases (the warning carries `class_name_root` for diagnostic).
   - **R7** (test bidder-constant referenced matches expected) — `provenance.warnings` entry. Java does not have `openrtb_ext.Bidder{Xyz}` constants; the equivalent check is whether the configuration class's `@PropertySource` path matches the `bidder` name. Misalignment surfaces as a `class-yaml-name-mismatch` warning. See [references/provenance-warnings.md](references/provenance-warnings.md).
   - **R8** (endpoint placeholders unresolved) — `provenance.warnings`. For Java check both `{{.MACRO}}` template syntax AND `#{TOKEN}#` deploy-time tokens.
   - **R9** (legacy direct JSON usage) — Java analog: warn if `import com.fasterxml.jackson.databind.ObjectMapper` appears outside the framework-supplied `JacksonMapper`. Rare.
   - **R10** (canonical harness used) — Java analog: warn if the unit test class does NOT extend `VertxTest` or the IT class does NOT extend `IntegrationTest`.
10. Java-specific extra warnings (see `provenance-warnings.md`):
    - `pom-version-mismatch` (Step 3 result).
    - `disabled-bidder-read` if `bidder_info.default_enabled == false` AND the read was not explicitly opted-in via `--allow-disabled` (default off; defensive against misuse on disabled bidders).
    - `class-yaml-name-mismatch` if `KoblerConfiguration.java`'s `@PropertySource` path does not point at `classpath:/bidder-config/kobler.yaml`.
    - `yaml-field-name-typo` if YAML uses `endpointCompression` (camelCase — Go style) instead of `endpoint-compression` (kebab-case — Java style). Canonical: Ogury PR #3788 regression.
    - `bidder-constant-mismatch` analog: Java has no constant; instead check that `KoblerConfiguration.koblerBidderDeps()` factory method name matches the YAML bidder name. Misalignment is a copy-paste artifact.
    - `test-application-properties-missing-entries` if `test-application.properties` does not contain any of `adapters.{xyz}.enabled=true`, `adapters.{xyz}.endpoint=...`, `adapters.{xyz}.modifying-vast-xml-allowed=true` (modify-vast adapters only). Every Java adapter PR appends 2–4 lines.

### Step 7: Emit YAML + Markdown summary

Emit per the [Output](#output) contract.

## Output

The Java orchestrator's emission rules are identical in shape to the Go orchestrator's (see [`../../../../prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md`](../../../../prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md) `## Output`), with the path roots swapped:

- `--persist` → `prebid-server-java/read/specs/{bidder}/{shortsha}.{yaml,md}` plus `latest.yaml` symlink. Directory `.gitignore`d by default.
- `--out=<path>` (synonym `--output=<path>`) → same precedence and PATH/extension semantics as Go.
- `--run-id=<id>` (or `${FULL_LOOP_RUN_ID}` env var, with neither `--persist` nor `--out` given) → write to `.tmp/full-loop/{run-id}/java/{bidder}.yaml`. The `.tmp/full-loop/` directory is `.gitignore`d. This is the **Teal-flow convention** — see [`../../../../docs/methodology/end-to-end-flow.md`](../../../../docs/methodology/end-to-end-flow.md) §1.2 for the read → port → review handoff. The `port-go2java` / `port-java2go` skills look for the source spec at this canonical path.
- (default) → stdout with `--- yaml ---` / `--- markdown ---` delimiters.

`--format` and `--fixture-mode` flags behave identically to Go. YAML encoding contract is identical (LF, 2-space indent, single trailing `\n`, fixture lists alphabetically sorted, header order matches `../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json`).

Goldens at `read/test-fixtures/*.golden.spec.yaml` (Java side) demonstrate the canonical format for non-alias bidders, alias bidders, and the `lifecycle.rename` block.

## Cross-skill integration

The output spec feeds the future `port-java2go/` skill (Phase D; will live under `prebid-server-go/port-java2go/` since it produces Go artifacts). That skill will consume a Java-source spec and emit Go artifacts using the 46 port-translation rules at `../../../../prebid-server-go/read/skills/shared/port-translation-rules.md`. Specifically:

- `port-java2go` reverses Rules 33 (alias inversion), 34 (YAML unification), 36 (4-file split → httpCalls), 37 (per-alias IT class deletion — Go aliases need no test files).
- `port-java2go` consumes `cross_language.java_specific_concerns[]` to flag fidelity issues that don't translate cleanly to Go.

The spec's `bidder_params_ref.sha256` and `bidder_params_ref.bytes` are equal to a Go-side spec's for the same bidder. R5 (cross-language structural parity) enforces this, on two independently measured digests.

When invoked via `pr-triage` for prior-spec comparison, the orchestrator's output at `read/specs/{bidder}/latest.yaml` is loaded as `prior_spec` and reviewer skills can flag behavioral regressions.

## Edge cases the orchestrator handles

The 17 Java-specific edge cases (#18–#34) all map to explicit field assignments — none fall through to `quirks` + `custom`. The full catalog with per-case field mappings, master samples, and owner skills lives at [`../../../references/java-edge-cases.md`](../../../references/java-edge-cases.md).

Orchestrator-specific responsibilities (the cases this orchestrator validates or merges across readers):

- #18 — validates `spring_config.property_source_path` matches the expected `classpath:/bidder-config/{bidder}.yaml` shape.
- #25 — Step 6 warns when `tests.test_application_properties_entries_added: 0` (likely missing append on a non-alias bidder).
- #30 — emits `disabled-bidder-read` warning when `bidder_info.default_enabled: false` unless `--allow-disabled` was passed.
- #33 — Step 4 detects the old-name-as-alias-of-new pattern and emits BOTH specs (old: alias-only; new: full read with `lifecycle.rename.*` populated).
- #34 — Step 6 emits `yaml-field-name-typo` warning when `endpointCompression` (camelCase) is observed instead of `endpoint-compression` (kebab-case).

## Differences from Go orchestrator

The Java orchestrator MIRRORS the Go orchestrator's 7-step workflow but with these structural differences:

| Concern | Go orchestrator | Java orchestrator |
|---|---|---|
| YAML hierarchy | Splits across `static/bidder-info/{xyz}.yaml` + main `config.yaml` | Reads UNIFIED `src/main/resources/bidder-config/{xyz}.yaml` (info + endpoint + aliases together). Step 6 records `cross_language.port_concerns.yaml_unification: true`. |
| Aliases | Child YAML declares `aliasOf: parent` | Parent YAML declares `aliases: { child: ~ }`. Step 4 walks parent registry; Step 6 records `aliases_inverted: true`. |
| Test fixtures | Single JSON file with `httpCalls[]` array | Multi-file split: 4 files per integration test case (request, response, auction-request, auction-response). `fixture_inventory.integration[]` carries each file. |
| Per-alias tests | Aliases need NO test files (parent's tests cover them) | Each alias requires its own IT class + 4-file fixture set + `test-application.properties` entries. Step 4 gathers `test_assets`. |
| Bidder constants | Go has `openrtb_ext.Bidder{Xyz}` constants — `bidder-constant-mismatch` warning checks this | Java has NO constants. Equivalent check: `@PropertySource` path matches YAML name; factory method name matches YAML name. Surfaces as `class-yaml-name-mismatch`. |
| Module versioning | `go.mod` carries `module github.com/prebid/prebid-server/v4` (major in path) | `pom.xml` carries `<version>3.41.0-SNAPSHOT</version>`. Step 3 reads it. |
| Review expectations | per-repo | Derived from each repo's own upstream source, config, and merged-PR corpus. NO review-pattern transfer between languages, and no check keyed on reviewer identity — see `shared/review-pattern-transfer-policy.md`. Emit `cross_language.reviewer_cohort` as null; the field is inert and slated for removal in the next schema major. |
| Skill output sharing | The schema is identical; the populated blocks differ. Both languages read the SAME `adapter-spec.md`, `behavior-taxonomy.md`, `port-translation-rules.md`. |

The reviewer cohort disjointness is documented at [`../../../../prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md`](../../../../prebid-server-go/read/skills/shared/review-pattern-transfer-policy.md) §1, with the consumer-facing summary at [`../../../../prebid-server-go/read/skills/shared/cross-skill-integration.md`](../../../../prebid-server-go/read/skills/shared/cross-skill-integration.md) §8.4. When a port pair is read in both languages, the dual-spec assertions enforce R5 cross-language structural parity. Review-pattern matchers MUST be encoded per-language and never transferred — the master plan explicitly bans this.

## Verification

The Kobler Java golden spec at `../../test-fixtures/kobler.golden.spec.yaml` is the reference output. To smoke-test:

```
read-bidder-orchestrator --bidder=kobler --source-mode=local --format=yaml | yq .meta
# Expected: bidder_name=kobler, is_alias=false, java_artifact_version=3.41.0
# Expected (rest of spec): targets byte-identical reproduction of kobler.golden.spec.yaml modulo provenance.read.timestamp_utc + provenance.read.operator (R4 enforces idempotency under round-trip, not raw-byte equality)
```

Round-trip determinism (R4): re-running on the same commit produces a spec idempotent under `yaml.safe_load → safe_dump` (R4 asserts dump2 == dump3). The orchestrator targets byte-identical reproduction modulo the two provenance read fields; R4 enforces idempotency, not raw-byte equality against a stored golden.

Cross-language R5 verification: read Kobler in BOTH suites and compare the two outputs — `bidder_params_ref.sha256` and `bidder_params_ref.bytes` (each measured by that side's Step 1 command; equality between the two stdouts is the check, and no value is transcribed from this document into a spec), `bidder_info.capabilities` (banner-only on both), `params.schema_interpretation` (single `test: boolean` field), `bidder_info.gvl_vendor_id` (0 on both).

Manual inspection corpus (full v1, 10 Java goldens): `kobler, optidigital, mediasquare, appnexus, rubicon, generic, aax, huaweiads, 152media (alias), elementaltv (rename)`. After a successful read of each, manually verify the Markdown summary captures the bidder's behavior precisely enough to recreate the adapter and port to Go without referencing source.

## Sources

- Canonical schema: `../../../../prebid-server-go/read/skills/shared/adapter-spec.md`
- Behavior taxonomy: `../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md`
- Port translation rules (46 rules): `../../../../prebid-server-go/read/skills/shared/port-translation-rules.md`
- Java golden reference: `../../test-fixtures/kobler.golden.spec.yaml`
- Java reference list (49 PRs): `../../references/new-bid-adapter-prs.md`
- Sibling Go orchestrator: `../../../../prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md`
- Per-domain Java readers: `../read-bidder-class/SKILL.md`, `../read-bidder-config/SKILL.md`, `../read-bidder-params-java/SKILL.md`
