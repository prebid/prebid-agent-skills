# Go artifact shapes (port-java2go emission contract)

Phase D1.3 deliverable — captures the exact shape Go artifacts must take so that `port-java2go`'s Step 5 emission produces files indistinguishable from upstream-merged hand-authored Go code, and so the emission passes upstream `prebid-server`'s CI gates without operator hand-edits.

## 1. Source-of-truth pinning

Templates in `../templates/*.j2` are derived from real merged PRs in `prebid/prebid-server`, NOT synthesized ideals. The pinned reference: upstream master at SHA `2fae16f31693` (verified 2026-05-04 per [`../../../docs/methodology/repo-rules.md`](../../../docs/methodology/repo-rules.md)).

When upstream Go conventions shift (e.g., a new `adapters.*` helper supersedes an old idiom), templates regenerate AND `repo-rules.md`'s "Last verified" cell bumps in the same PR.

## 2. License headers

`prebid/prebid-server` does NOT use per-file license headers (verified across 271 bidder packages). Repository-level LICENSE.md (Apache 2.0) covers all files. Templates emit:

- NO `// Copyright ...` header
- NO `//go:build` directive (these adapters compile unconditionally on all targets)
- The first non-blank line is the `package {bidder}` declaration

## 3. Package declarations

Per upstream convention, every Go file under `adapters/{bidder}/` declares:

```go
package {bidder}
```

Where `{bidder}` is the camelCase or snake_case Go YAML name (matching the directory name; see [`../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml`](../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml) for the canonical mapping). Note that the package name MAY differ from the YAML name in a small set of cases (e.g., `cadent_aperture_mx` directory contains `package cadentaperturemx`). The port skill consults the read-skill's `cross_language.go_artifacts.package_name` field for the authoritative package name.

Files at `openrtb_ext/imp_{bidder}.go` declare `package openrtb_ext` (a single shared package).

## 4. Import order (gofmt + goimports convention)

Two groups separated by exactly one blank line. `gofmt` enforces sorting within each group:

```go
package kobler

import (
    "encoding/json"
    "fmt"
    "net/http"

    "github.com/prebid/openrtb/v20/openrtb2"
    "github.com/prebid/prebid-server/v3/adapters"
    "github.com/prebid/prebid-server/v3/config"
    "github.com/prebid/prebid-server/v3/openrtb_ext"
)
```

Group 1: stdlib (`net/http`, `encoding/json`, etc.).
Group 2: third-party + project-own (`github.com/prebid/...`, `github.com/iab/...`, etc.).

Templates emit imports in this convention; `gofmt -s -w` post-process is the gate (`scripts/lib/port_engine.gofmt_post_process`).

## 5. File naming convention (per-bidder package layout)

Minimum viable file set for a Go adapter:

| File | Purpose |
|---|---|
| `adapters/{bidder}/{bidder}.go` | Main implementation: `Builder` + `MakeRequests` + `MakeBids`. |
| `adapters/{bidder}/{bidder}_test.go` | Thin test wrapper invoking `adapters.RunJSONBidderTest("{bidder}test/exemplary")`. |
| `adapters/{bidder}/{bidder}test/exemplary/*.json` | Fixture pairs (one file per call) — happy path. |
| `adapters/{bidder}/{bidder}test/supplemental/*.json` | Fixture pairs — error paths reachable in Go. |
| `adapters/{bidder}/params_test.go` | Validates `static/bidder-params/{bidder}.json` against schema. |
| `openrtb_ext/imp_{bidder}.go` | Cross-package POJO struct: `ImpExt{Bidder}` with `json:"X"` tags. |
| `static/bidder-info/{bidder}.yaml` | Bidder-info YAML (camelCase keys). |
| `static/bidder-params/{bidder}.json` | Bidder-params JSON Schema (byte-copy from Java per Rule 38). |

For multi-file adapters (rare; large codebases like rubicon, appnexus), additional `.go` files at `adapters/{bidder}/` carry helper functions; the convention is one file per logical concern (e.g., `models.go`, `utils.go`). Most ported adapters fit in a single `{bidder}.go` file.

## 6. Builder + MakeRequests + MakeBids skeleton

Canonical signature (per real-merged-PR audit):

```go
type adapter struct {
    endpoint string
    // Optional: extra config fields if Rule 35 inverse demoted typed Java
    // config to opaque ExtraAdapterInfo.
}

func Builder(_ openrtb_ext.BidderName, config config.Adapter, _ config.Server) (adapters.Bidder, error) {
    return &adapter{endpoint: config.Endpoint}, nil
}

func (a *adapter) MakeRequests(request *openrtb2.BidRequest, reqInfo *adapters.ExtraRequestInfo) ([]*adapters.RequestData, []error) {
    // ... per-batching-rule logic (Rule 16/17/18)
}

func (a *adapter) MakeBids(request *openrtb2.BidRequest, requestData *adapters.RequestData, responseData *adapters.ResponseData) (*adapters.BidderResponse, []error) {
    // Rule 30 canonical helpers:
    if adapters.IsResponseStatusCodeNoContent(responseData) {
        return nil, nil
    }
    if err := adapters.CheckResponseStatusCodeForErrors(responseData); err != nil {
        return nil, []error{err}
    }
    // ... bid-type resolution (Rule 23-25)
}
```

`Builder` MUST take three parameters in this order even if some are unused (the framework dispatch convention). Underscore-rename unused params; gofmt enforces.

`MakeRequests` returns `[]*adapters.RequestData, []error`. NEVER return `nil, nil` for a successful empty response — return `[]*adapters.RequestData{}, nil` (or omit the empty slice entirely; framework treats nil as zero requests).

`MakeBids` returns `*adapters.BidderResponse, []error`. Use the canonical helpers per Rule 30 — explicit `responseData.StatusCode == 204` checks are legacy and surface a quirk on read; the port skill emits the canonical-helper form.

## 7. Headers construction (Rule 19 inverse)

Java's `HttpUtil.headers()` collapses to a single helper call. Go expands explicitly:

```go
headers := http.Header{}
headers.Add("Content-Type", "application/json;charset=utf-8")
headers.Add("Accept", "application/json")
// Optional auth/X-OpenRTB-Version per the source spec:
headers.Add("X-OpenRTB-Version", "2.6")
```

Templates emit each header on its own `Add()` line (NOT `Set()` — `Add()` is the upstream convention even for single-value headers).

## 8. ImpExt{Bidder} POJO (cross-package)

`openrtb_ext/imp_{bidder}.go` declares the per-impression bidder-extension struct. Translation from Java's `ExtImp{Bidder}.java`:

| Java | Go |
|---|---|
| `@JsonProperty("paramName") String fieldName;` | `FieldName string `json:"paramName"`` |
| Lombok `@Builder` | (no equivalent; templates emit composite literal in tests) |
| Lombok `@Value` | (no equivalent; struct is a plain Go struct) |
| `@JsonProperty("nested") NestedClass nested;` | `Nested NestedClass `json:"nested"`` (separate struct) |

PascalCase Go field names; lowercase-or-camelCase JSON tag matching the source spec's wire format.

## 9. Bidder-info YAML emission rules

`static/bidder-info/{bidder}.yaml` (NOT under `adapters/{bidder}/`):

```yaml
endpoint: <URL>
maintainer:
  email: <email>
gvlVendorID: <int>
endpointCompression: gzip  # optional
geoscope:
  - <region>
modifyingVastXmlAllowed: true  # optional
capabilities:
  site:
    mediaTypes:
      - banner
      - video
  app:
    mediaTypes:
      - banner
userSync:  # optional, since Wave-D conversion
  ...
```

**Field-name convention**: camelCase (NOT kebab-case). The Java-side equivalent uses kebab-case. Template MUST emit camelCase regardless of source spec's `bidder_info.yaml_field_name_quirks[]`.

For alias children, the YAML carries `aliasOf: parent_yaml_name` instead of repeating the parent's fields:

```yaml
aliasOf: adkernel
endpoint: https://eu.example.com/{{Host}}/bid  # only fields that diverge from parent
```

## 10. Exemplary-fixture re-authoring (Rule 36 inverse)

Java IT 4-file split → Go flat exemplary shape. Per source-spec call:

- Java `test-{bidder}-bid-request.json` + `test-{bidder}-bid-response.json` collapse into ONE Go fixture file under `{bidder}test/exemplary/{descriptive-name}.json`.
- The Go file structure is:

```json
{
  "expectedRequestSequence": [
    {
      "expectedRequest": { "uri": "...", "body": { ... } },
      "mockResponse": { "status": 200, "body": { ... } }
    }
  ],
  "httpCalls": [
    {
      "expectedRequest": { ... },
      "mockResponse": { ... }
    }
  ],
  "expectedBidResponses": [{ ... }]
}
```

The port skill emits `{descriptive-name}` based on the Java IT method name (e.g., `requestToBidderShouldReturnBids` → `simple-banner.json`). When the source IT class has no descriptive name, the skill generates `case-{n}.json`.

Error-path fixtures land in `{bidder}test/supplemental/` only when the error path is REACHABLE in Go. Java's IT errors that depend on Java-only framework state (Spring DI failures, Vert.x event-loop backpressure) are documented in `quirks[]` but not emitted as Go fixtures.

## 11. Registry insertion (`bidders.go` + `adapter_builders.go`)

`openrtb_ext/bidders.go`:
```go
const (
    ...
    BidderKobler   BidderName = "kobler"
    ...
)

var coreBidderNames = []BidderName{
    ...
    BidderKobler,
    ...
}
```

`exchange/adapter_builders.go`:
```go
import (
    ...
    "github.com/prebid/prebid-server/v3/adapters/kobler"
    ...
)

func newAdapterBuilders() map[openrtb_ext.BidderName]adapters.Builder {
    return map[openrtb_ext.BidderName]adapters.Builder{
        ...
        openrtb_ext.BidderKobler:   kobler.Builder,
        ...
    }
}
```

Insertion rules per [`registration-rules.md`](registration-rules.md). The port skill uses `scripts/lib/port_engine.alphabetical_insert` for both files.

## 12. Pre-emit checklist (D3 acceptance gates)

Before D3 considers an emission complete, every emitted file passes:

1. `go build ./adapters/{bidder}/...` exits 0
2. `gofmt -s -l ./adapters/{bidder}/...` exits with no diff
3. `go vet ./adapters/{bidder}/...` exits 0
4. `go test ./adapters/{bidder}/...` exits 0
5. `TestBidderUniquenessGatekeeping` passes (first-6-letter prefix unique against current `coreBidderNames` per `scripts/lib/port_engine.prefix_uniqueness_check`)
6. Adapter-coverage report (per upstream `./scripts/check_coverage.sh`) ≥ 80% on the new adapter
7. The emitted `bidder-params/{bidder}.json` byte-matches the Java-side source per Rule 38

The skill's Step 6 R5 check at port time runs after these gates pass.

## See also

- [`pr-shape.md`](pr-shape.md) — Go PR title + body convention (Go has no upstream PR template).
- [`registration-rules.md`](registration-rules.md) — alphabetical insertion across `bidders.go`, `adapter_builders.go`.
- [`porting-guide.md`](porting-guide.md) — internally-authored inverse porting guide (Java → Go specific; analogue of upstream Java's bid-adapter-porting-guide.md).
- [`../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml`](../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml) — canonical yaml_name → constant_root mapping (271 entries).
- [`../../../prebid-server-go/read/skills/read-adapter-code/references/file-role-heuristics.md`](../../../prebid-server-go/read/skills/read-adapter-code/references/file-role-heuristics.md) — read-side role classification (mirrors the emission contract here).
