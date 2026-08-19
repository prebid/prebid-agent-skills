# Execution Plan: Phase D — Port Skills (`port-go2java` + `port-java2go`)

**Status**: Draft (planning complete; awaits approval to begin execution)
**Date**: 2026-05-04
**Scope**: D0–D4 — pre-D refactor → scaffolding → `port-go2java` MVP → `port-java2go` MVP → CI integration. Both port skills ship production-grade. Per `ROADMAP.md` Phase D and the design at `docs/methodology/port-skills-design.md`.

**In scope**: bid adapters only (`adapters/{bidder}/` Go; `src/main/java/org/prebid/server/bidder/{bidder}/` Java) plus the bidder's static config, params, ext POJO, and test fixtures. New-adapter ports are MVP; alias-only ports and empire-parent ports are MVP (single-bidder invocation handles all three shapes — primary, alias, empire-parent — by inspecting the source spec's `meta.is_alias` / `aliases[]`).

**Out of scope**: analytics modules (`analytics/`), RTD / general modules (`modules/`), stored-request handlers, cookie-sync infrastructure — these are less prevalent in cross-language porting workflows and have no read-skill / taxonomy / rule-corpus support today. Delta-ports (`Port {Bidder}: <update>` updating an already-ported adapter) are also deferred — the MVP targets new-adapter ports only; delta-port support requires a source-vs-existing-destination diff layer that is reasonably a future phase.

This plan supersedes the conversation-prep punch list. Two parallel research passes (rules, pair-fixtures, R5-refactor contract, emission-readiness; then upstream CI standards, real-world port-PR workflow, rule machine-readability, orchestrator/review-side reality) surfaced 11 course-corrections incorporated below. The original execution-plan at `docs/execution-plan.md` (Phases 0–5 read-skill hardening) is complete and stands as historical record.

## Six guiding principles

1. **Both directions ship production-grade.** The user-stated workflow is bidirectional: translate the same adapter Go→Java and Java→Go. The empirical Go→Java dominance in merged PRs (12+ vs 0 in 18 months, with prebid.org stating "we port Go-to-Java, but not the other way around") reflects *current tooling limits*, NOT user need or maintainer disinterest. Phase D removes that asymmetry as a first-class deliverable. The research still informs *sequencing* — D2 ships first because Go→Java has empirical CI-gate evidence to validate against; D3 ships second using D2's port-engine + round-trip determinism as its verification path.
2. **Prose-driven SKILL with mechanical helpers, not pure-Python walker.** 95% of the 46 rules are prose; only Rules 38/44/45/46 are mechanically structured. Architecture: SKILL.md walks rules; `scripts/lib/port_engine.py` provides 9 mechanical helpers.
3. **Re-author, don't byte-copy.** Test fixtures use different harness shapes (Go flat exemplary; Java 4-file IT split). bidder-params JSON is semantically-equal-not-byte-equal in 4/5 real ports. Rule 36 reframes from "fixture inventory parity" to "semantic-coverage parity."
4. **Bind to upstream CI gates from day one.** `gofmt -s` (Go), checkstyle (Java), import-order, alphabetical registry insertion, first-6-letter prefix uniqueness, mandatory PR template, `do not port` label. Output that doesn't pass these wastes maintainer time.
5. **Pin to the porting guide.** `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` (PR #3768) is the maintainer-authored spec. Port skills version-pin to its SHA, just as read skills pin to upstream commit SHAs.
6. **Quality bar — indistinguishable from hand-authored.** Port output must (a) pass upstream CI gates without operator hand-edits (gofmt, checkstyle, semgrep, registration alphabetization, prefix uniqueness), (b) reach upstream test-coverage expectations (Go ≥80% real-world median, Java ≥90% PR-template requirement), (c) be idiomatic to the target language (no Java-isms in Go output; no Go-isms in Java output), (d) include a companion `prebid/prebid.github.io` docs-PR draft (maintainer-mandatory for Java-target ports), (e) rebase to upstream `master` immediately before PR submission. Anything less wastes maintainer review time and fails the user's stated quality goal.

## Phases at a glance

| Phase | Effort | Net LOC | Outcome |
|---|---|---|---|
| D0 — Pre-D refactor + sync | 1.5 days | +250 / -180 | `scripts/lib/r5_check.py` extracted; `sync-from-upstream` run; `repo-rules.md` refreshed |
| D1 — Scaffold + emission refs + port-engine | 6 days | +2,200 | Both skill dirs (`port-go2java` + `port-java2go`) + `port_engine.py` + bidirectional emission references + `cross-skill-integration.md` split + `port-report.schema.json` v0.2.0 |
| D2 — `port-go2java` MVP | 7 days | +2,400 | 7-step pipeline; 10 mechanical-ready rules; 6 MVP pairs validated; auto-PR with porting-guide-compliant title/body/label |
| D3 — `port-java2go` MVP | 6 days | +2,000 | Mirror pipeline (Go target); same 10 rules inverse; same 6 pairs validated reversed; auto-PR with Go-side conventions; `gofmt` + `go vet` smoke |
| D4 — CI + fixture gaps | 4 days | +600 / -100 | `round-trip-ci.py` port-side R4 (both directions); coverage rule-table; checkstyle dry-run; ADR-007 F1 fixture (`beachfront`) |

**Total**: ~24.5 working days. Net delta: ~+7,100 LOC concentrated in skill dirs + port-engine + emission references.

## Pre-execution audit corrections applied (2026-05-04)

| # | Finding | Correction |
|---|---|---|
| R1 | `port-go2java` has 12+ merged PRs in 18 months; `port-java2go` has zero. The user-stated bidirectional goal is hard scope. | Both directions ship production-grade. The asymmetric merged-PR count reflects missing tooling, not user need; Phase D removes the asymmetry. Sequencing: D2 first (validates against empirical CI evidence); D3 second (uses D2's port-engine + round-trip determinism as the verification path). ROADMAP.md updated by D1 to drop any "experimental" framing. |
| R2 | The 46 rules are mostly prose; "walk rule-by-rule" is partially aspirational. Only Rules 38/44/45/46 carry mechanical structure. | D2 architecture is SKILL.md prose-driven with `port_engine.py` mechanical helpers, not pure-Python walker. |
| R3 | Test fixtures are NEVER byte-copied between languages; harness shapes differ structurally. | D2 emit re-authors fixtures using semantic-coverage parity. Rule 36 docs reframed. |
| R4 | bidder-params JSON is semantically-equal-not-byte-equal in 4/5 real ports (Adverxo, Connatix, Ogury, Kobler-whitespace). Rule 38 byte-fidelity is aspirational. | `port-report.schema.json` gains `r5_check.state: warn-target-strengthens-source` for the Connatix-style "Java adds constraint absent in Go" case. |
| R5 | Reviewers quote raw Go source in Java review threads; PR-description source-link provenance is mandatory. | Schema gains `source_pr_url`, `source_pr_merged_commit_sha`, `source_discussion_anchors[]`, `re_authored_paragraphs[]`, `recommended_pr_title`, `target_pr_label_recommendations[]`. Bumps to 0.2.0. |
| R6 | Official porting guide at `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` (PR #3768) mandates `Port <Bidder>: New Adapter` title and `do not port` label. | Port skill version-pins to the guide's SHA; auto-emits compliant title/label. |
| R7 | "Orchestrator" CLI is fully aspirational; no code exists. `.tmp/full-loop/{run-id}/` and `${FULL_LOOP_RUN_ID}` are conventions only. | D1 establishes the convention: read-orchestrator gains `--output=`; port skill writes destination spec + port-report at canonical paths. Phase D does NOT build a "full-loop" orchestrator CLI; manual sequencing per `end-to-end-flow.md` §1.2 is documented. |
| R8 | Upstream Go has zero `.golangci.yml`; lone style gate is `gofmt -s`. CI also runs `go vet`, semgrep adapter rules, 30% coverage warning. `TestBidderUniquenessGatekeeping` enforces first-6-letter uniqueness. Alphabetical insert into `bidders.go`/`adapter_builders.go`. | D1's port-engine includes `gofmt -s -w` post-processor + alphabetical-insert + prefix-uniqueness pre-check. |
| R9 | Upstream Java has hard-fail checkstyle (LineLength≤120, EmptyLineSeparator, ImportOrder strict 3-group, ban `io.vertx.core.json.Json`, FinalLocalVariable) — `<goal>check</goal>` is bound at `extra/pom.xml:302`. Coverage is NOT in that set: upstream asks contributors to self-certify ≥90% on changed code (`docs/developers/contributing.md:17`; PR-template checkbox) but declares Jacoco `prepare-agent` + `report` only (`extra/pom.xml:325-344`), so it cannot fail CI. Mandatory PR template. | D1's emission templates are checkstyle-compliant by construction; D4 adds local `mvn checkstyle:check` dry-run. |
| R10 | Upstream Java PR #4126 (URL validation) is in-flight; could land between port-emit and PR-open. | D0 sync-from-upstream + D2 pre-submit rebase to current `master`. |
| R11 | Connatix Java port ADDED `minimum:0, maximum:1` constraints absent in Go (target strengthens source). aax R5-fail goes the other way. | Schema `r5_check.state` distinguishes `warn-target-strengthens-source` and `fail-source-omits-target-constraint`; D2 handler routes accordingly. |

## Phase D0 — Pre-D refactor + sync (1.5 days, 2 commits)

### D0.1 — Extract `scripts/lib/r5_check.py`

Per design §7. Lift `R5_STRICT_KEYS`, `R5_FORM_DIVERGENT_KEYS`, `R5_ADVISORY_DIVERGENT_KEYS`, `r5_check()`, helpers (`deep_eq`, `_list_set_eq`, `_maintainer_eq`, `normalize_endpoint_macros`) from `scripts/round-trip-ci.py:730-1041` to `scripts/lib/r5_check.py`. Public API:

- `compare_pair(go_spec, java_spec, assertions=None) -> R5Result`
- `aggregate_state(diagnostics, pair_present) -> (state, byte_equal[], warn[], fail[])` — net-new logic; the four schema states aren't computed by the harness today.

Duck-typed `SpecView` so existing `Spec` is untouched; `R5Diagnostic` is comparator-neutral so callers wrap to `Finding` (harness) or schema dict (port skill). Round-trip-ci.py shrinks ~180 lines net. Tests split: `scripts/tests/test_r5_check.py` (new, lib-level) + harness-level smoke at `test_round_trip_ci.py`. Module-level re-exports keep existing test imports intact.

### D0.2 — sync-from-upstream + repo-rules refresh

`docs/methodology/repo-rules.md` snapshot is 7-12 days stale. Run `python3 scripts/sync-from-upstream.py`; refresh SHAs. Verify `prebid/prebid-server-java` PR #4126 (URL validation) status — its changes could break port-emitted endpoint formats.

**End-state**: lib refactor complete with passing tests; round-trip-ci.py is a thin shim; repo-rules.md SHAs match upstream HEAD on D1 start day.

## Phase D1 — Scaffold + emission references + port-engine (6 days, 7-9 commits)

### D1.1 — Skill scaffolds (both directions)

Create `prebid-server-java/port-go2java/` AND `prebid-server-go/port-java2go/`, each with `SKILL.md` skeleton (frontmatter v0.1.0; description names the source-vs-artifact-language inversion explicitly), `references/`, and `templates/` (per-skill, NOT shared `/templates/`). SKILL bodies mirror design-doc §3 7-step pipeline with TODO placeholders; D2 fills `port-go2java` and D3 fills `port-java2go`. The skill dirs share no code at this stage — only the convention.

### D1.2 — `scripts/lib/port_engine.py` mechanical helpers

Nine helpers, each with tests at `scripts/tests/test_port_engine.py`:

- `byte_copy(source_path, dest_path)` — Rule 38 verbatim copy + SHA verify
- `normalize_bidder_name(go_name) -> java_yaml_name` — Rule 46 mechanical formula + allow-list
- `alias_graph_invert(parent_spec, alias_specs) -> per_child_yamls` — Rule 33
- `iab_table_translate(direction, source_spec) -> dest_artifact` — Rule 42 (Go data table ↔ Java YAML inline)
- `r5_check_at_port_time(source_spec, dest_spec) -> R5Result` — calls `lib/r5_check.py`
- `port_report_emit(report_dict, path)` — schema-validated write
- `alphabetical_insert(file_path, marker_pattern, insert_line, language)` — `bidders.go`/`adapter_builders.go` (case-insensitive lower-first)
- `prefix_uniqueness_check(target_lang, bidder_name) -> ok | colliding_existing` — pre-emit guard against `TestBidderUniquenessGatekeeping`
- `gofmt_post_process(file_paths)` — bash shell-out to `gofmt -s -w` (Go-target only)

### D1.3 — Emission reference docs (bidirectional)

The 8 emission gaps surfaced in research, plus their Go-target parallels:

**Java target (consumed by `port-go2java`)**:

1. **License headers + Java package decls** at `prebid-server-java/port-go2java/references/java-artifact-shapes.md`.
2. **`framework-utilities-java.md`** parallel to existing Go-side: `BidderUtil.defaultRequest`, `BidderDeps`, `BidderDepsAssembler`, `JacksonMapper`, `CurrencyConversionService`, `HttpUtil.headers()`. At `prebid-server-java/read/skills/shared/framework-utilities-java.md` (sibling read-side; consumed port-side).
3. **`test-application.properties`** 2-line append shape — in `java-artifact-shapes.md`.
4. **Checkstyle ImportOrder + EmptyLineSeparator + ban-list** rules — in `java-artifact-shapes.md`.
5. **Java PR-template auto-population mapping** — populates `[x]` checkboxes against the source spec's behavioral fields, mandatory `do not port` label, `Port {Bidder}: New Adapter` title. At `port-go2java/references/pr-template-mapping.md`.

**Go target (consumed by `port-java2go`)**:

6. **Go file shapes** (canonical Builder/MakeRequests/MakeBids skeletons; minimal-header convention; per-bidder package layout) at `prebid-server-go/port-java2go/references/go-artifact-shapes.md`. Distilled from existing read-side `read-adapter-code/references/{file-role-heuristics,adapter-code-patterns}.md` plus inversion-specific guidance.
7. **Inverse porting guide** at `prebid-server-go/port-java2go/references/porting-guide.md` — analogue of upstream Java's `bid-adapter-porting-guide.md`. Authored internally since upstream Go has no equivalent guide; distilled from Java→Go research findings + observed real-world Go-side new-adapter PRs. Captures: "treat as re-implementation," lossy-direction asymmetries (Rule 35 typed-config-subclass demotion), test-fixture re-authoring contract, prohibited patterns. Offered upstream for adoption if maintainers find it useful.
8. **Go PR-shape convention** — Go has no upstream PR template (verified 404). At `port-java2go/references/pr-shape.md`: title `New Adapter: {Bidder}` (capitalized A, observed 100% of merged PRs), body distilled from real PRs, no mandatory label.

**Bidirectional (consumed by both)**:

9. **`cross-skill-integration.md` §2 split** into §2-Go-target + §2-Java-target sub-sections (currently mixed and Go-biased).
10. **`bidders.go` constant lookup table** for the 84/271 non-mechanical brand-acronym names. Sourced from upstream HEAD via `gh api`. At `prebid-server-go/read/skills/shared/bidder-constant-table.yaml` (machine-readable map). Used by both directions: `port-go2java` reads it to know the Go-side constant when generating cross-language artifacts; `port-java2go` writes it (alphabetical-insert) when emitting a new Go bidder.
11. **Sortable insertion-position rules** across `bidders.go`, `adapter_builders.go`, alias YAML maps, `test-application.properties`. Per-skill `references/registration-rules.md`; the Go-side rules are case-insensitive lower-first (verified against real PRs).

### D1.4 — `port-report.schema.json` v0.2.0

Additive fields (MINOR per `schema-versioning.md`):

- `source_pr_url`, `source_pr_merged_commit_sha` (40-hex)
- `source_discussion_anchors[]`, `re_authored_paragraphs[]`
- `recommended_pr_title`, `target_pr_label_recommendations[]` (default `["do not port"]`)
- `upstream_bugs_to_file[]` — Connatix-style "found a Go bug while porting" cases for Phase F to triage
- `companion_docs_pr_draft: { target_repo, file_path, body_markdown }` — the draft adapter-docs page for the maintainer-mandatory `prebid/prebid.github.io` companion PR
- `pre_submit_rebase: { upstream_repo, base_sha_at_emit, base_sha_at_submit, conflicts_detected: bool, conflicts_summary }` — captures the rebase outcome so Phase F can correlate post-merge surprises with framework drift
- `r5_check.state` enum extended with `warn-target-strengthens-source` and `fail-source-omits-target-constraint`

CHANGELOG entry: `[port_report_version 0.2.0]`. All 0.1.0 reports remain valid.

### D1.5 — Read-orchestrator `--output=` flag

`prebid-server-go/read/skills/read-adapter-orchestrator/SKILL.md` and `prebid-server-java/read/skills/read-bidder-orchestrator/SKILL.md` gain `--output=<path>` semantics targeting `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml`. Frontmatter MINOR bump (1.0.0 → 1.1.0; additive optional arg).

### D1.6 — CONTRIBUTING.md

Add "Adding a port skill / port fixture" section, mirroring the existing "Adding a new fixture" / "Adding a port-translation rule" sections. Document the port-engine helper-authoring contract.

**End-state**: skill scaffold exists with empty pipeline; `port_engine.py` provides 9 helpers with passing tests; emission references close the 8 gaps; `port-report.schema.json` v0.2.0 is the contract.

## Phase D2 — `port-go2java` MVP (7 days, 10-15 commits)

### D2.1 — Pipeline Steps 1-4 (spec handling)

Walk the 7-step pipeline per design §3. Steps 1-4 load + validate source spec, discover the bidder family, walk rules, author destination spec.

The 10 mechanical-ready rules (priority order):

1. **Rule 38** — bidder-params byte-fidelity (`byte_copy` + SHA verify)
2. **Rule 46** — naming-convention normalization (`normalize_bidder_name`)
3. **Rule 33** — alias-graph invert (`alias_graph_invert`)
4. **Rule 44** — alias-empire flavor coherence
5. **Rule 36** — fixture-inventory parity → semantic-coverage parity (re-author Java IT 4-file split from Go's flat fixtures; document unreachable-error-paths exclusion per porting guide)
6. **Rule 42** — IAB-cat storage translation (`iab_table_translate`)
7. **Rule 35** — config-properties subclass scaffolding (Jinja template at `templates/configuration-properties.java.j2`)
8. **Rule 39** — derived-view (no-op on porter)
9. **Rule 19** — standard headers (`HttpUtil.headers()` collapse)
10. **Rule 30** — canonical Go status helpers ↔ Java framework default

### D2.2 — Pipeline Steps 5-7 (artifact emission, R5, port-report)

Step 5 emits artifacts at canonical paths per the upstream-CI audit's minimum-file-set:

- `src/main/resources/bidder-config/{bidder}.yaml` (kebab-case keys)
- `src/main/resources/static/bidder-params/{bidder}.json` (byte-copy from Go)
- `src/main/java/org/prebid/server/proto/openrtb/ext/request/{bidder}/ExtImp{Bidder}.java`
- `src/main/java/org/prebid/server/bidder/{bidder}/{Bidder}Bidder.java`
- `src/main/java/org/prebid/server/spring/config/bidder/{Bidder}Configuration.java`
- `src/test/java/org/prebid/server/bidder/{bidder}/{Bidder}BidderTest.java`
- `src/test/java/org/prebid/server/it/{Bidder}Test.java`
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-auction-{bidder}-{request,response}.json`
- `src/test/resources/org/prebid/server/it/openrtb2/{bidder}/test-{bidder}-bid-{request,response}.json`
- `src/test/resources/org/prebid/server/it/test-application.properties` (append two lines)

PR-shape automation: title `Port {Bidder}: New Adapter` (or `Port {alias}: New alias for {parent}`), body from upstream `.github/pull_request_template.md`, label `do not port`. Pre-submit: rebase the target branch onto upstream `prebid/prebid-server-java` `master` HEAD; abort with operator notification if a conflicting framework change has landed since D0's sync.

Companion docs PR: emit a draft `prebid/prebid.github.io` adapter-docs page at `dev-docs/bidders/{bidder}.md` populated from the source spec's `bidder_info`, `params`, and `meta` fields. Surface in `port-report.json::companion_docs_pr_draft` so the operator can submit the docs PR alongside the main PR. Maintainer-mandatory per BeOp #4660 review pattern.

Step 6 invokes `port_engine.r5_check_at_port_time`; produces `R5Result`. Step 7 emits `port-report.json` at `.tmp/full-loop/{run-id}/port-report.json`.

### D2.3 — Validate against MVP corpus

Six pairs covering distinct pipeline paths. Per-pair acceptance criteria (ALL must pass for the pair to count as validated):

1. Emitted Java compiles cleanly via `mvn -B compile --file extra/pom.xml`.
2. Emitted unit tests pass via `mvn -B test -Dtest={Bidder}BidderTest --file extra/pom.xml`.
3. Jacoco line-coverage on the new `{Bidder}Bidder.java` ≥ 90% — this repo's own acceptance bar, measured locally. It matches the level upstream asks contributors to self-certify (`docs/developers/contributing.md:17`; PR-template checkbox), which upstream CI does not check.
4. `mvn -B checkstyle:check` exits 0.
5. Emitted YAML validates against Java's `bidder-info-schema.json`; emitted JSON validates against `static/bidder-params/_schema.json`.
6. `port-report.json` schema-validates against `port-report.schema.json` v0.2.0.
7. `r5_check.state` matches the per-pair expectation below.

| Bidder | Pipeline path | `r5_check.state` expected |
|---|---|---|
| `kobler` | R5-pass baseline; byte-equal bidder-params | `pass` |
| `aax` | Rule 39 + R5 fail-semantic (Java omits minLength:1 that Go enforces) | `fail-source-omits-target-constraint` (port emits Java schema with the Go-correct `minLength:1`; surfaces upstream-Java fidelity bug in `human_todos[]`) |
| `adkernelAdn` | Rule 46 master + macro-form asymmetry | `pass` (after name-normalization) |
| `adverxo` | Rule 44 registration-only empire (3 children) + Rule 33 alias-graph inversion | `pass` |
| `vungle` | ADR-007 F3 (Site→App synthesis); `$defs` not yet `$ref`-wired so port hand-walks per design §5 | `pass` (F3 pattern preserved verbatim) |
| `thetradedesk` | ADR-007 F4 (bid-post-processing macros) | `pass` (F4 pattern preserved) |

**End-state**: all 6 pairs validated against the 7-criterion checklist; the `port-go2java` skill ships at v1.0.0; companion docs PR drafts emit alongside the main PR.

## Phase D3 — `port-java2go` MVP (6 days, 10-15 commits)

Production-grade mirror of D2 with Go as the artifact target. Reuses D1's `port_engine.py` helpers and `port-report.schema.json` v0.2.0 contract; direction-specific work is the Go-target emission templates, Go-side PR-shape automation, and inverse-direction rule application.

### D3.1 — Pipeline Steps 1-4 (spec handling, inverse direction)

Walk the 7-step pipeline per design §3 with source=Java, target=Go. Same 10 rules as D2 in inverse direction (priority order):

1. **Rule 38** — bidder-params byte-fidelity (`byte_copy` Java→Go).
2. **Rule 46 inverse** — name-normalization reversal (Java lowercase `adkerneladn` → Go camelCase `adkernelAdn`); requires the dual-spec assertion lookup since not fully mechanical in this direction.
3. **Rule 33 inverse** — Java parent→child YAML decomposes into Go child→parent YAMLs.
4. **Rule 44 inverse** — alias-empire flavor coherence (parent flavor inferred from Java aliases block, projected into Go child-yamls + alias entries).
5. **Rule 36 inverse** — Java IT 4-file split + JUnit class collapses to Go's flat `{bidder}test/exemplary/*.json` + `{bidder}_test.go` thin runner (semantic-coverage parity, not 1:1).
6. **Rule 42 inverse** — Java YAML-inlined IAB cats convert to Go data-table `iab_categories.go` with static-init `delivery_mechanism`.
7. **Rule 35 inverse (lossy-direction)** — Java typed `BidderConfigurationProperties` subclass demotes to Go's `ExtraAdapterInfo` opaque JSON string (per Round-Trip Safety section pre-declaration). Emit `quirks[]: hardcoded-config-as-anti-pattern` if the Java subclass has fields the Go side won't structurally enforce.
8. **Rule 39** — derived-view (no-op).
9. **Rule 19 inverse** — Java `HttpUtil.headers()` collapse expands to explicit Go `http.Header` `Add()` calls.
10. **Rule 30 inverse** — Java framework-default HTTP status handling expands to explicit Go `adapters.IsResponseStatusCodeNoContent` + `adapters.CheckResponseStatusCodeForErrors` helper calls.

### D3.2 — Pipeline Steps 5-7 (Go artifact emission, R5, port-report)

Step 5 emits at canonical Go paths per the upstream-CI audit minimum-file-set:

- `static/bidder-info/{bidder}.yaml` (camelCase keys; converted from Java's kebab-case)
- `static/bidder-params/{bidder}.json` (byte-copy from Java)
- `openrtb_ext/imp_{bidder}.go` (struct emitted from Java's `ExtImp{Bidder}.java` + Lombok annotations stripped)
- `adapters/{bidder}/{bidder}.go` (Builder + MakeRequests + MakeBids per Go canonical pattern)
- `adapters/{bidder}/{bidder}_test.go` (thin `RunJSONBidderTest` wrapper)
- `adapters/{bidder}/{bidder}test/exemplary/*.json` (re-authored from Java IT 4-file fixtures into Go's flat shape)
- `adapters/{bidder}/{bidder}test/supplemental/*.json` (error-path fixtures; preserve those reachable in Go)
- `adapters/{bidder}/params_test.go` (validates schema)
- `openrtb_ext/bidders.go` constant addition + `coreBidderNames` slice entry (alphabetical, lower-first; via `port_engine.alphabetical_insert`)
- `exchange/adapter_builders.go` import + map entry (alphabetical)

Pre-emit: `port_engine.prefix_uniqueness_check` against `coreBidderNames` to avoid `TestBidderUniquenessGatekeeping` collision. Post-emit: `port_engine.gofmt_post_process` on every emitted `.go`.

PR-shape automation: title `New Adapter: {Bidder}` (per real-PR convention; capital A), body from `port-java2go/references/pr-shape.md`, no mandatory label (Go has no upstream PR template). Pre-submit: rebase target branch onto upstream `prebid/prebid-server` `master` HEAD; abort with operator notification on framework conflict since D0's sync.

Companion docs PR: same draft mechanism as D2 — emit `dev-docs/bidders/{bidder}.md` populated from the source spec — surfaced in `port-report.json::companion_docs_pr_draft`. Less maintainer-pressure than Java side, but expected for parity.

Step 6 invokes `port_engine.r5_check_at_port_time`; produces `R5Result`. Step 7 emits `port-report.json` at `.tmp/full-loop/{run-id}/port-report.json`.

### D3.3 — Validate against MVP corpus (reversed)

Same 6 pairs as D2, reversed (Java source → Go destination). Per-pair acceptance criteria (ALL must pass):

1. Emitted Go compiles cleanly via `go build ./adapters/{bidder}/...`.
2. Emitted tests pass via `go test ./adapters/{bidder}/...`.
3. Adapter-coverage report (per upstream `./scripts/check_coverage.sh`) ≥ 80% (real-world median; well above the 30% CI minimum).
4. `gofmt -s -l` exits with no diff; `go vet ./adapters/{bidder}/...` exits clean.
5. `TestBidderUniquenessGatekeeping` passes (first-6-letter prefix unique against current `coreBidderNames`).
6. Emitted YAML validates against Go's `static/bidder-info/_schema.json`; emitted JSON validates against the bidder-params schema convention.
7. `port-report.json` schema-validates against `port-report.schema.json` v0.2.0.
8. `r5_check.state` matches expectation:

| Bidder | Pipeline path | `r5_check.state` expected |
|---|---|---|
| `kobler` | R5-pass baseline reversed | `pass` |
| `aax` | Reversed direction — Go's `minLength:1` is strictly tighter than Java's omission | `warn-target-strengthens-source` (Go output retains `minLength:1`; record divergence in `human_todos[]` category `upstream-confirmation`) |
| `adkernelAdn` | Rule 46 inverse: Java `adkerneladn` → Go `adkernelAdn` (requires dual-spec assertion lookup; not fully mechanical inverse) | `pass` |
| `adverxo` | Rule 44 inverse: Java parent → Go child→parent YAMLs + Rule 33 inverse | `pass` |
| `vungle` | ADR-007 F3 inverse: Java Site→App synthesis → Go equivalent | `pass` (F3 pattern preserved) |
| `thetradedesk` | ADR-007 F4 inverse: Java bid-post-processing macros → Go equivalent | `pass` |

**End-state**: bidirectional port skills exist; both production-grade. All 12 validation runs (6 pairs × 2 directions) pass the per-direction acceptance checklist; the `port-java2go` skill ships at v1.0.0.

## Phase D4 — CI integration + fixture-gap fills (4 days, 5-7 commits)

### D4.1 — Port-side R4 (round-trip determinism)

Extend `scripts/round-trip-ci.py` with `r_port_round_trip`: for each paired bidder, read source spec → invoke `port-go2java` → re-read destination → invoke `port-java2go` → byte-equal-source. Lossy-direction asymmetries (per `port-translation-rules.yaml` Round-Trip Safety section) are recorded as expected, NOT failures.

### D4.2 — Coverage report extension

`scripts/coverage-report.py` gains a per-rule applied-count table sourced from `port-report.json` archives. Surfaces over- and under-exercised rules.

### D4.3 — Pre-submit checkstyle dry-run

D2's port skill optionally invokes `mvn -B checkstyle:check --file extra/pom.xml` against the emitted Java tree, surfacing violations as `human_todos[]` with category `framework-asymmetry` or new `style-violation`. Skips if `mvn` not on PATH; warns the operator.

### D4.4 — Fixture gap fills

Backfill the corpus gaps surfaced in research:

- **beachfront** — ADR-007 F1 (multi-endpoint-by-mediatype) master sample. Add Go + Java goldens + dual-spec.
- **(time-permitting)** Connatix — exercises the new `warn-target-strengthens-source` R5 state.

**End-state**: round-trip-ci enforces port-side R4; coverage report shows rule applied-counts; checkstyle dry-run integrated; ADR-007 F1 master sample exists.

## Sequencing

```
D0 (refactor + sync) ──→ D1 (scaffold + emission refs + port-engine) ──→ D2 (port-go2java MVP) ──→ D3 (port-java2go MVP) ──→ D4 (CI + fixture gaps)
```

D0 and D1 are sequential (D1 needs the lib refactor). D2 depends on D1's port-engine. D3 follows D2 sequentially — D2 validates the prose-driven-SKILL-with-mechanical-helpers architecture against empirical Go→Java CI evidence; D3 mirrors that validated architecture for the inverse direction. D4 picks up after D3 to grow round-trip-ci with bidirectional port-side R4 and backfill the corpus gaps. D3 and D4 could be parallelized at the cost of debugging both directions before either is fully validated; the sequential ordering trades 2-3 days of wall-clock for substantially lower integration risk.

## Risks

1. **Upstream Java PR #4126 lands during D2** — endpoint URL validation could break port-emitted YAML. Mitigation: D0 sync; D2 pre-submit rebase; if it lands mid-D2, regenerate test fixtures.
2. **The 84/271 non-mechanical Go bidder-constant names** lack a canonical lookup table. D1.3 item 4 builds it but requires manual curation against `openrtb_ext/bidders.go` HEAD. Mitigation: source from upstream constants directly; commit the table at a pinned SHA; refresh via D0 sync.
3. **D2 emission produces Java that fails checkstyle ImportOrder** (strict 3-group with blank-line separation). Mitigation: D1.3 templates are checkstyle-compliant by construction; D4.3 catches drift before PR submission.
4. **The aax R5-fail handler is the only fail-state fixture** — high test-leverage, low coverage. Mitigation: D2.3 explicit behavioral assertions, not just round-trip.
5. **Cross-version replay (Phase F) depends on port-report SemVer integrity** — D1.4's bump to 0.2.0 must be additive, not breaking. Mitigation: schema-versioning policy MINOR criteria enforced; CHANGELOG entry mandatory.
6. **No upstream Go-side porting guide exists**. Phase D ships an inverse guide internally at `prebid-server-go/port-java2go/references/porting-guide.md`, distilled from the Java-side guide and observed real-world Go-side new-adapter PRs. Mitigation: maintain the inverse guide as part of D3; offer it upstream via a docs PR if Go maintainers find it useful. Risk if not maintained: D3 emission drifts from Go-maintainer expectations as upstream evolves.
7. **Lossy direction asymmetries** (Rule 35 Java typed-config-subclass → Go opaque `extra_info`; Rule 8/19/30 Java helper collapses → Go explicit expansions) are pre-declared in `port-translation-rules.yaml` Round-Trip Safety section. Mitigation: D3 preserves source-side semantic information by emitting explicit `quirks[]` entries on the Go destination spec capturing what was lossy, so a future Go→Java re-port retains traceability. R4 round-trip determinism is verified per-direction in D4.1 with the lossy-fields list as expected non-equality.
8. **Maintainer aesthetic disagreement** — checkstyle / gofmt clean does not guarantee idiomatic. A reviewer may push back on patterns the linter accepts but the maintainer cohort considers non-idiomatic (e.g., variable naming, helper-method extraction granularity, error-message phrasing). Mitigation: emission templates in D1 are derived from observed real-merged-PR shapes, not from synthesized ideals; D2 ships `kobler` first to a maintainer for an "is this acceptable shape?" gut-check before broader rollout; D3 uses the same gut-check on a maintainer for the Go-target shape. Phase F's reflection loop is the durable channel for incorporating maintainer feedback into the rule corpus.
9. **Bidder-constant lookup table staleness** — the 84/271 non-mechanical name table at `prebid-server-go/read/skills/shared/bidder-constant-table.yaml` is sourced from upstream HEAD via `gh api` at D0 sync time. Between D0 and the next sync, new upstream adapters can land that aren't in the table; Phase D emit would either pick a wrong constant or fail prefix-uniqueness. Mitigation: D0.2's sync refreshes the table; D2/D3 pre-emit re-fetches via `gh api repos/prebid/prebid-server/contents/openrtb_ext/bidders.go` and validates table-vs-upstream parity; warns the operator if drift detected.

## Reference: ADR + design-doc index

| Source | Topic | Phase D dependency |
|---|---|---|
| `docs/methodology/port-skills-design.md` | 7-step pipeline + conflict resolution + novel-pattern handling | D2 implements; D1 schema bump |
| `docs/methodology/end-to-end-flow.md` | Teal flow CLI + run-scoped artifact layout | D1.5 read-orchestrator amendment |
| `docs/methodology/reflection-loop.md` | Phase F consumer of port-report | D1.4 schema additions feed Phase F |
| `docs/methodology/schema-versioning.md` | SemVer policy | D1.4 schema bump compliance |
| `docs/methodology/repo-rules.md` | Upstream snapshot policies | D0.2 refresh |
| `prebid-server-go/read/skills/shared/port-translation-rules.yaml` | 46 rules; v0.2.0 | D2 walked rule-by-rule |
| `prebid-server-go/read/skills/shared/port-report.schema.json` | port-report contract | D1.4 bumps to v0.2.0 |
| `prebid/prebid-server-java/docs/developers/bid-adapter-porting-guide.md` (upstream) | Maintainer porting guide | D1 version-pin SHA; D2 PR-shape compliance |
| `docs/decisions/007-novel-pattern-schema-additions.md` | F1/F3/F4/F5 schema fields | D2 hand-walks per design §5; `$ref`-wiring deferred |
| `docs/decisions/003-rule-44-alias-empire-consolidation.md` | Rule 44 mechanics | D2 implements |
| `docs/decisions/005-rule-46-naming-convention-normalization.md` | Rule 46 mechanics | D2 implements |
