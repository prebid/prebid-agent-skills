# Go test fixtures

10 hand-authored Adapter Specification fixtures for the `prebid-server-go` read suite. All fixtures pinned to upstream commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e` (`prebid/prebid-server` master, 2026-04-27).

## Fixtures

| Bidder | Edge case |
|---|---|
| `152media` | Alias-only spec (parent: adkernel); cross-language port pair |
| `33across` | `package ttx` directory mismatch; `Bidder33Across` acronym preservation |
| `adkernel` | Multi-alias parent (152media, rxnetwork, xapads); composed batching `[grouped-by-key, format-split]` |
| `adtonos` | Currency conversion via `reqInfo.ConvertCurrency` helper |
| `appnexus` | Custom `UnmarshalJSON` for keywords; pod-grouping batching; multi-imp |
| `bidstack` | Bearer-token authentication |
| `kobler` | Phase A acceptance-gate; cross-language port pair; documented R7 bugs (`BidderKargo` in `kobler_test.go:12`, `BidderKrushmedia` in `params_test.go:47`) |
| `mediasquare` | Custom request body types (`msqResponse`, `msqParameters`); cross-language port pair |
| `msft` | Bidder-name rebrand (formerly Microsoft); IAB-category data table; dual test root (`test/` + `test-extrainfo/`) |
| `optidigital` | Phase A acceptance-gate (clean baseline); hardcoded dev-endpoint quirk; cross-language port pair |

## Round-trip determinism (R4)

Each fixture should reproduce byte-identically when re-emitted by the read-orchestrator skill against the same `provenance.source.resolved_commit`, modulo `provenance.read.timestamp_utc` and `provenance.read.operator`. The CI harness (`scripts/round-trip-ci.py`) enforces R4 alongside R1–R10 plus the cross-language-pair dual-spec assertions.

## Adding or refreshing a fixture

1. Identify the bidder and the upstream commit to pin against.
2. Run the `read-adapter-orchestrator` skill at that commit. See `prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md`.
3. Save the emitted YAML as `{bidder}.golden.spec.yaml`.
4. Run `python3 scripts/round-trip-ci.py --strict-r3` to verify R1–R10 pass.
5. If the bidder has a Java counterpart, also add `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` (see the README there).
6. Add a row to the table above.
