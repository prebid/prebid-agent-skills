# BidderInfo Field Index

Complete Go struct mapping from `config/bidderinfo.go`. Use this to trace any YAML field back to its source type, validation function, and constraints.

**Upstream source (canonical):** https://github.com/prebid/prebid-server/blob/master/config/bidderinfo.go
**Raw URL (for fetching):** https://raw.githubusercontent.com/prebid/prebid-server/master/config/bidderinfo.go

> **Sync policy:** This file is a local snapshot. The `pr-triage` skill's Step 2 runs centralized drift checks against the live source on every review run; this skill's Step 1b reads those drift results from the manifest. If new fields are found upstream, update this file to match.

---

## Module path

**Current major:** `github.com/prebid/prebid-server/v4` (since release v4.0.0, March 2026). The raw URL above stays on `master` branch — its content reflects the current major.

For framework-wide concerns (endpoint template macros, error types, anti-patterns, maintainer email policy, white-label policy, naming conventions, alias semantics, test harness contract), see [../../shared/framework-utilities.md](../../shared/framework-utilities.md).

---

## BidderInfo (root)

```go
type BidderInfo struct {
    AliasOf                 string                `yaml:"aliasOf"`
    WhiteLabelOnly          bool                  `yaml:"whiteLabelOnly"`
    Disabled                bool                  `yaml:"disabled"`
    Endpoint                string                `yaml:"endpoint"`
    ExtraAdapterInfo        string                `yaml:"extra_info"`
    OpenRTB                 *OpenRTBInfo          `yaml:"openrtb"`
    Maintainer              *MaintainerInfo       `yaml:"maintainer"`
    Capabilities            *CapabilitiesInfo     `yaml:"capabilities"`
    ModifyingVastXmlAllowed bool                  `yaml:"modifyingVastXmlAllowed"`
    Debug                   *DebugInfo            `yaml:"debug"`
    Geoscope                []string              `yaml:"geoscope"`
    GVLVendorID             uint16                `yaml:"gvlVendorID"`
    Syncer                  *Syncer               `yaml:"userSync"`
    Experiment              BidderInfoExperiment  `yaml:"experiment"`
    XAPI                    AdapterXAPI           `yaml:"xapi"`
    PlatformID              string                `yaml:"platform_id"`
    AppSecret               string                `yaml:"app_secret"`
    EndpointCompression     string                `yaml:"endpointCompression"`
}
```

| YAML Path | Go Field | Go Type | Required | Validation |
|-----------|----------|---------|----------|------------|
| `aliasOf` | AliasOf | string | No | Parent must exist, no alias chains. Minimum valid alias YAML is `aliasOf: parent` (1 line — full inheritance). The 2-line form (`endpoint:` + `aliasOf:`) is the SmartHub/Limelight family pattern. See SKILL.md Workflow: Alias Adapter Added step 9. |
| `whiteLabelOnly` | WhiteLabelOnly | bool | No | Marks the bidder as available only as a white-label parent (aliases will reference it). Does NOT preclude Go adapter code on the parent (e.g., TeqBlaze parent has Go code AND `whiteLabelOnly: true` to enable aliases). See ../../shared/framework-utilities.md#aliasing. |
| `disabled` | Disabled | bool | No | Default: false |
| `endpoint` | Endpoint | string | Yes | `validateAdapterEndpoint()` — valid URL, template macro resolution |
| `extra_info` | ExtraAdapterInfo | string | No | Must be valid JSON if present |
| `openrtb` | OpenRTB | *OpenRTBInfo | No | — |
| `maintainer` | Maintainer | *MaintainerInfo | Yes | `validateMaintainer()` |
| `capabilities` | Capabilities | *CapabilitiesInfo | Yes | `validateCapabilities()` |
| `modifyingVastXmlAllowed` | ModifyingVastXmlAllowed | bool | No | Default: true |
| `debug` | Debug | *DebugInfo | No | — |
| `geoscope` | Geoscope | []string | No | `validateGeoscope()` — **case-insensitive**: each entry is `strings.ToUpper(strings.TrimSpace(...))`-ed before every comparison, so lowercase entries pass. Uppercase is conventional; lowercase `global` is the dominant master form (27 files vs 1 `GLOBAL`). Casing is not a defect — do not FAIL or WARN on it. |
| `gvlVendorID` | GVLVendorID | uint16 | No | Must be > 0 if present |
| `userSync` | Syncer | *Syncer | No | `validateSyncer()` |
| `experiment` | Experiment | BidderInfoExperiment | No | — |
| `xapi` | XAPI | AdapterXAPI | No | — |
| `platform_id` | PlatformID | string | No | — |
| `app_secret` | AppSecret | string | No | SECURITY: no real secrets |
| `endpointCompression` | EndpointCompression | string | No | Value casing NOT case-sensitive: runtime `strings.ToUpper`s it (`exchange/bidder.go:850`) before matching `Gzip = "GZIP"` (`:100`), so `gzip`/`GZIP`/`Gzip` all enable compression — non-uppercase *value* is **INFO** (uppercase `GZIP` is convention), not FAIL. The real FAIL is a field-NAME typo (`endpoint-compression`/`endpoint_compression` ≠ camelCase key) → silent no-op (Ogury). Omit entirely if not supporting compression. |

---

## OpenRTBInfo

```go
type OpenRTBInfo struct {
    Version              string `yaml:"version"`
    GPPSupported         bool   `yaml:"gpp-supported"`
    MultiformatSupported *bool  `yaml:"multiformat-supported"`
}
```

| YAML Path | Go Field | Go Type | Notes |
|-----------|----------|---------|-------|
| `openrtb.version` | Version | string | e.g., `"2.6"` |
| `openrtb.gpp-supported` | GPPSupported | bool | Not yet actively supported |
| `openrtb.multiformat-supported` | MultiformatSupported | *bool | nil = default behavior |

---

## MaintainerInfo

```go
type MaintainerInfo struct {
    Email string `yaml:"email"`
}
```

| YAML Path | Go Field | Go Type | Required | Notes |
|-----------|----------|---------|----------|-------|
| `maintainer.email` | Email | string | **Yes** | `validateMaintainer()` enforces presence |

---

## CapabilitiesInfo

```go
type CapabilitiesInfo struct {
    App  *PlatformInfo `yaml:"app"`
    Site *PlatformInfo `yaml:"site"`
    DOOH *PlatformInfo `yaml:"dooh"`
}
```

At least one of `app`, `site`, or `dooh` must be present. Validated by `validateCapabilities()`.

### PlatformInfo

```go
type PlatformInfo struct {
    MediaTypes []openrtb_ext.BidType `yaml:"mediaTypes"`
}
```

| YAML Path | Go Field | Go Type | Valid Values |
|-----------|----------|---------|-------------|
| `capabilities.{app,site,dooh}.mediaTypes` | MediaTypes | []BidType | `banner`, `video`, `native`, `audio` |

Validated by `validatePlatformInfo()`. At least one media type required per platform.

---

## DebugInfo

```go
type DebugInfo struct {
    Allow bool `yaml:"allow"`
}
```

| YAML Path | Go Field | Go Type |
|-----------|----------|---------|
| `debug.allow` | Allow | bool |

---

## Syncer (userSync)

```go
type Syncer struct {
    Key             string           `yaml:"key"`
    Supports        []string         `yaml:"supports"`
    IFrame          *SyncerEndpoint  `yaml:"iframe"`
    Redirect        *SyncerEndpoint  `yaml:"redirect"`
    ExternalURL     string           `yaml:"externalUrl"`
    FormatOverride  string           `yaml:"formatOverride"`
    Enabled         *bool            `yaml:"enabled"`
    SkipWhen        *SkipWhen        `yaml:"skipwhen"`
}
```

| YAML Path | Go Field | Go Type | Validation |
|-----------|----------|---------|------------|
| `userSync.key` | Key | string | Must be unique across bidders |
| `userSync.supports` | Supports | []string | `iframe` or `redirect` only |
| `userSync.iframe` | IFrame | *SyncerEndpoint | — |
| `userSync.redirect` | Redirect | *SyncerEndpoint | — |
| `userSync.externalUrl` | ExternalURL | string | — |
| `userSync.formatOverride` | FormatOverride | string | `""`, `"b"`, or `"i"` only |
| `userSync.enabled` | Enabled | *bool | nil = default |
| `userSync.skipwhen` | SkipWhen | *SkipWhen | — |

### SyncerEndpoint

```go
type SyncerEndpoint struct {
    URL         string `yaml:"url"`
    RedirectURL string `yaml:"redirectUrl"`
    ExternalURL string `yaml:"externalUrl"`
    UserMacro   string `yaml:"userMacro"`
}
```

Applies to both `userSync.iframe.*` and `userSync.redirect.*`.

| YAML Suffix | Go Field | Notes |
|-------------|----------|-------|
| `.url` | URL | Required for endpoint. Template macros: `{{.GDPR}}`, `{{.GDPRConsent}}`, `{{.USPrivacy}}`, `{{.GPP}}`, `{{.GPPSID}}`, `{{.RedirectURL}}` |
| `.redirectUrl` | RedirectURL | Template macros: `{{.ExternalURL}}`, `{{.BidderName}}`, `{{.SyncType}}`, `{{.UserMacro}}` |
| `.externalUrl` | ExternalURL | Falls back to syncer or host level |
| `.userMacro` | UserMacro | Bidder-specific, e.g., `$UID` |

### SkipWhen

```go
type SkipWhen struct {
    GDPR   bool     `yaml:"gdpr"`
    GPPSID []string `yaml:"gpp_sid"`
}
```

| YAML Path | Go Field | Go Type |
|-----------|----------|---------|
| `userSync.skipwhen.gdpr` | GDPR | bool |
| `userSync.skipwhen.gpp_sid` | GPPSID | []string |

---

## BidderInfoExperiment

```go
type BidderInfoExperiment struct {
    AdsCert BidderAdsCert `yaml:"adsCert"`
}
```

### BidderAdsCert

```go
type BidderAdsCert struct {
    Enabled bool `yaml:"enabled"`
}
```

| YAML Path | Go Field | Go Type |
|-----------|----------|---------|
| `experiment.adsCert.enabled` | Enabled | bool |

---

## AdapterXAPI

```go
type AdapterXAPI struct {
    Username string `yaml:"username"`
    Password string `yaml:"password"`
    Tracker  string `yaml:"tracker"`
}
```

| YAML Path | Go Field | Go Type | Notes |
|-----------|----------|---------|-------|
| `xapi.username` | Username | string | Primarily Rubicon |
| `xapi.password` | Password | string | SECURITY: no real credentials |
| `xapi.tracker` | Tracker | string | Primarily Rubicon |

---

## Common YAML Field Patterns Observed in Master

Patterns surfaced from review of the 89 reference adapter PRs (`prebid-server-go/references/new-bid-adapter-prs.md`):

- **Minimal alias** (1 line): `aliasOf: parent` only — fully inheriting (PR #4216 admaticde, PR #4357 ttd).
- **Standard alias** (2 lines): `endpoint:` + `aliasOf: parent` — most SmartHub/Limelight/Adkernel family aliases.
- **Alias with override**: `aliasOf:` + override fields (`gvlVendorID`, `endpoint`, `maintainer`, `userSync`).
- **Disabled-by-default + region placeholder**: when `endpoint` contains a non-Go-template placeholder (e.g., `#{REGION}#`, `${X}`), the YAML MUST set `disabled: true` and include a comment block listing valid values (PR #4502 appStockSSP).
- **Alias parent**: a parent with many aliases keeps its own Go adapter, which serves the aliases. At @0ba3523 the largest are `teqblaze` (25 aliases), `limelightDigital` (23), `smarthub` (11). `whiteLabelOnly: true` does NOT preclude Go code — but it is also NOT the alias-parent marker: `teqblaze.yaml` is the only upstream file that sets it, and `smarthub.yaml` serves 11 aliases without it. Key alias-parent reasoning on alias count, not on the flag.
- **`whiteLabelOnly` + `aliasOf` is a startup abort**: `validateAliases` (`config/bidderinfo.go:461-463`) returns `bidder '%s' is an alias and cannot be set as white label only`, reaching `logger.Fatalf` through `processBidderAliases` → `LoadBidderInfoFromDisk`. **FAIL**.
- **HTTP endpoint tolerated**: HTTPS preferred but HTTP permitted per PR #4211. Limelight family adapters routinely use HTTP.
- **GVL vendor ID is NEVER inherited by an alias**: `config/bidderinfo.go:371-373` states the alias's `GVLVendorID` is intentionally never set from the parent, "as inheriting from the parent is not safe for legal reasons"; the merge block below it copies nine other fields and omits this one. `ToGVLVendorIDMap` (`:428-436`) then drops any bidder with `GVLVendorID == 0`, so an alias omitting the field gets no GDPR vendor registration. A non-zero declaration on an alias is the required form (**PASS**); omission where the parent has a GVL is **WARN**; `gvlVendorID: 0` is **WARN** for removal (PR #4329). 44 of 113 upstream alias YAMLs declare their own.
- **GVL name tolerance**: GVL ID 377 = "AddApptr GmbH" but PR #4547 (Gravite) was accepted because privacy URL is gravite.net — corporate restructure case. GVL name mismatches are tolerated when there's a credible relationship.
- **modifyingVastXmlAllowed**: common — 61 `static/bidder-info/*.yaml` files carry the key at @0ba3523. Do not flag its presence as unusual; verify the value is deliberate for a video adapter opting in or out of VAST modification tracking.
- **endpointCompression**: the runtime `strings.ToUpper`s the value before comparing it to the `Gzip = "GZIP"` constant (`exchange/bidder.go:849-850`; constant at `:100`), so any casing works and there is no uppercase convention to enforce — lowercase `gzip` is in fact the majority upstream (58 vs 16 at @0ba3523). Emit no finding on value casing. The FAIL case is a field-NAME typo (`endpoint-compression` / `endpoint_compression`), which does not bind and silently disables compression.
- **userSync.supports list**: declares which sync types (`iframe`, `redirect`) the bidder supports without providing default URLs (host configures URLs). Common when bidder requires onboarding before sync activation.
- **Bidder rename for major version**: rename PRs (e.g., `adoppler` → `elementaltv` PR #4639) are deferred to the next major release due to breaking-change semantics. Flag rename intent as INFO.

---

## Validation Functions

| Function | What It Validates |
|----------|-------------------|
| `(BidderInfos).validate()` | Method (NOT a top-level function) on `BidderInfos` map. Orchestrates all validation for all enabled bidders. Doc-comment misleadingly references it as `validateBidderInfos` but the actual symbol is `(BidderInfos).validate`. Called from `config.New` at startup. |
| `validateAdapterEndpoint()` | Endpoint URL validity, template macro resolution |
| `validateInfo()` | Maintainer, geoscope, capabilities |
| `validateMaintainer()` | `maintainer.email` must exist |
| `validateGeoscope()` | ISO 3166-1 alpha-3, `GLOBAL`, `EEA`, `!` prefix. Upper-cases and trims each entry before every comparison (`config/bidderinfo.go:645-675`), so the check is case-insensitive and lowercase entries validate — casing is never a defect. |
| `validateCapabilities()` | At least one platform with valid media types |
| `validatePlatformInfo()` | Media types: `banner`, `video`, `native`, `audio` |
| `validateAliasCapabilities()` | Alias capabilities subset of parent |
| `validateSyncer()` | FormatOverride and Supports values |
| `validateAliases()` | Parent exists, no chains, field overrides |

---

## Canonical YAML Field Paths

Flat list of every possible YAML path for task creation:

```
endpoint
endpointCompression
maintainer.email
gvlVendorID
geoscope
disabled
modifyingVastXmlAllowed
extra_info
aliasOf
whiteLabelOnly
platform_id
app_secret
openrtb.version
openrtb.gpp-supported
openrtb.multiformat-supported
capabilities.app.mediaTypes
capabilities.site.mediaTypes
capabilities.dooh.mediaTypes
debug.allow
userSync.key
userSync.supports
userSync.iframe.url
userSync.iframe.redirectUrl
userSync.iframe.externalUrl
userSync.iframe.userMacro
userSync.redirect.url
userSync.redirect.redirectUrl
userSync.redirect.externalUrl
userSync.redirect.userMacro
userSync.externalUrl
userSync.formatOverride
userSync.enabled
userSync.skipwhen.gdpr
userSync.skipwhen.gpp_sid
experiment.adsCert.enabled
xapi.username
xapi.password
xapi.tracker
```

## Regeneration commands

Commands behind the counts quoted in `SKILL.md`. They live here rather than in the SKILL body because that body is loaded into context on every review; the numbers belong in the check, the shell does not.

**Command 1** — run in a `prebid/prebid-server` checkout at the pinned SHA.

```bash
     # in a prebid-server checkout
     python3 - <<'EOF'
     import glob, os, json, yaml
     d = {os.path.basename(f)[:-5]: yaml.safe_load(open(f)) or {} for f in glob.glob('static/bidder-info/*.yaml')}
     a = {n: v for n, v in d.items() if v.get('aliasOf')}
     for k in ('capabilities', 'userSync', 'gvlVendorID'):
         dec = [n for n in a if k in a[n]]
         same = [n for n in dec if k in d.get(a[n]['aliasOf'], {})
                 and json.dumps(d[a[n]['aliasOf']][k], sort_keys=True) == json.dumps(a[n][k], sort_keys=True)]
         print(k, len(a), len(dec), len(same))   # capabilities 113 12 11 | userSync 113 55 20 | gvlVendorID 113 44 18
     EOF
```

**Command 2** — run in a `prebid/prebid-server` checkout at the pinned SHA.

```bash
   # in a prebid-server checkout — regenerate the 115/349 split
   python3 - <<'EOF'
   import glob, os, re, yaml
   from urllib.parse import urlparse
   tot = un = 0
   for p in glob.glob('static/bidder-info/*.yaml'):
       b = os.path.basename(p)[:-5]
       ep = (yaml.safe_load(open(p)) or {}).get('endpoint')
       if not isinstance(ep, str): continue
       h = urlparse(ep).netloc.lower()
       if not h: continue
       tot += 1
       nb, nh = re.sub(r'[^a-z0-9]', '', b.lower()), re.sub(r'[^a-z0-9]', '', h)
       if not any(nb[i:i + 5] in nh for i in range(max(1, len(nb) - 4))): un += 1
   print(tot, un)   # 349 115
   EOF
```

**Command 3** — run in a `prebid/prebid-server` checkout at the pinned SHA.

```bash
  # in a prebid-server checkout — counted at master @0ba3523
  grep -lE '^ +- *"?!?global"?$' static/bidder-info/*.yaml | wc -l   # 27
  grep -lE '^ +- *"?!?GLOBAL"?$' static/bidder-info/*.yaml | wc -l   # 1
  grep -lE '^geoscope:' static/bidder-info/*.yaml | wc -l            # 47 files declare the field
```

**Command 4** — run in a `prebid/prebid-server` checkout at the pinned SHA.

```bash
    python3 - <<'EOF'
    import glob, json, yaml
    m = f = both = 0
    for p in glob.glob('static/bidder-info/*.yaml'):
        d = yaml.safe_load(open(p)) or {}
        macro = any(x in json.dumps(d.get('userSync') or {}) for x in ('{{.GPP}}', '{{.GPPSID}}'))
        flag = bool((d.get('openrtb') or {}).get('gpp-supported'))
        m += macro; f += flag; both += macro and flag
    print(m, f, both)   # 90 26 16  -> 74 macro-without-flag
    EOF
```

**Command 5** — run in a `prebid/prebid-server` checkout at the pinned SHA.

```bash
    # in a prebid-server checkout — adapters sending a 2.6 header, vs what their YAML declares
    python3 - <<'EOF'
    import glob, os, re, yaml
    send26 = set()
    for f in glob.glob('adapters/*/*.go'):
        if f.endswith('_test.go'):
            continue
        t = open(f, errors='ignore').read()
        if not re.search(r'(?i)x-openrtb-version', t):
            continue                                  # header sent inline, or via a named constant:
        if re.search(r'(?i)x-openrtb-version[^\n]{0,60}2\.6', t) or re.search(r'(?i)\w*openrtbversion\w*\s*=\s*"2\.6"', t):
            send26.add(f.split('/')[1])
    for b in sorted(send26):
        p = 'static/bidder-info/%s.yaml' % b
        v = ((yaml.safe_load(open(p)) or {}).get('openrtb') or {}).get('version') if os.path.exists(p) else None
        print('%-14s %s' % (b, v or 'NO openrtb.version -> request is down-converted to 2.5'))
    EOF
    # at master @0ba3523: 7 senders; madsense / resetdigital / trustx declare no openrtb.version
```
