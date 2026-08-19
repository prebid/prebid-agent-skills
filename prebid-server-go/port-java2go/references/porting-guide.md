# Inverse porting guide (Java → Go)

Phase D1.3 deliverable — internally-authored porting guide for the Java → Go direction. Analogue of upstream Java's [`bid-adapter-porting-guide.md`](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md), distilled from observed real-world Go-side new-adapter PRs + the lossy-direction asymmetries pre-declared in `port-translation-rules.yaml` Round-Trip Safety section.

This guide is offered upstream to `prebid/prebid-server` for adoption if Go maintainers find it useful, but until/unless that happens it lives here as the port-java2go skill's reference.

## 1. Treat the port as a re-implementation, not a translation

Unlike the Go → Java direction (where Java's framework supplies many concerns automatically — Spring DI, Lombok, `BidderUtil.defaultRequest`, `JacksonMapper`), the Java → Go direction REQUIRES the porter to expand many Java idioms into explicit Go code.

The port skill's emission is not a 1:1 translation. It re-authors the bidder using Go idioms while preserving:

- The bidder's behavior (which media types it accepts, how it batches, how it resolves endpoints, how it parses bid responses).
- The bidder-params JSON Schema (byte-equal copy per Rule 38 — the cross-language contract).
- The wire format (every field named the same on both languages, modulo `json:"X"` ↔ `@JsonProperty("X")` annotation translation).

What the port re-authors:

- HTTP header construction (Rule 19 inverse: Java `HttpUtil.headers()` collapse → Go explicit `http.Header.Add(...)` calls per [`go-artifact-shapes.md`](go-artifact-shapes.md) §7).
- HTTP status handling (Rule 30 inverse: Java framework-default → Go canonical helpers `adapters.IsResponseStatusCodeNoContent` + `adapters.CheckResponseStatusCodeForErrors`).
- Configuration access (Rule 35 inverse: Java typed `BidderConfigurationProperties` subclass → Go opaque `ExtraAdapterInfo` JSON string, with quirks emitted to capture loss).
- Test fixtures (Rule 36 inverse: Java IT 4-file split → Go flat `{bidder}test/exemplary/*.json` thin runner).

## 2. Lossy-direction asymmetries

The Java → Go direction is **less-information-preserving** than Go → Java. Specifically, the following Java constructs have no direct Go equivalent and lose structure in the port. The port skill emits `quirks[]` entries on the Go destination spec capturing what was lossy, so a future Go → Java re-port retains traceability.

### 2.1 Rule 35: typed-config-subclass demotion

**Java (source)** — typed configuration class:

```java
public class KoblerBidderConfigurationProperties extends BidderConfigurationProperties {
    private String devEndpoint;

    public String getDevEndpoint() { return devEndpoint; }
    public void setDevEndpoint(String devEndpoint) { this.devEndpoint = devEndpoint; }
}
```

**Go (target)** — opaque-string demotion:

```go
type adapter struct {
    endpoint string
    extraInfo extraInfo  // parsed from config.Adapter.ExtraAdapterInfo string at Builder time
}

type extraInfo struct {
    DevEndpoint string `json:"devEndpoint"`
}
```

The Go `config.Adapter.ExtraAdapterInfo` field is a JSON-string blob; the Builder parses it with `json.Unmarshal`. There is no Go-side equivalent of Java's `@ConfigurationProperties` typed binding — the Go config is structurally weaker.

**Quirk emission**: when a port-java2go run hits this case, emit `quirks[]: { id: "hardcoded-config-as-anti-pattern", summary: "Java typed config class demoted to Go opaque ExtraAdapterInfo JSON string; Go side lacks structural binding..." }`. Future Go → Java re-port detects this quirk and reconstructs the typed config class.

### 2.2 Rule 19: helper-collapse expansion

**Java (source)**:

```java
final HttpResponseHeader headers = HttpUtil.headers();
headers.put("X-OpenRTB-Version", "2.6");
```

**Go (target)**:

```go
headers := http.Header{}
headers.Add("Content-Type", "application/json;charset=utf-8")
headers.Add("Accept", "application/json")
headers.Add("X-OpenRTB-Version", "2.6")
```

`HttpUtil.headers()` provides Content-Type and Accept by default; Go must add them explicitly. The port skill emits the explicit form. The lossiness is mild — re-porting Go → Java collapses the explicit `Add` calls back to `HttpUtil.headers()` plus per-bidder additions.

### 2.3 Rule 8: Lombok @Builder loss

**Java (source)**:

```java
@Builder(toBuilder = true)
@Value
public class ExtImpKobler {
    String placementId;
    String testFlag;
}

ExtImpKobler ext = ExtImpKobler.builder()
    .placementId("pid")
    .testFlag("test")
    .build();
```

**Go (target)** — composite literal:

```go
type ImpExtKobler struct {
    PlacementId string `json:"placementId"`
    TestFlag    string `json:"testFlag,omitempty"`
}

ext := ImpExtKobler{
    PlacementId: "pid",
    TestFlag:    "test",
}
```

The Lombok @Builder pattern (immutable rebuild, fluent API) has no Go analog. Go uses composite literals. No quirk emitted — this is the canonical Go form.

## 3. Test-fixture re-authoring contract

Java IT tests use a 4-file split per scenario:

```
src/test/resources/org/prebid/server/it/openrtb2/{bidder}/
  test-auction-{bidder}-request.json
  test-auction-{bidder}-response.json
src/test/java/org/prebid/server/it/{Bidder}Test.java
```

Go uses a flat exemplary structure:

```
adapters/{bidder}/{bidder}test/exemplary/
  simple-banner.json    # all of the above scenario in one file
  simple-video.json     # next scenario
adapters/{bidder}/{bidder}_test.go    # thin runner: adapters.RunJSONBidderTest(...)
```

The port skill collapses each Java IT scenario into one Go fixture file containing `expectedRequestSequence`, `httpCalls`, `expectedBidResponses` arrays. The mapping is per-scenario, not per-file; one `{Bidder}Test.java` test method may correspond to one Go exemplary fixture.

Naming: when the source IT method has a descriptive name (e.g., `requestToBidderShouldReturnBids`), the Go fixture takes a kebab-case derivation (`simple-banner.json`). When no descriptive name is available, the port skill emits `case-{n}.json` and surfaces a `human_todos[]: { category: "test-fixture-naming", summary: "..." }`.

Error-path fixtures land in `{bidder}test/supplemental/` only when REACHABLE in Go. Java's IT errors that depend on Java-only framework state (Spring DI failures, Vert.x event-loop backpressure, Jackson configuration mismatches) are documented in `quirks[]` but not emitted as Go fixtures.

## 4. Prohibited patterns (port output MUST NOT contain)

Real-PR audit identified patterns that recur in declined Go new-adapter PRs. The port skill avoids these by construction:

| Prohibited | Recommended | Why |
|---|---|---|
| Hardcoded `const endpoint = "..."` | Read from `config.Adapter.Endpoint` (which loads `static/bidder-info/{bidder}.yaml`) | Operators need to override per environment without code changes (Rule 13). |
| Raw `responseData.StatusCode == 204` | `adapters.IsResponseStatusCodeNoContent(responseData)` | Rule 30 canonical helper. |
| Raw `responseData.StatusCode != 200` | `adapters.CheckResponseStatusCodeForErrors(responseData)` | Rule 30 canonical helper; returns proper error type. |
| Custom `*Bid` struct | Reuse `openrtb_ext.Bid` or rely on `adapters.BidderResponse` | Don't reinvent existing types; the framework's `*adapters.BidderResponse` is the contract. |
| Returning `nil, nil` from `MakeRequests` on success | Return `[]*adapters.RequestData{}, nil` (or no requests = nil framework treats as zero) | The convention is empty slice, not nil-with-no-error. |
| Importing `github.com/sirupsen/logrus` | Use `glog` if logging is needed (rare in adapters) | Upstream restricts logging deps; adapters typically don't log. |
| Per-bidder utility files like `helpers.go` for one-line helpers | Inline in `{bidder}.go` | Single-file adapters are the norm; multi-file is for genuinely large codebases (rubicon, appnexus). |
| Hand-rolled string/collection helper duplicating a Go stdlib idiom (e.g. a `unicode.IsSpace` rune-loop reproducing Java `StringUtils.isBlank`) | The stdlib idiom (`strings.TrimSpace(s) == ""`); drop the now-unused `unicode` import | Port Java Apache-Commons / `Character` calls to their Go-stdlib equivalent, not rune-for-rune — target-idiom beats source-fidelity (ADR-009). `strings.TrimSpace` uses `unicode.IsSpace`, so NBSP-class behavior is preserved; the hand-rolled loop buys nothing. Record load-bearing behavioral divergence in `quirks[]`. |

## 5. Mandatory steps before submitting the PR

1. `gofmt -s -w` over every emitted `.go` (the port skill's `gofmt_post_process` does this).
2. `go vet ./adapters/{bidder}/...` exits 0.
3. `go build ./adapters/{bidder}/...` exits 0.
4. `go test ./adapters/{bidder}/...` exits 0.
5. `TestBidderUniquenessGatekeeping` passes (per `prefix_uniqueness_check`).
6. Coverage ≥ 80% (per `./scripts/check_coverage.sh`).
7. Pre-submit rebase against upstream `master` HEAD (per [`pr-shape.md`](pr-shape.md) §5).
8. Companion docs PR drafted (per [`pr-shape.md`](pr-shape.md) §4).

When these all pass, the PR meets the same quality bar as a hand-authored merge.

## 6. Round-trip determinism

Two port runs of the same source spec at the same `port_translation_rules_version` produce byte-identical destination artifacts (R4 round-trip determinism applies to ports). When discrepancies appear between two runs, the port skill is non-deterministic and that is a bug to fix.

The harness's `scripts/round-trip-ci.py` (Phase D4.1 extension) gains a port-side R4 gate that exercises this guarantee per-bidder per-direction.

## 7. Rules cross-reference

For each port-translation rule the inverse direction triggers, see:

- Rule 5 (mutation strategy pairing): Java `immutable-rebuild` ↔ Go `copy-then-mutate` or `in-place`. Pair handled mechanically.
- Rule 8 (helper collapse): Java framework helpers expand to explicit Go code. Lossy in the trivial sense (more verbose) but no semantic loss.
- Rule 9 (custom request type): Java `parameterized_request_type` ≠ BidRequest → Go `request_body.kind=custom`.
- Rule 11 (multi-token-substitution endpoint): Spring EL `#{X}` / `${X}` → Go `text/template` syntax `{{.X}}`.
- Rule 19, 30 (covered above).
- Rule 33 (alias inversion): Java parent → Go child YAMLs (covered in [`registration-rules.md`](registration-rules.md)).
- Rule 35 (covered above).
- Rule 36 (test-fixture re-authoring; covered above).
- Rule 38 (bidder-params byte-fidelity): materialise from `bidder_params_ref` via `port_engine.materialize_params`, then binary-write and re-hash the emitted file against `ref.sha256` / `ref.bytes`. Never re-serialise, and never rebuild the file from the deprecated `bidder_params_json` string.
- Rule 42 (IAB-cat translation): Java YAML inline → Go data file (`port_engine.iab_table_translate(direction='java-to-go')`).
- Rule 44 (alias-empire flavor coherence): per-alias overrides recorded in Go aliases' `bidder-info` YAMLs.
- Rule 46 inverse (naming normalization): not fully mechanical; requires dual-spec assertion lookup.

The full rules corpus lives at [`../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml`](../../../prebid-server-go/read/skills/shared/port-translation-rules.yaml).

## See also

- [`go-artifact-shapes.md`](go-artifact-shapes.md) — file naming, package conventions, Builder/MakeRequests/MakeBids skeleton.
- [`registration-rules.md`](registration-rules.md) — alphabetical insertion across `bidders.go`, `adapter_builders.go`.
- [`pr-shape.md`](pr-shape.md) — Go PR title + body convention.
- Upstream Java porting guide (the analogue this doc inverts): [`prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md`](https://github.com/prebid/prebid-server-java/blob/master/docs/developers/bid-adapter-porting-guide.md).
