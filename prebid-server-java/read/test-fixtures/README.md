# Java test fixtures

10 hand-authored Adapter Specification fixtures for the `prebid-server-java` read suite. All fixtures pinned to upstream commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a` (`prebid/prebid-server-java` master, 2026-04-22).

## Fixtures

| Bidder | Edge case |
|---|---|
| `152media` | Alias-only spec with full `aliases[]` block; identifier rule workaround (`OneFiveTwoMediaTest`); cross-language port pair |
| `aax` | 3-step `bid_type_resolution.method_chain`; missing `minLength: 1` on `cid`/`crid` (port-fidelity bug vs Go) |
| `appnexus` | `mediafuse` parent_alias declaration (Java side only); `json-aliases-present` combinator extension |
| `elementaltv` | Three-step rename from Adoppler with `lifecycle.rename` block |
| `generic` | Reference adapter (no bidder-specific quirks) |
| `huaweiads` | `runtime-region-selection` endpoint with 5 endpoints; HMAC authentication; `retcode-field` application status; 196 unit `@Test` methods; 23 IT subdirectories |
| `kobler` | Phase A acceptance-gate; cross-language port pair; canonical clean reference (Go and Java SHAs match) |
| `mediasquare` | `Bidder<MediasquareRequest>` parameterized request type; 9 co-located helper classes; cross-language port pair |
| `optidigital` | Cross-language port pair; `default_enabled: false` divergence vs Go |
| `rubicon` | Most ambitious fixture: 13-arg constructor, 145 hand-written test methods, basic-auth pre-built header, `@Validated` Lombok stack, multi-folder integration test pattern, custom `RubiconBidResponse` |

## Round-trip determinism (R4)

Each fixture should reproduce byte-identically when re-emitted by the read-orchestrator skill against the same `provenance.source.resolved_commit`, modulo `provenance.read.timestamp_utc` and `provenance.read.operator`.

## Adding or refreshing a fixture

1. Identify the bidder and the upstream commit to pin against.
2. Run the `read-bidder-orchestrator` skill at that commit. See `prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md`.
3. Save the emitted YAML as `{bidder}.golden.spec.yaml`.
4. Run `python3 scripts/round-trip-ci.py --strict-r3` to verify R1–R10 pass.
5. If the bidder has a Go counterpart, also add `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` (see the README there).
6. Add a row to the table above.

## Schema sharing

Java goldens conform to the same canonical Adapter Specification schema as Go goldens. The schema lives at `prebid-server-go/read/skills/shared/adapter-spec.md`. Java-only sections (`spring_config`, `bidder_class`, `aliases[]`, `lifecycle:`, `code_naming:`) are documented in that file as conditionally-present blocks. A future Java-specific schema fork would land at `prebid-server-java/read/skills/shared/adapter-spec-java.md`.
