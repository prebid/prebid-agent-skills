# Endpoint Classification Decision Tree

Deterministic mapping from the literal `endpoint:` YAML string (and adjacent YAML signals) to `bidder_info.endpoint_construction.kind`. Used by `read-bidder-info` Step 3.

## Output enum (canonical, cross-language)

The `kind` field must be exactly one of (taxonomy mastered at [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md), section "code.make_requests.endpoint_resolution / endpoint_construction"):

| Kind | One-line semantics |
|---|---|
| `static` | Literal URL, no substitution at all. |
| `template-macro` | Contains one or more `{{.X}}` Go-template macros from the canonical 22-field `EndpointTemplateParams` list. |
| `url-with-query` | Static base URL with literal `?key=value&...` query string. No substitution. |
| `dev-prod-toggle` | YAML signals a second URL (paired `dev-endpoint:` field, or `extra_info.dev_endpoint`) — adapter Go code toggles between primary and secondary. |
| `hardcoded-toggle` | Adapter Go code toggles between `endpoint:` and a HARDCODED Go-source `const` (anti-pattern; canonical: Kobler). YAML alone cannot detect this — relies on incomplete-inference handoff to `read-adapter-code`. |
| `runtime-region-selection` | Region picked from request context (e.g., `device.geo.country`). YAML signal: `endpoint:` is a single literal but `extra_info` contains a region table. Adapter code does the dispatch. |
| `deploy-time-token` | URL contains a non-Go-template placeholder (`#{X}#`, `${X}`, `<X>`) that the deployment operator substitutes pre-startup. REQUIRES `disabled: true` paired in YAML. Canonical: Rubicon `REGION`. |
| `custom` | Anything not captured above. REQUIRES a paired `quirks[]` entry per Validation Rule R3. |

---

## Decision tree (in order — first match wins)

The skill evaluates the `endpoint:` string against this tree top-down. Stop at the first match. Order matters because some cases overlap (e.g., a query string can also contain a deploy-time token).

```
INPUT: endpoint_str (the literal value of the YAML `endpoint:` key)
INPUT: yaml_keys    (the full set of top-level keys present in the YAML)
INPUT: extra_info   (parsed JSON of the `extra_info:` field, or null)

if endpoint_str == null OR endpoint_str == "":
    -> kind = custom
       quirk: endpoint-empty-or-missing
    STOP

# Step A: Non-Go-template placeholders (highest precedence — affects deploy gate).
if endpoint_str matches /#{[A-Z_]+}#/   # Rubicon-style hash-curly
   OR endpoint_str matches /\$\{[A-Z_]+\}/  # shell-style ${VAR}
   OR endpoint_str matches /<[A-Z_]+>/     # angle-bracket <VAR>
:
    -> kind = deploy-time-token
       For each captured token T:
           append T to placeholders_unresolved[]
           emit deploy_time_tokens[] entry:
               { token: T, file: static/bidder-info/{xyz}.yaml,
                 notes: "operator substitutes pre-deployment" }
       if NOT (yaml_keys contains "disabled" AND yaml.disabled == true):
           emit warning type=endpoint-placeholder-unresolved severity=FAIL
              "Deploy-time token <T> requires disabled: true per PR #4502 convention"
    STOP

# Step B: Go-template macros.
captures = regex_findall(endpoint_str, /\{\{\.([A-Za-z]+)\}\}/g)
if captures is non-empty:
    canonical_set = EndpointTemplateParams 22-field list  # See ../../shared/endpoint-macros.yaml.
    macros_used   = []
    placeholders  = []
    for ident in captures:
        if ident in canonical_set:
            macros_used.append(ident)
        else:
            placeholders.append(ident)
            emit warning type=endpoint-placeholder-unresolved severity=FAIL
               "{{." + ident + "}} is NOT a known EndpointTemplateParams field — template execution fails, so config validation rejects this endpoint"
    if macros_used non-empty:
        -> kind = template-macro
           endpoint_construction.macros_used = macros_used
           endpoint_construction.placeholders_unresolved = placeholders
        STOP
    else:
        # All captures fell out of the canonical set — still semantically a template attempt.
        -> kind = template-macro
           endpoint_construction.macros_used = []
           endpoint_construction.placeholders_unresolved = placeholders
        # Already emitted FAIL warnings above per identifier.
        STOP

# Step C: Query parameter augmentation (no substitution; literal query string).
if endpoint_str contains "?" AND no substring after "?" matches Go-template / non-Go-template patterns:
    -> kind = url-with-query
    STOP

# Step D: Dev-prod toggle inferred from YAML signals.
# Java unified bidder-config files can declare `dev-endpoint:` directly.
# A Go file can carry the secondary URL inside `extra_info` as JSON.
if yaml_keys contains "dev-endpoint" OR yaml_keys contains "devEndpoint":
    -> kind = dev-prod-toggle
       quirk: yaml-field-name-typo if "dev-endpoint" key found in Go YAML  # kebab-case is Java-style
    STOP
if extra_info is parseable JSON AND extra_info has key matching /^dev[_-]?endpoint$/i:
    -> kind = dev-prod-toggle
    STOP

# Step E: Runtime-region-selection inferred from extra_info table.
if extra_info is parseable JSON AND extra_info has key matching /(region|country)[_-]?(map|table)?/i AND value is map/list:
    -> kind = runtime-region-selection
    STOP

# Step F: Hardcoded-toggle (YAML cannot fully detect; defer to read-adapter-code).
# Example: Kobler — endpoint is the prod URL; dev URL is a Go-source `const` outside YAML.
# YAML emits no signal. Default to `static` here and emit an inference-incomplete note so
# the orchestrator can re-classify after read-adapter-code runs.
# (Step F is implicit — falls through to Step G.)

# Step G: Default — no substitution detected.
-> kind = static
   if endpoint_str does NOT begin with "http://" OR "https://":
       emit warning type=endpoint-malformed-url severity=FAIL
   if endpoint_str begins with "http://":
       emit warning type=endpoint-http-not-https severity=INFO
       # HTTP is permitted (PR #4211) but HTTPS preferred.
STOP
```

After Step G falls through to `static`, the orchestrator may receive an `incomplete-classification` quirk if `read-adapter-code` later detects a runtime toggle that the YAML alone could not see (Kobler-style hardcoded-toggle, or a region-dispatching switch statement). At that reconciliation point the orchestrator UPGRADES `kind` from `static` -> `hardcoded-toggle` / `runtime-region-selection` / `dev-prod-toggle` and emits a quirk with `edge_case_taxon: hardcoded-config-as-anti-pattern` if the adapter chose hardcoded over YAML config.

---

## Examples

### Example 1: Optidigital (clean static)

```yaml
# static/bidder-info/optidigital.yaml
endpoint: "https://pbs.optidigital.com/bidder/openrtb2"
```

- Step A: no `#{X}#` / `${X}` / `<X>`.
- Step B: no `{{.X}}` captures.
- Step C: no `?` in URL.
- Step D: no `dev-endpoint:` key.
- Step E: no `extra_info`.
- Step G: starts with `https://` -> kind = `static`. No warnings.

Output:
```yaml
endpoint_construction:
  kind: static
  macros_used: []
  placeholders_unresolved: []
```

### Example 2: Adagio (template-macro)

Suppose YAML carries `endpoint: "https://{{.PublisherID}}.adagio.io/openrtb2/auction"`.

- Step A: no non-Go-template placeholders.
- Step B: captures = [`PublisherID`]. `PublisherID` IS in the canonical 22-field set. macros_used = [`PublisherID`]. -> kind = `template-macro`.

Output:
```yaml
endpoint_construction:
  kind: template-macro
  macros_used: [PublisherID]
  placeholders_unresolved: []
```

### Example 3: Rubicon (deploy-time-token)

```yaml
# static/bidder-info/rubicon.yaml
endpoint: "https://prebid-server.rubiconproject.com/openrtb2/auction?tk_xint=#{REGION}#"
disabled: true
```

- Step A: matches `#{REGION}#`. -> kind = `deploy-time-token`. `placeholders_unresolved: [REGION]`. `deploy_time_tokens[]` += `{ token: REGION, file: static/bidder-info/rubicon.yaml, notes: ... }`. `disabled: true` paired -> NO FAIL warning.

Output:
```yaml
endpoint_construction:
  kind: deploy-time-token
  macros_used: []
  placeholders_unresolved: [REGION]
deploy_time_tokens:
  - token: REGION
    file: static/bidder-info/rubicon.yaml
    notes: "operator substitutes pre-deployment"
```

### Example 4: Hypothetical query-augmented (url-with-query)

```yaml
endpoint: "https://bidder.example.com/openrtb2?member_id=42"
```

(Note: real Appnexus injects `member_id` per-request via `net/url`, NOT a literal in YAML — Appnexus's YAML endpoint is bare.) For a hypothetical bidder that bakes a query string in:

- Step A: no non-Go-template placeholders.
- Step B: no `{{.X}}` captures.
- Step C: contains `?member_id=42`, no template syntax after `?`. -> kind = `url-with-query`.

Output:
```yaml
endpoint_construction:
  kind: url-with-query
  macros_used: []
  placeholders_unresolved: []
```

### Example 5: Kobler (Go) — initial pass

```yaml
# static/bidder-info/kobler.yaml
endpoint: "https://bid.essrtb.com/bid/prebid_server_rtb_call"
endpointCompression: gzip
```

- Step A-F: no signals.
- Step G: -> kind = `static` initially. Emit `incomplete-classification` quirk.

Later, `read-adapter-code` discovers `const devBidderEndpoint = "..."` and a request-time toggle. The orchestrator upgrades:

```yaml
endpoint_construction:
  kind: dev-prod-toggle    # Or hardcoded-toggle — see Note below.
  macros_used: []
  placeholders_unresolved: []
```

**Note on dev-prod-toggle vs hardcoded-toggle**: when the secondary URL is in YAML/extra_info -> `dev-prod-toggle`. When the secondary URL is a hardcoded Go `const` outside any config -> `hardcoded-toggle` (anti-pattern). Kobler is `dev-prod-toggle` semantically (the toggle exists) but `hardcoded-toggle` structurally (the secondary URL is a Go const). Spec convention: emit the SEMANTIC kind (`dev-prod-toggle`) as the primary classification AND emit a `quirks[]` entry with `edge_case_taxon: hardcoded-config-as-anti-pattern` to record the structural anti-pattern. This matches the Kobler golden ([../../../test-fixtures/kobler.golden.spec.yaml](../../../test-fixtures/kobler.golden.spec.yaml)).

### Example 6: Hypothetical Java-style typo (yaml-field-name-typo + classification fallout)

```yaml
# Hypothetical Go YAML with Java-style kebab-case.
endpoint: "https://bid.example.com/rtb"
endpoint-compression: gzip   # Should be camelCase: endpointCompression.
dev-endpoint: "https://bid-dev.example.com/rtb"   # Java-only key in a Go file.
```

- Step 8 (typo detection in SKILL.md): emits two `yaml_field_name_quirks[]` entries.
- Step D (this file): YAML contains key `dev-endpoint` -> kind = `dev-prod-toggle`. Concurrent quirk for the kebab-case typo.

Output:
```yaml
endpoint_construction:
  kind: dev-prod-toggle
  macros_used: []
  placeholders_unresolved: []
yaml_field_name_quirks:
  - { found: "endpoint-compression", canonical: "endpointCompression", severity: FAIL, ... }
  - { found: "dev-endpoint", canonical: "(no Go canonical)", severity: INFO, ... }
```

---

## Macro detection rules (formal)

The Go-template macro regex is `\{\{\s*\.([A-Za-z][A-Za-z0-9]*)\s*\}\}`. Whitespace inside the braces is allowed (`{{ .X }}`) per `text/template` parser behavior. Capture group 1 is the field identifier.

For each captured identifier, perform a CASE-SENSITIVE membership check against the canonical 22-field set. The machine-readable copy this skill and R8 both consume is [../../shared/endpoint-macros.yaml](../../shared/endpoint-macros.yaml) (`go_template_macros`); the annotated table is at [../../../../review/skills/shared/framework-utilities.md](../../../../review/skills/shared/framework-utilities.md) (Endpoint Template Macros section). Both mirror `macros.EndpointTemplateParams` at `macros/macros.go:9-32`. The 22 fields in alphabetical order:

```
AccountID, AdUnit, AppDomain, Bundle, GvlID, Host,
ImpID, MediaType, NetworkId, PageID, PartnerId, PlacementID,
PublisherID, Region, SeatID, SiteDomain, SourceId, SspID,
SspId, SupplyId, TokenID, ZoneID
```

(`SspId` and `SspID` are BOTH valid — distinct fields with different casing per `macros/macros.go`. The same trap applies to `NetworkId`, `PartnerId`, and `SourceId`, which end in lowercase `d` while `AccountID`, `GvlID`, `ImpID`, `PlacementID`, `PublisherID`, `SeatID`, `TokenID`, and `ZoneID` end in uppercase `ID`.)

Common mistakes to detect:

- `{{.External_URL}}` -> NOT in set (it's `{{.ExternalURL}}` in user-sync templates, AND user-sync template fields don't apply to endpoint URLs). Emit FAIL.
- `{{.publisher_id}}` -> NOT in set (canonical is `PublisherID`). Emit FAIL.
- `{{.AccountId}}` -> NOT in set (canonical is `AccountID` with uppercase D). Emit FAIL.
- `{{.GVL_ID}}` -> NOT in set (canonical is `GvlID`). Emit FAIL.

The case-sensitive check is intentional — Go templates ARE case-sensitive on field names. A typo does not degrade quietly: `text/template` cannot resolve the field, `Execute` returns `can't evaluate field <Typo> in type macros.EndpointTemplateParams`, and `config.validateAdapterEndpoint` (`config/bidderinfo.go:492-507`) turns that into a config error that fails `TestBidderInfoFiles`.

---

## Deploy-time token detection rules (formal)

Three regex patterns scanned in order:

1. `#\{([A-Z_][A-Z0-9_]*)\}#` — captures `REGION` from `#{REGION}#`. Canonical: Rubicon, appStockSSP.
2. `\$\{([A-Z_][A-Z0-9_]*)\}` — captures `HOST` from `${HOST}`. Shell-style.
3. `<([A-Z_][A-Z0-9_]*)>` — captures `REGION` from `<REGION>`. Angle-bracket.

(Lowercase tokens are NOT detected — by convention deploy-time tokens are uppercase, matching shell ALL_CAPS env var convention. Lowercase angle-bracket-like content is treated as opaque URL content.)

For each match, the skill emits BOTH a `placeholders_unresolved[]` entry AND a `deploy_time_tokens[]` entry. The two collections serve different consumers:

- `placeholders_unresolved[]` -> fed to `endpoint-placeholder-unresolved` warning + porter awareness.
- `deploy_time_tokens[]` -> fed to operator-runbook generation (future tooling) + cross-language port-translation Rule 15.

Pairing requirement: deploy-time tokens REQUIRE `disabled: true` (Go) or `enabled: false` (Java) per PR #4502 convention. Missing pairing -> FAIL warning.

---

## Typo-quirk detection rules (formal — extends SKILL.md Step 8)

The endpoint string itself is rarely typo'd (it's a literal URL); typos affect SIBLING YAML keys. The full registry:

| Typo'd key (found) | Canonical key (Go) | Severity | Silent runtime effect |
|---|---|---|---|
| `endpoint-compression` | `endpointCompression` | FAIL | Compression silently disabled. |
| `endpoint_compression` | `endpointCompression` | FAIL | Snake_case variant; same silent effect. |
| `endpointcompression` | `endpointCompression` | FAIL | All-lowercase variant; same silent effect. |
| `modifying-vast-xml-allowed` | `modifyingVastXmlAllowed` | FAIL | Vast XML modification silently defaults. |
| `modifying_vast_xml_allowed` | `modifyingVastXmlAllowed` | FAIL | Snake_case variant. |
| `gvl-vendor-id` | `gvlVendorID` | FAIL | GVL silently 0 -> bidder unregistered from GVL. |
| `gvl_vendor_id` | `gvlVendorID` | FAIL | Snake_case variant. |
| `alias-of` | `aliasOf` | FAIL | Alias relationship silently broken. |
| `white-label-only` | `whiteLabelOnly` | FAIL | White-label flag silently false. |
| `dev-endpoint` | (no Go canonical) | INFO | Java-style key in a Go file. Unused at runtime. |
| `dev_endpoint` | (no Go canonical) | INFO | Snake_case Java-style residue. |
| `meta-info` | (no Go canonical) | INFO | Java-unified-config residue. |

For each detected typo, emit:

1. `bidder_info.yaml_field_name_quirks[]` entry: `{ found: <found-key>, canonical: <canonical-or-null>, severity: <FAIL|WARN|INFO>, line: <line-number>, summary: <text> }`.
2. `provenance.warnings[]` entry: `{ type: yaml-field-name-typo, file: static/bidder-info/{xyz}.yaml, line: <line>, summary: <text> }`.
3. Top-level `quirks[]` entry: `{ id: yaml-typo-{found-key}, file: static/bidder-info/{xyz}.yaml, summary: <text>, edge_case_taxon: yaml-field-name-typo }`. For the specific `endpointCompression` regression, use the more specific taxon `endpoint-compression-typo` per [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md).

Typo pass-through: the FOUND key (verbatim, with its typo'd casing) is preserved in `yaml_extra_fields` so a future `write/` skill emits the file byte-identically. Do NOT silently rewrite the typo to canonical form during the read pass — that would defeat round-trip determinism.

---

## Sources

- Schema: [../../shared/adapter-spec.md](../../shared/adapter-spec.md) (`bidder_info.endpoint_construction`, `deploy_time_tokens[]`, `yaml_field_name_quirks[]`).
- Taxonomy: [../../shared/behavior-taxonomy.md](../../shared/behavior-taxonomy.md) (the kind enum; the `quirks edge_case_taxon` registry).
- Port translation rules: [../../shared/port-translation-rules.md](../../shared/port-translation-rules.md) (Rules 11–15 for endpoint resolution; Rule 33 for aliases inversion; Rule 34 for YAML unification).
- Field index (master truth for canonical keys): [../../../../review/skills/bidder-info-pr-review/references/field-index.md](../../../../review/skills/bidder-info-pr-review/references/field-index.md).
- Endpoint macros (canonical machine-readable `EndpointTemplateParams` field set, 22 entries): [../../shared/endpoint-macros.yaml](../../shared/endpoint-macros.yaml) (`go_template_macros`).
- Framework utilities (annotated `EndpointTemplateParams` table and deploy-time token policy from PR #4502): [../../../../review/skills/shared/framework-utilities.md](../../../../review/skills/shared/framework-utilities.md).
- Reviewer practice: PR #4502 (appStockSSP `#{REGION}#`); PR #4211 (HTTP-tolerance: "While https is strongly preferred, http is still permitted"); Ogury `endpointCompression` regression (Java edge case 34).
