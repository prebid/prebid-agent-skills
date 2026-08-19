# Upstream repo rules (snapshot + provenance)

Snapshot of upstream `prebid/prebid-server` and `prebid/prebid-server-java`
policies that the read skills depend on. When upstream changes any of
these, the read skills' classification may misfire — drift detection
(`scripts/sync-from-upstream.py`, Phase 4.1) will surface the change as
a structural diff.

## Adapter naming

### Go side (`prebid/prebid-server`)

| Rule | Description | Source of truth | Last verified |
|---|---|---|---|
| YAML name = directory name | `static/bidder-info/{X}.yaml` ↔ `adapters/{X}/` | implicit (file system) | v4.1.0 (re-verified 2026-05-04) |
| Bidder constant = `Bidder<TitleCase>` | `openrtb_ext/bidders.go` declares `Bidder<X> BidderName = "<x>"` | `openrtb_ext/bidders.go` | v4.1.0 |
| TitleCase preserves brand acronyms | `BidderAJA`, `BidderMX`, `BidderTV`, `Bidder33Across` (NOT `Bidder33across`) | upstream maintainer convention | v4.1.0 |
| Underscore in YAML name allowed | `boldwin_rapid`, `e_volution`, `lm_kiviads`, `cadent_aperture_mx`, `triplelift_native` | PR #4211 (formal acceptance) | v4.1.0 |
| Hyphen in YAML name allowed (rare) | `freewheel-ssp` | upstream allow-list | v4.1.0 |

Lookup tools (deterministic): `openrtb_ext/bidders.go` maps every YAML
name to its TitleCase constant. The read skills MUST consult this file
verbatim — never derive the constant via flat TitleCase. See
`prebid-server-go/read/skills/read-bidder-params/SKILL.md` Step 5 for
the canonical lookup procedure.

### Java side (`prebid/prebid-server-java`)

| Rule | Description | Source of truth | Last verified |
|---|---|---|---|
| YAML parent name = `lowercase + drop non-[a-z0-9]` of Go name | per ADR-005 Rule 46 mechanical formula | derived rule | v3.41.0 (re-verified 2026-05-04) |
| Class root preserves brand acronyms | `ElementalTV`, `FeedAd`, `BidsCube`, `BidTheatre` | per Java edge case #27 | v3.41.0 |
| Class root capitalizes first letter after digit-leading prefix | `33across → Thirtythree`, `152media → OneFiveTwoMedia`, `360playvid → 360Playvid` | per Java edge case #26 | v3.41.0 |
| Configuration-class naming: `<Name>Configuration` OR `<Name>BidderConfiguration` | both forms accepted (Kobler vs Adverxo) | per Java edge case #19 | v3.41.0 |
| Test classes append `Test`: `<Name>Test.java` | with brand-acronym preservation: `HuaweiAdsTest` (not `Huaweiads`) | per Java edge cases #26, #27 | v3.41.0 |

## Adapter visibility

### Go default-enabled

Every Go YAML adapter is enabled by default UNLESS it declares
`disabled: true` (e.g., adapters with unresolved deploy-time tokens like
Rubicon). The default-disabled set covers ~5 bidders historically — use
the goldens + ADR-004 evidence as the snapshot. White-label bidders that
are intentionally Go-disabled (audienceNetwork, avocet, etc.) — Rule 45
inverse case.

### Java default-disabled (empire alias children)

Empire alias children (per ADR-003 Rule 44) ship `enabled: false` by
default; publishers opt in via deployment config. This is the canonical
Rule 45 case (`go-enabled-java-disabled` per dual-spec
`bidder_info_default_enabled.rule_45_match`). 72 of 78 cross-language
disabled-asymmetric pairs follow this pattern; 6 are inverse.

## Test-fixture structure

### Go canonical

- `adapters/{xyz}/{xyz}test/exemplary/*.json` — required.
- `adapters/{xyz}/{xyz}test/{supplemental,amp,video,videosupplemental}/*.json` — optional.
- Single-file test driver: `adapters/{xyz}/{xyz}_test.go` calls `RunJSONBidderTest`.

Legacy form (msft only): `adapters/{xyz}/test/` + `adapters/{xyz}/test-extrainfo/`.

### Java canonical

- `src/test/java/org/prebid/server/it/{Name}Test.java` — required IT class per bidder.
- `src/test/resources/org/prebid/server/it/openrtb2/{xyz}/` — fixture folder. The 4-file Wiremock pattern: `test-{xyz}-bid-request.json`, `test-{xyz}-bid-response.json`, `test-auction-{name}-request.json`, `test-auction-{name}-response.json`.
- `src/test/resources/test-application.properties` — central registry; every adapter appends 2–4 lines (`adapters.{xyz}.enabled=true`, `adapters.{xyz}.endpoint=...`).

Per-alias amplification (Rule 37): each Java alias requires its own IT
class + fixture set + registry append (~7 files per alias). Go aliases
need none — the parent's tests cover them.

## GVL (Global Vendor List) registration

`gvlVendorID` (Go) / `gvl-vendor-id` (Java) records the IAB Tech Lab GVL
registration. `0` is the conventional "not registered" placeholder; real
IDs are positive integers. The list of registered vendors is at
<https://vendor-list.consensu.org/v3/vendor-list.json>. Read skills do
NOT validate that the declared ID appears in the live list — that's a
review-time concern.

## Module path and major version

`go.mod` declares `module github.com/prebid/prebid-server/v4` (current
major). The orchestrator's Step 3 reads this and emits `meta.module_path_major: v4`.
A major bump (v4 → v5) is a breaking signal — read skills MUST flag
`module-major-drift` per `prebid-server-go/read/skills/read-adapter-orchestrator/references/provenance-warnings.md`
and may misclassify framework helpers if not updated.

## Java POM version

`pom.xml` declares the Maven artifact version (e.g., `3.41.0`). Goldens
record this at `meta.java_artifact_version`. Drift detection compares
the declared version against `provenance.source.resolved_commit` to
detect skew between the version-stamping commit and the actual commit
the spec was read from.

## Update cadence

Upstream policy changes are detected three ways:

1. **Weekly drift sync** (`scripts/sync-from-upstream.py`, Phase 4.1).
   Fetches `master` from both repos every Monday; compares each pinned
   golden's `provenance.source.resolved_commit` against the new HEAD.
   Flags structural changes (file additions/removals/renames).
2. **PR audit** (`scripts/audit-pr.py`, Phase 4.2). When a new bidder PR
   merges upstream, `audit-pr.py` classifies it: data-only (a new
   adapter following established patterns) or structural (introduces a
   pattern not yet in the taxonomy or rules).
3. **Manual review** of `prebid-server-{go,java}/references/new-bid-adapter-prs.md`
   when a maintainer notices an upstream policy shift in PR review.

When an upstream policy shifts, this file MUST be updated AND a CHANGELOG
entry filed. The "Last verified" column is the upstream commit at which
the policy was last re-confirmed.

## Sources

- Go upstream: `prebid/prebid-server` master at v4.1.0 (release commit `d7f8515b86258688304b0d9b6668c6a0e258bc9e`); re-verified 2026-05-04 against master HEAD `2fae16f31693`.
- Java upstream: `prebid/prebid-server-java` master at v3.41.0 (release commit `69b1993c39ed3212ca63012a8c0924fdfa0b5d4a`); re-verified 2026-05-04 against master HEAD `a1fe64e123d6`.
- ADR-005 (Rule 46 naming): the mechanical transformation table + 11 verified pairs (refined 2026-05-03 from 12 — `freewheel-ssp/freewheelssp` removed; see ADR-005 "Excluded cases").
- ADR-003 (Rule 44 alias-empire): 32-parent / 95-alias inventory.
- ADR-004 (Rule 45 disabled-by-default): 78 disabled-asymmetric pairs.
- Java edge cases #18–#34: `prebid-server-java/references/java-edge-cases.md`.

## In-flight upstream changes (tracked; not yet landed)

When upstream PRs that affect bidder-config / bidder-params shape are
in-flight, track them here so that Phase D port skills can pre-submit
rebase against the most current `master`. Phase D2/D3 emit MUST rebase
the target branch against upstream `master` HEAD immediately before
opening the PR; if any of the listed PRs land between port-emit and
PR-open, regenerate the affected goldens.

_None currently tracked._

Retired: **`prebid/prebid-server-java#4126` — "Bidder Configuration Fixes & URL
Validation"** was tracked here as OPEN as of 2026-05-04. It closed unmerged on
2026-07-20 with CHANGES_REQUESTED, so its URL-validation gates never landed and
no rebase precaution is owed to it.

Entries in this section pin a live upstream state and go stale silently. Re-check
each listed PR's state before relying on it, and remove it once it merges or closes.

## Known data-only drifts (operator-ack pending)

Drifts surfaced by `scripts/sync-from-upstream.py` that are real but not
schema-breaking. Operator may ack them into the affected goldens at any
time; they don't block Phase D execution.

- **`adkernel` (go) — `bidder_info.endpoint_compression`** changed value upstream. WARN-severity per drift detector; ack into the golden when the next adkernel-touching PR lands.
