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
| `geoscope` | Geoscope | []string | No | `validateGeoscope()` |
| `gvlVendorID` | GVLVendorID | uint16 | No | Must be > 0 if present |
| `userSync` | Syncer | *Syncer | No | `validateSyncer()` |
| `experiment` | Experiment | BidderInfoExperiment | No | — |
| `xapi` | XAPI | AdapterXAPI | No | — |
| `platform_id` | PlatformID | string | No | — |
| `app_secret` | AppSecret | string | No | SECURITY: no real secrets |
| `endpointCompression` | EndpointCompression | string | No | **`"GZIP"` (uppercase, case-sensitive)**. The check is direct string comparison against the `Gzip = "GZIP"` constant in `exchange/bidder.go:100`; lowercase `"gzip"` silently fails to enable compression. Omit entirely if not supporting compression. |

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
- **White-label parent**: parent has full Go adapter + `whiteLabelOnly: true` (TeqBlaze, SmartHub). Aliases reference the parent's name. The Go code of the parent serves the aliases — `whiteLabelOnly: true` does NOT preclude Go code.
- **HTTP endpoint tolerated**: HTTPS preferred but HTTP permitted per `bsardo` PR #4211 quote. Limelight family adapters routinely use HTTP.
- **GVL inheritance quirk**: aliases cannot effectively override the parent's GVL vendor ID — `config/bidderinfo.go` deliberately inherits whether the alias sets `gvlVendorID: 0` or omits the field. Setting `gvlVendorID: 0` adds confusion; reviewers ask to remove it (PR #4329).
- **GVL name tolerance**: GVL ID 377 = "AddApptr GmbH" but PR #4547 (Gravite) was accepted because privacy URL is gravite.net — corporate restructure case. GVL name mismatches are tolerated when there's a credible relationship.
- **modifyingVastXmlAllowed**: rare; only seen in #4522 alliance_gravity. Set deliberately when video adapter wants to opt-in/opt-out of VAST modification tracking.
- **endpointCompression: GZIP** is increasingly common (4+ PRs in 2025–2026). Suggest as INFO when adapter handles large requests. Value MUST be uppercase `"GZIP"` — case-sensitive comparison against the `Gzip = "GZIP"` constant.
- **userSync.supports list**: declares which sync types (`iframe`, `redirect`) the bidder supports without providing default URLs (host configures URLs). Common when bidder requires onboarding before sync activation.
- **Bidder rename for major version**: rename PRs (e.g., `progx` → `programmaticX` PR #4456) are deferred to the next major release (v3 → v4) due to breaking-change semantics. Flag rename intent as INFO.

---

## Validation Functions

| Function | What It Validates |
|----------|-------------------|
| `(BidderInfos).validate()` | Method (NOT a top-level function) on `BidderInfos` map. Orchestrates all validation for all enabled bidders. Doc-comment misleadingly references it as `validateBidderInfos` but the actual symbol is `(BidderInfos).validate`. Called from `config.New` at startup. |
| `validateAdapterEndpoint()` | Endpoint URL validity, template macro resolution |
| `validateInfo()` | Maintainer, geoscope, capabilities |
| `validateMaintainer()` | `maintainer.email` must exist |
| `validateGeoscope()` | ISO 3166-1 alpha-3, `GLOBAL`, `EEA`, `!` prefix |
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

---

## Pattern Catalog

Patterns extracted from periodic review of the 89 reference adapter PRs. Stable schema; cap 8 entries per skill.

### Schema

```
### Pattern P-{NN}: {short title}
- Symptom in diff: {what the diff looks like}
- Frequency observed: {N of total reference PRs}
- Affected workflow: {Workflow link}
- Severity: FAIL | WARN | INFO
- Action: {what the skill does when it sees this}
```

### Entries

(Populated by current refresh — see SKILL.md for the active rule list.)
