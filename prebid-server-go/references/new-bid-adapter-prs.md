# Prebid Server (Go) — New Bid Adapter Reference PRs

Reference list of new-bidder PRs in [prebid/prebid-server](https://github.com/prebid/prebid-server), grouped by release. Used to ground adapter-related skills (review, write, port-java2go) in real merged examples.

- **Source:** prebid/prebid-server
- **Period:** 2025-01-08 → 2026-04-16
- **Totals:** 42 new bid adapters + 47 alias-only adapters
- **Last refreshed:** 2026-04-27

**Classification (by heading):**
- **New Bid Adapters** — PRs that add a brand-new adapter directory with Go code (`adapters/<name>/<name>.go` + tests + registration).
- **Alias-Only Adapters** — PRs that add a new bidder name with no Go code: a single `static/bidder-info/<name>.yaml` referencing a parent via `aliasOf:`, or a YAML-only generic openrtb config.

---

## New Bid Adapters

### v3.7.0 — 2025-01-22
- [#3904](https://github.com/prebid/prebid-server/pull/3904) — `mtype-expected, force-push-policy`
- [#4018](https://github.com/prebid/prebid-server/pull/4018)
- [#4038](https://github.com/prebid/prebid-server/pull/4038)
- [#3929](https://github.com/prebid/prebid-server/pull/3929)
- [#3718](https://github.com/prebid/prebid-server/pull/3718)

### v3.8.0 — 2025-01-28
- [#4082](https://github.com/prebid/prebid-server/pull/4082) — `imp-ext-hoist-pattern, param_test-singular-slip`
- [#3987](https://github.com/prebid/prebid-server/pull/3987)
- [#3766](https://github.com/prebid/prebid-server/pull/3766) — `panic-prone-typeassertion-rejected`

### v3.9.0 — 2025-02-06
- [#4076](https://github.com/prebid/prebid-server/pull/4076)
- [#4104](https://github.com/prebid/prebid-server/pull/4104)
- [#4069](https://github.com/prebid/prebid-server/pull/4069)

### v3.10.0 — 2025-02-13
- [#4148](https://github.com/prebid/prebid-server/pull/4148)
- [#4023](https://github.com/prebid/prebid-server/pull/4023)

### v3.11.0 — 2025-02-20
- [#3994](https://github.com/prebid/prebid-server/pull/3994) — `multi-file-layout-exception`

### v3.13.0 — 2025-03-03
- [#4198](https://github.com/prebid/prebid-server/pull/4198)

### v3.16.0 — 2025-04-08
- [#4169](https://github.com/prebid/prebid-server/pull/4169)

### v3.17.0 — 2025-04-25
- [#4240](https://github.com/prebid/prebid-server/pull/4240)

### v3.18.0 — 2025-06-05
- [#4300](https://github.com/prebid/prebid-server/pull/4300)
- [#4287](https://github.com/prebid/prebid-server/pull/4287) — `typed-bid-pointer-pattern`
- [#4324](https://github.com/prebid/prebid-server/pull/4324)
- [#4309](https://github.com/prebid/prebid-server/pull/4309)

### v3.20.0 — 2025-06-30
- [#4243](https://github.com/prebid/prebid-server/pull/4243)
- [#4286](https://github.com/prebid/prebid-server/pull/4286) — `yaml-go-mtype-drift, companion-aliases`
- [#4275](https://github.com/prebid/prebid-server/pull/4275)

### v3.22.0 — 2025-07-17
- [#4233](https://github.com/prebid/prebid-server/pull/4233) — `open-url-rejected, yaml-go-mtype-drift`
- [#4237](https://github.com/prebid/prebid-server/pull/4237)
- [#4053](https://github.com/prebid/prebid-server/pull/4053)
- [#4250](https://github.com/prebid/prebid-server/pull/4250) — `pointer-mutation-hazard, json-framework-first`

### v3.23.0 — 2025-07-30
- [#4304](https://github.com/prebid/prebid-server/pull/4304) — `iterutil-perf-suggestion`

### v3.24.0 — 2025-08-19
- [#4380](https://github.com/prebid/prebid-server/pull/4380) — `endpoint-macro-validation`

### v3.25.0 — 2025-09-04
- [#4480](https://github.com/prebid/prebid-server/pull/4480) — `whiteLabelOnly-with-go-code-accepted`

### v3.26.0 — 2025-09-30
- [#4321](https://github.com/prebid/prebid-server/pull/4321) — `personal-email-rejected, amp-test-dir, approval-stall`
- [#4443](https://github.com/prebid/prebid-server/pull/4443)

### v3.29.0 — 2025-11-03
- [#4476](https://github.com/prebid/prebid-server/pull/4476) — `errortypes-failedToUnmarshal-mapping, conflicting-reviewer-arch-guidance`
- [#4533](https://github.com/prebid/prebid-server/pull/4533) — `companion-aliases, double-naming-camelCase-kebab-case`

### v3.30.0 — 2025-12-10
- [#4478](https://github.com/prebid/prebid-server/pull/4478)
- [#4535](https://github.com/prebid/prebid-server/pull/4535)
- [#4592](https://github.com/prebid/prebid-server/pull/4592) — `framework-debt-cascade, currency-assertion-added, serialization-naming-mismatch-pubclick-pub_click, multi-request-1to1-enforced`

### v4.0.0 — 2026-03-06
- [#4614](https://github.com/prebid/prebid-server/pull/4614) — `alias-to-full-migration, marshal-error-no-swallow-rule`
- [#4522](https://github.com/prebid/prebid-server/pull/4522)
- [#4660](https://github.com/prebid/prebid-server/pull/4660)
- [#4639](https://github.com/prebid/prebid-server/pull/4639) — `bidder-rename-major-version, openrtb-2.6-yaml-mismatch`

### v4.1.0 — 2026-04-16
None. All "New Adapter" PRs in this release were alias-only — see below.

---

## Alias-Only Adapters

### v3.9.0 — 2025-02-06
- [#4116](https://github.com/prebid/prebid-server/pull/4116) — `1-line-alias-foundation`
- [#4149](https://github.com/prebid/prebid-server/pull/4149) — `inherit-trim-recommendation`

### v3.10.0 — 2025-02-13
- [#4176](https://github.com/prebid/prebid-server/pull/4176)
- [#4183](https://github.com/prebid/prebid-server/pull/4183)

### v3.13.0 — 2025-03-03
- [#4199](https://github.com/prebid/prebid-server/pull/4199)
- [#4164](https://github.com/prebid/prebid-server/pull/4164) — `endpoint-empty-body-fix`
- [#4165](https://github.com/prebid/prebid-server/pull/4165)
- [#4209](https://github.com/prebid/prebid-server/pull/4209)

### v3.14.0 — 2025-03-13
- [#4210](https://github.com/prebid/prebid-server/pull/4210)
- [#4212](https://github.com/prebid/prebid-server/pull/4212)
- [#4214](https://github.com/prebid/prebid-server/pull/4214) — `one-alias-per-pr-rule`
- [#4215](https://github.com/prebid/prebid-server/pull/4215) — `one-alias-per-pr-rule`
- [#4216](https://github.com/prebid/prebid-server/pull/4216) — `1-line-alias, 6-char-waived-siblings`

### v3.15.0 — 2025-03-25
- [#4217](https://github.com/prebid/prebid-server/pull/4217)

### v3.16.0 — 2025-04-08
- [#4211](https://github.com/prebid/prebid-server/pull/4211) — `naming-underscore-allowed-bretg-escalation`

### v3.18.0 — 2025-06-05
- [#4201](https://github.com/prebid/prebid-server/pull/4201)
- [#4357](https://github.com/prebid/prebid-server/pull/4357) — `1-line-alias`

### v3.23.0 — 2025-07-30
- [#4428](https://github.com/prebid/prebid-server/pull/4428)
- [#4420](https://github.com/prebid/prebid-server/pull/4420)

### v3.24.0 — 2025-08-19
- [#4329](https://github.com/prebid/prebid-server/pull/4329) — `whitelabel-redirect, gvl-id-zero-removal`
- [#4441](https://github.com/prebid/prebid-server/pull/4441) — `inherited-email-confirmation`
- [#4350](https://github.com/prebid/prebid-server/pull/4350)

### v3.25.0 — 2025-09-04
- [#4383](https://github.com/prebid/prebid-server/pull/4383) — `whitelabel-redirect, whiteLabelOnly-mechanism-introduced`
- [#4376](https://github.com/prebid/prebid-server/pull/4376) — `whitelabel-redirect, package-name-lowercase`

### v3.26.0 — 2025-09-30
- [#4395](https://github.com/prebid/prebid-server/pull/4395)
- [#4391](https://github.com/prebid/prebid-server/pull/4391) — `whitelabel-redirect, personal-email-rejected`
- [#4434](https://github.com/prebid/prebid-server/pull/4434)

### v3.28.0 — 2025-10-09
- [#4534](https://github.com/prebid/prebid-server/pull/4534) — `setuid-cookie-flow-test`

### v3.29.0 — 2025-11-03
- [#4502](https://github.com/prebid/prebid-server/pull/4502) — `disabled-region-placeholder`
- [#4547](https://github.com/prebid/prebid-server/pull/4547) — `gvl-name-mismatch-tolerated-corporate-restructure`
- [#4283](https://github.com/prebid/prebid-server/pull/4283) — `approval-stall, blocked-on-docs-label`

### v4.0.0 — 2026-03-06
- [#4616](https://github.com/prebid/prebid-server/pull/4616) — `ssl-cert-refresh`
- [#4532](https://github.com/prebid/prebid-server/pull/4532)
- [#4456](https://github.com/prebid/prebid-server/pull/4456) — `bidder-rename-major-version`
- [#4663](https://github.com/prebid/prebid-server/pull/4663)
- [#4651](https://github.com/prebid/prebid-server/pull/4651) — `multi-adapter-bulk-exception`
- [#4607](https://github.com/prebid/prebid-server/pull/4607) — `ssl-cert-refresh, 404-on-empty-imps-tolerated`

### v4.1.0 — 2026-04-16
- [#4565](https://github.com/prebid/prebid-server/pull/4565) — `whitelabel-redirect-mid-review`
- [#4684](https://github.com/prebid/prebid-server/pull/4684) — `email-loop-reply-to-bug, agent-review-label`
- [#4617](https://github.com/prebid/prebid-server/pull/4617)
- [#4695](https://github.com/prebid/prebid-server/pull/4695)
- [#4693](https://github.com/prebid/prebid-server/pull/4693)
- [#4698](https://github.com/prebid/prebid-server/pull/4698) — `personal-email-rejected, agent-missed-personal-email-check`
- [#4671](https://github.com/prebid/prebid-server/pull/4671) — `draft-mode-incomplete`
- [#4597](https://github.com/prebid/prebid-server/pull/4597)
- [#4630](https://github.com/prebid/prebid-server/pull/4630)
- [#4712](https://github.com/prebid/prebid-server/pull/4712)
- [#4727](https://github.com/prebid/prebid-server/pull/4727)

---

## Releases with no new bid adapters

v3.6.0, v3.12.0, v3.14.0, v3.15.0, v3.19.0, v3.20.1, v3.21.0, v3.27.0, v3.28.0, v4.1.0

---

## Pattern Index

Cross-reference of pattern tags to canonical exemplar PRs. Each tag is a short slug used in the per-PR `Patterns Demonstrated` annotations above. Skills' `references/*.md` Pattern Catalog sections cite tags from this index.

### Code & Adapter Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `mtype-expected` | Reviewer expects `bid.MType` for bid type resolution; ad-markup detection is anti-pattern | #3904, #3766, #4082 |
| `panic-prone-typeassertion-rejected` | `map[string]interface{}` type assertions in adapter code can panic; structs mandated | #3766 |
| `multi-file-layout-exception` | Multi-file adapter Go layout (parsers.go/structs.go/utils.go) reluctantly accepted for non-OpenRTB serialization | #3994 |
| `imp-ext-hoist-pattern` | Two-phase imp.ext unmarshaling: first to `adapters.ExtImpBidder`, then to bidder-specific struct | #4082 |
| `pointer-mutation-hazard` | `request.Site`/`request.App` are pointers; mutate via shallow copy + write-back | #4250, #4275, #4237, #4243 |
| `typed-bid-pointer-pattern` | Use `&seatBid.Bid[i]` (slice index pointer), NOT `&bid` (loop variable pointer) | #4287 |
| `iterutil-perf-suggestion` | `iterutil.SlicePointerValues` performance suggestion (INFO-level, not blocking) | #4304 |
| `endpoint-macro-validation` | Endpoint URL macros must match the canonical 19-field `EndpointTemplateParams` list | #4380 |
| `open-url-rejected` | Endpoint URL from `imp.ext.bidder.endpoint` (publisher-controlled) is policy-rejected | #4233 |
| `yaml-go-mtype-drift` | YAML capabilities media types must match adapter's MakeBids switch coverage | #4233, #4286, #4321, #4533, #4660, #4535, #4480 |
| `errortypes-failedToUnmarshal-mapping` | Error type mapping has metric implications; `BadInput` vs `FailedToUnmarshal` distinct counters | #4476 |
| `marshal-error-no-swallow-rule` | Marshaling errors must NEVER be silently swallowed (production shared-memory-corruption surfacing) | #4614 |
| `force-push-policy` | Force-pushing during review dismisses prior approvals; reviewer guidance is no-force-push | #3904, #4023, #4076 |
| `json-framework-first` | Test coverage via `RunJSONBidderTest` JSON framework, NOT Go unit tests | #4250, #4533 |

### Test Fixtures Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `param_test-singular-slip` | Filename `param_test.go` (singular) merged once; canonical is `params_test.go` (plural) | #4082 |
| `amp-test-dir` | `amp/` test subdir is a valid third category alongside exemplary/supplemental | #4321 |
| `framework-debt-cascade` | Modifying `adapters/adapterstest/test_json.go` cascades to many existing adapters' fixtures | #4592 |
| `currency-assertion-added` | `expectedBidResponses[*].currency` now asserted by harness (was silently ignored pre-#4592) | #4592 |
| `multi-request-1to1-enforced` | Multi-request fixtures must match expected/actual entries 1:1 (post-#4592) | #4592 |
| `serialization-naming-mismatch-pubclick-pub_click` | JSON tag inconsistency between `openrtb_ext` struct and adapter internal `models.go` | #4592 |

### Aliases & White-Label Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `whitelabel-redirect` | Reviewer redirects full Go adapter → alias-only because adapter looks like a copy | #4329, #4383, #4391, #4376, #4565 |
| `whitelabel-redirect-mid-review` | Same as above but mid-review status change (started full, ended alias-only) | #4565 |
| `whiteLabelOnly-mechanism-introduced` | The `whiteLabelOnly: true` YAML flag introduced as a parent-marker for aliasing | #4383 |
| `whiteLabelOnly-with-go-code-accepted` | `whiteLabelOnly: true` paired with full Go code on parent — accepted (parent is alias target) | #4480 |
| `companion-aliases` | Full adapter + companion alias YAMLs in same PR | #4286, #4533 |
| `double-naming-camelCase-kebab-case` | Same alias added twice with different casing/formatting | #4533 |
| `gvl-id-zero-removal` | `gvlVendorID: 0` on alias is redundant; PBS inherits parent's GVL anyway | #4329 |
| `inherit-trim-recommendation` | Reviewer asks alias to delete fields that are inherited from parent | #4149, #4329, #4376 |
| `1-line-alias` | Alias YAML containing only `aliasOf: parent` is valid (full inheritance) | #4216, #4357, #4116 |
| `1-line-alias-foundation` | Earliest minimal alias example | #4116 |
| `6-char-waived-siblings` | First-6-character uniqueness rule waived for sibling-family aliases (intentional collision) | #4216 |
| `naming-underscore-allowed-bretg-escalation` | Underscore in bidder name allowed server-side after cross-team escalation | #4211 |
| `package-name-lowercase` | Go package/folder name must be all-lowercase | #4376 |
| `endpoint-empty-body-fix` | SmartHub-family endpoints initially returned 404 on empty body; publisher fixed | #4164 |
| `inherited-email-confirmation` | Alias maintainer.email matches parent's; reviewer confirms intentional | #4441 |
| `setuid-cookie-flow-test` | Reviewer runs PBS locally to verify userSync setuid cookie flow end-to-end | #4534 |

### Policy & Process Patterns

| Tag | Description | Exemplar PRs |
|---|---|---|
| `personal-email-rejected` | `maintainer.email` cannot be personal address; reviewer requires group/role mailbox | #4321, #4391, #4434, #4698 |
| `agent-missed-personal-email-check` | Automated agent review missed the personal-email policy violation | #4698 |
| `agent-review-label` | PR carries `agent review` label (auto-review by ChrisHuie's agent) | #4684, #4671, #4693, #4695, #4698 |
| `email-loop-reply-to-bug` | Reviewer's reply-to was set to publisher's own address — verification email looped | #4684 |
| `ssl-cert-refresh` | SSL cert expired (`token is exterminated`); publisher refreshed mid-review | #4607, #4616 |
| `gvl-name-mismatch-tolerated-corporate-restructure` | GVL ID name doesn't match bidder name; tolerated when there's a credible relationship (corporate restructure) | #4547 |
| `404-on-empty-imps-tolerated` | Endpoint returns 404 for body-less requests; reviewer accepts as evidence-of-life | #4607 |
| `disabled-region-placeholder` | Endpoint with non-Go-template `#{REGION}#` placeholder requires `disabled: true` | #4502 |
| `bidder-rename-major-version` | Bidder rename PRs deferred to next major release (breaking change) | #4456, #4639 |
| `alias-to-full-migration` | YAML had `aliasOf:` deleted, replaced with full endpoint/capabilities (alias→full transition) | #4614 |
| `multi-adapter-bulk-exception` | N aliases-of-same-parent bundled in one PR, accepted because identical schema | #4651 |
| `one-alias-per-pr-rule` | Reviewer requires splitting bundled aliases into separate PRs | #4214, #4215, #4201 |
| `approval-stall` | Approved PR stalled 100+ days awaiting merge / docs PR resolution | #4321, #4283 |
| `blocked-on-docs-label` | `blocked` label added pending corresponding docs PR | #4283 |
| `draft-mode-incomplete` | Reviewer moves incomplete PR to draft mode | #4671 |
| `openrtb-2.6-yaml-mismatch` | Adapter sends `X-OpenRTB-Version: 2.6` header but YAML doesn't declare 2.6 → bidder receives 2.5 | #4639 |
| `conflicting-reviewer-arch-guidance` | Two reviewers gave conflicting architectural guidance (jsonutil contribute vs adapter-local) | #4476 |

### Reviewer Verification Procedures (manual, but skills can record)

| Tag | Description | Exemplar PRs |
|---|---|---|
| `email-confirmation-pending` | Reviewer sent verification email; merge blocked until maintainer replies "received" | most PRs (canonical: #4480, #4660, #4614) |
| `gvl-vendor-list-cross-check` | Reviewer fetches `vendor-list.consensu.org` and verifies vendor name match | #4329, #4428, #4534, #4547, #4671, #4727 |
