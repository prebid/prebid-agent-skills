# Provenance Warnings

The schema and registry for the `provenance.warnings[]` block on the emitted Adapter Specification. Warnings are non-blocking read-time anomalies — they surface anomalous conditions without aborting the read. (Hard errors that abort the read are NOT warnings — they are R1/R2/R3 validation failures and produce no spec at all.)

This file is the canonical warning registry: every warning the orchestrator emits MUST come from one of the types listed here. New warning types REQUIRE updating this file in the same change as the orchestrator code emitting them.

---

## Warning entry schema

Each `provenance.warnings[]` entry is a YAML object with these fields:

```yaml
- type: <warning-type-from-registry>     # required; from the registry below
  file: <path-relative-to-repo-root>     # required; the file the warning concerns
  line: <int>                            # OPTIONAL; line number when the warning is line-anchored
  summary: <free-text>                   # required; one sentence explaining the anomaly
```

Conventions:

- `type` is a kebab-case string from the registry below. Lowercase, no underscores.
- `file` is a path relative to the repository root (e.g., `adapters/kobler/kobler_test.go`, NOT a full URL or local path).
- `line` is 1-indexed. Omit (`line: null` or absent) when the warning is file-level, not line-level.
- `summary` is a single sentence (≤200 chars), no trailing punctuation. It MUST cite the specific evidence (e.g., name the wrong constant, name the typo'd field).

The orchestrator preserves warning ordering: warnings are emitted in the order they were detected during the workflow. For two warnings of the same type touching the same file, the line-number order determines emission order; for unanchored warnings, the order in which the underlying check fires.

---

## Warning type registry

### `bidder-constant-mismatch`

**Trigger**: `params.params_test.bidder_constant_referenced != <canonical-constant>` OR adapter-test code calls `Builder` / `validator.Validate` with a non-matching `openrtb_ext.Bidder*` constant. The `<canonical-constant>` is the value declared as `Bidder<X> BidderName = "<bidder>"` in `openrtb_ext/bidders.go` at the resolved commit — NOT a derived PascalCase form. Many bidders have manually-curated capitalization that doesn't match a mechanical PascalCase: `aja → BidderAJA`, `33across → Bidder33Across`, `cadent_aperture_mx → BidderCadentApertureMX`, `huaweiads → BidderHuaweiAds` (and ~80 other examples — 84 of 271 BidderName constants don't match simple PascalCase per upstream verification).

**Detection**: At Step 6 the orchestrator (a) reads `openrtb_ext/bidders.go` at the resolved commit and looks up the canonical `BidderName` constant for the bidder name, (b) extracts the actual bidder constant referenced in the params_test.go AND scans `adapters/<xyz>/<xyz>_test.go` for `Builder(openrtb_ext.Bidder<NAME>` calls, (c) emits one warning per occurrence where the referenced constant doesn't match the canonical `bidders.go` constant.

**Real bug example** (from Phase 2 Kobler validation):

```yaml
- type: bidder-constant-mismatch
  file: adapters/kobler/kobler_test.go
  line: 12
  summary: "Builder called with openrtb_ext.BidderKargo (copy-paste artifact); should be openrtb_ext.BidderKobler. RunJSONBidderTest does not cross-check the constant, so the test passes despite the wrong identifier."

- type: bidder-constant-mismatch
  file: adapters/kobler/params_test.go
  line: 47
  summary: "validator.Validate called with openrtb_ext.BidderKrushmedia (copy-paste artifact) inside TestInvalidParams; should be openrtb_ext.BidderKobler. The Validate call still rejects all 8 invalid params under the wrong bidder name, so the test passes."
```

Why it matters: both real bugs in master compile, pass tests, and ship — because neither the JSON test runner nor the params validator cross-checks the constant against the bidder name. The warning surfaces these copy-paste artifacts during read so they can be flagged for fix.

> **Cross-reference**: `bidder-constant-mismatch` is also a `quirks[].edge_case_taxon` value — see [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md) "quirks edge_case_taxon (full registry)". When this warning fires, the orchestrator ALSO emits a paired `quirks[]` entry of taxon `bidder-constant-mismatch`.

### `module-major-drift`

**Trigger**: `go.mod` at the resolved commit declares a module path with a major-version suffix differing from the canonical major (`v4` per [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md)).

**Detection**: Step 3 drift check parses the `module github.com/prebid/prebid-server/<vN>` line. If `<vN>` differs from `v4` (or differs from whatever the canonical reference declares), emit warning.

**Example**:

```yaml
- type: module-major-drift
  file: go.mod
  line: 1
  summary: "module path major version changed (canonical=v4 → upstream=v5); reader heuristics may be stale and downstream framework-utilities.md must be updated"
```

Why it matters: an undetected major bump means the readers may misclassify framework helpers (e.g., `adapters.IsResponseStatusCodeNoContent` may have moved or been renamed in v5). The spec is still emitted but downstream consumers should treat the spec as advisory until heuristics are refreshed.

> **Note**: This warning ONLY fires on the top-level `go.mod` declaration. A single adapter file inside a PR diff that imports `prebid-server/v3/...` while master is `v4` is NOT drift — it's the v3→v4 sweep aftermath (see [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) for the canonical note).

### `disabled-bidder-read`

**Trigger**: `bidder_info.disabled: true` in the YAML at the resolved commit.

**Detection**: Step 5 dispatch (read-bidder-info) extracts the `disabled` field. The orchestrator forwards this to `meta.disabled: true` AND emits a paired warning.

**Example**:

```yaml
- type: disabled-bidder-read
  file: static/bidder-info/oldbidder.yaml
  line: null
  summary: "bidder is currently disabled in master (bidder_info.disabled: true); spec captures last known shape but adapter is not active in production"
```

Why it matters: a disabled bidder is still in master (the YAML and code may exist) but is not registered with the auction. Consumers reading a disabled bidder's spec are typically doing archaeology or planning a re-enable; the warning ensures they know.

### `alias-resolution-circular`

**Trigger**: `bidder_info.aliasOf: <parent>` is set AND `static/bidder-params/<xyz>.json` ALSO exists for the alias.

**Detection**: Step 4 alias short-circuit detection AND Step 2 discovery output: if both signals are present, emit warning.

**Example**:

```yaml
- type: alias-resolution-circular
  file: static/bidder-info/childbidder.yaml
  line: null
  summary: "alias declares aliasOf:parentbidder but has its own static/bidder-params/childbidder.json; parent's params would normally apply but the dedicated file overrides at runtime — verify intent"
```

Why it matters: an alias with its own bidder-params JSON is typically unintentional (forgotten to delete during a copy-paste alias creation). At runtime PBS prefers the alias's own params if present, which can cause behavioral divergence from the parent. The warning surfaces this for review.

### `bidder-params-sha-conflict`

**Trigger**: At Step 6 assemble, the orchestrator independently computes `sha256(bidder_params_json)` and asserts it matches the `bidder_params_sha256` reported by `read-bidder-params`. Mismatch → R2 hard error converted to warning AND aborted read.

**Detection**: Step 6 SHA recomputation. If the orchestrator's local sha differs from the reader's sha, this is a serious bug — typically caused by a race condition in the reader or an encoding-conversion error mid-pipeline. Emit warning AND abort with R2 hard error.

**Example**:

```yaml
- type: bidder-params-sha-conflict
  file: static/bidder-params/foo.json
  line: null
  summary: "orchestrator-computed sha256 (abc123...) does not match reader-reported sha256 (def456...) — likely a byte-encoding bug in read-bidder-params; aborting per R2"
```

Why it matters: the cross-language byte-identity contract depends on this SHA being correct. A mismatch means the spec is unreliable for the downstream port-go2java skill. The hard-error abort is intentional — emit the warning AND stop.

### `yaml-field-name-typo`

**Trigger**: A YAML field uses a near-canonical name that PBS silently ignores. Canonical example: `endpointCompression` (camelCase) vs `endpoint-compression` (kebab-case, the form PBS actually parses).

**Detection**: Step 5 dispatch (read-bidder-info) compares each top-level YAML key against the canonical `BidderInfo` field index ([`../../../../review/skills/bidder-info-pr-review/references/field-index.md`](../../../../review/skills/bidder-info-pr-review/references/field-index.md)). Keys that are case-only different from a canonical name are typos — PBS silently ignores them, so the field has no effect at runtime.

**Real bug example** (Ogury):

```yaml
- type: yaml-field-name-typo
  file: static/bidder-info/ogury.yaml
  line: <line of typo>
  summary: "yaml field 'endpointCompression' (camelCase) is silently ignored by PBS; canonical name is 'endpoint-compression' (kebab-case). The compression setting has no effect at runtime."
```

Why it matters: a typo'd YAML field provides false confidence — the YAML LOOKS like compression is enabled but the runtime never sees it. The warning surfaces this for fix.

> **Cross-reference**: this warning is a specific case of the `yaml-field-name-typo` taxon in the quirks edge_case_taxon registry (see [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md)). The warning is the surface; the quirks entry is the structural representation.

### `package-directory-mismatch`

**Trigger**: The Go package name declared in `adapters/<xyz>/<xyz>.go` does NOT match the directory name `<xyz>`.

**Detection**: Step 5 dispatch (read-adapter-code) extracts the package name from the `package` declaration in the primary adapter file. If it differs from the directory name, emit warning.

**Real example** (`33across`):

```yaml
- type: package-directory-mismatch
  file: adapters/33across/33across.go
  line: 1
  summary: "directory name '33across' does not match Go package name 'ttx'; this is the canonical 33across exception (numeric leading character forces a package rename)"
```

Why it matters: most code-generation tools assume package == directory. The mismatch is captured in `code.package_directory_mismatch: true` AND in this warning so consumers don't trip over it.

### `endpoint-placeholder-unresolved`

**Trigger**: `bidder_info.endpoint` contains a `{{.XYZ}}` template placeholder where `XYZ` is NOT in the canonical `macros.EndpointTemplateParams` 22-field list.

**Detection**: Step 6 assemble validates each macro in the endpoint string against the canonical machine-readable list at [`../../shared/endpoint-macros.yaml`](../../shared/endpoint-macros.yaml) (`go_template_macros`; annotated table at [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md)). An unrecognized macro is not a silent runtime degradation — `text/template` cannot resolve the field, so `config.validateAdapterEndpoint` (`config/bidderinfo.go:492-507`) records a config error and `TestBidderInfoFiles` fails.

**Example**:

```yaml
- type: endpoint-placeholder-unresolved
  file: static/bidder-info/foo.yaml
  line: <line of endpoint declaration>
  summary: "endpoint template macro {{.UnknownField}} is not in macros.EndpointTemplateParams (22 fields); template execution fails, so config validation rejects this endpoint"
```

Note: NON-template placeholders (`#{REGION}#`, `${X}`, `<X>`) are NOT macros — they are deploy-time tokens substituted by the operator pre-deployment. Those surface separately under `deploy_time_tokens[]` and require `disabled: true` on the YAML (per the [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) policy).

### `legacy-encoding-json-direct-usage`

**Trigger**: `code.imports.has_jsonutil == false` AND any `Marshal`/`Unmarshal` call from `encoding/json` appears in the adapter code.

**Detection**: Step 5 dispatch (read-adapter-code) scans imports and call sites. Direct `json.Marshal` / `json.Unmarshal` is discouraged (jsonutil offers richer helpers — see [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) Framework Helper Functions table).

**Example**:

```yaml
- type: legacy-encoding-json-direct-usage
  file: adapters/foo/foo.go
  line: 87
  summary: "uses encoding/json.Unmarshal directly; recommended migration to jsonutil.Unmarshal (or jsonutil.UnmarshalValid for stricter validation)"
```

> **Cross-reference**: paired with quirks taxon `legacy-encoding-json-direct-usage` (see [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md)).

### `legacy-test-helpers-imported`

**Trigger**: The adapter test runner does NOT use `RunJSONBidderTest` (the canonical harness) AND/OR imports legacy helpers (`OrtbMockService`, `BidOnTags`, `SampleBid`, `VerifyStringValue`).

**Detection**: Step 5 dispatch (read-adapter-code). `tests.uses_canonical_harness == false` triggers this warning.

**Example**:

```yaml
- type: legacy-test-helpers-imported
  file: adapters/oldbidder/oldbidder_test.go
  line: <line of legacy import>
  summary: "test does not use adapterstest.RunJSONBidderTest (canonical harness); should migrate to JSON-fixture-driven tests"
```

> **Cross-reference**: paired with quirks taxon `legacy-test-helpers-imported`.

### `cross-language-byte-divergence`

**Trigger**: the bidder-params file's digest differs between the Go-side and Java-side specs for the same bidder. The byte-identity contract is per Rule 1 of [`../../shared/port-translation-rules.md`](../../shared/port-translation-rules.md): porters copy bytes verbatim; any whitespace or ordering divergence breaks port-fidelity.

**Detection**: Step 6 cross-check (R5 cross-language structural parity, when a sibling-language spec is locally available). If the orchestrator can resolve the sibling spec, it compares `bidder_params_ref.sha256` and `bidder_params_ref.bytes`; mismatch emits this warning AND a paired `quirks[]` entry. Both sides' numbers must have been measured by their own reader's Step 1 — comparing two transcriptions of the same value proves nothing (V2 in [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md#verbatim-capture-and-computed-values-v1-v4)).

**Real example** (Java side detecting divergence vs Go):

```yaml
- type: cross-language-byte-divergence
  file: src/main/resources/static/bidder-params/elementaltv.json
  line: null
  summary: "JSON byte-content differs from prebid-server-go static/bidder-params/elementaltv.json (whitespace ordering); sha256 mismatch breaks the port-fidelity contract."
```

Why it matters: porters expect the raw JSON to be byte-identical so a single shared `bidder-params/{bidder}.json` can drive both languages. Divergence requires either reformatting one side or accepting a known-broken pair (record in `cross_language.port_concerns`).

> **Cross-reference**: paired with quirks taxon `cross-language-byte-divergence` (see [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md)). Four legacy spellings observed in goldens (`cross-language-bidder-params-byte-divergence`, `bidder-params-byte-divergence-cross-language`, `cross-language-params-sha-divergence`, `cross-language-bytes-divergence`) are all canonicalized to this single name.

---

## Summary table

| Type | File-level or line-level | Hard or soft | Paired quirks taxon |
|---|---|---|---|
| `bidder-constant-mismatch` | line | soft | `bidder-constant-mismatch` |
| `module-major-drift` | line | soft | (none — drift signal) |
| `disabled-bidder-read` | file | soft | (none — meta signal) |
| `alias-resolution-circular` | file | soft | (none — discovery signal) |
| `bidder-params-sha-conflict` | file | hard (R2 abort) | (none — R2 violation) |
| `yaml-field-name-typo` | line | soft | `yaml-field-name-typo` (or `endpoint-compression-typo` for the gzip-compression field specifically) |
| `package-directory-mismatch` | line | soft | (captured in `code.package_directory_mismatch`) |
| `endpoint-placeholder-unresolved` | line | soft | (none — R8 signal) |
| `legacy-encoding-json-direct-usage` | line | soft | `legacy-encoding-json-direct-usage` |
| `legacy-test-helpers-imported` | line | soft | `legacy-test-helpers-imported` |
| `cross-language-byte-divergence` | file | soft | `cross-language-byte-divergence` |

Soft warnings produce a non-empty `provenance.warnings[]` but the spec emits normally. Hard warnings ALSO emit but trigger an abort after the read completes; in practice, the only hard warning is `bidder-params-sha-conflict` (R2 violation).

---

## Warning vs quirk vs hard error: which is which

The spec has three signals for read-time anomalies:

1. **Hard error**: the read aborts; no spec is produced. Reserved for R1 (file not at resolved_commit) and R3 (custom-without-quirks). R2 (sha mismatch) is hard but ALSO emits a warning so the failure mode is documented.
2. **Warning** (`provenance.warnings[]`): the read continues; the spec is emitted. Used for anomalies that are interesting but don't make the spec wrong (typos, copy-paste constants, drift, disabled bidders).
3. **Quirk** (`quirks[]`): a structural classification of the adapter. Used for behavioral oddities that the spec captures correctly but that are worth flagging for downstream consumers (hardcoded constants, multi-file layouts, custom UnmarshalJSON, etc.).

Many warnings have a paired quirk so the same anomaly surfaces in both the read-time signal block AND the structural-classification block. The `bidder-constant-mismatch` real bug example shows this: it surfaces as a `provenance.warnings[]` entry (the read-time signal — "this test file references the wrong constant") AND as a `quirks[]` entry of taxon `bidder-constant-mismatch` (the structural classification — "this adapter has a constant-mismatch behavioral quirk that downstream consumers should know about").

The pairing is informational; consumers can read either block independently.

---

## Warning emission policy

The orchestrator emits warnings using these rules:

1. **De-duplication**: If two checks would emit identical `(type, file, line, summary)` tuples, emit only one. Different lines of the same type/file are emitted separately.
2. **Ordering**: Warnings are emitted in detection order during the workflow. Within a single step, line-anchored warnings are emitted in line-number order.
3. **No suppression**: There is no "ignore this warning" flag. If a check fires, the warning emits. Consumers can filter on `type` after reading the spec.
4. **No interactive prompting**: The orchestrator never asks the user "should I emit this warning?" — read is non-interactive. All emissions are deterministic given the resolved commit (R4 round-trip determinism).
5. **Empty array**: If no warnings fire, `provenance.warnings: []` is emitted (NOT omitted). This is required for schema completeness and so consumers can rely on the field always being present.

---

## Sources

- Phase 2 reconnaissance findings ("Real bugs found during validation"): `kobler_test.go:12` calls `Builder` with `openrtb_ext.BidderKargo`; `params_test.go:47` references `openrtb_ext.BidderKrushmedia` — both pass tests; the spec's `provenance.warnings` block is load-bearing for surfacing these.
- Spec schema: [`../../shared/adapter-spec.md`](../../shared/adapter-spec.md) — `provenance.warnings[]` schema definition (Per-section field reference → `provenance` table → "Warnings schema" subsection); validation rules R1–R10 and which warnings they emit.
- Behavior taxonomy: [`../../shared/behavior-taxonomy.md`](../../shared/behavior-taxonomy.md) — `quirks[].edge_case_taxon` registry (closed list of registered taxa); cross-reference for paired warning↔quirk taxa.
- Endpoint macros (Go): [`../../shared/endpoint-macros.yaml`](../../shared/endpoint-macros.yaml) — canonical machine-readable `EndpointTemplateParams` field set, 22 entries (drives `endpoint-placeholder-unresolved` warning).
- Framework utilities (Go): [`../../../../review/skills/shared/framework-utilities.md`](../../../../review/skills/shared/framework-utilities.md) — annotated `EndpointTemplateParams` table; module-path `v4` major-version reference (drives `module-major-drift`); `jsonutil` package and the recommendation against direct `encoding/json` (drives `legacy-encoding-json-direct-usage`); v3-import-in-PR-diff is NOT drift rule.
- pr-triage routing rules (used to compute file paths cited in warnings): [`../../../../review/skills/pr-triage/references/routing-rules.md`](../../../../review/skills/pr-triage/references/routing-rules.md).
- BidderInfo field index (drives `yaml-field-name-typo` near-canonical-name detection): [`../../../../review/skills/bidder-info-pr-review/references/field-index.md`](../../../../review/skills/bidder-info-pr-review/references/field-index.md).
- Kobler golden (showing both `bidder-constant-mismatch` warnings AND paired quirks): [`../../../test-fixtures/kobler.golden.spec.yaml`](../../../test-fixtures/kobler.golden.spec.yaml).
- Optidigital golden (showing empty `warnings: []`): [`../../../test-fixtures/optidigital.golden.spec.yaml`](../../../test-fixtures/optidigital.golden.spec.yaml).
- prebid-server master: commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (v4.1.0, 2026-04-27).
