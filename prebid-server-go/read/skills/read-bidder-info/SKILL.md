---
name: read-bidder-info
description: Parses Go prebid-server `static/bidder-info/{xyz}.yaml` and emits the `bidder_info:` block of the canonical Adapter Specification. USE WHEN the orchestrator (read-adapter-orchestrator) dispatches the bidder-info domain for a Go adapter, OR when a user wants to extract the YAML metadata block from a single bidder-info file at a resolved commit. Do NOT use for `static/bidder-params/*.json` (read-bidder-params owns that), `adapters/*.go` (read-adapter-code), or Java's unified `bidder-config/{xyz}.yaml` (the Java sibling skill `read-bidder-config` owns that).
version: 1.0.0
---

# read-bidder-info (Go)

## Overview

This skill parses a single `static/bidder-info/{xyz}.yaml` file from `prebid/prebid-server` (Go) at a resolved commit and produces the `bidder_info:` block of the canonical Adapter Specification (see [../shared/adapter-spec.md](../shared/adapter-spec.md)). The skill:

1. Recognizes every canonical `BidderInfo` Go-struct field — full list mastered in [../../../review/skills/bidder-info-pr-review/references/field-index.md](../../../review/skills/bidder-info-pr-review/references/field-index.md). This skill REUSES that index; it does NOT re-list the fields.
2. Classifies the endpoint URL into a deterministic `endpoint_construction.kind` enum.
3. Detects `EndpointTemplateParams` macro usage — the canonical 18-field set lives in [../../../review/skills/shared/framework-utilities.md](../../../review/skills/shared/framework-utilities.md) (Endpoint Template Macros section). Do NOT re-enumerate.
4. Detects deploy-time placeholder tokens (`#{REGION}#`) distinct from runtime macros.
5. Detects YAML field-name typo regressions (`endpointCompression` vs `endpoint-compression`).
6. Preserves unknown YAML keys verbatim under `yaml_extra_fields` so round-trip writes can reconstruct the file byte-for-byte.

The output is a YAML fragment matching the `bidder_info:` schema; the orchestrator splices it into the assembled spec. Cross-language fields populated by this Go reader: `endpoint`, `endpoint_construction`, `endpoint_compression`, `default_enabled`, `modifying_vast_xml_allowed`, `ortb_version` (always null on Go — see Step 2), `maintainer`, `capabilities`, `geoscope`, `gvl_vendor_id`, `user_sync` (Go layout, verbatim), `yaml_extra_fields`, `yaml_field_name_quirks`.

## Inputs

- **File path**: `static/bidder-info/{xyz}.yaml` at the resolved commit (`provenance.source.resolved_commit`). The orchestrator passes the file bytes; this skill does NOT fetch.
- **Bidder name** (`{xyz}`) for cross-checking and for emitting warnings.
- **Optional**: previous-pass spec fragment (for round-trip determinism testing). Ignored for the primary read.

## Workflow

### Step 1: Parse YAML

- Decode the file as YAML. Preserve insertion order of map keys (most YAML libraries do by default; if not, fall back to a streaming pass that records key order — `yaml_extra_fields` requires order preservation for round-trip determinism per Validation Rule R4).
- If parsing fails, emit a hard error to the orchestrator with `parse_error` warning type and abort the bidder_info read for this bidder.

### Step 2: Extract canonical fields

Walk the parsed YAML and map each known top-level key to the spec field. The canonical key list and Go-struct mapping is mastered at [../../../review/skills/bidder-info-pr-review/references/field-index.md](../../../review/skills/bidder-info-pr-review/references/field-index.md). For each canonical key found, emit the corresponding spec field:

- `endpoint` -> `bidder_info.endpoint` (string).
- `endpointCompression` -> `bidder_info.endpoint_compression` (string; expected canonical value `"GZIP"` uppercase per `exchange/bidder.go` constant — silently fails compression if any other casing).
- `disabled` (bool) -> `meta.disabled` is OWNED by the orchestrator's `meta` block (NOT this skill); but if present in this YAML, surface here so the orchestrator can read it. Do NOT emit a `disabled` field under bidder_info — there is no such path in the schema; emit only via meta.
- `whiteLabelOnly` -> same handling as `disabled`: orchestrator reads it from this skill's pass-through.
- `modifyingVastXmlAllowed` (bool) -> `bidder_info.modifying_vast_xml_allowed`. Default `false` if absent.
- `aliasOf` -> orchestrator reads it for `meta.alias_of` and the alias short-circuit. Pass-through.
- `extra_info` (string-encoded JSON) -> orchestrator reads it; pass-through.
- `openrtb.version` -> `bidder_info.ortb_version`. **Cross-language note**: in Go YAML the key is `openrtb.version`. The Adapter Spec field is `ortb_version`. Go YAMLs typically do NOT declare it (Optidigital's golden does, in `yaml_extra_fields.openrtb.version: 2.6`); when absent emit `null`. The Java side declares `ortb-version: "2.6"` quoted — that's a Java-specific edge case. Per the spec doc, the Go side may emit either:
  - Top-level `bidder_info.ortb_version` if `openrtb.version` is structurally present, OR
  - Pass it through `yaml_extra_fields.openrtb.version` when the original YAML uses the `openrtb:` nested block (the Optidigital golden shows this style).
  Use whichever style preserves the original YAML structure for round-trip. Default policy: if `openrtb` is a nested map, preserve as `yaml_extra_fields.openrtb.*` and leave top-level `ortb_version: null`.
- `enabled` (bool) -> `bidder_info.default_enabled`. Default `true` if absent. (Java's opt-in `enabled: false` for Optidigital/Adverxo aliases is a Java-specific edge case — Go YAML does not typically use this key.)
- `maintainer` -> `bidder_info.maintainer` (verbatim subtree, expected `{ email: <string> }`).
- `capabilities` -> `bidder_info.capabilities` (see Step 6).
- `geoscope` -> `bidder_info.geoscope` (list of 3-letter ISO 3166-1 alpha-3 country codes / `GLOBAL` / `EEA` / `!`-prefixed negations).
- `gvlVendorID` -> `bidder_info.gvl_vendor_id` (uint16; emit `0` as `0`, not `null`).
- `userSync` -> `bidder_info.user_sync` (see Step 7).
- `experiment.adsCert.enabled`, `xapi.{username,password,tracker}`, `platform_id`, `app_secret`, `debug.allow` -> recognized canonical fields; emit under their normalized field names. `xapi.password` and `app_secret` MUST NOT be sniffed for content beyond presence flagging.

Any OTHER top-level key (or unrecognized nested key under a recognized parent) -> Step 9 (`yaml_extra_fields`).

### Step 3: Classify `endpoint_construction.kind`

Apply the deterministic decision tree at [references/endpoint-classification.md](references/endpoint-classification.md). Output one of: `static`, `template-macro`, `url-with-query`, `dev-prod-toggle`, `hardcoded-toggle`, `runtime-region-selection`, `deploy-time-token`, `custom`.

This is the SEMANTIC classification (cross-language). The Go-specific implementation mechanism (`text/template`, `macros.NewStringIndexBasedReplacer`, `string-concat`, `net/url`) is recorded by `read-adapter-code` under `code.make_requests.endpoint_resolution.mechanism_go` — do NOT populate that field here.

The decision tree's primary inputs are:

- The literal `endpoint:` string from the YAML.
- Whether the string contains any `{{.X}}` Go-template syntax.
- Whether the string contains query params (`?...`).
- Whether the string contains non-Go-template placeholders (`#{X}#`, `${X}`, `<X>`).
- Whether the YAML declares `extra_info` or whether `disabled: true` is paired.

Note: this skill only reads the YAML. Detection of patterns that require adapter-Go code (e.g., `dev-prod-toggle` toggling between `endpoint` and a hardcoded `devEndpoint` constant) is INFERRED from YAML signals (presence of a paired `dev-endpoint:` field, presence of `extra_info` carrying a second URL). When YAML alone is insufficient, the kind defaults to `static` and this skill emits an `endpoint_construction_inference_incomplete` warning so the orchestrator can re-classify after `read-adapter-code` runs. The orchestrator owns the final reconciliation under spec Validation Rule R3 (no invented fields).

### Step 4: Detect macros (`endpoint_construction.macros_used[]` + `macro_syntax`)

- Regex-extract every `{{.<Identifier>}}` substring from the `endpoint:` string.
- For each captured identifier, check membership against the canonical 18-field set documented at [../../../review/skills/shared/framework-utilities.md](../../../review/skills/shared/framework-utilities.md) (Endpoint Template Macros section — fields: `Host`, `PublisherID`, `ZoneID`, `SourceId`, `AccountID`, `AdUnit`, `MediaType`, `GvlID`, `PageID`, `SupplyId`, `ImpID`, `SspId`, `SspID`, `SeatID`, `TokenID`, `PartnerId`, `Region`, `PlacementID`).
- Identifiers in the canonical 18-field list -> append the BARE identifier (no `{{.X}}` wrapper) to `endpoint_construction.macros_used[]`. The delimiter convention is captured separately via `endpoint_construction.macro_syntax`.
- Identifiers NOT in the canonical 18-field list -> append the bare identifier to `endpoint_construction.placeholders_unresolved[]` AND emit warning of type `endpoint-placeholder-unresolved` (Validation Rule R8). These will silently resolve to empty string at runtime.
- Set `endpoint_construction.macro_syntax`:
  - `go-template` when the source endpoint uses `{{.Identifier}}` form (Go canonical) — applies to all Go-source specs.
  - `null` when `macros_used` is empty.
  - (Java-source specs additionally use `java-string-replace` for `{{Identifier}}` form, `printf` for `%s`-style positional, `custom` paired with a `quirks` entry; these only surface in `read-bidder-config`.)

Note: `{{.ExternalURL}}` and other user-sync template fields are NOT endpoint macros — if found in `endpoint:`, they are unresolved (R8).

### Step 5: Detect non-template tokens

Scan the `endpoint:` string (and any URL-typed sub-field of `userSync`) for non-Go-template placeholder syntax:

- `#{X}#` (canonical: Rubicon `REGION`).
- `${X}` (shell-style).
- `<X>` (angle-bracket).

For each match:

1. Append to `endpoint_construction.placeholders_unresolved[]` (so the porter sees them).
2. Append a `deploy_time_tokens[]` entry at the SPEC top level: `{ token: <captured-name>, file: static/bidder-info/{xyz}.yaml, notes: "operator substitutes pre-deployment" }`. The orchestrator splices this into the assembled spec — this skill emits the entry inline next to the bidder_info block under a sibling key the orchestrator picks up.
3. Set `endpoint_construction.kind: deploy-time-token` (overrides any earlier classification from Step 3).
4. If `disabled: true` is NOT also set in the YAML, emit warning type `endpoint-placeholder-unresolved` with severity FAIL — per the convention from PR #4502 (appStockSSP), unresolved deploy-time tokens REQUIRE `disabled: true`.

### Step 6: Extract capabilities

The `capabilities:` block has up to three sub-blocks: `site`, `app`, `dooh`. Each contains a `mediaTypes` list. Valid mediaTypes per the field index: `banner`, `video`, `native`, `audio`.

Emit:

```yaml
bidder_info:
  capabilities:
    site: { mediaTypes: [...] }   # Only if site declared in YAML.
    app:  { mediaTypes: [...] }   # Only if app declared.
    dooh: { mediaTypes: [...] }   # Only if dooh declared.
```

Omit any sub-block not present in the YAML — do not synthesize empty platforms.

If a mediaType value is NOT in the four-valid set, emit warning type `invalid-media-type` and include the offending value in the warning summary; still emit it under spec field for round-trip fidelity (the orchestrator will surface the warning).

### Step 7: Extract usersync block verbatim

The `userSync:` block in Go YAML has a known shape mastered in the field index. This skill emits the entire `userSync:` subtree VERBATIM under `bidder_info.user_sync` — preserving:

- Key order.
- All sub-fields: `key`, `supports`, `iframe.{url, redirectUrl, externalUrl, userMacro}`, `redirect.{url, redirectUrl, externalUrl, userMacro}`, `externalUrl`, `formatOverride`, `enabled`, `skipwhen.{gdpr, gpp_sid}`.
- Macro substrings inside URL values are NOT expanded — emit them as-is.

If the YAML has no `userSync:` block, emit `bidder_info.user_sync: {}` (empty map, NOT null — for round-trip determinism).

Per Step 5, scan all URL-typed sub-fields of userSync for deploy-time tokens — they're rare in user-sync URLs but still possible.

### Step 8: Detect typo quirks (`yaml_field_name_quirks[]`)

Scan ALL top-level YAML keys (and one level of nesting under canonical parents) and check for known typo patterns. The canonical typo registry:

| YAML key found | Canonical Go key | Severity | Notes |
|---|---|---|---|
| `endpoint-compression` | `endpointCompression` | FAIL (silent no-op) | Java uses kebab-case (`endpoint-compression`); Go uses camelCase. Go reading kebab-case silently ignores the field — compression is NOT applied. Canonical regression: Ogury. |
| `dev-endpoint` | (no Go canonical; promoted-to-config in Java only) | INFO | Java declares `dev-endpoint:` in unified `bidder-config/{xyz}.yaml`. If found in a Go file, it's a port-fidelity remnant — preserve in `yaml_extra_fields` and surface as `dev-endpoint` quirk. |
| `modifying-vast-xml-allowed` | `modifyingVastXmlAllowed` | FAIL (silent default) | Java kebab-case form; Go camelCase. Same silent-ignore semantics. |
| `gvl-vendor-id` | `gvlVendorID` | FAIL (silent default 0) | Java kebab-case form. |
| `meta-info` | (no Go canonical; Java-specific top-level key) | INFO | Java unified-config block name; if found in Go, it's a Java port residue. |

For each typo match, emit:

1. `yaml_field_name_quirks[]` entry: `{ found: <found-key>, canonical: <canonical-key>, severity: <FAIL|WARN|INFO>, line: <yaml-line-number>, summary: <short-text> }`.
2. Warning type `yaml-field-name-typo` with file:line and summary.
3. Quirks-list entry at the spec top level with `edge_case_taxon: yaml-field-name-typo` (or `endpoint-compression-typo` for the specific endpointCompression case — see [../shared/behavior-taxonomy.md](../shared/behavior-taxonomy.md) for the registry).

Pass through the typo'd value in `yaml_extra_fields` so round-trip writes preserve byte fidelity. Do NOT silently rename it to the canonical form.

### Step 9: Capture unknown fields (`yaml_extra_fields`)

Any YAML key not matched in Steps 2 / 3 / 6 / 7 / 8 -> `bidder_info.yaml_extra_fields` as a verbatim subtree. Preserve:

- Original key (do NOT normalize case or hyphens).
- Original value type (string vs int vs bool vs nested map vs list).
- Insertion order.

This is the round-trip determinism contract (Validation Rule R4). The future `write/` skill reconstructs the YAML byte-for-byte by re-emitting `yaml_extra_fields` in original order alongside the canonical fields.

The Optidigital golden's `yaml_extra_fields: { openrtb: { version: 2.6 } }` is the canonical example — `openrtb` is a recognized canonical parent (per field index), but the Go reader chose to preserve its nested layout rather than flatten to top-level `ortb_version`.

## Edge case mapping

The full Go edge-case catalog is in (Claude Code planning artifact). This skill covers:

| Edge case | Plan ref | Captured by |
|---|---|---|
| Three endpoint construction routes (static, template-macro, custom-toggle) | Go #10 | `bidder_info.endpoint_construction.kind` (Step 3) |
| EndpointTemplateParams macro field usage | Go #16 | `endpoint_construction.macros_used[]` (Step 4); subset of the canonical 18-field set |
| Deploy-time tokens (`#{REGION}#`) | Cross-language | `endpoint_construction.placeholders_unresolved[]` + spec-top-level `deploy_time_tokens[]` (Step 5) |
| `endpoint-compression` typo regression | Java #34 / Cross-language | Step 8 typo registry |
| `default_enabled` (Java opt-in pattern) | Java #30 | Step 2 emits `bidder_info.default_enabled` (Go YAMLs typically never trigger this; default `true`) |
| `modifying_vast_xml_allowed` | Java #31 | Step 2 emits `bidder_info.modifying_vast_xml_allowed` |
| `ortb_version` quoted-string field | Java #29 | Step 2 — Go side typically null; preserved in `yaml_extra_fields` if `openrtb:` block is nested |

Edge cases owned by OTHER skills (do not duplicate):

- Adapter Go-code patterns (Go #1-9, #11-15, #17) -> `read-adapter-code`.
- Bidder-params JSON Schema and ext struct (Go #17 partial) -> `read-bidder-params`.
- Java unified `bidder-config/{xyz}.yaml` parsing -> Java's `read-bidder-config`.
- Spring DI / `BidderConfigurationProperties` subclass -> Java's `read-bidder-class`.

## Cross-language note

Go's `static/bidder-info/{xyz}.yaml` corresponds to a SUBSET of Java's unified `src/main/resources/bidder-config/{xyz}.yaml`. The Java unified file additionally contains:

- The endpoint URL (Go has it here too — overlap).
- Aliases as a child map under the parent (Go INVERTS this — child files reference parent via `aliasOf:`).
- Spring `BidderConfigurationProperties` subclass extra fields (Go uses `extra_info:` opaque JSON instead).
- IAB categories inlined (Go uses a separate `.go` data file).

This skill emits `cross_language.port_concerns.yaml_unification: true` for every Go bidder (the asymmetry is structural, applies always). The Java sibling reader (`read-bidder-config`) is responsible for the inverse split — taking the Java unified file and producing the same `bidder_info:` block plus an endpoint config plus an aliases map. Reference: Port Translation Rule 34 (YAML unification) at [../shared/port-translation-rules.md](../shared/port-translation-rules.md).

Aliases inversion (Port Rule 33): if this YAML contains `aliasOf:`, the orchestrator emits `cross_language.port_concerns.aliases_inverted: true`. This skill passes through the `aliasOf` value; the orchestrator handles the cross-language semantics.

## Verification

The skill is verified against two golden specs:

- **Optidigital** ([../../test-fixtures/optidigital.golden.spec.yaml](../../test-fixtures/optidigital.golden.spec.yaml)) — clean baseline. Expected `bidder_info` keys: `endpoint` (`https://pbs.optidigital.com/bidder/openrtb2`), `endpoint_construction.kind: static`, `endpoint_compression: gzip`, `default_enabled: true`, `modifying_vast_xml_allowed: false`, `ortb_version: null` (preserved in `yaml_extra_fields.openrtb.version: 2.6`), capabilities for site/app/dooh banner-only, `geoscope: []`, `gvl_vendor_id: 915`, full `user_sync` iframe block, `yaml_extra_fields.openrtb.version: 2.6`, empty `yaml_field_name_quirks`.
- **Kobler** ([../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml)) — port pair example. Expected `bidder_info` keys: `endpoint` (Kobler URL), `endpoint_construction.kind: dev-prod-toggle` (note: classifying this as `dev-prod-toggle` from YAML alone requires Step 3's "incomplete inference" handling; the orchestrator may upgrade after `read-adapter-code` confirms the Go const + toggle), `endpoint_compression: gzip`, capabilities site/app banner-only, `geoscope: [NOR, SWE, DNK]`, `gvl_vendor_id: 0`, empty `user_sync`, empty `yaml_extra_fields`, empty `yaml_field_name_quirks`.

Round-trip determinism (Validation Rule R4): re-running this skill on the same YAML bytes produces a `bidder_info` block idempotent under round-trip (`yaml.safe_load → safe_dump` is byte-stable). Byte-identical reproduction is the target; R4 enforces idempotency.

Cross-language structural parity (Validation Rule R5): for any bidder present in both Go and Java repos, the `bidder_info.capabilities`, `bidder_info.gvl_vendor_id`, and `bidder_info.maintainer.email` fields MUST match between the Go-source and Java-source specs.

## How to test this skill

```
# Smoke-test against Kobler at a known commit.
read-adapter-orchestrator --bidder=kobler --source-mode=local --format=yaml | yq .bidder_info

# Expected: endpoint matches Kobler URL, endpoint_construction.kind=dev-prod-toggle (or static
# with incomplete-inference warning, depending on adapter-code reconciliation),
# endpoint_compression=gzip, capabilities.{site,app}.mediaTypes==[banner], geoscope=[NOR, SWE, DNK].
```

```
# Smoke-test typo detection: feed a YAML with `endpoint-compression: gzip` (kebab-case).
read-adapter-orchestrator --bidder=ogury-typo-test --source-mode=local --format=yaml | yq .bidder_info.yaml_field_name_quirks
# Expected: one entry with found=endpoint-compression, canonical=endpointCompression, severity=FAIL.
```

## Sources

- Plan: (Claude Code planning artifact) (Phase B — read-bidder-info).
- Schema: [../shared/adapter-spec.md](../shared/adapter-spec.md) (`bidder_info:` section, including `endpoint_construction`, `capabilities`, `geoscope`, `gvl_vendor_id`, `user_sync`, `yaml_extra_fields`, `default_enabled`, `modifying_vast_xml_allowed`, `ortb_version`, `yaml_field_name_quirks[]`).
- Taxonomy: [../shared/behavior-taxonomy.md](../shared/behavior-taxonomy.md) (the `quirks edge_case_taxon` registry — `yaml-field-name-typo`, `endpoint-compression-typo`).
- Port translation rules: [../shared/port-translation-rules.md](../shared/port-translation-rules.md) (Rule 34 — YAML unification asymmetry; Rule 14 / Rule 11–15 — endpoint resolution; Rule 33 — aliases inversion).
- Field index (master truth for `BidderInfo` Go struct): [../../../review/skills/bidder-info-pr-review/references/field-index.md](../../../review/skills/bidder-info-pr-review/references/field-index.md). REUSED — not duplicated.
- Framework utilities (master truth for `EndpointTemplateParams` 18-field list, deploy-time-token policy, endpointCompression case-sensitivity): [../../../review/skills/shared/framework-utilities.md](../../../review/skills/shared/framework-utilities.md). REUSED — not duplicated.
- Sibling review skill: [../../../review/skills/bidder-info-pr-review/SKILL.md](../../../review/skills/bidder-info-pr-review/SKILL.md).
- Endpoint classification decision tree: [references/endpoint-classification.md](references/endpoint-classification.md).
- Golden specs:
  - [../../test-fixtures/optidigital.golden.spec.yaml](../../test-fixtures/optidigital.golden.spec.yaml).
  - [../../test-fixtures/kobler.golden.spec.yaml](../../test-fixtures/kobler.golden.spec.yaml).
