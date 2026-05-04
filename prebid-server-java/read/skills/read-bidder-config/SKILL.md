---
name: read-bidder-config
description: Parse prebid-server-java's unified `src/main/resources/bidder-config/{xyz}.yaml` into the Adapter Specification's separated bidder_info block + endpoint config + aliases array. USE WHEN read-bidder-orchestrator dispatches the bidder-config domain, OR when a user wants YAML metadata + alias map + custom fields from one Java unified config file at a resolved commit. Do NOT use for `static/bidder-params/*.json` (read-bidder-params-java), `bidder/*.java` (read-bidder-class), or Go's split `static/bidder-info/*.yaml` (Go-side read-bidder-info — inverse round-trip pair).
version: 1.0.0
---

# read-bidder-config (Java)

## Overview

This skill parses a single `src/main/resources/bidder-config/{xyz}.yaml` file from `prebid/prebid-server-java` at a resolved commit. Unlike Go's `static/bidder-info/{xyz}.yaml` (split, flat), the Java file UNIFIES bidder-info + endpoint + aliases under an `adapters: { xyz: { ... } }` wrapper. This skill produces the canonical Adapter Specification's separated `bidder_info:` block (see [../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../prebid-server-go/read/skills/shared/adapter-spec.md)) — the **inverse operation** of Go's `read-bidder-info` reader: same output shape, different input layout.

The skill:

1. Descends into the `adapters.{xyz}` wrapper (Java's mandatory top-level shape).
2. Splits unified content back into the language-neutral `bidder_info:` fields (endpoint + maintainer + capabilities + geoscope + gvl + usersync + ortb_version + default_enabled + modifying_vast_xml_allowed) per the Adapter Specification schema.
3. Extracts aliases as a `aliases[]` array of children, distinguishing tilde-syntax (`name: ~`) from full-block (`name: { endpoint: "..." }`) per Java edge case #32.
4. Detects the bidder-rename three-step refactor pattern (Java edge case #33): missing-old-yaml + alias-back via tilde + new YAML for the renamed bidder (canonical: Adoppler → ElementalTV via PR #4326).
5. Detects the `endpointCompression` vs `endpoint-compression` typo regression (Java edge case #34): Java's canonical kebab-case is `endpoint-compression`; camelCase is silently ignored. Canonical regression: Ogury PR #3788.
6. Captures custom (operator-supplied) YAML fields (`dev-endpoint`, `platform-id`, `iab-categories`, `extra-info`) under `bidder_info.yaml_extra_fields` so the Spring `BidderConfigurationProperties` subclass detector (`read-bidder-class`) can correlate them.
7. Flags `cross_language.port_concerns.yaml_unification: true` — this skill OWNS that flag because it is the LOAD-BEARING side of Port Translation Rule 34. The Go-side reader sets it as a structural constant; this skill confirms it from observed structure.

The output is a YAML fragment matching the `bidder_info:` schema PLUS an `aliases[]` array PLUS a possible `lifecycle.rename` block; the orchestrator splices each into the assembled spec. (Endpoint construction lives entirely under `bidder_info.endpoint` + `bidder_info.endpoint_construction` — there is no separate `endpoint_config` micro-block.) Cross-language fields populated by this Java reader: `endpoint`, `endpoint_construction`, `endpoint_compression`, `default_enabled`, `modifying_vast_xml_allowed`, `ortb_version`, `maintainer`, `capabilities`, `geoscope`, `gvl_vendor_id`, `user_sync`, `yaml_extra_fields`, `yaml_field_name_quirks`.

For the unification-mapping rules (which Java key maps to which spec field) see [references/yaml-unification-rules.md](references/yaml-unification-rules.md).

## Inputs

- **Primary file**: `src/main/resources/bidder-config/{xyz}.yaml` at the resolved commit (`provenance.source.resolved_commit`). The orchestrator passes the file bytes; this skill does NOT fetch.
- **Bidder name** (`{xyz}`) for cross-checking against `adapters.{xyz}` and for emitting warnings.
- **Optional parent file**: `src/main/resources/bidder-config/{parent}.yaml` if `xyz` is detected as an alias-only and the orchestrator is short-circuiting. The parent provides authoritative endpoint/capabilities the alias inherits.
- **Optional bidder-rename signals** from the orchestrator: list of YAMLs known to exist at the resolved commit. Used to detect the missing-old-yaml side of the rename-three-step refactor (Step 6).

## Workflow

### Step 1: Parse YAML

- Decode the file as YAML. Preserve insertion order of map keys; tilde-syntax detection requires distinguishing YAML `null` (the `~` sigil) from absent, so the parser MUST emit `null` for explicit `~` rather than dropping the key.
- If parsing fails, emit a hard error to the orchestrator with `parse_error` warning type and abort.
- If the top-level structure is NOT `adapters: { xyz: { ... } }`, emit warning type `unified-yaml-shape-violation` and abort. Java unified bidder-config files MUST start with the wrapper.

### Step 2: Descend into `adapters.{xyz}`

The Java unified YAML's mandatory top-level shape is:

```yaml
adapters:
  {xyz}:
    endpoint: "..."
    meta-info:
      maintainer-email: "..."
      vendor-id: 12345
      site-media-types: [...]
      app-media-types: [...]
      dooh-media-types: [...]
    geoscope: [...]
    usersync: ...
    aliases: ...
    # plus per-bidder custom keys
```

The wrapper key MUST equal the bidder filename (e.g., `kobler.yaml` -> `adapters.kobler`). Mismatch is a `bidder-name-wrapper-mismatch` warning.

### Step 3: Extract canonical `bidder_info:` fields

Walk the inner adapter map and apply the unified→canonical field mapping per the table at [references/yaml-unification-rules.md](references/yaml-unification-rules.md) (the canonical home — Java keys, target spec fields, Go-side equivalents, plus the kebab-case-vs-camelCase / structural-flattening / quoting divergences). Per-step reminders for this skill's workflow:

- `aliases:` is NOT a `bidder_info` field — it routes to Step 5 (sibling `aliases[]` block).
- Keys absent from the canonical table flow through Step 8 (`yaml_extra_fields`).
- Edge-case callouts the references doc covers: #29 (`ortb-version` quoting), #30 (`enabled: false` opt-in default-flip), #31 (`modifying-vast-xml-allowed` kebab-case Boolean).
- The kebab-case typo for `endpoint-compression` is detected by Step 7.

Endpoint construction (`bidder_info.endpoint_construction.{kind, macros_used, placeholders_unresolved}`) is classified using the same enum and decision tree as the Go side. The decision tree's structural inputs are language-neutral (literal endpoint string + presence of `{{.X}}` template syntax + presence of `?...` query + presence of `#{X}#` non-Go-template tokens + presence of paired `dev-endpoint:`); the Go reader's [endpoint-classification.md](../../../../prebid-server-go/read/skills/read-bidder-info/references/endpoint-classification.md) enumerates the rules. Apply the same enum here. Java-specific note: when `dev-endpoint:` is present alongside `endpoint:` (canonical: Kobler), classify as `dev-prod-toggle` directly from the YAML — Java promotes the dev URL to YAML config (Kobler PR #3684, Port Translation Rule 13 + Rule 35), unlike Go where the dev URL is typically a hardcoded constant in adapter Go-code.

### Step 4: Classify `endpoint_construction.kind` and detect macros

Apply the same kind enum as the Go reader (9 values per `shared/adapter-spec.md:129`): `static`, `template-macro`, `url-with-query`, `dev-prod-toggle`, `hardcoded-toggle`, `runtime-region-selection`, `deploy-time-token`, `single-token-substitution`, `custom`. Macro extraction follows the per-language convention; the canonical 18-field set lives in [../../../../prebid-server-go/review/skills/shared/framework-utilities.md](../../../../prebid-server-go/review/skills/shared/framework-utilities.md) (Endpoint Template Macros). Append the BARE identifier (no `{{.X}}` wrapper) to `macros_used[]`; capture the delimiter convention separately as `endpoint_construction.macro_syntax`: `java-string-replace` for `{{Identifier}}` form (canonical Java; e.g., ElementalTV `{{AdUnit}}`), `printf` for `%s`-style positional tokens (e.g., 152media `endpoint: "http://pbs.adksrv.com/hb?zone=%s"`), `go-template` for `{{.Identifier}}` form (rare on Java but emit when observed), `null` when `macros_used` is empty, `custom` paired with a `quirks` entry otherwise. Identifiers NOT in the canonical set -> `placeholders_unresolved[]` and warning `endpoint-placeholder-unresolved` (Validation Rule R8). Non-template tokens (`#{X}#`, `${X}`, `<X>`) -> `placeholders_unresolved[]` PLUS spec-top-level `deploy_time_tokens[]` entry; if `enabled: false` is NOT also set, severity is FAIL (Port Translation Rule 15).

Java-side mechanism (`mechanism_java`) is recorded by `read-bidder-class` under `code.make_requests.endpoint_resolution.mechanism_java` — do NOT populate that field here.

### Step 5: Extract `aliases[]`

For each child key inside `adapters.{xyz}.aliases`:

1. Read the value. There are exactly two valid forms:
   - **Tilde-inherit (`name: ~`)**: the YAML value is `null` (the `~` sigil parses to YAML null). The alias inherits all parent fields. Emit `aliases[].config_form: tilde_inherit` (Java edge case #32).
   - **Full-block (`name: { endpoint: "...", ... }`)**: the YAML value is a map. The alias overrides one or more parent fields. Emit `aliases[].config_form: full_block` plus the override fields verbatim under `aliases[].overrides`.
2. Tilde-syntax detection rule: a YAML value `~` parses to **YAML null**. Distinguish from absent (key not present). When `aliases:` is itself absent or empty, emit `aliases: []` (NOT null). When `aliases.<name>` is the YAML null (`~`), emit `config_form: tilde_inherit`. When `aliases.<name>` is a non-null map, emit `config_form: full_block`. Other shapes (scalar string, list) are warnings (`alias-shape-unknown`).
3. Per-alias `aliases[].name` is the child YAML key. Per-alias `aliases[].alias_of` equals the parent (`{xyz}`). Per-alias `aliases[].overrides` is the map of override fields when full-block; absent when tilde-inherit.

The aliases-inversion semantic (Port Translation Rule 33) is owned by the orchestrator — it sets `cross_language.port_concerns.aliases_inverted: true` whenever this skill emits a non-empty `aliases[]`. This skill produces the children-list view from the unified YAML; the Go-side reader produces the inverse child-side view from per-child YAMLs.

Quirk emission: each tilde-inherit alias also emits a `quirks[]` entry with `edge_case_taxon: tilde-alias-syntax` so cross-language porters consuming a Java-source spec are reminded to split the entry into a child YAML when porting to Go.

### Step 6: Detect bidder rename (`lifecycle.rename`)

The bidder-rename three-step refactor (Java edge case #33, canonical: Adoppler → ElementalTV via PR #4326):

1. DELETE old YAML (`bidder-config/{old_name}.yaml` no longer exists).
2. CREATE new YAML (`bidder-config/{new_name}.yaml` exists).
3. ADD alias-back: the new YAML's `aliases:` map carries the old name as a tilde-inherit (`{old_name}: ~`) for backward compatibility.

Detection rule (this skill executes when reading the NEW yaml):

- Iterate `aliases[]` from Step 5 looking for tilde-inherit entries.
- For each tilde-inherit entry (`alias_name`), query the orchestrator's known-YAML registry: does `bidder-config/{alias_name}.yaml` exist at the resolved commit?
  - If YES — it is a normal sibling alias. Skip rename detection for this entry.
  - If NO — it is a candidate alias-back-after-rename. Cross-reference [../../../prebid-server-java/references/new-bid-adapter-prs.md](../../references/new-bid-adapter-prs.md) Pattern Index for the `alias-back-via-tilde` + `bidder-rename-major-version` tags. Confirmed-rename criteria:
    - The PR introducing the new YAML is tagged `bidder-rename-major-version` AND `alias-back-via-tilde`, AND
    - The orchestrator's discovery confirms the old YAML was deleted at the same commit.
- When confirmed, emit:

```yaml
lifecycle:
  rename:
    old_name: <alias_name>
    new_name: <xyz>
    yaml_deletes:
      - src/main/resources/bidder-config/{old_name}.yaml
    yaml_adds:
      - src/main/resources/bidder-config/{xyz}.yaml
    alias_back: true
    package_moves:
      - { from: src/main/java/org/prebid/server/bidder/{old_name}/, to: src/main/java/org/prebid/server/bidder/{xyz}/ }
    fixture_dir_moves:
      - { from: src/test/resources/org/prebid/server/it/openrtb2/{old_name}/, to: src/test/resources/org/prebid/server/it/openrtb2/{xyz}/ }
```

Quirk emission: rename detection adds a `quirks[]` entry with `edge_case_taxon: bidder-rename-three-step` referencing the alias-back-via-tilde pattern.

Edge cases unresolved by this skill:

- Bidder-renames that did NOT use alias-back (e.g., Smarthub → Attekmi rebrand). The skill does NOT detect those from YAML alone; the orchestrator's discovery + git history correlation is required.
- Multi-step renames (A → B → C). The skill detects A → B at one commit and B → C at a later commit but does NOT correlate them.

### Step 7: Detect typo quirks (`yaml_field_name_quirks[]`)

Scan top-level YAML keys (and one level of nesting under `meta-info`) for known typo patterns. The Java canonical typo registry:

| YAML key found | Canonical Java key | Severity | Notes |
|---|---|---|---|
| `endpointCompression` | `endpoint-compression` | FAIL (silent no-op) | Java edge case #34. Java uses kebab-case; camelCase is silently ignored — compression is NOT applied. Canonical regression: Ogury PR #3788. |
| `endpoint-compression` | (canonical) | INFO | Acknowledge canonical form. |
| `modifyingVastXmlAllowed` | `modifying-vast-xml-allowed` | FAIL (silent default) | Same kebab-case-vs-camelCase asymmetry. |
| `gvlVendorID` (on root, not under `meta-info.vendor-id`) | `meta-info.vendor-id` | FAIL (silent default 0) | Go camelCase form bleeding into Java YAML. |
| `dev-endpoint` (no Go canonical) | (Java-specific custom field) | INFO | Acknowledge canonical custom field; correlate with Spring `BidderConfigurationProperties` subclass. |
| `platformId` | `platform-id` | FAIL | Appnexus port residue if found. |

For each typo match, emit:

1. `bidder_info.yaml_field_name_quirks[]` entry: `{ found, canonical, severity, line, summary }`.
2. Warning type `yaml-field-name-typo` (or `endpoint-compression-typo` for the specific compression case) with file:line.
3. Quirks-list entry at the spec top level with `edge_case_taxon: yaml-field-name-typo` (or `endpoint-compression-typo`).

Pass through the typo'd value in `yaml_extra_fields` so round-trip writes preserve byte fidelity. Do NOT silently rename.

### Step 8: Capture custom and unknown fields (`yaml_extra_fields`)

Any YAML key not matched in Steps 3 / 5 / 7 -> `bidder_info.yaml_extra_fields` as a verbatim subtree. Preserve original key (do NOT normalize case or hyphens), original value type, and insertion order.

Common Java custom fields (operator-supplied, mapped to a `BidderConfigurationProperties` subclass — captured cross-skill by `read-bidder-class` under `spring_config.configuration_properties_class.extra_fields[]`):

- `dev-endpoint` (Kobler PR #3684) — second URL for dev/test mode. Promoted from Go-side hardcoded const into Java YAML config (Port Translation Rule 35 — `dev-endpoint-config-promotion` quirk).
- `platform-id` (Appnexus) — partner-supplied platform identifier.
- `iab-categories` (Appnexus) — 120-entry inlined map of IAB category IDs to bidder-internal codes. Captured cross-skill in `iab_category_storage.{storage_kind: yaml-inlined, yaml_field: iab-categories, table_size: 120}`.
- `extra-info` (Huaweiads, NextMillennium) — opaque JSON or nested map for the `ExtraInfo` static nested class.

For each known custom field, emit (additionally) an INFO-level entry under `quirks[]` with `edge_case_taxon: dev-endpoint-config-promotion` (for `dev-endpoint`) so cross-language porters going Java→Go know to either inline the value as a Go const (anti-pattern, surfaces a separate `hardcoded-config-as-anti-pattern` quirk) or pass it through `extra_info` JSON in Go's `static/bidder-info/{xyz}.yaml`.

### Step 9: Flag `cross_language.port_concerns.yaml_unification: true`

This flag is OWNED by this skill (Java is the load-bearing side of Port Translation Rule 34 — the Java unified YAML is what Go's split YAML must merge into; the asymmetry surfaces here).

- Always emit `cross_language.port_concerns.yaml_unification: true` for every Java-source spec.
- The Go-side reader (`read-bidder-info`) also emits this flag for round-trip awareness, but Go's value is a structural constant (Go ALWAYS splits, Java ALWAYS unifies). This skill confirms it from observed structure: YAML starts with `adapters: { xyz: { ... } }` wrapper.
- Emit `cross_language.port_concerns.aliases_inverted: true` if Step 5 emitted any `aliases[]` entry; otherwise emit `false`.

The `port-go2java/` skill consumes the Go spec's `yaml_unification: false` and merges Go's split (info file + main config) into a Java unified file. The `port-java2go/` skill consumes the Java spec's `yaml_unification: true` and splits the Java unified file back into Go's flat info file + alias child files.

## Edge case mapping

This skill covers the following Java edge cases Java-specific cases #29-#34:

| Edge case | Plan ref | Captured by |
|---|---|---|
| `ortb-version: "2.6"` quoted-string field | Java #29 | Step 3 — preserve as string, not float |
| `enabled: false` opt-in default | Java #30 | Step 3 — flips `bidder_info.default_enabled` to false |
| `modifying-vast-xml-allowed: true` | Java #31 | Step 3 — emits `bidder_info.modifying_vast_xml_allowed: true` |
| Tilde-syntax aliases (`name: ~`) vs full-block | Java #32 | Step 5 — `aliases[].config_form: tilde_inherit \| full_block` |
| Bidder rename three-step refactor | Java #33 | Step 6 — `lifecycle.rename` block + `alias_back: true` |
| `endpointCompression` vs `endpoint-compression` typo | Java #34 | Step 7 — `bidder_info.yaml_field_name_quirks[]` + `endpoint-compression-typo` quirk |

Edge cases owned by OTHER skills (do not duplicate):

- Spring DI / `BidderConfigurationProperties` subclass / IAB-categories-inline (Java #18-#21) -> `read-bidder-class`.
- Class-name identifier workarounds / TitleCase acronym preservation (Java #26-#27) -> `read-bidder-class`.
- `Bidder<T>` generic for custom payloads (Java #28) -> `read-bidder-class`.
- 4-file IT fixture pattern + per-alias IT class (Java #23-#24) -> `read-bidder-class`.
- `test-application.properties` registry append (Java #25) -> orchestrator.
- Bidder-params JSON Schema and ext POJO (cross-language) -> `read-bidder-params-java`.
- Go's split `static/bidder-info/{xyz}.yaml` parsing -> Go's `read-bidder-info`.

## Cross-language note

Java's unified `src/main/resources/bidder-config/{xyz}.yaml` corresponds to Go's split:

- `static/bidder-info/{xyz}.yaml` (the bidder-info subset of the unified file).
- The main Go config (the `endpoint:` field overlap).
- A chain of per-child alias files (`static/bidder-info/{child}.yaml` with `aliasOf: parent`).

Round-trip semantics:

- A Go-source spec carries `cross_language.port_concerns.yaml_unification: false`. The `port-go2java/` skill consumes this flag, merges Go's split into a single Java unified YAML, and inverts the alias chain (Go child→parent into Java parent→children — Port Translation Rule 33).
- A Java-source spec carries `cross_language.port_concerns.yaml_unification: true` (this skill emits it). The `port-java2go/` skill consumes this flag, splits the Java unified YAML into Go's flat info file + per-alias child files.

Other structural divergences (Port Translation Rule 34): Java's `meta-info.{site,app,dooh}-media-types` flattens what Go nests under `capabilities.{site|app|dooh}.mediaTypes`. Java's kebab-case (`endpoint-compression`) vs Go's camelCase (`endpointCompression`). Java's `aliases:` parent-block vs Go's `aliasOf:` child-field. The `bidder_info:` block this skill emits is the cross-language-canonical normalization — both Go and Java specs MUST agree on the field shapes (Validation Rule R5).

## Verification

Verified against the Java Kobler golden ([`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml)). Kobler's expected `bidder_info`: `endpoint_construction.kind: dev-prod-toggle` + `dev-endpoint` in `yaml_extra_fields`; `endpoint_compression: gzip`; `default_enabled: true`; `modifying_vast_xml_allowed: false`; `capabilities.{site,app}.mediaTypes: [banner]`; `geoscope: [NOR, SWE, DNK]`; `gvl_vendor_id: 0`; `yaml_field_name_quirks: []`. Aliases empty (parent); `lifecycle.rename` absent. `cross_language.port_concerns.yaml_unification: true` (always for Java); `aliases_inverted: false` (no aliases).

R4 (round-trip determinism): re-running on the same YAML bytes MUST produce byte-identical blocks (modulo timestamp). R5 (cross-language structural parity): Go-source and Java-source MUST agree on `capabilities`, `gvl_vendor_id`, `maintainer.email`. Multi-alias parents (Limelight family, Adkernel family) emit one `aliases[]` entry per child with `config_form: tilde_inherit`. ElementalTV (PR #4326) emits the `aliases[]` alias-back entry for `adoppler` AND a `lifecycle.rename` block (with `subtype: bilateral` per ADR-006) AND a `bidder-rename-three-step` quirk.

## Sources

- Schema (canonical): [`../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json`](../../../../prebid-server-go/read/skills/shared/adapter-spec.schema.json), [`../../../../prebid-server-go/read/skills/shared/adapter-spec.md`](../../../../prebid-server-go/read/skills/shared/adapter-spec.md). Owns: `bidder_info`, `aliases[].config_form`, `lifecycle.rename`, `yaml_field_name_quirks[]`, `cross_language.port_concerns.yaml_unification`.
- Taxonomy: [`../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`](../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.yaml) — `tilde-alias-syntax`, `bidder-rename-three-step`, `endpoint-compression-typo`, `yaml-field-name-typo`, `dev-endpoint-config-promotion` taxa.
- Port rules: [`../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) — this skill is the LOAD-BEARING side for Rules 33 (alias inversion), 34 (YAML unification), 35 (config-subclass), plus 11–15 (endpoint resolution) and 13 (dev-prod toggle).
- Java edge cases #29–#34: [`../../../references/java-edge-cases.md`](../../../references/java-edge-cases.md). Java reference PRs (35 full + 14 alias-only): [`../../../references/new-bid-adapter-prs.md`](../../../references/new-bid-adapter-prs.md). Canonical exemplars: Kobler PR #3684, Optidigital PR #4054, FeedAd PR #3869, Mediasquare PR #4031, Ogury PR #3788, 152media PR #3829, ElementalTV PR #4326.
- Sibling Go skill (inverse round-trip): [`../../../../prebid-server-go/read/skills/read-bidder-info/SKILL.md`](../../../../prebid-server-go/read/skills/read-bidder-info/SKILL.md) + endpoint classification decision tree at [`../../../../prebid-server-go/read/skills/read-bidder-info/references/endpoint-classification.md`](../../../../prebid-server-go/read/skills/read-bidder-info/references/endpoint-classification.md).
- Local: [`references/yaml-unification-rules.md`](references/yaml-unification-rules.md). Golden: [`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml).
