# F6 — rtbstack Go → Java green-field canary (port-go2java v1.0.0 promotion run)

**Run-id**: `2026-07-06T1908Z-79b6`
**Date**: 2026-07-06
**Operator**: claude-code/fable-5 (multi-agent gauntlet: 6 named reviewer teammates)
**Branches**: skills repo `feat/f6-port-go2java-v1.0.0` (this reflection); prebid-server-java `feat/port-rtbstack`
**Pinned SHAs**: Go source `16f2ebd62d506b91e328eedb6f9ea1ce33a03f68` (master; adapter unchanged since its birth PR #4685, merged 2026-05-13); Java base `d8a4f85be` (origin/master, verified against ls-remote); final port commit `ed297b01c` (+1,062 lines, 12 files)
**Predecessors**: D2.8 6-pair MVP batch (2026-05-11, Gates 1/4/6/7); D3.8 canary 8 "teal" (the Java→Go green-field analog whose success this run mirrors in reverse)
**Status**: **COMPLETE — all gates green, gauntlet clean, submitted upstream as `prebid/prebid-server-java#4552` ("Port RTBStack: New Adapter", closes #4497)**

This is the **green-field validation canary** the port-go2java v0.5.0 status block required for v1.0.0 promotion (the "D3.8-canary-8 analog"): an adapter outside the 6-pair MVP corpus, ported end-to-end read → port → review → submit, with Gates 2+3 cleared by operator-completed scaffolds. It is also the first full Teal-flow execution in the Go→Java direction and the reverse-direction mirror of the approved Teal port (prebid/prebid-server#4765).

## 1. Why rtbstack

- prebid-server-java issue #4497 ("Port PR from PBS-Go: New Adapter: RTBStack") — open, unassigned, label `auto`; the port closes a maintainer-tracked request.
- All four media types on site+app, OpenRTB 2.6, and `getMediaTypeForBid` switches on `bid.MType` with error-on-miss — natively matching the hardened by-bid-mtype template path (zero fidelity-vs-conformance tension on the Teal-lesson pattern).
- Feature surface exercises the pipeline hard: per-route imp grouping (→ Rule 47), 4-macro endpoint derived by parsing a route URL param (→ Rule 48 + new taxon), imp.ext repack with empty-map drop, `tagId` promotion, `site.domain` synthesis with raw-page fallback, currency passthrough.
- Rich source corpus: 17 exemplary + 11 supplemental fixtures → 30-cell Java parity map.

## 2. Phase scoreboard

| Phase | Result |
|---|---|
| 1 — Read | Source spec schema-valid (Draft 2020-12, zero errors); R2 params sha recompute `eb49518f…` (629 B, NO trailing newline); byte-eq vs upstream file; R4 round-trip deterministic; Go tests 4/4 in the pinned worktree; 0 provenance warnings; 2 quirks (route-url-derived macros → `runtime-region-selection` + NEW-TAXON candidate; imp-ext-replace-with-subset) |
| 2 — Port | 46-rule walk: **15 applied / 29 skipped-not-applicable / 2 skipped-source-side-only**; 4 `unresolved_translations[]` (the Rule 47/48/49 candidates + mtype-tolerance ambiguity — all four became this reflection); 11 artifacts + properties insert; params byte-copy sha-verified both sides |
| 2 — Gates | compile ✓ · checkstyle **0 violations** (validate-phase run, full reactor) · unit **27/27 first try** · aggregate **8,595/8,595** (891 classes) · Jacoco **104/104 lines = 100%** (branches 33/37) · IT `RtbStackTest` 1/1 (×2 runs) · port-report v0.2.0 schema-valid · `r5_check.state=pass` |
| 3 — Gauntlet | 6 independent reviewers, **25 findings, 0 FAIL**; every finding adversarially verified against live code before action; post-fix: unit 29/29 · Jacoco 101/101 = 100% (branches 32/35) · checkstyle 0 · IT 1/1 · **fixture parity 30/30, zero fidelity inversions** |
| 4 — Submit | Fork + push (single commit `ed297b01c`); pre-submit rebase: **no drift** (`d8a4f85be` at emit == at submit); PR #4552 OPEN/MERGEABLE, body per repo template (Floxis #4529 convention), `do not port` label requested in-body (authors lack label perms); no companion docs PR needed (`dev-docs/bidders/rtbstack.md` already live with `pbs: true`) |
| 5 — Reflect | This PR: Rules 47/48/49 (rules 0.3.0), taxon `param-derived-endpoint-macros` (taxonomy 1.1.0), two template arms + polarity fix, 4 doc-vs-live corrections, SKILL 0.5.0 → **1.0.0**, ADR-010 |

## 3. Gauntlet summary (Phase 3)

Six parallel, independent reviewers: three skill-driven (bidder-class / bidder-config / bidder-params, with the Go spec as `prior_source_spec`), a fresh-eyes upstream-maintainer lens with zero port context, an upstream porting-guide checklist sweep, and a fixture-parity auditor mapping all 28 Go fixtures + 2 hand-written Go tests onto Java coverage.

| Disposition | Count | Detail |
|---|---|---|
| WARN confirmed → fixed | 4 | **V1 headline**: explicit `modifying-vast-xml-allowed: false` (Go-effective false vs Java-default true — both mechanisms reproduced independently; → Rule 49) · synthetic test data per code-style.md "real data" rule (kept the `-adx-admixer` host label — production parsing logic) · test-constants partial-apply (single-use pair inlined; 3 heavily-reused kept with rationale) · `sg` region test added (all 3 allow-list members now pinned) |
| WARN split verdict | 1 | reuse half adopted (`HttpUtil.getHostFromUrl`), semantic half REFUTED — raw-page `site.domain` fallback KEPT: vendor-owned behavior pinned by a dedicated Go exemplary fixture; ADR-009 no-auto-promote guard (beachfront's null-on-failure is one adapter's choice, not a repo norm) |
| WARN refuted | 1 | "usersync missing vs admixer sibling" — reviewer lacked Go access; Go rtbstack.yaml has NO userSync block; omission is faithful |
| INFO applied | 4 | properties lines relocated into the `adapters.*` cluster (→ F-new-110) · `Collectors.toList()` → `.toList()` (→ F-new-114) · `encodeUrl` differential test (`client%201` → `client+1`, also pins the Go-raw vs Java-encode delta empirically) · customParams value-type matrix (string/number/boolean/int/nested-map/array) |
| INFO rejected with rationale | 2 | params-JSON trailing newline (2 reviewers independently) — Rule 38 byte-fidelity wins; sha `eb49518f…` is the contract |
| INFO corroboration / framework-validated / pre-documented | 13 | incl. R1 independently converging on exactly the two pre-declared deltas (encodeUrl, mtype error-message wording) — no undocumented divergence found |

## 4. F-new findings catalogued (F-new-105 … F-new-115)

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| **F-new-105** | `bidder-config.yaml.j2` vast-flag arm INVERTED — emitted `modifying-vast-xml-allowed` only when true (redundant vs Java default) and omitted it when false (the behavioral case). Written against Go's opt-in polarity and transplanted. | **HIGH** | **FIXED** — always-explicit emission both polarities (Rule 49); render + e2e tests updated |
| **F-new-106** | Effective-value blind spot: Step-4 raw carry-over + Step-6 spec-vs-spec compare → `r5_check=pass` while emitted artifacts diverge behaviorally (`R5_STRICT_KEYS` `deep_eq` is value-blind to framework back-fill). Corpus proof: adkernelAdn / adverxo / thetradedesk pairs divergent in live upstream TODAY (Go-effective false, Java-effective true, all video-capable), all passing R5 spec-strict. | **HIGH** | **MITIGATED** — SKILL Step-4 effective-value contract + Step-6 re-derivation from emitted artifact; reader-side effective-value emission + pair-corpus re-audit DEFERRED (ROADMAP follow-up; ADR-010) |
| F-new-107 | `bidder.java.j2` had no `grouped-by-key` arm (taxon existed; port-java2go got its per-key arm in F2; Go→Java fell through to the TODO throw) | MEDIUM | **FIXED** — Rule 47 + `ctx.batching_per_key` arm (LinkedHashMap, first-seen order, two-level badInput isolation) + 3 render tests |
| F-new-108 | `by-bid-mtype` arm only expressed abort-all (`throw`); rtbstack/zentotem-class sources accumulate-and-skip per bid (`errs = append; continue`). Tolerance is a fidelity property of the source, not a style choice. Spec-expressibility gap: `method_chain[].fallback_action` has no accumulate-and-skip value (taxonomy follow-up candidate). | MEDIUM | **FIXED** — `ctx.bid_type_error_tolerance` (render-guarded to by-bid-mtype) + 3 render tests |
| F-new-109 | Param-derived endpoint macros: novel mechanism (parse ONE publisher param → validate against allow-list → fill all macros) had neither taxon nor rule; Phase 1 filed it as a NEW-TAXON quirk under `runtime-region-selection` | MEDIUM | **FIXED** — taxon `param-derived-endpoint-macros` (kind row + quirk registry; taxonomy 1.1.0) + Rule 48 (deliberately operator-fill; worked example is the contract) |
| F-new-110 | "Append at EOF" properties rule wrong vs live: the `adapters.*` cluster ends mid-file (tail carries `ccpa.enforce` etc.); EOF-append lands entries ~60 lines outside the cluster (caught by fresh-eyes reviewer) | LOW | **FIXED** — registration-rules.md, java-artifact-shapes.md §10, SKILL Step-5 row: insert at END of `adapters.*` cluster |
| F-new-111 | java-artifact-shapes.md §4 import groups INVERTED (showed `java.*` first; live checkstyle convention + every template + merged adapter puts `java.*`/`javax.*` LAST) | LOW | **FIXED** — §4 rewritten with corrected example |
| F-new-112 | java-artifact-shapes.md §11 showed `gvl-vendor-id:` and `user-sync:` — both silently-ignored keys against the live binding (the silent-binding-typo class). Live: `vendor-id` (every meta-info block) and `usersync` (164 files, zero `user-sync`). | LOW | **FIXED** — §11 corrected + Rule-49 line added to the example |
| F-new-113 | SKILL Step-4 `port_lineage` doc block listed `port_translation_rules_version` + `port_skill_version` — the schema's `$defs/CrossLanguage.port_lineage` is closed (`additionalProperties: false`) and rejects both (hit live during the canary; keys dropped to pass Step-4 validation) | LOW | **FIXED** — doc block matches the 5 schema keys; note points to the port-report layer |
| F-new-114 | Sibling-idiom drift: hand-filling from zentotem (the behavioral sibling) imported zentotem-era idioms (`Collectors.toList()`, local `tuple()` shim, fully-qualified `UnaryOperator`) that the gauntlet then modernized | LOW | **FIXED** — java-artifact-shapes.md §6.1 "idiom currency" guidance (reference set = most recently merged adapters, not the behavioral sibling) |
| F-new-115 | `coverage-report.py --check` was environment-sensitive: default discovery included the gitignored `.tmp/full-loop/*/port-report.json` glob, so an operator mid-Teal-flow either fails the check locally or bakes transient counts into the committed report, which then fails on CI. Surfaced live by this reflection PR's own first `validate` run (drift in 10s). | MEDIUM | **FIXED** — transient glob removed from default discovery; the committed report is a function of committed state only (persisted `output/` globs kept — operator-explicit) |

**Process lessons (runbook, not F-new-numbered):**
- **Never pipe gate runs** — `mvn | tail/grep` masked exit codes and destroyed diagnostics three separate times (standalone `checkstyle:check` sweeping generated protobuf sources with hidden status; an IT failure reported as exit 0; a WireMock near-miss diff truncated away). Canonical Java gate: `mvn -B package --file extra/pom.xml` (checkstyle binds to validate in `extra/pom.xml`); verify from surefire XML / `checkstyle-result.xml`. → canary-runbook §10 anti-pattern.
- **Teammate-reviewer delivery protocol** — a reviewer running as a named teammate agent "finished" by printing findings that the orchestrator never sees; delivery must be an explicit message back to the orchestrator, and the dispatch prompt must say so. → canary-runbook §7 output conventions.

## 5. v1.0.0 promotion case (criteria → disposition)

The 0.5.0 status block gated promotion on two conditions; ROADMAP listed two more:

1. **Gates 2+3 routinely cleared by operator-completed scaffolds** — CLEARED green-field: unit 27/27 first-run at emission (29/29 post-review), Jacoco 100% line on the emitted bidder, full suite 8,595/8,595, IT 1/1.
2. **Green-field validation canary (D3.8-canary-8 analog)** — THIS RUN: adapter outside the MVP corpus, no upstream Java reference to lean on, submitted upstream at merge quality.
3. **SKILL prose audit for the 0.5.0 ctx additions** (`ctx.entity_strategies`, `ctx.has_bid_post_processing_macros`, `ctx.config_class_name`, Rule 30 framework-default mapping) — VERIFIED present in SKILL.md Step 3 (all four consulted during this run; Rule 30 + entity-strategy paths exercised live).
4. **Tier-4 cosmetics** — F-new-62 (Gate-5 phantom schemas) RETIRED via execution-plan-phase-d.md §183 correction in this PR; F-new-69 (family-shape classifier `meta.empire_*` consultation) verified addressed in the 0.5.0 Step-2 classification table; F-new-48/49/54/55 remain catalogued, cosmetic, non-blocking.

**SKILL frontmatter 0.5.0 → 1.0.0 (production-promoted)** — symmetric to port-java2go's 2026-05-12 promotion. Both port directions now ship at v1.0.0.

## 6. Follow-ups (tracked, not in this PR)

1. **Reader-side effective-value program** (ADR-010 deferred half): Java read suite emits effective values for adapter-default-backed `bidder_info` fields + pair-corpus re-audit — will surface the adkernelAdn/adverxo/thetradedesk divergences as true R5 findings. ROADMAP Phase E list.
2. **Upstream report for the 3 live divergent pairs** — per-vendor maintainer judgment (flip Java to effective false vs opt the Go configs in); outward action, needs its own authorization.
3. **rtbstack pair fixtures** (goldens both sides + `cross-language-pairs/rtbstack.dual-spec-assertions.yaml`) once #4552 merges and a Java commit can be pinned.
4. **Taxonomy candidate**: bid-loop error-tolerance expressibility (`method_chain[].fallback_action` lacks accumulate-and-skip; F-new-108 note) — schema-touching, deserves its own MINOR.
5. Monitor #4552 CI/review; address maintainer feedback on the port branch.
