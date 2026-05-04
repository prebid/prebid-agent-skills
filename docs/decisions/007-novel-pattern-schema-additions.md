# ADR-007: Five New Schema Fields for Novel Patterns

**Date**: 2026-05-02 (refined 2026-05-02 audit C7 — added array ordering policy for round-trip determinism; refined 2026-05-03 — F1 Java-side wording tightened; F2 footnote on one-sided header mutations added per Phase 5 empirical verification)
**Status**: Partially implemented in Phase 2.8 / Wave 11b (2026-05-03)
- Schema additions landed at `adapter_spec_version 1.1.0` (ADR-007 F1/F3/F4/F5 `$defs` admitted).
- Wave 11b at `adapter_spec_version 1.2.0`: closed 17 accidentally-open `additionalProperties:true` sites, lifted 4 top-level open-maps to structured `$defs` (SpringConfig/BidderClass/CodeNaming/Lifecycle), closed 8 round-2 sweep sites under `code.*` and `cross_language.*`, tightened Java-alias and Go-source if/then invariants.
- F2 (`language_stamped_headers`) shipped at 1.1.0.
- F1/F3/F4/F5 `$defs` themselves are STILL not `$ref`-wired into `Code`; Code's sub-objects (`code.make_requests`, `code.make_bids`) gained their own structured `$defs` in Wave 11b's B3+ sweep, but the per-pattern `$ref` wiring (e.g., `code.make_bids.bid_post_processing` ↔ `$defs/BidPostProcessing`) remains for a future wave.
- DEFERRED to Wave 11c C4: `cross_language.port_lineage` shared-genesis canonical encoding (freewheelssp-Java's `destination_language: null` is captured as F2-contradicted exemplar; tightening to symmetric shared-genesis would unilaterally invalidate that ADR-007 F2 evidence and is being deferred for an explicit ADR amendment).

**Note on array ordering and R4 round-trip determinism**: The new fields F1 (`endpoints[]`), F2 (`language_stamped_headers[]`), and F4 (`bid_post_processing.macros[]`) are arrays. To preserve R4 round-trip-determinism (`yaml.safe_dump → load → dump` byte-equality), arrays in the schema MUST have a deterministic ordering policy:

- **Logical ordering** (where order has semantic meaning): preserve insertion order. Rule: emit in the order the source code defines them.
- **Set-like ordering** (where order doesn't matter): sort lexicographically by primary identifier (e.g., `name` field for `endpoints[]` and `language_stamped_headers[]`; `macro` field for `bid_post_processing.macros[]`).

For the F1/F2/F4 fields below, emission policy is **logical ordering** (Go/Java code defines them in a specific order; preserve it). R4 verifies pass-2 vs pass-3 byte equality after a load+dump cycle; if PyYAML's `safe_dump(..., sort_keys=True)` reorders an array's items, the round-trip breaks. Since arrays of objects don't get sorted by `sort_keys` (only object KEYS), logical ordering is preserved naturally.
**Context**: Round 3 diversity sample (10 primary-primary pairs not in our 22 goldens) surfaced 5 patterns that don't fit our existing taxonomy. Each is a real cross-language port concern that a porter without these fields would miss. They're not edge cases — they appear in widely-used adapters (thetradedesk, beachfront, vungle, freewheelssp, beintoo).

## Decision

Add five schema fields/blocks to capture the novel patterns. Each is targeted to a specific known case and admits future expansion.

### F1 — `endpoint_resolution.endpoints[]` (multi-endpoint per adapter)

**Pattern**: A single adapter routes requests to **multiple distinct endpoints** based on mediatype (or other dispatch logic). Current `endpoint_resolution.kind` enum models a single resolution path.

**Master sample**: `beachfront` — splits requests by mediatype: `bannerEndpoint` for banner, `videoEndpoint` for video (parallel ADM and NURL paths). Go encodes both endpoints by storing the banner endpoint in `config.Endpoint` (the standard slot) and the video endpoint as a JSON-string in `config.ExtraAdapterInfo` (`{"video_endpoint": "..."}`); Java promotes only the second endpoint to a structured `BeachfrontConfigurationProperties.videoEndpoint` field on a `@ConfigurationProperties`-bound subclass — the banner endpoint reuses the inherited `BidderConfigurationProperties.endpoint` field. Java YAML `bidder-config/beachfront.yaml` exposes the second endpoint via a custom `video-endpoint:` key (the only non-standard endpoint key in the entire Java corpus at the pinned commits).

**Empirical cardinality** (verified at Go SHA `2fae16f3` / Java SHA `a1fe64e1`): exactly one bidder — `beachfront`. No other corpus bidder uses a multi-endpoint-by-mediatype YAML shape. Treat as a singleton master sample; future corpus expansion that introduces a second F1 example should add a fixture rather than amend the schema.

**Schema addition**:
```yaml
code:
  make_requests:
    endpoint_resolution:
      kind: ... | multi-endpoint-by-mediatype | multi-endpoint-by-shape
      endpoints:                                # Optional. Populated when kind = multi-endpoint-*.
        - { name: <id>, role: banner|video|adm|nurl|<custom>, value: <url-or-template>, mechanism: <as for single endpoint> }
```

**Cross-language**: Go uses `extra_info` JSON-string; Java uses structured config-properties subclass. This is a **lossless port asymmetry** — same wire endpoints, different config delivery.

### F2 — `headers_constructed.language_stamped` (language-divergent header values)

**Pattern**: Adapter sends a header whose VALUE differs by language (e.g., `prebid-go` vs `prebid-java`), breaking byte-equality of outgoing requests across languages.

**Master sample**: `freewheelssp` — sends `Componentid: prebid-go` (Go) vs `Componentid: prebid-java` (Java). Same header name, different values.

**Schema addition**:
```yaml
headers_constructed:
  language_stamped: bool                        # True when at least one header value differs by language at request time.
  language_stamped_headers:                     # Populated when language_stamped = true.
    - { name: <header-name>, go_value: <string>, java_value: <string>, rationale: <free-text> }
```

**Cross-language**: This is an **explicit port-asymmetry** that Rule 38 (bidder_params byte-fidelity) does NOT cover — Rule 38 is about params JSON, not outbound HTTP headers. New Pattern Index tag: `language-stamped-header-divergence`.

**Footnote on one-sided header mutations (NOT F2)**: F2 requires the SAME header NAME to be emitted by BOTH languages with divergent values. Adapters where only one language emits the header (e.g., `aduptech` Java emits `Componentid: prebid-java` but Go aduptech emits no Componentid header at all) are a different asymmetry — model them as a quirk on the side that adds the header, not as F2. The schema field `language_stamped_headers[]` REQUIRES both `go_value` and `java_value` populated; one-sided header additions would have a missing field. Likewise, sibling adapters that share the F2 mechanism but lack a cross-language counterpart (e.g., Go-only `fwssp` emits `Componentid: prebid-go` but has no Java port) are LATENT F2 candidates — F2 would apply if a Java port lands later, but the corpus at these SHAs has only `freewheelssp` as a fully cross-language F2 master.

### F3 — `mutation.entity_strategies.Site/App: synthesize-replacement` (mediatype-context rewrite)

**Pattern**: Adapter destructively converts request shape — e.g., **deletes `request.Site` and constructs a new `App{ID: ...}`** to coerce request to the bidder's expected mediatype context.

**Master sample**: `vungle` — rewards-video adapter; if request has `Site` only, deletes it and synthesizes `App{ID: pubAppStoreID}`. More invasive than `replace-with-null`; not modeled by current `entity_strategies` enum.

**Schema addition** (extend existing enum):
```yaml
mutation:
  entity_strategies:
    Site: ... | synthesize-app-replacement
    App: ... | synthesize-from-site
```

Plus a new taxon `mediatype-context-rewrite-site-to-app` paired with quirks.

### F4 — `make_bids.bid_post_processing.macros[]` (bid-level macro replacement)

**Pattern**: Adapter performs **post-decode mutation of bid fields** — e.g., replaces `${AUCTION_PRICE}` in `bid.NURL`, `bid.AdM`, `bid.BURL` after deserialization.

**Master sample**: `thetradedesk` — replaces `AUCTION_PRICE` in three bid fields with the actual bid price.

**Schema addition**:
```yaml
code:
  make_bids:
    bid_post_processing:                        # Optional. Populated when adapter mutates bid fields after deserialization.
      macros:
        - { macro: <name>, fields: [<bid-path>], source: <where-the-value-comes-from>, mechanism: <details> }
```

**Cross-language**: Both Go and Java implementations should match — the wire effect of macro replacement is observable in `bid.AdM` content. New Pattern Index tag: `bid-post-processing-macro`.

### F5 — `imp_ext_unmarshal.strip_post_extraction` (zero-out imp.ext)

**Pattern**: After parsing `imp.ext`, adapter **sets `imp.Ext = nil`** (or `ext(null)` in Java) before sending the outgoing payload. Distinct from the `standard-two-phase` extraction pattern which preserves the bidder ext.

**Master sample**: `beintoo` — banner-only adapter; strips bidder ext from outgoing payload entirely.

**Schema addition**:
```yaml
code:
  make_requests:
    imp_ext_unmarshal:
      kind: ... (existing)
      strip_post_extraction: bool               # True when adapter zeroes out imp.Ext after parsing.
```

**Cross-language**: This is purely an outbound-payload concern; affects what arrives at the upstream bidder. New Pattern Index tag: `imp-ext-strip-post-extraction`.

## Other patterns observed but NOT promoted to schema fields

The diversity sample also surfaced these "nice-to-add" patterns. Phase 2 captures them as **quirks** rather than dedicated schema fields, because they're either too rare or too easily expressed as quirks:

- **Forced-currency request rewrite** (adview) — `requestCopy.Cur = ["USD"]` at request build. Quirk: `forced-currency-request-rewrite-USD`.
- **Imp-ext re-wrap** (axis) — Go re-marshals to `{"bidder": {...}}`. Quirk: `imp-ext-rewrap-bidder-key`.
- **Cached endpoint-macro predicate** (between) — one-time validation flag. Quirk: `cached-endpoint-macro-predicate`.
- **Format slice trimming** (beintoo, between) — `Format = Format[1:]` after promotion. Quirk: `format-slice-trim-after-promote` (paired with existing `banner-format-dim-promotion`).
- **Asymmetric `disabled` flag** (adagio Go vs Java) — already covered by ADR-004 Rule 45.

## Mechanizability

- F1, F2, F3, F4, F5 are all **structurally mechanizable** — Phase 4.6 lint can verify presence of these fields when corresponding patterns are detected
- F2 (language-stamped headers) violates Rule 38 (byte-equality) IFF assertion claims `byte_equal: true`; the lint can verify

## Consequences

- Phase 2 schema migration adds 5 fields/blocks
- Phase 2 adds 5 new taxa: `multi-endpoint-by-mediatype`, `language-stamped-header-divergence`, `mediatype-context-rewrite-site-to-app`, `bid-post-processing-macro`, `imp-ext-strip-post-extraction`
- Phase 5 fixtures (when added in future expansions) for beachfront, vungle, thetradedesk, freewheelssp, beintoo would exercise these fields
- Phase 5 immediate scope (ADR-008) includes vungle/liftoff pair which exercises F3 — provides a real master sample on Day 1 of Phase 2

## References

- Round 3 diversity sample (this conversation): "Novel patterns surfaced — Must-add" section
- Sampled bidders: thetradedesk, adagio, beachfront, adview, beintoo, axis, between, freewheelssp, mgidx, vungle
- PR refs: TheTradeDesk Go #4448 (AUCTION_PRICE), Java #4081; vungle Go #3727 (Liftoff→Vungle rename), Java #3383; beachfront Go #1844-2078 (pre-window); freewheelssp Go #2392 (pre-window), Java #2251 (pre-window)
- Existing taxa to update: `banner-format-dim-promotion` (paired with new `format-slice-trim-after-promote`); `unguarded-hardcoded` (paired with new `forced-currency-request-rewrite-USD`)
