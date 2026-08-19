# Bidder Params Type Index

Mapping of JSON Schema types to Go struct conventions for `static/bidder-params/*.json` and `openrtb_ext/imp_*.go` files.

**Upstream sources (canonical):**
- Schema validator: https://github.com/prebid/prebid-server/blob/master/openrtb_ext/bidders.go (`NewBidderParamsValidator`, uses `gojsonschema` library)
- Imp ext structs: https://github.com/prebid/prebid-server/tree/master/openrtb_ext (files matching `imp_*.go`)
- Params test convention: https://github.com/prebid/prebid-server/tree/master/adapters (files matching `*/params_test.go`)

**Raw URLs (for fetching):**
- https://raw.githubusercontent.com/prebid/prebid-server/master/openrtb_ext/bidders.go
- https://raw.githubusercontent.com/prebid/prebid-server/master/static/bidder-params/{bidder}.json

> **Sync policy:** This file is a local snapshot. The `pr-triage` skill's Step 2 runs centralized drift checks against the live source on every review run; this skill's Step 1b reads those drift results from the manifest. If new fields/types are found upstream, update this file to match.

---

## Module path

**Current major:** `github.com/prebid/prebid-server/v4` (since release v4.0.0, March 2026).
**Note on PR diffs that show `v3` imports:** the v3 → v4 migration was a mechanical sweep on master. PR diffs authored before that sweep can show `v3` imports and merge against `v4` master. Do NOT flag `v3` imports in PR diffs as stale.

For framework-wide concerns (helper functions, marshaling safety, error types, endpoint macros, test harness contract), see [../../shared/framework-utilities.md](../../shared/framework-utilities.md).

---

## JSON Schema to Go Type Mapping

| JSON Schema Type | Go Type | Notes |
|-----------------|---------|-------|
| `"string"` | `string` | Use `*string` if optional and zero-value matters |
| `"string"` with `"minLength": 1` | `string` | Required non-empty |
| `"integer"` | `int` or `int64` | Use `int64` for large IDs |
| `"number"` | `float64` | For bid floors, reserves, etc. |
| `"boolean"` | `bool` | Use `*bool` if tri-state needed |
| `["integer", "string"]` | `jsonutil.StringInt` | Preferred PBS type for placement IDs that accept both int and string. Imported from `github.com/prebid/prebid-server/v4/util/jsonutil`. Alternative `interface{}` is permissive — flag as WARN. Use `jsonutil.StringInt` for typed handling. |
| `anyOf: [{type: number}, {type: string}]` | `interface{}` | Used when a field accepts multiple types via `anyOf`. Permissive — flag as WARN. Seen in Sovrn `bidfloor` |
| `"object"` (nested) | nested struct or `json.RawMessage` | Prefer typed struct; `json.RawMessage` for opaque pass-through |
| `"object"` (no properties) | `map[string]any` | Very permissive — flag as WARN. Only acceptable for truly opaque pass-through (e.g., Missena `settings`) |
| `"array"` of primitives | `[]string`, `[]int`, etc. | |
| `"array"` of objects | `[]NestedStruct` | |

---

## Go Struct Conventions

### Naming
- Package: `openrtb_ext`
- **Canonical type name: `ExtImp{Bidder}`** (e.g., `ExtImpAax`, `ExtImpAdkernel`, `ExtImp33across`) — the majority form in current master; the legacy `ImpExt{Bidder}` form (e.g., `ImpExtMsft`) is a substantial minority. Regenerate the split rather than quoting a stale count:
  ```bash
  grep -rhoP 'type ExtImp\w+' openrtb_ext/imp_*.go | wc -l   # 170 at @0ba3523
  grep -rhoP 'type ImpExt\w+' openrtb_ext/imp_*.go | wc -l   #  78 at @0ba3523
  ls openrtb_ext/imp_*.go | wc -l                             # 259 at @0ba3523
  ```
- The legacy `ImpExt{Bidder}` pattern exists in some older files but is NOT recommended for new adapters. When reviewing a NEW adapter that uses `ImpExt{Bidder}`, flag as INFO — recommend converting for consistency. When reviewing modifications to existing files, do not require renames.
- Bidder name in type is CamelCase: `ExtImpAax`, `ExtImpAJA`, `ExtImp33across`. Helper types (e.g., `ExtImpGumGumBanner`) are acceptable when they support the main imp ext struct.
- Go field-name capitalization fixes (e.g., `ApiKey` → `APIKey` per Go acronym conventions) are non-functional if `json:"..."` tags are unchanged. Accept without follow-up.

### JSON Tags
- Must match schema property names exactly (case-sensitive)
- Use `json:"propertyName"` for required fields
- Use `json:"propertyName,omitempty"` for optional fields
- Tag name = schema property name, not Go field name

### Examples

**Simple (AAX — 2 required string fields):**
```go
type ExtImpAax struct {
    Cid  string `json:"cid"`
    Crid string `json:"crid"`
}
```

**With optional fields (33Across — conditional required):**
```go
type ExtImp33across struct {
    ZoneId    string `json:"zoneId,omitempty"`
    SiteId    string `json:"siteId,omitempty"`
    ProductId string `json:"productId,omitempty"`
}
```

**Renamed field (AJA — Go name differs from JSON):**
```go
type ExtImpAJA struct {
    AdSpotID string `json:"asi"`
}
```

---

## JSON Schema draft-04 Rules

### Required Elements
- `"$schema": "http://json-schema.org/draft-04/schema#"` — house style, **not loader-enforced**. `NewBidderParamsValidator` (`openrtb_ext/bidders.go:783-830`) delegates to `gojsonschema` without pinning a draft; the draft comes from each file's own `$schema`. 271 of 272 files use draft-04 at @0ba3523; `ogury.json` uses `https://json-schema.org/draft/2020-12/schema` and loads fine. A different draft string is **WARN**, not FAIL. What *is* FAIL is using a post-draft-04 keyword under a draft-04 `$schema` — the constraint is then silently ignored.
- `"title"` — descriptive title like `"{Bidder} Adapter Params"`
- `"type": "object"` — top-level must be object
- `"properties": {}` — must exist even if adapter has no params

### Conditional Validation Constructs

**`required`** — simple list of always-required fields:
```json
"required": ["placementId"]
```

**`anyOf`** — at least one condition must be true (OR):
```json
"anyOf": [
  { "required": ["productId", "siteId"] },
  { "required": ["productId", "zoneId"] }
]
```

**`oneOf`** — exactly one condition must be true (XOR):
```json
"oneOf": [
  { "required": ["appIds"] },
  { "required": ["appId"] }
]
```

**`not`** — condition must be false:
```json
"not": { "required": ["placementId", "invCode", "member"] }
```

**Nested `oneOf` in `oneOf`** — for complex backward-compat (AppNexus pattern):
```json
"oneOf": [
  { "oneOf": [
    { "required": ["placementId"] },
    { "required": ["placement_id"] }
  ]},
  { "oneOf": [
    { "required": ["invCode", "member"] },
    { "required": ["inv_code", "member"] }
  ]}
]
```

### Common Mistakes
- Using draft-07 features (`if`/`then`/`else`, `const`, `contentEncoding`) under a draft-04 `$schema` — the keyword is ignored, so the constraint silently does nothing
- Missing `$schema` declaration
- Using `additionalProperties: true` without reason (allows arbitrary fields)
- Declaring `required` fields that are actually optional in the adapter code
- Regex patterns that are overly strict or don't match real-world values

---

## Params Test Conventions

**Filename note:** The canonical filename is `params_test.go` (plural). At least one historical PR (#4082 Ogury) merged with `param_test.go` (singular) — flag the singular form as WARN when reviewing new adapters; tolerate it on existing files (don't churn).

### Standard Structure
```go
package {bidder}

import (
    "encoding/json"
    "testing"
    "github.com/prebid/prebid-server/v4/openrtb_ext"
)

func TestValidParams(t *testing.T) {
    validator, err := openrtb_ext.NewBidderParamsValidator("../../static/bidder-params")
    if err != nil {
        t.Fatalf("Failed to fetch the json-schemas. %v", err)
    }
    for _, validParam := range validParams {
        if err := validator.Validate(openrtb_ext.Bidder{Name}, json.RawMessage(validParam)); err != nil {
            t.Errorf("Schema rejected {bidder} params: %s", validParam)
        }
    }
}

func TestInvalidParams(t *testing.T) {
    validator, err := openrtb_ext.NewBidderParamsValidator("../../static/bidder-params")
    if err != nil {
        t.Fatalf("Failed to fetch the json-schemas. %v", err)
    }
    for _, invalidParam := range invalidParams {
        if err := validator.Validate(openrtb_ext.Bidder{Name}, json.RawMessage(invalidParam)); err == nil {
            t.Errorf("Schema allowed unexpected params: %s", invalidParam)
        }
    }
}

var validParams = []string{ /* ... */ }
var invalidParams = []string{ /* ... */ }
```

### Expected Coverage

**Disposition for everything in this section: INFO (NOTE).** These lists are suggested coverage, not a gate — only 72 of 235 upstream `params_test.go` files contain all six primitive rejections and 92 contain none (counts and regenerating command in `../SKILL.md` Workflow: Params Test Changed step 4). Report absences as a single note naming the gaps, never one finding per item and never a FAIL. The one FAIL in this area is scope-bound, not list-bound: a `required` field added by *this* PR with no `TestInvalidParams` case omitting it.

**validParams should include:**
- Required-fields-only case (minimum valid input)
- All-optional-fields populated
- Edge cases: empty strings where allowed, boundary numeric values, flexible types (`int` and `string` for same field)
- **Avoid the `ext` field outside the schema:** test cases should validate ONLY the required and optional fields defined in the adapter's schema. Including `ext` keys (or other fields not in `properties`) in `validParams` was rejected in PR #4243 review — keep tests aligned with what the schema actually validates.

**invalidParams should include:**
- Empty string `""`
- `null`
- `true` (boolean)
- `5` (number)
- `4.2` (float)
- `[]` (array)
- `{}` (empty object — if fields are required)
- Missing each required field individually
- Wrong type for each field (string where int expected, etc.)
- Empty strings for fields with `minLength: 1`
- Unknown/misspelled field names only

---

## Reserved OpenRTB Fields (Must NOT Be Bidder Params)

These standard OpenRTB 2.x fields should not be duplicated as bidder-specific parameters. Publishers configure them through standard Prebid paths. **The table is split by whether upstream master actually holds the line** — a rule with 24 merged counterexamples cannot be a FAIL.

**Hard exclusions — FAIL (zero upstream counterexamples at @0ba3523):**

| Field | Standard Path | Why Not a Bidder Param |
|-------|--------------|----------------------|
| Supply chain | `source.ext.schain` | Standard OpenRTB 2.5+. `grep -l '"schain"' static/bidder-params/*.json` returns 0 files. |
| GDPR consent | `regs.ext.gdpr`, `user.ext.consent` | Standard privacy path; duplicating it lets a publisher param contradict the real consent signal |
| US Privacy | `regs.ext.us_privacy` | Standard privacy path |
| COPPA | `regs.coppa` | Standard OpenRTB 2.x; a per-bidder COPPA override is a compliance hazard |
| GPP | `regs.gpp`, `regs.gpp_sid` | Standard OpenRTB 2.6 |

**Soft exclusions — WARN (ASK), with upstream precedent:**

| Field | Standard Path | Precedent |
|-------|--------------|-----------|
| Bid floor | `imp.bidfloor` / `ext.prebid.floors` | **24** `static/bidder-params/*.json` declare `bidfloor` or `bidFloor` at @0ba3523 (`grep -l '"bidfloor"\|"bidFloor"' static/bidder-params/*.json \| wc -l`). Ask why the standard floor path is insufficient; accept a bidder-specific reason. Do NOT block. |
| Video params | `imp.video.*` | Standard OpenRTB 2.x — ask before blocking; some bidders carry genuinely non-OpenRTB video config |
| First party data | `imp.ext.data`, `site.ext.data`, `user.ext.data` | PBS first-party data paths |
| Referrer | `site.page`, `site.ref` | Standard OpenRTB 2.x |

### Reserved Extension Keys (in `imp.ext.prebid`):
- `context`, `data` — first party data
- `gpid` — Global Placement ID
- `skadn` — Apple SKAdNetwork
- `tid` — Transaction ID
- `prebid` — Prebid Server config
- `ae`, `igs` — PAAPI (Protected Audience API)

---

## Common Parameter Patterns

Frequently seen across existing adapters:

| Pattern | Example Schema | Example Adapters |
|---------|---------------|-----------------|
| Single placement ID | `"placementId": {"type": "string"}` | AAX, AJA, many others |
| Account + placement | `"accountId": ..., "placementId": ...` | Various |
| Zone ID | `"zoneId": {"type": "string"}` | 33Across, AdKernel |
| Seat + token | `"seat": ..., "token": ...` | SmartHub family |
| App ID per media type | `"appIds": {"video": ..., "banner": ...}` | Beachfront |
| Flexible int/string | `"type": ["integer", "string"]` | AppNexus (placement_id) |
| Legacy + new naming | oneOf with old and new field names | AppNexus (placementId vs placement_id) |

---

## Alias Behavior

When a bidder is an alias (`aliasOf` in bidder-info), the parameter schema is inherited from the parent. From `NewBidderParamsValidator`:

```go
for alias, parent := range aliasBidderToParent {
    parentSchema := schemas[parent]
    schemas[alias] = parentSchema
}
```

This means:
- Alias adapters do NOT need their own `static/bidder-params/{alias}.json` file
- Alias adapters do NOT need their own `openrtb_ext/imp_{alias}.go` file
- Alias adapters do NOT need their own `params_test.go` file
- If any of these exist for an alias, flag as suspicious — they should inherit from parent

---

## Imp ext struct + adapter code consistency

When both `openrtb_ext/imp_{bidder}.go` AND `adapters/{bidder}/{bidder}.go` (or related files like `adapters/{bidder}/models.go`) are in the same PR, cross-verify that JSON tag spellings match across files:

Compare **within a direction, never across the two** — inbound and outbound are separate wire contracts:

- **Inbound** (publisher → PBS): the `json:"..."` tags on `openrtb_ext.ExtImp{Bidder}` must match the property names in `static/bidder-params/{bidder}.json` and what the adapter reads from `bidderExt.Bidder`.
- **Outbound** (PBS → bidder server): if the adapter has its OWN payload struct (e.g., `adapters/msft/models.go`), its tags must match what the upstream server expects, as pinned by the exemplary fixtures' `expectedRequest.body`.
- **An inbound tag differing from an outbound tag is normal, not a defect.** In merged `msft`, `openrtb_ext/imp_msft.go:14` declares `json:"pubclick"` (matching `static/bidder-params/msft.json`) while `adapters/msft/models.go:30` emits `json:"pub_click,omitempty"`, and `adapters/msft/test/exemplary/all-params.json` asserts both. Do not flag this shape.

The `adapter-code-pr-review` skill owns the disposition; this skill emits an INFO referencing it (avoid duplicate findings).
