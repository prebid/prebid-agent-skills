# New Bid Adapters in prebid-server-java — 2025 → 2026-04-27

Generated: 2026-04-27
Source: `github_activity.db` (prebid/prebid-server-java, repository_id=2)

## Definition

A "new bid adapter" PR creates a brand-new bidder directory with Java code:
- `src/main/java/org/prebid/server/bidder/<name>/<Name>Bidder.java` (main bidder class)
- Usually `src/main/java/org/prebid/server/proto/openrtb/ext/request/<name>/ExtImp<Name>.java`
- `src/main/resources/bidder-config/<name>.yaml`
- `src/main/resources/static/bidder-params/<name>.json`
- Test file: `src/test/java/org/prebid/server/bidder/<name>/<Name>BidderTest.java`
- Integration test: `src/test/java/org/prebid/server/it/<Name>Test.java`

This **excludes** alias-only adapters (PRs that add only YAML config to reuse a parent adapter's Java code, e.g., "Streamvision - LimelightDigital Alias", "RadiantFusion - Attekmi alias"). A separate **Alias-only adapters** section is included at the bottom of this file.

## Summary

**35 new bid adapters** + **14 alias-only adapters** merged between 2025-01-03 and 2026-04-22.

| Year | Full adapters | Alias-only |
|---|---|---|
| 2025 | 31 | 12 |
| 2026 (so far) | 4 | 2 |

---

## By Release

### v3.18.0 — 2025-01-14

| PR | Adapter | Merged |
|---|---|---|
| [#3647](https://github.com/prebid/prebid-server-java/pull/3647) | Insticator | 2025-01-03 |

### v3.23.0 — 2025-04-04

| PR | Adapter | Merged |
|---|---|---|
| [#3705](https://github.com/prebid/prebid-server-java/pull/3705) | Adverxo (port from Go) — `port-from-go, multi-alias-bundle, per-imp-request-strategy, alias-coverage-it-classes` | 2025-03-17 |
| [#3781](https://github.com/prebid/prebid-server-java/pull/3781) | Connatix (port from Go) — `port-from-go` | 2025-03-18 |
| [#3788](https://github.com/prebid/prebid-server-java/pull/3788) | Ogury (port from Go) — `port-from-go, free-form-imp-ext-no-proto, endpoint-compression-typo-camelcase` | 2025-04-01 |
| [#3684](https://github.com/prebid/prebid-server-java/pull/3684) | Kobler (port from Go) — `port-from-go, dev-prod-endpoint-toggle, configuration-properties-subclass, currency-conversion` | 2025-04-03 |

### v3.24.0 — 2025-04-24

| PR | Adapter | Merged |
|---|---|---|
| [#3869](https://github.com/prebid/prebid-server-java/pull/3869) | FeedAd (port from Go, follow-on to #3684) — `port-from-go, dead-code-proto-port-fidelity, modifying-vast-xml-allowed` | 2025-04-17 |

### v3.26.0 — 2025-05-21

| PR | Adapter | Merged |
|---|---|---|
| [#3916](https://github.com/prebid/prebid-server-java/pull/3916) | Seedtag — `port-from-go, currency-conversion-via-bidderutil` | 2025-05-16 |

### v3.27.0 — 2025-06-12

| PR | Adapter | Merged |
|---|---|---|
| [#3930](https://github.com/prebid/prebid-server-java/pull/3930) | Kueez (kueezrtb, port from Go) — `port-from-go` | 2025-06-03 |
| [#3942](https://github.com/prebid/prebid-server-java/pull/3942) | Mobkoi (port from Go) — `port-from-go` | 2025-06-04 |
| [#3941](https://github.com/prebid/prebid-server-java/pull/3941) | Start.io (startio) — `java-first, empty-bidder-params-schema, all-three-platforms-declared` | 2025-06-10 |

### v3.28.0 — 2025-07-10

| PR | Adapter | Merged |
|---|---|---|
| [#4027](https://github.com/prebid/prebid-server-java/pull/4027) | Adagio — `port-from-go` | 2025-07-09 |
| [#4024](https://github.com/prebid/prebid-server-java/pull/4024) | AdupTech | 2025-07-09 |
| [#4021](https://github.com/prebid/prebid-server-java/pull/4021) | Smoot | 2025-07-09 |
| [#4023](https://github.com/prebid/prebid-server-java/pull/4023) | BidTheatre | 2025-07-09 |
| [#4045](https://github.com/prebid/prebid-server-java/pull/4045) | Flatads | 2025-07-09 |

### v3.29.0 — 2025-07-31

| PR | Adapter | Merged |
|---|---|---|
| [#4078](https://github.com/prebid/prebid-server-java/pull/4078) | Zentotem — `port-from-go` | 2025-07-28 |
| [#4054](https://github.com/prebid/prebid-server-java/pull/4054) | Optidigital — `port-from-go, dooh-platform-declared, enabled-false-default, ortb-version-quoted` | 2025-07-28 |
| [#4053](https://github.com/prebid/prebid-server-java/pull/4053) | Nexx360 — `port-from-go` | 2025-07-28 |
| [#4031](https://github.com/prebid/prebid-server-java/pull/4031) | Mediasquare — `port-from-go, custom-typed-payload-Bidder-T, multi-class-proto-request-response-split, multi-file-go-preserved` | 2025-07-28 |
| [#4082](https://github.com/prebid/prebid-server-java/pull/4082) | Rediads — `port-from-go` | 2025-07-28 |
| [#4087](https://github.com/prebid/prebid-server-java/pull/4087) | Akcelo — `port-from-go` | 2025-07-28 |
| [#3972](https://github.com/prebid/prebid-server-java/pull/3972) | Madsense — `port-from-go` | 2025-07-29 |

### v3.31.0 — 2025-08-22

| PR | Adapter | Merged |
|---|---|---|
| [#4107](https://github.com/prebid/prebid-server-java/pull/4107) | Blis — `port-from-go` | 2025-08-20 |
| [#3985](https://github.com/prebid/prebid-server-java/pull/3985) | Sparteo — `port-from-go` | 2025-08-20 |
| [#4111](https://github.com/prebid/prebid-server-java/pull/4111) | Exco — `port-from-go` | 2025-08-20 |

### v3.32.0 — 2025-09-12

| PR | Adapter | Merged |
|---|---|---|
| [#4153](https://github.com/prebid/prebid-server-java/pull/4153) | Afront — `port-from-go` | 2025-09-03 |

### v3.33.0 — 2025-10-08

| PR | Adapter | Merged |
|---|---|---|
| [#4161](https://github.com/prebid/prebid-server-java/pull/4161) | TeqBlaze — `port-from-go, whitelabel-only-parent` | 2025-09-19 |

### v3.34.0 — 2025-10-24

| PR | Adapter | Merged |
|---|---|---|
| [#4240](https://github.com/prebid/prebid-server-java/pull/4240) | Contxtful — `port-from-go` | 2025-10-21 |
| [#4190](https://github.com/prebid/prebid-server-java/pull/4190) | Showheroes — `port-from-go, companion-aliases-bs-suffix` | 2025-10-21 |

### v3.36.0 — 2025-11-20

| PR | Adapter | Merged |
|---|---|---|
| [#4223](https://github.com/prebid/prebid-server-java/pull/4223) | Nativery — `port-from-go, amp-test-folder` | 2025-11-18 |
| [#4285](https://github.com/prebid/prebid-server-java/pull/4285) | BoldwinRapid — `port-from-go, snake-case-bidder-name` | 2025-11-18 |

### v3.38.0 — 2026-01-21

| PR | Adapter | Merged |
|---|---|---|
| [#4326](https://github.com/prebid/prebid-server-java/pull/4326) | ElementalTV (renamed from Adoppler) — `bidder-rename-major-version, alias-back-via-tilde, package-rename-fixture-dir-rename, acronym-case-preservation` | 2026-01-12 |

### v3.39.0 — 2026-02-06

| PR | Adapter | Merged |
|---|---|---|
| [#4299](https://github.com/prebid/prebid-server-java/pull/4299) | Clydo — `port-from-go` | 2026-02-04 |
| [#4350](https://github.com/prebid/prebid-server-java/pull/4350) | Teal — `java-first` | 2026-02-05 |

### v3.41.0 — 2026-03-25

| PR | Adapter | Merged |
|---|---|---|
| [#4428](https://github.com/prebid/prebid-server-java/pull/4428) | TrustX — `port-from-go, alias-to-full-migration-counterpart` | 2026-03-23 |

---

## Releases with no new bid adapters

v3.19.0, v3.20.0, v3.21.0, v3.22.0, v3.25.0, v3.30.0, v3.35.0, v3.37.0, v3.40.0

## Notes

- Many 2025 adapters are explicit ports from the Go server (e.g., Adverxo, Connatix, Ogury, Kobler, FeedAd, Kueez, Mobkoi). Java tends to follow Go by 2-6 months for net-new bidder code.
- Releases with the highest volume: v3.28.0 (5 adapters) and v3.29.0 (7 adapters) — both in July 2025, a clear bidder onboarding push.
- 2026 has slowed to 4 new adapters across 4 months, mirroring the trend in prebid-server (Go).
- PR titles use multiple conventions: "New Adapter: X", "New X Adapter", "Port X: New Adapter", "X: New adapter ported from Go", "X bidder", "X: Add Bidder".

## SQL used

```sql
WITH new_adapter_prs AS (
  SELECT DISTINCT pr.number, pr.title, pr.close_date, pr.files_changed, pr.lines_added,
         json_extract(fc.value, '$.filename') AS fname
  FROM pull_requests pr, json_each(pr.file_changes) fc
  WHERE pr.repository_id = 2
    AND pr.state = 'MERGED'
    AND pr.close_date >= '2025-01-01'
)
SELECT number, title, close_date, files_changed, lines_added,
       GROUP_CONCAT(DISTINCT fname) AS bidder_files
FROM new_adapter_prs
WHERE fname GLOB 'src/main/java/org/prebid/server/bidder/*/*Bidder.java'
GROUP BY number
HAVING lines_added > 400  -- filters out modifications to existing bidders
ORDER BY close_date;
```

(Final list further filtered by manual title inspection to exclude feature ports of existing adapters and confirm true new-directory creations.)

Release dates from `gh release list --repo prebid/prebid-server-java`. PRs are assigned to the first release whose publish timestamp is after the PR's merge timestamp.

---

## Alias-Only Adapters

These PRs add a new bidder name but no new `Bidder.java` directory — they reuse a parent adapter's Java code via the `aliasOf:` field in `src/main/resources/bidder-config/<parent>.yaml`. PR sizes are larger than Go aliases because each Java alias still needs an integration test class and JSON test fixtures (~7 files each).

**14 alias-only adapters** between 2025-02-20 and 2026-04-22.

### v3.21.0 — 2025-02-21

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#3738](https://github.com/prebid/prebid-server-java/pull/3738) | Connektai — `port-from-go-alias` | Xeworks | 2025-02-20 |

### v3.23.0 — 2025-04-04

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#3805](https://github.com/prebid/prebid-server-java/pull/3805) | Streamvision — `port-from-go-alias, limelight-family` | LimelightDigital | 2025-03-17 |
| [#3838](https://github.com/prebid/prebid-server-java/pull/3838) | OrangeClickMedia | Limelight | 2025-04-01 |
| [#3875](https://github.com/prebid/prebid-server-java/pull/3875) | Yobee | Admatic | 2025-04-01 |
| [#3874](https://github.com/prebid/prebid-server-java/pull/3874) | AdmaticDe | Admatic | 2025-04-01 |
| [#3873](https://github.com/prebid/prebid-server-java/pull/3873) | MonetixAds | Admatic | 2025-04-01 |
| [#3872](https://github.com/prebid/prebid-server-java/pull/3872) | Pixad | Admatic | 2025-04-01 |

### v3.25.0 — 2025-05-07

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#3909](https://github.com/prebid/prebid-server-java/pull/3909) | AdTarget.org — `underscore-or-dot-in-bidder-name` | Limelight | 2025-04-25 |
| [#3840](https://github.com/prebid/prebid-server-java/pull/3840) | Velonium | Limelight | 2025-04-25 |

### v3.27.0 — 2025-06-12

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#3829](https://github.com/prebid/prebid-server-java/pull/3829) | 152 Media — `digit-leading-bidder-class-workaround-OneFiveTwoMedia, co-shipped-second-alias-rxnetwork` | Adkernel | 2025-06-03 |

### v3.35.0 — 2025-11-07

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#4272](https://github.com/prebid/prebid-server-java/pull/4272) | Performist — `limelight-family` | Limelight | 2025-11-05 |
| [#4273](https://github.com/prebid/prebid-server-java/pull/4273) | Gravite — `gvl-name-mismatch-tolerated, teqblaze-family` | TeqBlaze | 2025-11-05 |

### v3.39.0 — 2026-02-06

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#4365](https://github.com/prebid/prebid-server-java/pull/4365) | RadiantFusion — `attekmi-family-rebrand-from-smarthub` | Attekmi | 2026-02-04 |

### Pending next release (post v3.41.0)

| PR | Adapter | Parent | Merged |
|---|---|---|---|
| [#4361](https://github.com/prebid/prebid-server-java/pull/4361) | 360playvid — `digit-leading-bidder-name-as-yaml-only` | TeqBlaze | 2026-04-22 |

### Notes on alias-only adapters

- Each Java alias PR is ~7 files (vs ~1 for Go) because of integration tests, fixtures, and properties files.
- Java aliases tend to follow the corresponding Go aliases by 1-3 months (Connektai, Streamvision, Yobee, Admatic family, Velonium, Performist, RadiantFusion all appeared in Go first).
- Java has fewer pure YAML-only "generic openrtb" adapters than Go — most Java aliases name a parent.

---

## Pattern Index

Cross-reference of pattern tags to canonical exemplar PRs. Each tag is a short slug used in the per-PR `Patterns Demonstrated` annotations above. Skills' `references/*.md` Pattern Catalog sections cite tags from this index. Java-specific tags carry Java semantics; cross-language tags (e.g., `port-from-go`, `bidder-rename-major-version`) parallel the Go list's Pattern Index.

### Porting & Provenance

| Tag | Description | Exemplar PRs |
|---|---|---|
| `port-from-go` | Java adapter ported from a pre-existing Go implementation (~1-3 months later) | #3684, #3705, #3781, #3788, #3869, #3916, #3930, #3942, #4027, #4031, #4053, #4054, #4078, #4082, #4087, #3972, #4107, #3985, #4111, #4153, #4161, #4240, #4190, #4223, #4285, #4299, #4428 |
| `port-from-go-alias` | Alias-only port from Go (Java alias YAML follows Go alias by weeks) | #3738, #3805 |
| `java-first` | Java adapter introduced before/without a Go counterpart | #3941, #4350 |
| `dead-code-proto-port-fidelity` | Java port preserves Go-side fields/code that aren't actively used (port fidelity) | #3869 |
| `multi-file-go-preserved` | Go side had multi-file layout; Java port preserves equivalent multi-class split | #4031 |
| `alias-to-full-migration-counterpart` | Java equivalent of a Go `alias-to-full-migration` (alias YAML upgraded to full bidder code) | #4428 |

### Code & Adapter Patterns (Java-specific)

| Tag | Description | Exemplar PRs |
|---|---|---|
| `configuration-properties-subclass` | Per-bidder `@ConfigurationProperties` subclass extending the common base for non-default fields | #3684 |
| `dev-prod-endpoint-toggle` | Bidder selects dev vs prod endpoint at runtime via config flag | #3684 |
| `currency-conversion` | Adapter performs explicit `CurrencyConversionService` invocation in MakeRequests | #3684 |
| `currency-conversion-via-bidderutil` | Currency conversion delegated through `BidderUtil` helper rather than inline | #3916 |
| `per-imp-request-strategy` | One outgoing HTTP request per `imp` (vs single bundled request) | #3705 |
| `multi-alias-bundle` | Adapter PR ships parent + multiple aliases atomically (Java-side bundle) | #3705 |
| `alias-coverage-it-classes` | Each alias gets its own `*Test.java` integration test class | #3705 |
| `free-form-imp-ext-no-proto` | `imp.ext` parsed as free-form `ObjectNode`/`Map` rather than a typed `ExtImp<Name>` | #3788 |
| `endpoint-compression-typo-camelcase` | YAML key casing slip — `endpointCompression` typo or casing inconsistency | #3788 |
| `modifying-vast-xml-allowed` | Adapter may modify VAST XML response payload (allowed for video adapters) | #3869 |
| `custom-typed-payload-Bidder-T` | `Bidder<T>` parameterized over a custom typed request payload (non-`BidRequest`) | #4031 |
| `multi-class-proto-request-response-split` | `proto/openrtb/ext` split across multiple request/response classes per bidder | #4031 |
| `dooh-platform-declared` | `dooh` declared in YAML capabilities alongside site/app | #4054 |
| `enabled-false-default` | Bidder ships `enabled: false` by default in YAML (publisher activates) | #4054 |
| `ortb-version-quoted` | YAML declares OpenRTB version as a quoted string (`"2.6"`) to preserve format | #4054 |
| `whitelabel-only-parent` | Parent adapter marked as whitelabel-only — only used as alias root, not directly | #4161 |
| `companion-aliases-bs-suffix` | Companion aliases differ from parent by `-bs` (bid-stream) suffix only | #4190 |
| `amp-test-folder` | Integration tests include AMP-specific test fixtures folder | #4223 |
| `snake-case-bidder-name` | Bidder name uses snake_case-style or compound-form (e.g., `boldwinrapid`) | #4285 |
| `empty-bidder-params-schema` | `bidder-params/<name>.json` JSON schema is intentionally empty/free-form | #3941 |
| `all-three-platforms-declared` | YAML declares site, app, AND dooh capabilities together | #3941 |

### Rename / Migration Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `bidder-rename-major-version` | Bidder rename done as part of a major release (breaking change tolerated) | #4326 |
| `alias-back-via-tilde` | Old name retained as `~aliasOf:` (tilde-prefixed) backward-compat alias | #4326 |
| `package-rename-fixture-dir-rename` | Java package rename also requires fixture directory rename (cascading rename) | #4326 |
| `acronym-case-preservation` | Title-case class name preserves acronym casing (e.g., `ElementalTV` not `ElementalTv`) | #4326 |

### Aliases & White-Label Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `limelight-family` | Alias rooted at the LimelightDigital/Limelight parent family | #3805, #4272 |
| `teqblaze-family` | Alias rooted at the TeqBlaze parent | #4273, #4361 |
| `attekmi-family-rebrand-from-smarthub` | Alias under the Attekmi parent (post SmartHub→Attekmi rebrand) | #4365 |
| `co-shipped-second-alias-rxnetwork` | Alias PR co-ships a second sibling alias in the same PR (rxnetwork bundled) | #3829 |
| `gvl-name-mismatch-tolerated` | GVL ID name does not match bidder name; tolerated when relationship is credible | #4273 |

### Naming-Edge-Case Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `digit-leading-bidder-class-workaround-OneFiveTwoMedia` | Java class name cannot start with a digit; `152` workaround → `OneFiveTwoMedia` | #3829 |
| `digit-leading-bidder-name-as-yaml-only` | Digit-leading name accepted as YAML-only alias (no Java class needed) | #4361 |
| `underscore-or-dot-in-bidder-name` | Bidder name contains `.` (or underscore) — accepted with file-system caveats | #3909 |
