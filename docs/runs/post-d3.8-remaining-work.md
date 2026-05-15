# Post-D3.8 Remaining-Work Audit

**Audit date**: 2026-05-06
**Auditor**: claude-code/opus-4-7
**Audit scope**: every phase A–F, every SKILL tree (Go + Java), every cleanup item
**Anchors**: ROADMAP.md, CHANGELOG.md (most recent 2026-05-05 entry), `docs/methodology/*.md` (8 files), `docs/runs/d3.8-*` (9 traces), `docs/execution-plan-phase-d.md`, `.tmp/teal-recon/` (canary 8 work-in-flight)

---

## 0. Up-front discrepancy notes

Two prompt-vs-repo mismatches I want to flag before the audit body:

1. **`docs/runs/d3.8-teal-reflection.md` does not exist.** The user's prompt references this file, but the only canary 8 / teal documentation in the repo today is in `.tmp/teal-recon/` (gitignored). Specifically:
   - `.tmp/teal-recon/teal-java-spec.yaml` — the canary 8 source spec (727 lines)
   - `.tmp/teal-recon/iter-final-fidelity-audit.md` — Java fidelity audit
   - `.tmp/teal-recon/iter5-review-skills-findings.md` — review-skills self-review
   - `.tmp/teal-recon/iter5-beyond-review-findings.md` — opus subagent's "what review skills miss" (25 BR-NN findings)
   - `.tmp/teal-recon/preflight-teal-team-review.md` — Teal-team-perspective Pre-PR review
   - `.tmp/teal-recon/plan.md` — the master plan (says reflection memo lands at `docs/runs/d3.8-teal-reflection.md` in Phase F, but Phase F has not run yet)

   The reflection memo is on the to-do list — see Section 7 "Phase F1: write the d3.8-teal-reflection.md memo." It's NOT a deliverable that already shipped. The merged commit `4c09783` (PR #5) consolidated D3.8 canaries 1-7 only; canary 8 (teal) is mid-flight on `feat/teal-port`.

2. **F-new-37 through F-new-43, not F-new-37 through F-new-47.** The prompt references "F-new-37 through F-new-47" (11 findings); the actual catalogue in `.tmp/teal-recon/teal-java-spec.yaml` shows F-new-37 to F-new-43 (7 findings). F-new-44/45/46/47 are not yet authored. Section 5 below uses the 7-finding actual data.

These are not blocking the audit, but the user should know what's actually in the repo before I describe what's left.

---

## 1. Big-picture status

The project is at a **mid-arc inflection point**: the read/port/review/reflect end-to-end loop has been **designed end-to-end** (Phases A–F all have docs landed) and the **engineering layer for Phases A–D is fully shipped** (read-skill suites for both languages, port-engine helpers, both port skills with full template sets, port-report v0.2.0 schema, round-trip CI extended for port-side R4). What's left to do is the **operator-validation layer** and the **review-side + reflection-side skill trees**.

D3.8 (operator validation of port-java2go) just completed for the 6 MVP pairs (kobler, aax, adkernelAdn, adverxo, vungle, thetradedesk), bumping `port-java2go` SKILL frontmatter from 0.3.0 → 0.5.0 (NOT 1.0.0 — 4 HIGH-priority blockers remain plus 1 non-MVP validation canary). A canary 8 / teal port is in flight on `feat/teal-port` — code is hand-emitted (M1/M2/M3 mutations not yet templated; F-new-37/38/39 catalogued for SKILL follow-up) and audited; it has NOT been merged or written to a `docs/runs/d3.8-teal-*` permanent trace. The symmetric direction (D2.8 port-go2java validation against the same 6 MVP pairs) has **NOT** started.

Phase E (review-skill expansion) and Phase F (reflection loop) have **design-only** status. Specifically: Java review-skill suite does not exist (`prebid-server-java/review/` directory absent); `write/` skills don't exist for either language; `diff-spec` skills don't exist; the `--- PRIOR SOURCE SPEC COMPARISON ---` block authored by `pr-triage` has zero downstream consumers (the 3 Go review skills don't read it).

In short: **engineering complete for half the surface, operator-validation complete for one quarter, review/reflect entirely TBD**. The project arc has roughly 50–70% of the total operator-day budget still ahead of it.

---

## 2. Phase-by-phase backlog

### Phase A — Acceptance-gate goldens

**Declared status**: COMPLETE (per ROADMAP §"Phase A — Acceptance-gate goldens").

**Actual remaining work**:
- 23 Go goldens vs 21 Java goldens (Go has 2 more: `33across`, `adtonos`, `bidstack`, `cadent_aperture_mx`, `msft`; Java has `generic`, `huaweiads`, `rubicon` not in Go). 17 dual-spec assertion pairs.
- `docs/coverage-report.md` shows **Rule 46**: 1/11 pairs fully covered (only `adkernelAdn`); **Rule 43**: 3/7 pairs covered. So even though "Phase A complete" is declared, the *fixture corpus* has documented coverage gaps.
- `.tmp/teal-recon/teal-java-spec.yaml` is a canary 8 spec written but NOT promoted to `prebid-server-java/read/test-fixtures/teal.golden.spec.yaml` — teal becomes the 18th paired bidder once promoted.

**Effort estimate**: small (1–2 operator-days to promote teal golden + author dual-spec; ~10–15 operator-days to backfill the 10 missing Rule 46 pairs and 4 missing Rule 43 pairs, *if* the user wants full coverage; likely deferrable).

**Type**: small chunk = engineering+operator (golden authoring is mechanical via read-orchestrator). Coverage backfill = decision (does the user need 100% rule coverage in goldens to ship?).

### Phase B — Go read-skill suite

**Declared status**: COMPLETE (per ROADMAP §"Phase B").

**Actual remaining work**: nothing on the SKILL prose itself — all 4 skills (`read-adapter-orchestrator`, `read-adapter-code`, `read-bidder-info`, `read-bidder-params`) are at v1.0.0 frontmatter with `read-adapter-orchestrator` at v1.1.0 (post D1.5 `--output=` flag). Possible future-work flags:
- `read-adapter-orchestrator/SKILL.md:168` mentions `write/` (Go) — future. Not currently scheduled.
- No tests against the new D1.4 port-report fields from a read-skill perspective.

**Effort estimate**: zero (truly done).

**Type**: n/a.

### Phase C — Java read-skill suite

**Declared status**: COMPLETE.

**Actual remaining work**:
- Same as Phase B — all 4 Java skills at v1.0.0 (orchestrator at v1.1.0). No further work *in* this phase.
- One forward-flag: ROADMAP §Phase C: "A future Java-specific schema would land at `prebid-server-java/read/skills/shared/adapter-spec-java.md` if divergence demands it." That divergence has not been demanded; no work needed today.

**Effort estimate**: zero.

**Type**: n/a.

### Phase D — Port skills

**Declared status**: ENGINEERING COMPLETE; OPERATOR VALIDATION PARTIALLY COMPLETE.

**Actual remaining work** (this is the bulk of "what's left right now"):

#### D2 — port-go2java pipeline + templates
- All 11 Java-target Jinja templates shipped (D2.1-D2.7). Frontmatter at v0.3.0.
- **D2.8 OPERATOR VALIDATION: NOT STARTED.** Same 6 MVP pairs in reverse (Go source → Java target). Per execution plan §D2.3: `mvn -B compile`, `mvn -B test -Dtest={Bidder}BidderTest`, Jacoco line-coverage ≥ 90%, `mvn -B checkstyle:check`, schema validation, port-report schema, R5 state per pair. Requires local `prebid-server-java` clone (canary 8 pattern).
- Cite: ROADMAP line 57; execution-plan-phase-d.md §D2.3 (lines 175-196); `prebid-server-java/port-go2java/SKILL.md:9` ("Frontmatter bumps to 1.0.0 once each MVP pair clears all 7 gates").

**Effort estimate**: medium (5–8 operator-days mirroring D3.8's 7 canary cadence; Java tooling has slower test cycles than Go).

**Type**: operator (canary execution) + engineering (template fixes for findings as they surface).

#### D3 — port-java2go pipeline + templates + operator validation
- 7 Go-target Jinja templates shipped (D3.1+D3.2+D3.8 supplemental). Frontmatter at v0.5.0.
- **D3.8 COMPLETE (2026-05-05)** for 6 MVP pairs.
- **Canary 8 (teal) IN FLIGHT** on `feat/teal-port` branch. Hand-emitted code lives at `.tmp/teal-port/upstream/`. NOT merged; NOT yet written to a `docs/runs/d3.8-teal-canary-*.md` permanent trace; NOT yet captured in CHANGELOG/ROADMAP.
- **port-java2go v1.0.0 promotion blockers**: 5 criteria stated in canary 7 trace; per the user's prompt criterion 5 was retired by canary 8. Net 4 remaining HIGH blockers. See Section 4 below.

**Effort estimate**: small (2–3 operator-days to land canary 8 trace + reflection memo + CHANGELOG/ROADMAP updates) + medium (5–8 operator-days for the 4 v1.0.0 promotion criteria — F-new-2/-7-EXT-A/-7-EXT-B/-34 template work).

**Type**: engineering (template authoring) + operator (validation canaries).

#### D4 — CI integration + fixture-gap fills
- D4.1 round-trip-ci R11 port-side: COMPLETE.
- D4.2 coverage-report per-rule applied count: COMPLETE.
- D4.3 mvn checkstyle dry-run: COMPLETE (helper landed; not yet exercised end-to-end against an emitted Java tree because D2.8 hasn't run).
- D4.4 beachfront ADR-007 F1 master fixture: COMPLETE.
- D4.4 (time-permitting) Connatix fixture: NOT STARTED. Per execution plan §D4.4 line 283: "exercises the new `warn-target-strengthens-source` R5 state." This is the *only* fixture exercising the new R5 state in 0.2.0. Without Connatix, the new state has zero corpus exercise.

**Effort estimate**: D4.4 Connatix backfill = small (1 operator-day).

**Type**: operator (golden authoring).

### Phase E — Review-skill expansion + cross-skill integration

**Declared status**: PARTIALLY SHIPPED.

**Shipped** (per ROADMAP):
- `pr-triage` SKILL has `prior_source_spec` slot and authors a `--- PRIOR SOURCE SPEC COMPARISON ---` block.
- `.tmp/full-loop/{run-id}/` convention for transient run-scoped specs.

**Actual remaining work**:
- **Java review-skill suite**: ENTIRELY ABSENT. ROADMAP says "currently absent." `prebid-server-java/review/` directory does not exist (verified). Should mirror the Go-side 4-skill split: `pr-triage-java`, `bidder-class-pr-review`, `bidder-config-pr-review`, `bidder-params-java-pr-review`. Plus the `prior_source_spec` slot and downstream consumption hooks should be wired symmetrically.
- **Downstream consumption of `--- PRIOR SOURCE SPEC COMPARISON ---`**: zero Go review skills currently read this block. Per ROADMAP line 69: "the hooks are authored in `pr-triage` but no downstream skill reads them yet." 3 skills affected: `adapter-code-pr-review`, `bidder-info-pr-review`, `bidder-params-pr-review`. Each needs a "Step N: cross-language port-fidelity check" prose section that consumes the manifest block and emits port-fidelity findings (severity policy already documented in `pr-triage/SKILL.md:593`).
- **`write/` skills (both languages)**: ROADMAP line 70: "generate adapters from a spec." NOT STARTED. The `cross-skill-integration.md` doc (§3 + §4) heavily references `write/` as a future consumer; the design is partially documented but no `prebid-server-{go,java}/write/` directory exists.
- **`diff-spec` skills (both languages)**: ROADMAP line 71: "compare two specs across commits." NOT STARTED. Two cross-version uses: (a) read-time diff a bidder spec at upstream HEAD vs a pinned older SHA to detect drift; (b) port-time replay an old port-report against a newer rules version (per Phase F cross-version replay). No design doc beyond the one-liner.
- **`evals.json` (skill-creator standard)**: cross-skill-integration.md §"Future" (lines 389-391) flags this as a TODO for runnable skills.

**Effort estimate**:
- Java review-skill suite: large (10–15 operator-days; requires Java codebase familiarity, mirroring 4 Go skills with Java-specific patterns).
- Downstream consumption hooks (3 Go skills): medium (3–5 operator-days; prose-only, no new tooling).
- `write/` skills: large (15–25 operator-days, both languages combined; deserves its own design doc and execution plan).
- `diff-spec` skills: medium (5–10 operator-days, both languages).

**Type**: engineering (skill prose authoring) + design (write/diff-spec need ADR-level decisions about scope and pipeline).

### Phase F — Reflection loop

**Declared status**: DESIGN LANDED.

**Actual remaining work**: ENTIRE IMPLEMENTATION.

Per `docs/methodology/reflection-loop.md`:
- Triage matrix (9 rows, mapping issue type → fix location): authored as prose; NOT implemented.
- ADR amendment protocol: documented; NOT automated.
- Cross-version replay: documented at `scripts/replay-port.py` (future); script does not exist.
- Three triggers (post-port, post-merge, periodic sweep): NOT implemented. Per the doc: "Trigger 1 is invoked via the orchestrator (Teal flow); triggers 2 and 3 run on a schedule (GitHub Actions weekly cron)."
- Output: PRs against `prebid-agent-skills`. Auto-PR-creation infrastructure absent.
- Failure modes (4 documented): handlers not coded.
- Specifically: the `d3.8-teal-reflection.md` memo the user references is the **first concrete Phase F deliverable** — the canary 8 plan calls for it as Phase F output (`.tmp/teal-recon/plan.md` line 175-176). Its absence is the most visible Phase F gap right now.

**Effort estimate**: very large (20–40 operator-days for the full reflection-loop implementation including cross-version replay, triage automation, and weekly cron). The teal-reflection memo alone = small (1–2 operator-days, hand-authored).

**Type**: engineering (replay script + cron + auto-PR) + operator (per-port memo authoring) + decision (when to fully automate vs leave hand-authored).

---

## 3. SKILL tree audit

### `prebid-server-go/read/skills/` — COMPLETE
- `read-adapter-orchestrator/SKILL.md` v1.1.0 + references/
- `read-adapter-code/SKILL.md` v1.0.0 + references/
- `read-bidder-info/SKILL.md` v1.0.0 + references/
- `read-bidder-params/SKILL.md` v1.0.0 + references/
- `shared/`: 11 files (adapter-spec.md, adapter-spec.schema.json, behavior-taxonomy.md+yaml, port-translation-rules.md+yaml, port-report.schema.json, cross-skill-integration.md, bidder-constant-table.yaml, endpoint-macros.yaml, review-pattern-transfer-policy.md)
- **Status**: nothing missing.

### `prebid-server-go/port-java2go/` — D3.8 COMPLETE (operator validation), NOT YET v1.0.0
- `SKILL.md` frontmatter v0.5.0 (bumped from 0.3.0 in D3.8).
- `references/` directory present.
- `templates/`: 7 templates (`bidder-info.yaml.j2`, `bidder-test.go.j2`, `bidder.go.j2`, `exemplary-fixture.json.j2`, `imp-ext-pojo.go.j2`, `params-test.go.j2`, `supplemental-fixture.json.j2`).
- **What's missing for v1.0.0**: see Section 4.

### `prebid-server-go/review/skills/` — PARTIALLY SHIPPED, MISSING DOWNSTREAM HOOKS
- `pr-triage/SKILL.md` v1.0.0 — authors `--- PRIOR SOURCE SPEC COMPARISON ---` block (since Wave 5).
- `adapter-code-pr-review/SKILL.md` v1.0.0 — does NOT consume the source-spec block.
- `bidder-info-pr-review/SKILL.md` v1.0.0 — does NOT consume the source-spec block.
- `bidder-params-pr-review/SKILL.md` v1.0.0 — does NOT consume the source-spec block.
- `shared/`: 1 file (`framework-utilities.md`).
- **What's missing**: per ROADMAP, downstream consumption hooks. Also missing: any `write/` or `diff-spec` siblings.

### `prebid-server-java/read/skills/` — COMPLETE
- `read-bidder-orchestrator/SKILL.md` v1.1.0
- `read-bidder-class/SKILL.md` v1.0.0
- `read-bidder-config/SKILL.md` v1.0.0
- `read-bidder-params-java/SKILL.md` v1.0.0
- `shared/` (Java side; mostly cross-references the Go-side `shared/` for canonical schema)
- **Status**: nothing missing.

### `prebid-server-java/port-go2java/` — D2 ENGINEERING COMPLETE, D2.8 OPERATOR VALIDATION NOT STARTED
- `SKILL.md` frontmatter v0.3.0 (NOT yet bumped because operator validation hasn't run).
- `references/` directory present.
- `templates/`: 11 templates (the most of any skill — `bidder-config.yaml.j2`, `bidder-test.java.j2`, `bidder.java.j2`, `configuration-properties.java.j2`, `configuration.java.j2`, `ext-imp-pojo.java.j2`, 4 IT fixture JSONs, `it-test.java.j2`).
- **What's missing for v1.0.0**: D2.8 operator validation against 6 MVP pairs (mirror of D3.8). No specific template gaps catalogued yet because no canary has run.

### `prebid-server-java/review/` — DOES NOT EXIST
- ROADMAP line 68: "Java review-skill suite (`prebid-server-java/review/skills/`) — currently absent."
- Verified: `find prebid-server-java/review -type d` returns empty.
- **What's needed** (mirror of Go-side 4-skill split): `pr-triage-java`, `bidder-class-pr-review`, `bidder-config-pr-review`, `bidder-params-java-pr-review`, plus `shared/framework-utilities-java.md`.
- This is the largest single SKILL-tree gap in the project today.

### Diff-spec skills — NOT EXIST
- No `prebid-server-{go,java}/diff-spec/` directory.
- No design doc beyond the one-liner in ROADMAP line 71.

### Write skills — NOT EXIST
- No `prebid-server-{go,java}/write/` directory.
- Heavy forward-references in `cross-skill-integration.md` §3 + §4 (TODO comments for `quirks[]` surfacing, fixture handling, etc.).

### Phase F reflection-loop implementation — NOT EXIST
- No `scripts/replay-port.py` (deferred per `port-skills-design.md` §10).
- No `.github/workflows/reflect-cron.yml` (Phase F weekly trigger).
- No `prebid-server-{go,java}/reflect/` skill directory.
- The canary 8 reflection memo (`docs/runs/d3.8-teal-reflection.md`) — the first hand-authored Phase F output — does not exist yet.

---

## 4. v1.0.0 promotion ledger

### `port-java2go` (current SKILL frontmatter version: **0.5.0**)

**Promotion criteria** (from `prebid-server-go/port-java2go/SKILL.md:8-16` and canary 7 trace):

| # | Criterion | Status | Effort to clear |
|---|-----------|--------|-----------------|
| 1 | Template-macro / multi-token-substitution real bodies (F-new-2, F-new-27) | TODO STUB in `bidder.go.j2:500`. Confirmed in 3 canaries (adverxo, thetradedesk, adkernelAdn). | medium (2–3 operator-days; need `ctx.endpoint_token_set` schema field + 25-line template branch + 8-line ctx wiring + tests). |
| 2 | Per-key batching template branch (F-new-7 EXT-A) | TODO STUB in `bidder.go.j2:381`. Confirmed in 1 canary (adkernelAdn). | small-medium (1–2 operator-days; `ctx.batching_group_key` + `ctx.batching_group_struct` schema; 25-line template addition). |
| 3 | imp-id-correlation template branch (F-new-7 EXT-B) | TODO STUB. Confirmed in 1 canary (adkernelAdn). | small (1 operator-day; `ctx.bid_type_fallback_value` schema; 12-line template addition). |
| 4 | `naming_form_resolution` ctx schema (F-new-34) | Renderer multi-form aware; needs schema generalization. Confirmed in 1 canary. | medium (2–3 operator-days; `ctx.naming_form_resolution: dict` schema; per-aspect form table; bidder-constant-table.yaml `forms` sub-map; 4–6 affected pairs). |
| 5 | ~~Non-MVP validation canary (≤1 retry)~~ | **RETIRED by canary 8 / teal**, per the user's note. Canary 8 itself was the non-MVP validation canary. | n/a. |

**Other open items not in the v1.0.0 list** (lower priority — don't block 1.0):
- F-new-13/16/20/32/33 imp-mutations schema + renderer auto-add (MEDIUM corpus relevance): `ctx.imp_mutations: list[strategy]` schema + renderer wiring. ~50% of corpus benefits. Effort: medium (3–4 operator-days).
- F-new-31 extra_info_kind schema: 2–3 corpus pairs. Effort: small (1 operator-day).
- F-new-15 Site→App synthesis (vungle): MEDIUM. Effort: small (1 operator-day).
- F-new-17 bid post-processing macros (adverxo, thetradedesk): MEDIUM. Effort: small (1 operator-day).
- F-new-18 native ADM unwrap (adverxo): LOW. Effort: tiny (per-bidder hand-fill).

**Total v1.0.0 effort (criteria 1–4)**: ~6–9 operator-days of engineering.

### `port-go2java` (current SKILL frontmatter version: **0.3.0**)

**Promotion criteria** (from `prebid-server-java/port-go2java/SKILL.md:9` — implicit in "Frontmatter bumps to 1.0.0 once each MVP pair clears all 7 gates"):

The execution plan §D2.3 specifies 7 per-pair acceptance criteria. The 6 MVP pairs are kobler, aax, adkernelAdn, adverxo, vungle, thetradedesk (same as D3.8). NONE have been run.

**Specific blockers**:
1. **Local Java clone needed**. Operator must `git clone prebid/prebid-server-java` at the pinned SHA (`a1fe64e123d6` per repo-rules.md) for `mvn` invocations.
2. **No prior canary trace**. Unknown what F-new findings will surface — the Java target may have its own 30+ findings analogous to the Java→Go side.
3. **mvn toolchain availability**. `mvn`, `java 17+`, network access to Maven Central. The CI runner has these but the local operator might not.
4. **Checkstyle strictness**. Per execution plan R9: "Upstream Java has hard-fail checkstyle (LineLength≤120, EmptyLineSeparator, ImportOrder strict 3-group, ban `io.vertx.core.json.Json`, FinalLocalVariable, ≥90% Jacoco coverage expected)." Templates are checkstyle-compliant by construction; D4.3 has the dry-run helper but it has not been exercised against emitted output.

**Estimated effort to v1.0.0**: medium-large (5–10 operator-days, based on D3.8 trajectory of 7 canaries × ~1 day each. Java side may go faster if the Go upstream codebase has cleaner shapes; may go slower if the Java framework asymmetries surface harder findings).

**Type**: operator (canary execution) + engineering (template fixes for findings).

---

## 5. Canary 8 follow-up backlog (F-new-37 through F-new-43)

**ACTUAL** F-new range: **F-new-37 through F-new-43** (7 findings, not 11 as the prompt suggested). All catalogued in `.tmp/teal-recon/teal-java-spec.yaml`.

| ID | Description | Severity | Corpus rel. | Recommended bucket |
|----|-------------|----------|-------------|---------------------|
| F-new-37 | Per-imp `imp.ext.prebid.storedrequest.id` injection (M1; teal `placement` → injected). Mediatype priority `banner > video > audio > native` inversion vs Go-default. | HIGH for teal; LOW for corpus today (1/17 pairs). | LOW | NICE — defer until 2nd bidder exhibits pattern. |
| F-new-38 | Cross-imp first-imp-wins `account` propagation to BOTH `site.publisher.id` AND `app.publisher.id` (M2). Existing site/app-publisher-rewrite ops take a STATIC publisher_id; this is dynamic per-request. | HIGH for teal; LOW corpus today (1/17). | LOW | NICE — defer until 2nd bidder. |
| F-new-39 | Root-of-request `ext.bids = {pbs:1}` FlexibleExtension property addition (M3). Java FlexibleExtension mutator vs Go `map[string]json.RawMessage` round-trip — cross-language asymmetry. | HIGH for teal; LOW corpus today (1/17). | LOW | NICE — defer until 2nd bidder. |
| F-new-40 | Collect-and-continue per-imp error semantics — partial-success preserved across the loop. Bidder.go.j2's `single-batched` body parses for side-effect only; doesn't `continue` per-imp. | HIGH for teal; MEDIUM corpus (estimated 4–6 pairs need this). | MEDIUM | MUST for v1.1.0 (post-1.0 enhancement). Schema: `ctx.per_imp_error_strategy: collect-and-continue \| short-circuit`. |
| F-new-41 | Builder-time URL validation parity (`HttpUtil.validateUrl` ↔ Go `url.ParseRequestURI`). Template doesn't emit Builder-time URL parse. | LOW. | LOW | DEFER — per-bidder operator hand-fill. Document in `references/go-artifact-shapes.md`. |
| F-new-42 | `getBidType` signature: Java takes `String impId`, template takes `*openrtb2.Bid`. Go signature subsumes Java's — no template change needed. | INFO/benign. | n/a | RESOLVED-BY-DOCUMENTATION (no code change). |
| F-new-43 | `tealplus` disabled-by-default alias-graph inversion: Java `aliases.tealplus.enabled: false` map-form ↔ Go `static/bidder-info/tealplus.yaml: { aliasOf: teal, disabled: true }`. ALREADY SUPPORTED by Rule 45 / Rule 33; teal is just confirming the canonical case. | confirmed-applicable. | n/a | RESOLVED — no SKILL change needed. |

**MUST for v1.0.0** (i.e., block port-java2go 1.0): NONE of F-new-37..43. The user retired criterion 5 ("non-MVP validation canary") via canary 8, and 37-43 are pattern-extensions surfaced by the canary; v1.0.0 was already gated on F-new-2/-7-EXT-A/-7-EXT-B/-34. The teal canary work confirms no F-new-37..43 are blockers for the 4 outstanding v1.0.0 gates.

**MUST for v1.1.0 / "first NICE bump after 1.0"**: F-new-40 (collect-and-continue), since 4–6 pairs would exercise it.

**DEFERRED** (not on either ladder): F-new-37/38/39 (M1/M2/M3 — teal-specific until a second bidder shows them). F-new-41 (Builder URL validation — too LOW). F-new-42 (resolved by doc).

---

## 6. Cleanup / hygiene items

### TODO / FIXME markers found in source

**Templates** (`bidder.go.j2` and `bidder.java.j2`):
- `prebid-server-go/port-java2go/templates/bidder.go.j2:262` — TODO: operator fills extra-info struct fields (Rule 35 inverse).
- `prebid-server-go/port-java2go/templates/bidder.go.j2:381` — TODO: batching_kind={{ ctx.batching_kind }} not yet implemented (catchall for unsupported batching kinds).
- `prebid-server-go/port-java2go/templates/bidder.go.j2:500` — TODO: endpoint_resolution_kind not yet templated (the F-new-2 stub).
- `prebid-server-go/port-java2go/templates/bidder.go.j2:613` — TODO: by-bid-ext-typed-field with non-canonical field path (F-new-25).
- `prebid-server-go/port-java2go/templates/bidder.go.j2:635` — TODO: by-request-uri-suffix.
- `prebid-server-go/port-java2go/templates/bidder.go.j2:663` — TODO: bid_type_resolution catchall.
- `prebid-server-go/port-java2go/templates/bidder.go.j2:685` — TODO: hardcoded supportedCurrency="USD".
- `prebid-server-java/port-go2java/templates/bidder-test.java.j2:145` — TODO: operator fills test body.
- `prebid-server-java/port-go2java/templates/bidder.java.j2:166` — TODO: batching_kind catchall.
- `prebid-server-java/port-go2java/templates/bidder.java.j2:232` — TODO: endpoint_resolution catchall.
- `prebid-server-java/port-go2java/templates/bidder.java.j2:290` — TODO: bid_type_resolution catchall.

These TODOs are **intentional by design** (per `cross-skill-integration.md` — quirks and unsupported patterns surface as TODOs, not silent failures). They should NOT be removed; they should be PROMOTED into real template branches as the v1.0.0 promotion blockers (Section 4) work proceeds.

**Empty-adapter templates** (`templates/empty-adapter-spec-{go,java}.yaml`): contain TODO placeholders by design (template scaffolding for new bidders). No cleanup needed.

**Scripts**: none. `port_engine.py`, `r5_check.py`, the lint scripts, and the harness scripts are TODO-clean.

**Documentation**: `docs/decisions/007-novel-pattern-schema-additions.md:9` flags an item DEFERRED to Wave 11c C4 (cross_language.port_lineage canonical encoding) — this is a known deferral from prior waves; not a new cleanup. Decision: confirm whether to land Wave 11c at all (given Phase D/E momentum, may stay deferred indefinitely).

### Stale references

None found. The ROADMAP, CHANGELOG, SKILL frontmatters, and execution-plan all cross-reference the same set of documents and ADRs.

### Documentation gaps

1. **`docs/runs/d3.8-teal-canary-*.md`** — canary 8 (teal) trace document does not exist yet. The work happened on `feat/teal-port` and lives in `.tmp/teal-recon/`. This is the most visible doc gap. (Effort: small, 1 operator-day.)
2. **`docs/runs/d3.8-teal-reflection.md`** — Phase F output for canary 8. Does not exist. The canary 8 plan flagged this as the Phase F deliverable. (Effort: small, 1–2 operator-days.)
3. **CHANGELOG entry for canary 8** — not yet authored.
4. **ROADMAP `Phase D — Operator validation status`** — does not yet mention canary 8 / teal.
5. **`d3.8-template-coverage-audit.md`** — current pre-D3.8; does not include the canary 1–7 outcomes nor the canary 8 confirmation. Could benefit from a "post-D3.8 update" section.

### Test scaffolding that should be removed

`scripts/tests/`: 488 tests, all current. No skipped/deferred tests visible. The Kobler IT 4-file fixture set was committed in canary v2 to make `test_kobler_shape_passthrough` actually run (was previously silent-skipping). No further test-scaffolding hygiene required.

### "Deferred to follow-up" lingering items

1. ADR-007 F1/F3/F4/F5 `$defs` `$ref`-wiring — schema-versioning sub-phase 2.8 (per ROADMAP "Phase numbering map" line 93). NOT STARTED.
2. Wave 11c C4 `cross_language.port_lineage` canonical encoding — see ADR-007 line 9.
3. The 4.X methodology numbering scheme has 4.1 through 4.7 done. No 4.8 declared. Ambient state.
4. `bidder-constant-table.yaml` "forms sub-map" recommended in canary 7 (F-new-34 follow-up) — hasn't landed.

---

## 7. Recommended sequencing to "multi-adapter both-directions sprint"

The user's stated end-goal is "testing with more adapters from both sides and porting/reviewing." Below is the operator-day-bucketed dependency-aware sequence. Each item is engineering / operator / decision tagged.

### Phase F1 — Land canary 8 (teal) the right way (3–4 operator-days)

| # | Item | Type | Effort | Prereqs |
|---|------|------|--------|---------|
| 1 | Author `docs/runs/d3.8-teal-canary-2026-05-05T*.md` permanent trace from `.tmp/teal-recon/` materials | operator | 1 day | none |
| 2 | Author `docs/runs/d3.8-teal-reflection.md` (the FIRST Phase F deliverable) — triage F-new-37..43 per the reflection-loop matrix; map each to fix location (taxonomy / schema / rules / SKILL prose / ADR) | operator | 1–2 days | item 1 |
| 3 | Promote `.tmp/teal-recon/teal-java-spec.yaml` → `prebid-server-java/read/test-fixtures/teal.golden.spec.yaml` + author `cross-language-pairs/teal.dual-spec-assertions.yaml` | operator | 0.5 day | item 1 |
| 4 | CHANGELOG entry for canary 8; ROADMAP § "Phase D — Operator validation status" amendment to mention teal | operator | 0.5 day | items 1, 2, 3 |
| 5 | Decide whether to merge `feat/teal-port` to upstream prebid/prebid-server (separate from this skills repo) | decision | n/a | item 1 |

**Recommended subagent dispatch**: items 1+2 are perfect for an opus subagent (heavy synthesis from existing materials). Items 3+4 are mechanical, do inline. Item 5 is a user decision.

### Phase F2 — Close port-java2go 1.0.0 promotion blockers (6–9 engineering-days)

| # | Item | Type | Effort | Prereqs |
|---|------|------|--------|---------|
| 6 | F-new-2: template-macro / multi-token-substitution real body (`ctx.endpoint_token_set` schema + 25-line `bidder.go.j2` branch + 8-line ctx wiring + tests) | engineering | 2–3 days | none |
| 7 | F-new-7-EXT-A: per-key batching branch (`ctx.batching_group_key`, `ctx.batching_group_struct`; 25-line template addition) | engineering | 1–2 days | none (independent of #6) |
| 8 | F-new-7-EXT-B: imp-id-correlation branch (`ctx.bid_type_fallback_value`; 12-line template addition) | engineering | 1 day | none |
| 9 | F-new-34: `naming_form_resolution` ctx schema + `bidder-constant-table.yaml` `forms` sub-map + renderer wiring | engineering | 2–3 days | none |
| 10 | Bump `port-java2go/SKILL.md` 0.5.0 → 1.0.0 frontmatter once #6+#7+#8+#9 land + a re-run of canaries 5/6/7 (auto-cleared) | engineering+operator | 0.5 day | items 6–9 |

**Recommended subagent dispatch**: each of items 6–9 is a perfect opus subagent task (template extension + tests). Run #6 and #7 in parallel; sequence #8 and #9 after.

### Phase F3 — D2.8 (port-go2java) operator validation (5–8 operator-days)

| # | Item | Type | Effort | Prereqs |
|---|------|------|--------|---------|
| 11 | Local clone `prebid/prebid-server-java` at SHA `a1fe64e123d6`. Verify mvn toolchain. | operator | 0.5 day | none |
| 12 | Canary 1 (kobler Go → Java) — run 7-step pipeline, score against execution plan §D2.3 acceptance gates | operator | 1 day | item 11 |
| 13 | Canaries 2–6 (aax, adkernelAdn, adverxo, vungle, thetradedesk) — same shape | operator | 4–5 days | items 11+12 (sequenced; each canary informs next) |
| 14 | Author 6 trace docs `docs/runs/d2.8-{bidder}-canary-*.md` | operator | 1 day | items 12+13 |
| 15 | Bump `port-go2java/SKILL.md` 0.3.0 → 0.5.0 (or higher, depending on findings cleanliness) | engineering | 0.5 day | item 14 |
| 16 | Iterate template fixes for D2.8 findings (analogous to D3.8 templates work). Effort UNKNOWN until canaries run; budget 3–6 days. | engineering | 3–6 days | item 14 |

**Recommended subagent dispatch**: items 12+13 — opus subagent per canary (heavy invocation). Item 16 — opus subagent per template extension.

### Phase F4 — Java review-skill suite (10–15 engineering-days)

| # | Item | Type | Effort | Prereqs |
|---|------|------|--------|---------|
| 17 | Design doc `docs/methodology/java-review-skill-design.md` — what's the Java analog of the 4 Go review skills? | design | 1–2 days | none |
| 18 | Author `prebid-server-java/review/skills/pr-triage-java/SKILL.md` (mirror Go pr-triage with Java-specific concerns: pom.xml diff handling, Spring config, checkstyle, etc.) | engineering | 3–4 days | item 17 |
| 19 | Author `bidder-class-pr-review/SKILL.md`, `bidder-config-pr-review/SKILL.md`, `bidder-params-java-pr-review/SKILL.md` | engineering | 4–6 days (3 skills) | item 18 |
| 20 | Author `prebid-server-java/review/skills/shared/framework-utilities-java.md` | engineering | 1 day | items 18+19 |
| 21 | Wire the Java side's `prior_source_spec` slot symmetric with the Go side | engineering | 1–2 days | items 18+19 |

**Recommended subagent dispatch**: item 17 — opus subagent for design synthesis. Items 18–21 — separate opus subagents per skill (proven pattern from Go-side review skills).

### Phase F5 — Wire downstream `--- PRIOR SOURCE SPEC COMPARISON ---` consumption — **LANDED 2026-05-15**

| # | Item | Type | Effort | Prereqs | Status |
|---|------|------|--------|---------|--------|
| 22 | Add "Step 1g: cross-language port-fidelity check" prose to `adapter-code-pr-review/SKILL.md` | engineering | 1 day | none | **LANDED in F5** — empirically-grounded markdown table (7 rows: F-new-7 EXT-A/B, F3 Site/App synthesis, F4 macros, F-new-14 status, F-new-45 nil-map panic, F2 language-stamped headers) |
| 23 | Same for `bidder-info-pr-review/SKILL.md` | engineering | 1 day | none | **LANDED in F5** — bulleted prose (~10 items: endpoint macros, R5-strict shared fields, F-new-43/44, alias asymmetries) |
| 24 | Same for `bidder-params-pr-review/SKILL.md` | engineering | 1 day | none | **LANDED in F5** — 4 numbered cases with emit blocks (Rule 38 byte-fidelity, aax urgent elevation, @JsonAlias asymmetry, present-empty trichotomy) |
| 25 | Mirror items 22–24 on the Java review side (post item 21) | engineering | 2 days | items 18+19+21 | **LANDED in F4 PR #10** (2026-05-15) |

**Beyond items 22-25, F5 also landed**:
- `shared/framework-utilities.md` §Cross-Language Port-Fidelity Hook Contract subsection — single source of truth for 4-tier severity matrix + dedup phrase + Step 5 emission template (closes F4's DRY violation)
- Severity matrix extended 3-tier → 4-tier (added `urgent` for dual-spec elevation, promoted from `bidder-params-java-pr-review`)
- Go pr-triage cross-language block promoted to literal manifest template (symmetric with Java pr-triage-java's lines 608-618)
- `cross-skill-integration.md §5.5` — formalizes the cross-language read↔review contract symmetrically with §5 (same-language hook)
- 4 Java-side forward-references unwound (`pr-triage-java:711`, `bidder-class:129`, `bidder-config:155`, `java-review-skill-design.md:163-167`)
- references/*-index.md cross-language port-fidelity callouts in all 3 Go review skills
- Frontmatter bumps 1.0.0 → 1.1.0 on all 3 Go downstream review skills

### Phase F6 — Reflection loop implementation (20–40 engineering-days; can be parallel to F2–F5)

| # | Item | Type | Effort | Prereqs |
|---|------|------|--------|---------|
| 26 | `scripts/replay-port.py` — cross-version replay of an old port report against current rules | engineering | 5–8 days | port-report.json archive shape |
| 27 | `scripts/reflect-loop.py` — triage matrix automation | engineering | 8–12 days | item 26 |
| 28 | `.github/workflows/reflect-cron.yml` — weekly periodic sweep | engineering | 1–2 days | item 27 |
| 29 | Auto-PR-creation against this repo from reflect output | engineering | 3–5 days | item 27 |
| 30 | `prebid-server-{go,java}/reflect/` skill directories with SKILL.md walking the matrix prose-by-prose | engineering | 5–10 days | items 27+28 |

**Recommended subagent dispatch**: items 26+27 — opus subagent (heavy script work; design synthesis from `reflection-loop.md` matrix). Items 28+29 — operator-driven (CI tooling). Item 30 — opus subagent per skill.

### Phase F7 — Multi-adapter cadence (the user's stated goal)

Once F1–F4 are at "adequately landed" (port-java2go at 1.0.0, port-go2java at ≥0.5.0, Java review skills exist), the user's "multi-adapter both-directions sprint" runs as:

```
For bidder in [next-priority-set]:
  1. Read Go side (read-adapter-orchestrator) → spec.yaml
  2. Read Java side (read-bidder-orchestrator) → spec.yaml
  3. Port Java → Go (port-java2go) → port-report.json + Go artifacts
  4. Port Go → Java (port-go2java) → port-report.json + Java artifacts
  5. Review the emitted Go (4 Go review skills)
  6. Review the emitted Java (4 Java review skills, post-F4)
  7. Reflect (Phase F) on both port reports — propose SKILL/rule/taxonomy updates
```

Each bidder cycle: 1–2 operator-days assuming SKILLs are mature. With 5+ bidders queued, this becomes a 1–2 week sprint.

**Optional helpers** for the multi-adapter cadence:
- `write/` skills (Phase E ROADMAP item) — generate from scratch rather than port. Less critical than the porting symmetry; defer.
- `diff-spec` skills (Phase E ROADMAP item) — useful for tracking upstream drift across bidders. Defer.
- Backfill remaining Rule 46 + Rule 43 fixture pairs (per coverage-report). Defer until the SKILL maturity warrants it.

---

## 8. Risks and dependencies

### Hard blockers (X must complete before Y can start)

- F1 (canary 8 trace + reflection memo) is **independent** — can run immediately.
- F2 (port-java2go v1.0.0 blockers) is **independent** of F1; can run in parallel.
- F3 (D2.8 operator validation) **requires local Java clone** — operator-side prereq.
- F4 (Java review-skill suite) **requires F3 to inform Java-specific review patterns** (e.g., pom.xml drift handling, mvn output parsing). Could start the design doc (item 17) before F3 completes.
- F5 (downstream consumption hooks) **independent** of F2/F3/F4 — can run anytime after F1.
- F6 (reflection loop) **requires F1's manual reflection memo to validate the matrix** before automating. Can start `replay-port.py` design earlier.
- F7 (multi-adapter sprint) **requires** F2 (port-java2go 1.0.0) at minimum; ideally F3 (port-go2java 0.5.0) too. F4 (Java review) is desirable but not strictly blocking.

### Parallelism opportunities

- Items 6, 7, 8 in F2 (template extensions for the 4 v1.0.0 blockers) are independent — 3 parallel subagent tasks.
- F2 and F3 can run in parallel (port-java2go template work doesn't conflict with port-go2java canary execution).
- F4 design (item 17) and F2 execution can run in parallel.
- F6 (`replay-port.py`) can be designed in parallel with F4–F5 implementation work.

### Unknown unknowns / decisions outstanding

1. **D2.8 finding count**. Likely surfaces 20–30 F-new-NN findings analogous to D3.8's 33 findings. Effort estimate is fuzzy until canary 1 runs.
2. **Java review skill design**. Should it mirror the 4-skill Go split or collapse? E.g., would `bidder-config-pr-review` and `bidder-class-pr-review` benefit from being unified given Java's tighter coupling? Decision needed at item 17.
3. **`write/` skill scope**. Out of all the proposed Phase E skills, this is the largest unknown. Does it consume *only* the spec, or is it a "spec + bidder-team interview" workflow? Decision: defer pending `port-{go,java}` maturity feedback.
4. **`diff-spec` skill ROI**. Useful for tracking upstream drift, but the existing `sync-from-upstream.py` already does that mechanically. Decision: defer; possibly merge into a "sync-and-diff" enhancement to existing tooling.
5. **Reflection loop full-automation timeline**. Hand-authored memos (per F1 item 2) have proven sufficient for canary 8. Whether to build the auto-PR pipeline (F6) versus stay manual is an operator workflow decision. Recommend: stay manual for the first 5 reflection memos, then automate.
6. **Phase 4.X / 2.X numbering schemes**. The 2.8 schema-evolution sub-phase ($defs $ref-wiring) is "future" per the numbering map. Decision: schedule into a future Phase D5 or leave parked? No urgency.
7. **Connatix fixture (D4.4)**. Master sample for `warn-target-strengthens-source` R5 state. Not authored. Decision: backlog item (small effort) — recommend landing it during the multi-adapter sprint when it naturally surfaces.

### Non-technical risks

- **Operator bandwidth**. The full sequence above is ~50–80 operator-days even with subagent parallelism. The user should plan in 2-week sprints with specific phase targets.
- **Upstream drift between snapshots**. `repo-rules.md` SHAs were re-verified 2026-05-04; D0.2 sync needs re-running before D2.8 begins. PR #4126 (URL validation) was tracked as in-flight; recheck its merge status.
- **Cache miss between operator sessions**. Phase F's reflection memo authoring benefits from warm context (just-completed canary). Hand-authoring memos days/weeks after the canary doubles the time. Recommend: each canary completes with the trace + reflection memo authored in the same session.

---

## Summary table — overall budget

| Bucket | Engineering-days | Operator-days | Decision items |
|--------|------------------|----------------|-----------------|
| F1 (canary 8 closure) | 0–1 | 3–4 | 1 (PR-merge decision) |
| F2 (port-java2go 1.0.0) | 6–9 | 0.5 | 0 |
| F3 (D2.8 validation) | 3–6 | 5.5–8.5 | 0 |
| F4 (Java review suite) | 9–13 | 1–2 | 1 (skill split) |
| F5 (cross-language hooks) | 3–5 | 0 | 0 |
| F6 (reflection auto) | 22–37 | 1–2 | 1 (full-auto vs manual) |
| F7 (multi-adapter cadence per-bidder) | 0 | 1–2 / bidder | 1 (which bidders next) |
| **Total to "operator-validated bidirectional + reviewed"** | ~21–34 | ~10–15 | 4 |
| **Total to "fully automated reflection loop"** | ~43–71 | ~11–17 | 5 |
| **Steady-state per-bidder (post all of F1–F6)** | 0 | 1–2 | 0 |

The user's stated end-goal — "more adapters from both sides and porting/reviewing" — is achievable after **F1+F2+F3 (≈15–25 operator-days total)** with the existing review skills (Go side only). Adding F4 (Java review) doubles the review surface but adds another ~10 days. F5 is small and high-value (3–5 days). F6 is large and low-urgency (defer).

**Recommended next 2-week sprint**: F1 (close canary 8) → F2 in parallel with F3 setup → start F2's first template extension (item 6) and F3's canary 1 (item 12) as parallel opus subagent dispatches. End of sprint 1: canary 8 documented; port-java2go at v0.6.0 with F-new-2 closed; D2.8 canary 1 (kobler) traced.
