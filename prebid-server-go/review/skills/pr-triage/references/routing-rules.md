# Routing Rules

File-to-skill mapping rules, unowned file patterns, PR type heuristics, and shared file resolution logic.

**Upstream source (canonical):** Derived from the activation patterns of:
- `bidder-info-pr-review/SKILL.md`
- `bidder-params-pr-review/SKILL.md`
- `adapter-code-pr-review/SKILL.md`

> **Sync policy:** When a downstream skill's activation patterns change, this file must be updated to match.

---

## Module path & framework reference

**Current major:** `github.com/prebid/prebid-server/v4` (since release v4.0.0, March 2026).

For framework-wide concerns (endpoint template macros canonical list, error types, anti-patterns, maintainer email policy, white-label policy, naming conventions, aliasing semantics, test harness contract), see [../../shared/framework-utilities.md](../../shared/framework-utilities.md). The pr-triage skill's drift checks reference this file.

---

## File-to-Skill Routing Table

### bidder-info-pr-review

| Pattern | Example | Notes |
|---------|---------|-------|
| `static/bidder-info/*.yaml` | `static/bidder-info/appnexus.yaml` | All bidder-info YAML files |

### bidder-params-pr-review

| Pattern | Example | Notes |
|---------|---------|-------|
| `static/bidder-params/*.json` | `static/bidder-params/appnexus.json` | Bidder parameter JSON schemas |
| `openrtb_ext/imp_*.go` | `openrtb_ext/imp_appnexus.go` | Impression extension Go structs |
| `adapters/*/params_test.go` | `adapters/appnexus/params_test.go` | Parameter validation tests |

### adapter-code-pr-review

| Pattern | Example | Notes |
|---------|---------|-------|
| `adapters/{bidder}/{bidder}.go` | `adapters/appnexus/appnexus.go` | Adapter implementation |
| `adapters/{bidder}/{bidder}_test.go` | `adapters/appnexus/appnexus_test.go` | Adapter JSON test runner |
| `adapters/{bidder}/*.go` (excl. `params_test.go`) | `adapters/appnexus/utils.go` | Additional adapter Go files |
| `adapters/{bidder}/{bidder}test/exemplary/*.json` | `adapters/appnexus/appnexustest/exemplary/banner.json` | Exemplary test fixtures |
| `adapters/{bidder}/{bidder}test/supplemental/*.json` | `adapters/appnexus/appnexustest/supplemental/bad-ext.json` | Supplemental test fixtures |
| `adapters/{bidder}/{bidder}test/amp/*.json` | `adapters/appnexus/appnexustest/amp/site.json` | AMP test fixtures |
| `adapters/{bidder}/{bidder}test/video/*.json` | `adapters/appnexus/appnexustest/video/sample.json` | Video-specific test fixtures |
| `adapters/{bidder}/{bidder}test/videosupplemental/*.json` | `adapters/appnexus/appnexustest/videosupplemental/bad-video.json` | Video error-path fixtures |
| `exchange/adapter_builders.go` | | Builder registration (exclusively owned) |
| `openrtb_ext/bidders.go` | | Bidder constant registration (shared — see below) |

---

## Test data directories supported

`adapters/adapterstest/test_json.go` supports five subdirectories under `<bidder>test/`:

| Directory | Owner skill | Notes |
|-----------|-------------|-------|
| `exemplary/` | adapter-code-pr-review | Happy-path fixtures |
| `supplemental/` | adapter-code-pr-review | Edge cases, error paths |
| `amp/` | adapter-code-pr-review | AMP-specific tests |
| `video/` | adapter-code-pr-review | Video-specific tests |
| `videosupplemental/` | adapter-code-pr-review | Video error-path fixtures |

Canonical test root name is `<bidder>test/`. Legacy alternates (`adapters/msft/test/`, `adapters/msft/test-extrainfo/`) tolerated.

---

## Shared File Resolution

### `openrtb_ext/bidders.go`

This file is referenced by both `bidder-params` (for `NewBidderParamsValidator`) and `adapter-code` (for bidder constant registration).

**Resolution by diff content:**

| Diff Content | Owner |
|-------------|-------|
| Changes to `const Bidder{Name}` or `coreBidderNames` entries | `adapter-code` |
| Changes to `NewBidderParamsValidator` or schema validation logic | `bidder-params` |
| Both types of changes present | `shared:bidder-params+adapter-code` (include in both skills' file lists) |

---

## Priority Rules for Overlapping Patterns

The pattern `adapters/{bidder}/*.go` in adapter-code overlaps with `adapters/*/params_test.go` in bidder-params.

| File | Winner | Reason |
|------|--------|--------|
| `adapters/{bidder}/params_test.go` | **bidder-params** | Explicit exclusion in adapter-code skill; more specific pattern wins |
| `adapters/{bidder}/{bidder}.go` | **adapter-code** | Direct match |
| `adapters/{bidder}/{bidder}_test.go` | **adapter-code** | Direct match |
| `adapters/{bidder}/*.go` (anything else) | **adapter-code** | Catch-all for adapter Go files |

---

## Unowned File Patterns

Files not matching any skill's activation patterns. Grouped by sub-category.

### Framework — Known Impact

| Pattern | Impact Scope | Recommendation |
|---------|-------------|----------------|
| `macros/macros.go` | All adapters using endpoint template macros | Check if `EndpointTemplateParams` changed — affects valid macro list |
| `macros/*.go` | Macro resolution system | Verify backward compatibility |
| `usersync/*.go` | All bidders with userSync config | Verify cookie handling backward compatibility |
| `config/config.go` | Global configuration loading | Verify bidder config auto-discovery still works |
| `config/bidderinfo.go` | BidderInfo struct, YAML loading, alias merge, endpoint validation | **Triggers drift in bidder-info field index.** Also owns `processBidderAliases`, `validateAliases`, `validateAdapterEndpoint`, `ToGVLVendorIDMap` |
| `exchange/*.go` (excl. `adapter_builders.go`) | Auction/exchange behavior | General exchange logic review |
| `openrtb_ext/request.go` | Request processing for all bidders | Verify request wrapper compatibility |
| `openrtb_ext/request_wrapper.go` | Request wrapper used by all adapters | Verify interface unchanged |
| `adapters/bidder.go` | Bidder interface definition | **If interface changes, ALL adapters affected** |
| `adapters/adapterstest/test_json.go` | All adapter test runners | **Triggers drift in adapter-code index** |
| `errortypes/errortypes.go` | Error types used by all adapters | Verify no breaking changes |
| `util/jsonutil/*.go` | JSON marshal/unmarshal for all adapters | Verify backward compatibility |
| `privacy/*.go` | Privacy (GDPR, CCPA, GPP) handling | Affects all bidders with privacy concerns |
| `gdpr/*.go` | GDPR enforcement | Affects all bidders with GVL IDs |

### Framework — Unknown Impact

Any `.go` file not in `adapters/`, `static/`, or matching known patterns above.

### Documentation

| Pattern | Notes |
|---------|-------|
| `*.md` | README, CONTRIBUTING, etc. |
| `docs/**` | Documentation directory |

### CI/CD

| Pattern | Notes |
|---------|-------|
| `.github/**` | GitHub Actions, workflows |
| `.golangci.yml` | Linter configuration |
| `Makefile` | Build configuration |
| `Dockerfile*` | Container configuration |

### Build/Config

| Pattern | Notes |
|---------|-------|
| `go.mod` | Go module dependencies |
| `go.sum` | Go module checksums |
| `.gitignore` | Git ignore rules |
| `config/*.go` (other than `bidderinfo.go`, `config.go`) | General config files |

### Other

Any file not matching any of the above categories.

---

## PR Type Detection Heuristics

### New Adapter

A PR is classified as `new-adapter` if ALL of the following are true for at least one bidder:
1. `adapters/{bidder}/{bidder}.go` has status `added`
2. At least ONE of:
   - `static/bidder-info/{bidder}.yaml` has status `added`
   - `openrtb_ext/bidders.go` diff contains a new `Bidder{Name}` constant

### Alias-Only

A PR is classified as `alias-only` if ALL of the following are true:
1. The only skill-owned files are in the `bidder-info` bucket
2. Every changed `static/bidder-info/*.yaml` file's diff contains `aliasOf` on an added (`+`) line
3. No adapter-code or bidder-params files are present

### Infrastructure/Bulk Change

A PR is classified as `infrastructure` if ANY of the following are true:
1. **5+ distinct bidder directories** have files in any single skill's bucket AND the changes follow a repetitive pattern (same file types modified, similar diff hunks)
2. **Framework files constitute >50%** of the total changed files
3. **Total files >50** AND >80% match a single repeated pattern

When infrastructure is detected:
- Extract the "bulk pattern" (what change is being applied uniformly)
- Identify outliers (files that deviate from the bulk pattern)
- Downstream skills activate in "bulk mode" — verify pattern consistency, not per-bidder detailed review

### Adapter Modification

A PR is classified as `adapter-modification` if:
- Files in an existing `adapters/{bidder}/` directory are modified (not added), OR
- Existing bidder-info/bidder-params files are modified

### Bidder Removal/Disable

A PR is classified as `bidder-removal` if:
- Adapter files are removed, OR
- A bidder-info YAML diff shows `disabled: true` being added

### Framework-Only

A PR is classified as `framework-only` if:
- All changed files are in `unowned:*` categories
- No skill-owned files exist

### Mixed

A PR is classified as `mixed` if multiple categories above apply (e.g., new adapter + framework change). Each sub-component is handled according to its own type.

### Bidder Rename / Refactor

A PR is classified as `bidder-rename` if:
- Files are deleted from `adapters/{old_bidder}/` AND added to `adapters/{new_bidder}/` in the same PR
- AND/OR `static/bidder-info/{old_bidder}.yaml` is deleted with `static/bidder-info/{new_bidder}.yaml` added
- AND/OR `openrtb_ext/bidders.go` shows the constant being renamed

When detected:
- Note that bidder renames are breaking changes typically deferred to the next major release (e.g., PR #4639 adoppler → elementaltv)
- Routing-wise: each affected file goes to its normal owner skill, but pr-triage records `RENAME: {old} → {new}` in the manifest and flags as INFO

### Cross-Cutting Framework Change

A PR is classified as `framework-debt` (additional sub-label on `infrastructure` type) when it modifies `adapters/adapterstest/test_json.go` (the test harness) OR similar files that affect many existing adapters.

When detected:
- Expect a wide blast radius (many existing adapters' test fixtures may need updating in the same PR)
- pr-triage drift output should be SPECIFIC about what changed (e.g., `DRIFT: adapter-code test harness — currency_check_changed | multi_request_1to1_enforced | error_comparison_default_changed`), NOT generic `DRIFT: drift detected`
- Reference: PR #4592 (Microsoft) added currency assertion + multi-request 1:1 matching to `test_json.go`, cascading 35+ adapter test directories

---

## Bidder Name Extraction Rules

| File Pattern | Bidder Name Source |
|-------------|-------------------|
| `static/bidder-info/{name}.yaml` | Filename without extension |
| `static/bidder-params/{name}.json` | Filename without extension |
| `openrtb_ext/imp_{name}.go` | Filename after `imp_` prefix, before `.go` |
| `adapters/{name}/` | Directory name |
| `adapters/{name}/{name}test/` | Parent directory name |
| `exchange/adapter_builders.go` | Extract from diff: `openrtb_ext.Bidder{Name}` |
| `openrtb_ext/bidders.go` | Extract from diff: `Bidder{Name} BidderName = "{name}"` |

---

## Valid Endpoint Template Macros

The canonical `macros.EndpointTemplateParams` allow-list is at [../../shared/framework-utilities.md#endpoint-template-macros](../../shared/framework-utilities.md#endpoint-template-macros) — the single source of truth. The pr-triage Step 5a (cross-skill concern: invalid macros in alias PRs) reads from that list. Do not keep a second copy or a field count here; both go stale and produce false FAILs.

An unrecognized macro is a **startup abort**, not a silent empty substitution: `config/bidderinfo.go:492-507` resolves the endpoint template via `macros.ResolveMacros` → `text/template` Execute, which errors on an unknown struct field.

**Non-Go-template placeholders** (e.g., `#{REGION}#`, `${X}`, `<X>`) are NOT runtime macros — they are deployment-time substitutions and require `disabled: true` in the YAML. See the canonical rule at the linked file.

---

## Bulk-Mode Exception for Multi-Adapter Alias PRs

A PR may bundle multiple alias-only files (e.g., 5 aliases-of-same-parent in one PR) WITHOUT triggering the one-alias-per-PR rule, IF:

1. ALL files target `static/bidder-info/*.yaml` (no Go code, no `bidder-params/`, no other paths)
2. ALL YAML files have IDENTICAL key set (e.g., just `endpoint:` + `aliasOf:` + maybe `maintainer:`)
3. ALL `aliasOf:` values reference the SAME parent
4. NO file > 5 lines (excluding comments)
5. No diverging fields per adapter (e.g., per-alias userSync, per-alias capabilities, per-alias gvlVendorID)

PR #4651 (5 Limelight adapters: altstar, anzuExchange, oveeo, rtbdemand, smootai) is the canonical example: all 5 use `aliasOf: limelightDigital`, identical 2-line schema, same macros. Approved without bundle-objection.

OUTSIDE this exception, the one-alias-per-PR rule applies (PR #4214/#4215 reviewer convention: "Please raise a separate PR for each of the new alias you are contributing. This is helpful in maintenance.").

---

## Whitelabel Policy

`whiteLabelOnly: true` in a `static/bidder-info/{bidder}.yaml` marks that bidder ineligible for direct auctions (`IsEnabled()`, `config/bidderinfo.go:249-251`) — but does NOT preclude Go adapter code on it. `teqblaze` has both the flag and a full Go adapter serving its aliases.

Two corrections to a common misreading:

- **The flag is not the alias-parent marker.** `teqblaze.yaml` is the ONLY upstream file carrying it at master @0ba3523; `smarthub.yaml` serves 11 aliases without it. Identify alias parents by alias count (`grep -rh "aliasOf" static/bidder-info/ | sort | uniq -c | sort -rn`), not by the flag.
- **`whiteLabelOnly: true` together with `aliasOf:` on the same file is a startup abort — FAIL.** `validateAliases` (`config/bidderinfo.go:461-463`) returns `bidder '%s' is an alias and cannot be set as white label only`, which reaches `logger.Fatalf` via `processBidderAliases` → `LoadBidderInfoFromDisk`.

For NEW PRs: when a full adapter is being added that resembles an existing adapter (similar endpoint, comparable params, copy-paste-style code), reviewers redirect contributor to use `aliasOf:` instead. This is detected heuristically — pr-triage cross-skill check 5g should flag PRs where:
- Type is `new-adapter`
- AND (PR description / commit messages / discussion mention "white label") OR (the adapter Go code length is significantly smaller than typical full adapters and the YAML resembles existing parents)

Severity: **WARN** with note suggesting alias-only conversion. The white-label workflow lives in `bidder-info-pr-review` skill; this is the cross-skill detection trigger.

Reference quotes (verbatim) from PRs #4329, #4383, #4391, #4376, #4565 are catalogued at [../../shared/framework-utilities.md#aliasing](../../shared/framework-utilities.md#aliasing) and [../../bidder-info-pr-review/SKILL.md](../../bidder-info-pr-review/SKILL.md) Workflow: White-Label Policy Compliance.
