# Registration insertion rules (Go target)

Phase D1.3 deliverable — alphabetical insertion-position rules for Go-side files where adding a new adapter requires editing a shared registry. The port-java2go SKILL Step 5 invokes `scripts/lib/port_engine.alphabetical_insert` per the per-file rule below.

## Files the port skill writes

| File | Edit kind | Sort | Helper |
|---|---|---|---|
| `static/bidder-info/{bidder}.yaml` | Create | N/A (one file per bidder) | direct write |
| `static/bidder-params/{bidder}.json` | Create | N/A (one file per bidder) | `byte_copy` |
| `adapters/{bidder}/{bidder}.go` | Create | N/A | direct write + `gofmt -s -w` |
| `adapters/{bidder}/{bidder}_test.go` | Create | N/A | direct write + `gofmt -s -w` |
| `adapters/{bidder}/{bidder}test/exemplary/*.json` | Create | N/A | direct write |
| `adapters/{bidder}/{bidder}test/supplemental/*.json` | Create | N/A | direct write |
| `adapters/{bidder}/params_test.go` | Create | N/A | direct write + `gofmt -s -w` |
| `openrtb_ext/imp_{bidder}.go` | Create | N/A | direct write + `gofmt -s -w` |
| `openrtb_ext/bidders.go` | EDIT (insert constant + slice entry) | alphabetical, case-insensitive lower-first | `alphabetical_insert` |
| `exchange/adapter_builders.go` | EDIT (insert import + map entry) | alphabetical, case-insensitive lower-first | `alphabetical_insert` |

## `openrtb_ext/bidders.go` insertion contract

The file has two regions the port skill edits:

### Region A — the `const (...)` block

```go
const (
    Bidder33Across   BidderName = "33across"
    BidderAax        BidderName = "aax"
    BidderAceex      BidderName = "aceex"
    BidderAcuityAds  BidderName = "acuityads"
    ...
)
```

Insertion: at the canonical position under sort key `(s.lower(), s)` — case-insensitive primary (matching upstream's predominant convention; verified against `prebid/prebid-server` HEAD `f601e3f3db83`), with case-sensitive ASCII tiebreak. Numeric prefixes (e.g., `Bidder33Across`) sort before letters because `'3'.lower()` is still `'3'` and `'3' < 'a'` in ASCII.

**The helper does NOT re-sort the existing block.** Upstream HEAD has ~20 of 261 entries that are locally out-of-order under `(s.lower(), s)` — `BidderAdtrgtme` precedes `BidderAdtelligent`, `BidderEdge226` precedes `BidderDmx`, etc. Re-sorting would create ~20 unrelated diffs in every port PR. `port_engine.alphabetical_insert` uses `bisect.bisect_left` against the existing block's sort keys, finding the canonical position for the new entry while preserving every existing line's position.

`port_engine.alphabetical_insert(file_path, marker_pattern=r'Bidder\w+\s+BidderName\s*=', insert_line=...)`. The helper finds all contiguous runs of marker-matching lines and picks the longest as the target block. Since `bidders.go` carries TWO `const ( ... )` blocks (10 Reserved* + 261 Bidder*), this scoping prevents the new entry from landing in the wrong block. If two runs tie for longest, the helper raises `ValueError` and the caller must use a more specific marker.

### Region B — the `coreBidderNames` slice

```go
var coreBidderNames = []BidderName{
    Bidder33Across,
    BidderAax,
    BidderAceex,
    ...
}
```

Same `(s.lower(), s)` insertion semantics. `port_engine.alphabetical_insert` is invoked separately for this region with a distinct marker pattern (`r'^\s+Bidder\w+,\s*$'` — matches the slice-entry shape, not the const-block shape, so no scoping ambiguity arises).

### Pre-emit validation

`scripts/lib/port_engine.prefix_uniqueness_check(target_lang='go', bidder_name=...)` MUST return `(True, [])` before the port skill emits to `bidders.go`. If the helper reports a collision (first-6-letter prefix shared with an existing entry), abort with operator notification — `TestBidderUniquenessGatekeeping` would fail post-merge otherwise.

## `exchange/adapter_builders.go` insertion contract

Two regions the port skill edits:

### Region A — the `import (...)` block (the per-bidder package import)

```go
import (
    ...
    "github.com/prebid/prebid-server/v3/adapters/aax"
    "github.com/prebid/prebid-server/v3/adapters/aceex"
    "github.com/prebid/prebid-server/v3/adapters/acuityads"
    ...
)
```

Insertion: by **import path** (the bidder package directory name; all lowercase since upstream package names are lowercase). Sort key `(s.lower(), s)` — for an all-lowercase block, the primary key alone is decisive, so this matches plain-ASCII sort here. The marker pattern: `r'"github.com/prebid/prebid-server/v\d+/adapters/'`.

### Region B — the dispatch-map entries

```go
func newAdapterBuilders() map[openrtb_ext.BidderName]adapters.Builder {
    return map[openrtb_ext.BidderName]adapters.Builder{
        ...
        openrtb_ext.BidderAax:        aax.Builder,
        openrtb_ext.BidderAceex:      aceex.Builder,
        openrtb_ext.BidderAcuityAds:  acuityads.Builder,
        ...
    }
}
```

Insertion: alphabetical by the `openrtb_ext.Bidder{X}` constant name (matches `bidders.go` const block ordering). The marker pattern: `r'openrtb_ext\.Bidder\w+:'`.

Indentation alignment between the colon and the value (`aax.Builder`) is maintained by `gofmt` post-process; the port skill emits a minimal-spacing version and lets `gofmt` align.

## Static-file YAML insertions

`static/bidder-info/{bidder}.yaml` — one file per bidder, no shared registry. The port skill writes the file directly.

For empire-parent ports (Rule 33 inverse), the alias children get THEIR OWN `static/bidder-info/{alias}.yaml` files containing `aliasOf: parent`. This is opposite to Java's consolidation pattern; the helper `port_engine.alias_graph_invert(direction='java-to-go')` produces the per-alias YAML dicts.

## Sort key reference

For all alphabetical inserts, the sort key is `(s.lower(), s)`:
- Primary: case-insensitive (lowercase form).
- Tiebreak: case-sensitive ASCII (uppercase letters sort before lowercase per ASCII).

This was chosen because empirical comparison against `prebid/prebid-server` HEAD `f601e3f3db83` showed:
- 20 of 261 entries out-of-order under `(s.lower(), s)` — local violations the upstream maintainers haven't normalized.
- 136 of 261 out-of-order under plain case-sensitive ASCII — the latter would be wrong for nearly half the entries (e.g., `BidderAJA` would sort before `BidderAax` under plain ASCII because `'J' < 'a'`).

`(s.lower(), s)` is the closer canonical form. The 20 local violations in upstream are preserved by the helper's `bisect.bisect_left` insertion strategy (no whole-block re-sort) — see `scripts/lib/port_engine.alphabetical_insert` docstring.

Examples:
- `BidderAax`, `BidderAdkernel`, `BidderAdkernelAdn`, `BidderAdverxo` → in this order (case-insensitive monotone increasing).
- The case-sensitive tiebreak surfaces for entries like `BidderEMX` vs `BidderEmx` (rare; not currently in the corpus). When upstream's local order violates the formula (e.g., `BidderAdtrgtme` precedes `BidderAdtelligent`), the helper preserves the violation rather than spuriously normalizing — port PRs touch only the new line.

## Connection to other rules

- Rule 38 (`byte_copy`): drives the `bidder-params/{bidder}.json` create step.
- Rule 46 inverse (per `port-translation-rules.yaml`): resolves the camelCase Go bidder name from Java's lowercase yaml_name (requires dual-spec assertion lookup; not fully mechanical).
- Rule 33 inverse (`alias_graph_invert`): produces per-alias `static/bidder-info/{alias}.yaml` files.
- `TestBidderUniquenessGatekeeping`: enforced upstream; the port skill's pre-emit `prefix_uniqueness_check` prevents the test from failing.

## See also

- [`go-artifact-shapes.md`](go-artifact-shapes.md) — file naming, package conventions, Builder/MakeRequests/MakeBids skeleton.
- [`pr-shape.md`](pr-shape.md) — Go PR title + body conventions (Go has no upstream PR template).
- [`porting-guide.md`](porting-guide.md) — the inverse porting guide; covers lossy-direction asymmetries (Rule 35 typed-config-subclass demotion, Rule 19 helper expansion).
- [`../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml`](../../../prebid-server-go/read/skills/shared/bidder-constant-table.yaml) — the canonical 271-entry yaml_name → constant_root mapping the helpers consult.
