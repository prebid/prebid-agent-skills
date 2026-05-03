# YAML Unification Rules (Java unified `bidder-config/{xyz}.yaml`)

How to split Java's unified `src/main/resources/bidder-config/{xyz}.yaml` back into the language-neutral `bidder_info:` block plus an `aliases[]` array plus optional `lifecycle.rename`. This is the inverse operation of Go's `read-bidder-info` reader (which reads from a flat `static/bidder-info/{xyz}.yaml`). The output schema is identical to Go's; the input layout differs.

This file documents the field-by-field mapping rules consumed by `SKILL.md` Steps 2–5, the tilde-syntax detection rule (Step 5), the bidder-rename detection pattern (Step 6), the typo registry (Step 7), and the custom-field passthrough convention (Step 8).

---

## Top-level structure (mandatory wrapper)

Java unified bidder-config files MUST start with the `adapters:` wrapper:

```yaml
adapters:
  {xyz}:
    endpoint: "..."
    meta-info: { ... }
    geoscope: [...]
    usersync: { ... }
    aliases: { ... }
    # optional custom keys (dev-endpoint, platform-id, iab-categories, ...)
```

The wrapper key MUST equal the bidder filename stem (e.g., `kobler.yaml` -> `adapters.kobler`). Mismatch -> warning `bidder-name-wrapper-mismatch`. A YAML that does NOT start with `adapters:` -> hard error `unified-yaml-shape-violation`. A YAML that has multiple sibling adapters under `adapters:` -> warning `multi-bidder-yaml`; the skill processes only `adapters.{xyz}` and skips siblings.

Compare to Go: Go's `static/bidder-info/{xyz}.yaml` is a flat top-level map (no wrapper). The asymmetry surfaces as Port Translation Rule 34 (yaml_unification).

---

## Field mapping table (cross-language canonical)

Maps each Java unified key to the corresponding canonical Adapter Specification field. The third column shows the Go-side equivalent for cross-language porters.

| Java key path (under `adapters.{xyz}`) | Spec field | Go equivalent (under top-level) |
|---|---|---|
| `endpoint` | `bidder_info.endpoint` | `endpoint` |
| `endpoint-compression` | `bidder_info.endpoint_compression` | `endpointCompression` |
| `meta-info.maintainer-email` | `bidder_info.maintainer.email` | `maintainer.email` |
| `meta-info.vendor-id` | `bidder_info.gvl_vendor_id` | `gvlVendorID` |
| `meta-info.site-media-types` | `bidder_info.capabilities.site.mediaTypes` | `capabilities.site.mediaTypes` |
| `meta-info.app-media-types` | `bidder_info.capabilities.app.mediaTypes` | `capabilities.app.mediaTypes` |
| `meta-info.dooh-media-types` | `bidder_info.capabilities.dooh.mediaTypes` | `capabilities.dooh.mediaTypes` |
| `geoscope` | `bidder_info.geoscope` | `geoscope` |
| `usersync` | `bidder_info.user_sync` | `userSync` |
| `enabled` | `bidder_info.default_enabled` | `enabled` (rare in Go) |
| `modifying-vast-xml-allowed` | `bidder_info.modifying_vast_xml_allowed` | `modifyingVastXmlAllowed` |
| `ortb-version` | `bidder_info.ortb_version` | `openrtb.version` (nested) |
| `aliases` | top-level sibling `aliases[]` array | (none — Go uses `aliasOf` on each child) |
| `dev-endpoint` | `bidder_info.yaml_extra_fields.dev-endpoint` | (none — Go inlines as const or `extra_info`) |
| `platform-id` | `bidder_info.yaml_extra_fields.platform-id` | (none — Go uses `platform_id` flat key) |
| `iab-categories` | `bidder_info.yaml_extra_fields.iab-categories` (full map) | (none — Go uses `iab_categories.go` data file) |
| `extra-info` | `bidder_info.yaml_extra_fields.extra-info` | `extra_info` (string-encoded JSON) |

**Naming convention divergence**: Java uses **kebab-case** for canonical YAML keys (`endpoint-compression`, `meta-info.vendor-id`, `modifying-vast-xml-allowed`); Go uses **camelCase** (`endpointCompression`, `gvlVendorID`, `modifyingVastXmlAllowed`). This is the primary surface for Port Translation Rule 34 (YAML unification + casing convention divergence).

**Structural flattening divergence**: Java's `meta-info.{site,app,dooh}-media-types` are FLAT lists keyed by platform-suffix; Go nests under `capabilities.{site|app|dooh}.mediaTypes`. The reader produces the Go-shaped output (under `capabilities`) regardless of input layout — the spec's `bidder_info.capabilities` field is the cross-language canonical normalization.

**`ortb-version` quoting** (Java edge case #29): The Java YAML declares `ortb-version: "2.6"` with explicit quotes to preserve string type (without quotes, YAML parses `2.6` as a float). The skill MUST detect from raw text whether the value was quoted. Emit as a string (`"2.6"`) regardless. Go YAMLs typically nest under `openrtb: { version: 2.6 }` and round-trip through `yaml_extra_fields` rather than top-level `ortb_version` — the inverse asymmetry.

---

## Tilde-syntax detection (`aliases[].config_form`)

Inside the unified file's `aliases:` map, each child key has exactly one of two valid value shapes:

### Tilde-inherit (`name: ~`)

```yaml
adapters:
  xeworks:
    endpoint: "https://..."
    aliases:
      connektai: ~                 # tilde syntax — alias inherits all parent fields
      streamvision: ~
```

The `~` sigil is YAML's explicit null literal — equivalent to `null` or empty. The YAML parser MUST emit a Python None / Java null / Go nil for the value, NOT drop the key. When the parser correctly preserves the key with null value, the skill emits:

```yaml
aliases:
  - name: connektai
    alias_of: xeworks
    config_form: tilde_inherit
  - name: streamvision
    alias_of: xeworks
    config_form: tilde_inherit
```

Detection rule (deterministic): a child's value is `tilde_inherit` if and only if `value === None` (Python) / `value == null` (Java/JS) / equivalent. Any non-null value (map, scalar, list) is NOT `tilde_inherit` — go to the full-block case.

Quirk emission: each tilde-inherit alias produces a `quirks[]` entry with `edge_case_taxon: tilde-alias-syntax` so cross-language porters going Java→Go know to materialize the alias as its own child YAML file (`static/bidder-info/{name}.yaml` with `aliasOf: parent`).

### Full-block (`name: { endpoint: "...", ... }`)

```yaml
adapters:
  xeworks:
    endpoint: "https://parent.example.com/auction"
    aliases:
      mybrand:
        endpoint: "https://mybrand.example.com/auction"   # override parent's endpoint
        meta-info:
          maintainer-email: "ops@mybrand.example.com"     # override parent's maintainer
```

When the alias child's value is a non-null map, the alias overrides one or more parent fields. The skill emits:

```yaml
aliases:
  - name: mybrand
    alias_of: xeworks
    config_form: full_block
    overrides:
      endpoint: "https://mybrand.example.com/auction"
      meta-info:
        maintainer-email: "ops@mybrand.example.com"
```

`overrides` is a verbatim subtree of the YAML map under the alias key — preserve insertion order, raw value types, and nested structure for round-trip determinism.

### Other shapes (warnings)

- `aliases.{name}: "string"` — a scalar string value -> warning `alias-shape-unknown` (the YAML is malformed; Java unified YAMLs reject this at startup).
- `aliases.{name}: ["list"]` — a list value -> warning `alias-shape-unknown`.
- `aliases:` itself absent OR empty map -> emit top-level `aliases: []` (NOT null), no warning.

### Why the rule matters

The tilde vs full-block distinction drives downstream skills:

- `port-java2go` consumes the spec and creates per-child `static/bidder-info/{name}.yaml` files. Tilde-inherit children become `aliasOf: parent` files with NO additional fields. Full-block children become `aliasOf: parent` files with the override fields copied over.
- `read-bidder-class` consumes `aliases[]` to know which alias names need per-alias IT classes (Java edge case #24).
- `lifecycle.rename` detection (Step 6 in SKILL.md) cross-references tilde-inherit entries against the orchestrator's known-YAML registry to find rename-by-alias-back patterns.

---

## Bidder-rename detection pattern (`lifecycle.rename`)

Java edge case #33 — the three-step refactor:

1. DELETE old YAML: `bidder-config/{old_name}.yaml` no longer exists at the target commit.
2. CREATE new YAML: `bidder-config/{new_name}.yaml` exists at the target commit.
3. ADD alias-back: the new YAML's `aliases:` map carries `{old_name}: ~` (tilde-inherit) for backward compatibility.

Canonical example (PR #4326): Adoppler renamed to ElementalTV.

```yaml
# bidder-config/adoppler.yaml — DELETED at commit C.
# bidder-config/elementaltv.yaml — CREATED at commit C, contains:
adapters:
  elementaltv:
    endpoint: "..."
    aliases:
      adoppler: ~                  # alias-back; old name accepted as alias of new
```

Detection rule (this skill executes when reading the NEW yaml):

For each tilde-inherit alias `{alias_name}` from Step 5:

1. Query the orchestrator's known-YAML registry: does `bidder-config/{alias_name}.yaml` exist at the resolved commit?
   - YES — normal sibling alias; skip rename detection for this entry.
   - NO — candidate rename-by-alias-back. Continue to step 2.
2. Cross-reference `references/new-bid-adapter-prs.md` Pattern Index for the `alias-back-via-tilde` + `bidder-rename-major-version` tags. Confirmed-rename criteria (BOTH must be true):
   - The PR introducing the new YAML is tagged with both `bidder-rename-major-version` AND `alias-back-via-tilde`.
   - The orchestrator's discovery confirms the old YAML was deleted at the same commit (or a recently preceding commit on the same release branch).
3. Emit (additionally to the normal `aliases[]` entry):

```yaml
lifecycle:
  rename:
    old_name: adoppler
    new_name: elementaltv
    yaml_deletes:
      - src/main/resources/bidder-config/adoppler.yaml
    yaml_adds:
      - src/main/resources/bidder-config/elementaltv.yaml
    alias_back: true
    package_moves:
      - from: src/main/java/org/prebid/server/bidder/adoppler/
        to:   src/main/java/org/prebid/server/bidder/elementaltv/
    fixture_dir_moves:
      - from: src/test/resources/org/prebid/server/it/openrtb2/adoppler/
        to:   src/test/resources/org/prebid/server/it/openrtb2/elementaltv/
```

4. Emit a `quirks[]` entry with `edge_case_taxon: bidder-rename-three-step` and a `quirks[]` entry with `edge_case_taxon: acronym-case-preservation` if the new name preserves brand acronym casing (per PR #4326 — `ElementalTV` rather than `Elementaltv`).

### Edge cases unresolved by this skill

- **Renames that did NOT use alias-back**: e.g., the SmartHub→Attekmi rebrand (relevant to PR #4365 RadiantFusion) was a clean rebrand without tilde-alias-back to Smarthub. The skill cannot detect this from YAML alone; the orchestrator's git-history correlation (`git log --follow`) is required.
- **Multi-step renames** (A → B → C): the skill detects A → B at one commit and B → C at a later commit but does NOT correlate them. The orchestrator's commit-history walker would.
- **Concurrent rename + content change** (rename plus endpoint URL change in same PR): the skill emits the rename block but does NOT diff the content; downstream review skills (`bidder-info-pr-review`) handle content diffs.
- **Cross-language rename without Java alias-back**: Go-side renames don't have an analogous tilde syntax (Go has no parent-side aliases map). The Java skill cannot detect a Go-only rename; the cross-language `port-go2java`/`port-java2go` chain handles that case.

---

## Typo registry (`bidder_info.yaml_field_name_quirks[]`)

The Java canonical typo registry, used by Step 7 of the workflow:

| YAML key found | Canonical Java key | Severity | Surface | Notes |
|---|---|---|---|---|
| `endpointCompression` | `endpoint-compression` | FAIL | silent no-op | Java edge case #34. Java uses kebab-case; camelCase is silently ignored. Compression is NOT applied — every response decoded raw. Canonical regression: Ogury PR #3788. |
| `endpoint-compression` | (canonical) | INFO | acknowledged | Acknowledge canonical form (no quirk emitted unless other typos surface). |
| `modifyingVastXmlAllowed` | `modifying-vast-xml-allowed` | FAIL | silent default | Same kebab-vs-camel asymmetry as endpoint-compression. Default `false` if camelCase form used (silently ignored). |
| `gvlVendorID` (top-level, not under `meta-info.vendor-id`) | `meta-info.vendor-id` | FAIL | silent default 0 | Go camelCase form bleeding into Java YAML. Java requires it under `meta-info`. |
| `dev-endpoint` (no Go canonical) | (Java-specific custom field) | INFO | acknowledged | Java's standard custom field for dev/test endpoint (Kobler PR #3684). Not a typo — INFO-level acknowledgement; correlate with Spring `BidderConfigurationProperties` subclass detection in `read-bidder-class`. |
| `platformId` | `platform-id` | FAIL | silent default | Appnexus port residue. Java requires kebab-case. |
| `vendorId` (top-level) | `meta-info.vendor-id` | FAIL | silent default 0 | Java requires it under `meta-info`. |
| `maintainerEmail` (top-level) | `meta-info.maintainer-email` | FAIL | silent missing | Java requires it under `meta-info`. |

For each typo match, the skill:

1. Emits `bidder_info.yaml_field_name_quirks[]` entry: `{ found, canonical, severity, line, summary }`.
2. Emits warning type `yaml-field-name-typo` (or `endpoint-compression-typo` for the specific compression case) with file:line.
3. Emits a `quirks[]` entry at the spec top level with `edge_case_taxon: yaml-field-name-typo` (or `endpoint-compression-typo`).
4. Passes through the typo'd value via `yaml_extra_fields` so round-trip writes preserve byte fidelity. Does NOT silently rename it.

---

## Custom-field passthrough (`bidder_info.yaml_extra_fields`)

Operator-supplied custom YAML fields (the keys outside the canonical Java set) are preserved verbatim under `bidder_info.yaml_extra_fields` in original key form, original value type, and insertion order. These fields are typically mapped to a `BidderConfigurationProperties` subclass extra_field by `read-bidder-class` (Spring DI sibling).

| Custom field | Bidder | Spring subclass field | Cross-language note |
|---|---|---|---|
| `dev-endpoint` | Kobler | `KoblerConfigurationProperties.devEndpoint` (`@NotBlank private String`) | Promoted from Go-side hardcoded const into Java YAML config. Surfaces as `dev-endpoint-config-promotion` quirk (cross-language win). Port Translation Rule 35. |
| `platform-id` | Appnexus | `AppnexusConfigurationProperties.platformId` | Mapped to a typed field for validation. |
| `iab-categories` | Appnexus | `AppnexusConfigurationProperties.iabCategories` (`Map<String, String>`) | 120-entry inlined map. Cross-skill correlation: `iab_category_storage.{storage_kind: yaml-inlined, yaml_field: iab-categories, table_size: 120, delivery_mechanism: constructor-arg}`. Go's equivalent is a separate `iab_categories.go` data file (storage_kind: go-data-table). |
| `extra-info` | Huaweiads, NextMillennium | nested static class `ExtraInfo` with typed fields | Java pattern for opaque-config: typed nested class instead of Go's stringified-JSON `extra_info`. |

For each known custom field, the skill emits an INFO-level entry under `quirks[]` to surface the cross-language asymmetry to porters:

- `dev-endpoint` -> quirk `dev-endpoint-config-promotion` (cross-language win — Java promotes Go-const to YAML).
- `iab-categories` -> quirk that captures the 120-entry inlined map and references `iab_category_storage` cross-skill.
- `extra-info` -> quirk that flags the nested-static-class pattern and contrasts with Go's `extra_info: '{}'` stringified JSON.
- `platform-id` -> no quirk by default; surfaces only if mismatched casing (`platformId`) is detected.

Unknown custom fields (operator-specific extensions outside the registry above) -> verbatim passthrough, no quirk.

---

## Round-trip determinism (Validation Rule R4)

The reader MUST produce a byte-identical `bidder_info` block + `aliases[]` array when re-run on the same YAML bytes. Practical implications:

- Preserve original key order under `yaml_extra_fields` (insertion order from YAML).
- Preserve raw value types (string `"2.6"` stays a string; bool `true` stays bool; float `915` stays integer).
- Preserve YAML null distinction (the `~` sigil parses to null; an absent key is absent — distinct).
- Preserve casing of typo'd field names (do not normalize `endpointCompression` to `endpoint-compression` — record both `found` and `canonical` separately).

The orchestrator's CI harness diffs the produced spec against checked-in golden specs (modulo `provenance.read.timestamp_utc` and `provenance.read.operator`).

---

## Cross-language structural parity (Validation Rule R5)

For any bidder present in BOTH Go and Java repos, the cross-language fields MUST agree between the Go-source spec and the Java-source spec produced by this skill:

| Field | Go reader emits | Java reader emits (this skill) | Required to match |
|---|---|---|---|
| `bidder_info.gvl_vendor_id` | from `gvlVendorID` flat key | from `meta-info.vendor-id` | YES |
| `bidder_info.maintainer.email` | from `maintainer.email` | from `meta-info.maintainer-email` | YES |
| `bidder_info.capabilities.site.mediaTypes` | from `capabilities.site.mediaTypes` | from `meta-info.site-media-types` | YES |
| `bidder_info.capabilities.app.mediaTypes` | from `capabilities.app.mediaTypes` | from `meta-info.app-media-types` | YES |
| `bidder_info.capabilities.dooh.mediaTypes` | from `capabilities.dooh.mediaTypes` | from `meta-info.dooh-media-types` | YES |
| `bidder_info.geoscope` | from `geoscope` | from `geoscope` | YES |
| `bidder_info.endpoint_compression` | from `endpointCompression` | from `endpoint-compression` | YES (after canonicalization) |
| `bidder_info.endpoint` | from `endpoint` | from `adapters.{xyz}.endpoint` | YES |

A mismatch surfaces as a `port_concerns` warning + dual-spec-assertion FAIL. The cross-language test harness diffs Kobler's Go-source vs Java-source spec on these fields; the kobler.golden.spec.yaml (Java) values shown in SKILL.md Verification section MUST match the Go-source kobler spec exactly.

---

## Sources

- Plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` (Phase C — read-bidder-config; Java edge cases #29-#34).
- Schema: [../../../../../prebid-server-go/read/skills/shared/adapter-spec.md](../../../../../prebid-server-go/read/skills/shared/adapter-spec.md) — `bidder_info:` section, `aliases[].config_form`, `lifecycle.rename`, `bidder_info.yaml_field_name_quirks[]`, `bidder_info.default_enabled`, `bidder_info.modifying_vast_xml_allowed`, `bidder_info.ortb_version`, `cross_language.port_concerns.yaml_unification`.
- Taxonomy: [../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md](../../../../../prebid-server-go/read/skills/shared/behavior-taxonomy.md) — `quirks edge_case_taxon` registry: `tilde-alias-syntax`, `bidder-rename-three-step`, `endpoint-compression-typo`, `yaml-field-name-typo`, `dev-endpoint-config-promotion`, `acronym-case-preservation`.
- Port translation rules: [../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md](../../../../../prebid-server-go/read/skills/shared/port-translation-rules.md) — Rule 34 (yaml_unification, including kebab vs camel + meta-info wrapper + capabilities flatten), Rule 33 (alias inversion), Rule 35 (dev-endpoint config promotion), Rule 13 (dev-prod toggle), Rule 11–15 (endpoint resolution).
- Java reference list: [../../../../references/new-bid-adapter-prs.md](../../../../references/new-bid-adapter-prs.md) — Pattern Index entries for `alias-back-via-tilde`, `bidder-rename-major-version`, `package-rename-fixture-dir-rename`, `acronym-case-preservation` (PR #4326 ElementalTV); `dev-prod-endpoint-toggle`, `configuration-properties-subclass`, `currency-conversion` (PR #3684 Kobler); `enabled-false-default`, `ortb-version-quoted`, `dooh-platform-declared` (PR #4054 Optidigital); `modifying-vast-xml-allowed` (PR #3869 FeedAd, PR #4031 Mediasquare); `endpoint-compression-typo-camelcase` (PR #3788 Ogury); `co-shipped-second-alias-rxnetwork` (PR #3829 152media); `digit-leading-bidder-class-workaround-OneFiveTwoMedia` (PR #3829 152media identifier-rule workaround).
- Sibling Go skill (inverse round-trip pair): [../../../../../prebid-server-go/read/skills/read-bidder-info/SKILL.md](../../../../../prebid-server-go/read/skills/read-bidder-info/SKILL.md).
- Go endpoint classification (cross-language reuse): [../../../../../prebid-server-go/read/skills/read-bidder-info/references/endpoint-classification.md](../../../../../prebid-server-go/read/skills/read-bidder-info/references/endpoint-classification.md).
- Java golden spec: [../../../test-fixtures/kobler.golden.spec.yaml](../../../test-fixtures/kobler.golden.spec.yaml).
