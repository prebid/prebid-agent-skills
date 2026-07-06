# Port skills — design doc (Phase D)

Design for the two port SKILLs: `port-go2java` (translates a Go-source spec to Java artifacts) and `port-java2go` (the symmetric inverse). Phase D ships both; this document is the contract that lets reviewers reason about the port output before code lands.

Status: **proposed design** (Phase D not yet started; no implementation in this PR). The shape declared here is what Phase D will implement — changes to this design require an ADR.

---

## 1. Skills, scope, placement

| Skill | Direction | Source | Target | Skill location |
|---|---|---|---|---|
| `port-java2go` | Java → Go | `prebid-server-java/read/specs/{bidder}/latest.yaml` (or `.tmp/full-loop/{run-id}/java/{bidder}.yaml`) | `prebid-server-go/adapters/{bidder}/**/*.go` plus YAML/static files plus tests | `prebid-server-go/port-java2go/SKILL.md` (lives under the Go tree because it produces Go artifacts; the SOURCE is Java but the artifact-language is Go) |
| `port-go2java` | Go → Java | `prebid-server-go/read/specs/{bidder}/latest.yaml` (or transient) | `prebid-server-java/src/main/java/org/prebid/server/bidder/{bidder}/**/*.java` plus YAML plus IT fixtures | `prebid-server-java/port-go2java/SKILL.md` |

**Scope** (in scope for both): take a structured Adapter Specification and emit the destination-language artifacts that satisfy R5-strict cross-language equivalence at port time. Apply the 49 port-translation rules. Emit a `port-report.json` documenting what was applied, what was novel, and what needs human review.

**Out of scope**: writing new adapters from scratch (that's `write/`, future); reviewing the ported code post-merge (that's `review/`, future composition); cross-language regression detection (that's `pr-triage` via `prior_source_spec`, see Wave 5).

---

## 2. Invocation contract

CLI form (Phase D will implement these as part of the orchestrator hand-off):

```bash
# One-shot Teal flow (read → port → review):
$ orchestrator port \
    --source-lang=java \
    --target-lang=go \
    --bidder=teal \
    --source-spec=prebid-server-java/read/specs/teal/latest.yaml \
    --target-branch=feat/teal-go-port \
    --run-id=2026-05-03T1430Z-a3f9

# Same skill via direct invocation (when the user has the spec persisted):
$ /port-java2go --bidder=teal --target-branch=feat/teal-go-port

# Spec-only port (no code emitted; useful for design review):
$ /port-java2go --bidder=teal --dry-run
```

**Pre-conditions** (the orchestrator MUST satisfy before invoking the skill):

1. The source spec exists and validates against `adapter-spec.schema.json`.
2. The target language clone is checked out clean on the target branch (or `--dry-run` is set).
3. `port-translation-rules.yaml` is at version 0.2.0 or later (port skills version-pin).

**Post-conditions** (the skill GUARANTEES on success):

1. Destination artifacts emitted at canonical paths (the heuristics docs at `prebid-server-{go,java}/read/skills/.../references/file-role-heuristics.md` define those paths).
2. A `port-report.json` written next to the destination spec at `.tmp/full-loop/{run-id}/port-report.json` (when running under the Teal flow) or `prebid-server-{target_lang}/port-{source_lang}2{target_lang}/output/{bidder}/port-report.json` (when persisted).
3. The destination spec, when re-read by the corresponding read-skill, validates against the schema AND produces an R5-strict-equivalent comparison against the source spec (at the level the dual-spec assertions encode — `bidder_info.capabilities`, `params.schema_interpretation` invariants, `bidder_info.gvl_vendor_id`, `bidder_info.maintainer`, etc.).

---

## 3. Pipeline

Each port skill executes the same 7-step pipeline, with direction-specific implementations of Steps 3 and 4.

### Step 1 — Load + validate source spec

Read the source spec YAML. Validate against `adapter-spec.schema.json`. Confirm `source_language` matches the skill's expected source. Reject (exit 1) if the spec is malformed or directionally wrong.

### Step 2 — Discover the bidder family

Determine whether the bidder is a primary (standalone) adapter or part of an alias-empire. Read `meta.is_alias`, `meta.parent_aliases`, `aliases[]` blocks. Record family shape — used by Rule 33 (alias inversion) and Rule 44 (alias-empire consolidation).

### Step 3 — Apply rules (direction-specific)

Walk `port-translation-rules.yaml` rule-by-rule. For each rule:

1. Check the rule's `spec_field_driver` against the source spec.
2. If the driver is null/empty/inapplicable → emit `verdict: skipped-not-applicable`.
3. If the driver indicates the rule applies in the source-language direction only (e.g., a Java-only ConfigurationProperties subclass when source=Go) → emit `verdict: skipped-source-side-only`.
4. Otherwise apply the rule's translation: emit destination-language artifacts and update the destination spec's corresponding field.

Rule application is **deterministic and ordered** — see Section 4 below for the canonical order.

### Step 4 — Author the destination spec

After all applicable rules have been applied, the destination spec is constructed. The order:

1. Copy cross-language-shared fields verbatim from source (`bidder_params_json` byte-equal per Rule 38; `bidder_info.{capabilities, gvl_vendor_id, maintainer, geoscope, modifying_vast_xml_allowed}` per R5-strict).
2. Apply per-language transformations on the language-specific blocks (e.g., `spring_config.*` is constructed when target=java; `code.adapter_struct + code.builder` when target=go; cross-package param-ext POJO `proto/openrtb/ext/request/{xyz}/ExtImp{Xyz}.java` when target=java).
3. Carry over `quirks[]` entries that are language-neutral; transform language-specific quirks.
4. Set `provenance.source.resolved_commit` to the SAME commit as the source spec (the port is point-in-time; reflecting on a different upstream is Phase F's job).
5. Re-compute SHA hashes (`bidder_params_sha256`).

### Step 5 — Emit destination-language artifacts

Walk the destination spec and emit the corresponding files:

- **Bidder package** (`adapters/{bidder}/` for Go; `src/main/java/org/prebid/server/bidder/{bidder}/` for Java) — implementation file, models, parsers, types, utils per the role-heuristics doc.
- **Static config** (`static/bidder-info/{bidder}.yaml` + `static/bidder-params/{bidder}.json` for Go; `src/main/resources/bidder-config/{bidder}.yaml` + `src/main/resources/static/bidder-params/{bidder}.json` for Java).
- **Tests** (JSON fixtures + harness invocation for Go; integration test class + JSON fixtures for Java; per Rule 36 fixture-inventory parity).
- **Spring config** (Java only, `src/main/java/org/prebid/server/spring/config/bidder/{Xyz}Configuration.java`).

### Step 6 — R5-strict check at port time

Re-read the destination spec via the same parser the read-skill uses. Compare R5-strict fields against the source spec. Record `r5_check.{state, byte_equal_fields, warn_fields, fail_fields, summary}` in the port report.

States:
- `pass` — all R5_STRICT_KEYS match; warn fields are within R5_DIVERGENT_KEYS.
- `warn-byte-only-divergence` — Rule 38 byte-only divergence detected; semantic equivalence holds.
- `fail-semantic-divergence` — at least one strict-key mismatch (e.g., the aax minLength bug). Port report flags as `human_todos` with category `byte-divergence-warning` or `upstream-confirmation`.
- `skipped-no-pair-fixture` — corpus has no matching pair; only one-side validation possible.

A `fail-semantic-divergence` does NOT abort the port. The port still ships its artifacts; the human review (downstream) decides whether to merge. Rationale: many semantic divergences are KNOWN (aax minLength, optidigital default-enabled, smarthub macro-syntax) and the right action is filing an upstream fix, not blocking the port.

### Step 7 — Emit port-report.json

Per the schema at `prebid-server-go/read/skills/shared/port-report.schema.json`. Includes the run provenance, every rule application verdict, every quirk emitted, the R5 check result, human-todos, and unresolved-translations. Phase F (reflection loop) consumes this report.

---

## 4. Rule application order

Rules are applied in the order declared in `port-translation-rules.yaml`. The YAML structure groups rules by topic (Bidder-params byte-fidelity → Imp.ext unmarshaling → Bidder-class → Spring-config → ... → Lifecycle). Within each topic, rules are listed by id ascending.

The order is **deterministic** so that two port runs of the same source spec at the same rules version produce byte-identical destination specs (R4 round-trip determinism applies to ports too).

When two rules act on overlapping spec fields, see Section 5 for the composition (typical) vs conflict (rare) distinction. For genuine conflicts where two rules produce mutually-exclusive artifacts, the rule with the lower id wins on artifact placement and the conflict is recorded as an `unresolved_translations` entry with reason `conflicting-rules` so the reflection loop sees it.

---

## 5. Rule composition and conflict resolution

Most rules are non-overlapping (each names its own `spec_field_driver`). When two rules touch the same field, the relationship is almost always **composition** — one rule's output becomes the other's input — not conflict. True winner-take-all conflict is rare; the port skill handles each shape differently.

### 5.1 Composition (the common case)

When two applicable rules produce complementary artifacts that compose cleanly, the port skill applies them in declared order. The lower-id rule lands its artifact first; the higher-id rule transforms or extends that artifact.

**Rule 11 ⊕ Rule 35 — endpoint construction composes with config-properties subclass.** When a Java config exposes `dev-endpoint` (Kobler) AND the endpoint URL uses `{{TOKEN}}` substitution, both Rule 11 (multi-token-substitution) and Rule 35 (config-properties subclass) apply. Resolution: apply Rule 35 first to construct the subclass field, then Rule 11 substitutes the field's value into the URL template. The higher-id rule transforms the lower-id's output. No conflict — both artifacts coexist by design.

**Rule 5 mutation strategy pairing.** Source has `entity_strategies.Site: deep-copy-then-mutate`; target language's idiom is `immutable-rebuild`. Rule 5 declares this is a valid pair. Apply the language-idiom translation (deep-copy-then-mutate → immutable-rebuild for Go→Java; the inverse for Java→Go). No conflict — the rule itself encodes the translation.

**ADR-007 F1/F3/F4/F5 patterns at adapter_spec_version 1.1.0+.** When the source spec uses one of these patterns (multi-endpoint, entity_strategies extensions, bid_post_processing, imp_ext_strip), the port applies the corresponding language idiom. Wave 11b B3+ closed `Code` and added structured `MakeRequests`/`MakeBids` $defs, but the F1/F3/F4/F5 $defs themselves remain unwired — the corresponding sub-positions (`endpoint_resolution`, `mutation`, `imp_ext_unmarshal`, `bid_post_processing`) are typed `object|null` and treated as implicit-open by the phantom-detector. The port skill applies the pattern by inspection of the source's `code.make_requests.{endpoint_resolution, mutation, imp_ext_unmarshal}` and `code.make_bids.bid_post_processing` blocks; per-pattern $ref-wiring is a future wave.

### 5.2 Pseudo-conflict (rule + cross-cutting concern)

Some rules trade off against cross-cutting language conventions. Both apply, both produce side-effects, but neither is "wrong" — the port skill emits both plus a `human_todos` so the operator can adjudicate.

**Rule 38 byte-equality vs language-specific reformatting.** When porting Go→Java, the bidder-params JSON might need re-formatting to match Java's 4-space indent. This breaks Rule 38 byte-equality but preserves semantic equivalence. The port skill applies Java's canonical formatting AND emits a `human_todos` entry with category `byte-divergence-warning` so a human can decide whether to (a) revert to Go-byte-equal, (b) accept the byte divergence, (c) file an upstream-bidder fix. Not a conflict in the winner-take-all sense — both forms are arguably correct.

### 5.3 Conflict (genuine winner-take-all; rare)

A genuine conflict is two rules emitting mutually-exclusive artifacts at the same path. The current rule corpus has no documented case; the resolution protocol is reserved for future rule additions.

**Resolution protocol** (when it arises):

1. The port skill identifies the conflict during Step 3 — both rules emit `verdict: applied` with overlapping artifact paths.
2. The lower-id rule's artifact wins (declared-order priority).
3. The higher-id rule's would-be artifact is recorded as an `unresolved_translations[]` entry with `reason: conflicting-rules` and `ambiguous_rule_ids: [lower_id, higher_id]`.
4. Phase F (reflection loop) triages the entry: amend one of the two rules to narrow its `spec_field_driver`, OR introduce a precedence note in `port-translation-rules.yaml`.

**Synthetic example** (illustrative; not currently in the corpus): Suppose a hypothetical Rule 50 emits a custom `{Bidder}HttpClient.java` while Rule 8 emits `{Bidder}Bidder.java` declaring its own `HttpClient` field with the same name. Both produce code referencing `{Bidder}HttpClient` but only one of the two files can compile. Lower id wins (Rule 8); Rule 50's would-be artifact lands in `unresolved_translations[]` for Phase F triage.

---

## 6. Novel-pattern handling

A "novel pattern" is a behavior in the source spec that no rule handles — typically because it didn't exist in the corpus when `port-translation-rules.yaml` was last updated. Detection:

- Rule walk in Step 3 produced no `applied` verdict for a given source-side feature.
- The source spec's `quirks[]` contains an `edge_case_taxon` not in `behavior-taxonomy.yaml.quirks_taxa[].id`.
- A `code.*` field has a value the destination-language has no obvious analog for.

Action:
1. The port skill applies a **best-effort transliteration** if confidence is high enough (e.g., the value is a string that maps cleanly to the target language's idiom catalog).
2. Emit a `human_todos` entry with category `novel-pattern` and a verbose `summary` describing the source feature + the porter's best-effort guess.
3. Emit an `unresolved_translations` entry with reason `novel-quirk` (or `novel-pattern-needs-schema-addition` when the pattern needs an ADR-007-style schema addition).
4. Do NOT silently drop the source feature — the destination spec records `quirks[]` entry capturing the situation so the read-skill on the destination side surfaces it on next read.

The reflection loop in Phase F triages these `unresolved_translations` entries — see [`reflection-loop.md`](reflection-loop.md).

---

## 7. R5-strict check at port time

The R5-strict check at port time calls `scripts/lib/r5_check.compare_pair`, the same comparator the harness uses, but invoked on the source ↔ destination pair instead of two existing fixtures. Three differences:

1. **Source/destination pairing**: source = the input spec; destination = the freshly-emitted one. No `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` is consulted (the pair file may not exist for new bidders being ported).
2. **Strict-keys decomposition**: applies the Wave 1 R5 fix — `params.schema_interpretation.{required_fields, combinators_used, flexible_types}` are the strict subfields; the prose-bearing description/notes are NOT compared.
3. **Severity remap**: a port-time R5 fail is a `human_todos` entry, not a CI failure. The port still ships; humans decide.

The R5 comparator was lifted to `scripts/lib/r5_check.py` in Phase D0.1 (the harness re-exports the public surface for backward compatibility). Port skills consume `compare_pair(go_spec, java_spec, *, assertions=None, overall=None) -> R5Result`; the harness wraps `R5Diagnostic` items into its own `Finding` dataclass.

---

## 8. Worked examples (reference for Phase D implementation)

### Example A — kobler Java → Go (clean port)

Source: `prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml` (paired bidder, R5 pass, byte-equal bidder_params).

Pipeline: Steps 1-2 trivial. Step 3 applies ~12 rules: Rule 5 (mutation strategy), Rule 9 (custom request type N/A — kobler is standard OpenRTB), Rule 11 (multi-token-substitution endpoint), Rule 33 (no aliases), Rule 35 (no config-properties subclass — kobler dev-endpoint becomes Go's `cfg.devEndpoint` per Rule 35), Rule 36 (test fixture parity), Rule 38 (byte-equal — passes), Rule 42 (no IAB cats), Rule 46 (no naming normalization needed — `kobler` is already lowercase). Step 4 emits Go-side `code.adapter_struct` + `code.builder` blocks. Step 5 emits `adapters/kobler/kobler.go`, `static/bidder-info/kobler.yaml`, `static/bidder-params/kobler.json`, `adapters/kobler/koblertest/`.

Step 6 R5 check: `state: pass`. byte_equal_fields includes `bidder_params_sha256`. Step 7 port-report emits with 12 rules consumed, 0 quirks, 0 human_todos, 0 unresolved.

### Example B — vungle Java → Go (R5-fail expected on Site/App pair)

Source: `prebid-server-java/read/test-fixtures/vungle.golden.spec.yaml`. Has `entity_strategies.Site: replace-with-app-synthesis` and `App: synthesize-app-replacement` — ADR-007 F3 patterns.

Pipeline: Step 3 applies Rule 5 with verdict `applied-with-warning` (the Site/App pair is ADR-007 F3, not the canonical copy-then-mutate↔immutable-rebuild from Rule 5; the port emits the F3 pattern but flags the Rule 5 warning). Step 5 emits Go-side `vungle.go` with the F3-equivalent destructive Site→App synthesis. Step 6 R5 check: `state: pass` (the pair is symmetric per ADR-007 F3 — both Site=replace-with-app-synthesis and App=synthesize-app-replacement match across languages). Step 7 port-report includes:

- `rules_consumed[]`: Rule 5 verdict=applied-with-warning, summary="ADR-007 F3 mediatype-context-rewrite: Site=replace-with-app-synthesis ↔ App=synthesize-app-replacement, port emitted the destructive synthesis pattern verbatim".
- `human_todos[]`: 1 entry, category=`novel-pattern`, summary="ADR-007 F3 (vungle Site/App synthesis) is shipped at adapter_spec_version 1.1.0; verify the port's Go-side vungle.go uses the same control-flow shape as the master sample".

### Example C — aax Java → Go (R5-fail-semantic — known minLength bug)

Source: `prebid-server-java/read/test-fixtures/aax.golden.spec.yaml`. Has `params.schema_interpretation.properties[].constraints` MISSING `minLength: 1` (per the dual-spec `severity: fail` assertion).

Pipeline: Step 6 R5 check: `state: fail-semantic-divergence`. fail_fields includes `params.schema_interpretation.required_fields` (semantic divergence — Java would accept empty cid/crid, Go would reject). Step 7 port-report includes:

- `r5_check.summary`: "aax minLength:1 omission on Java side (cid/crid). Port emitted Go-side bidder-params.json WITH minLength:1 to match Go's canonical schema. The Java-side dual-spec already records this divergence (severity:fail per cross-language-pairs/aax.dual-spec-assertions.yaml); the port-fidelity bug is a Java→upstream issue, not a port issue."
- `human_todos[]`: 1 entry, category=`upstream-confirmation`, summary="File a port-fidelity bug against prebid/prebid-server-java to add minLength:1 on aax cid/crid. The Go-side port is correct; the Java-side schema is incorrect."

The port still ships. The human review decides whether to merge the port AS-IS (preserving Go's minLength:1 enforcement) or wait for the Java-side fix to land first.

---

## 9. Testing strategy

Phase D's tests (live under `scripts/tests/test_port_skills.py` when authored) verify:

1. **Round-trip determinism (port-side R4)**: read source spec → port → re-read destination → port-back → byte-equal to source. This is stronger than the read-side R4 because it covers the rule-application transformation.
2. **R5-strict check correctness**: synthetic source/destination pairs that should pass / warn / fail; verify the port's R5 check returns the expected state.
3. **Rule coverage**: every rule has at least one fixture demonstrating `verdict: applied`.
4. **Composition**: synthetic specs exercising Rule 11 ⊕ Rule 35 (endpoint construction composes with config-properties subclass per §5.1) — verify both artifacts emit and the higher-id rule's transform applies after the lower-id rule's output. **Conflict resolution**: when a future rule introduces a genuine winner-take-all case (none in the current corpus per §5.3), verify lower-id-wins and the loser lands in `unresolved_translations[]`.
5. **Novel-pattern handling**: synthetic source with a quirk not in the taxonomy; verify `human_todos` + `unresolved_translations` populate correctly.
6. **Port-report schema validation**: every emitted report validates against `port-report.schema.json`.

The corpus of port-fixtures lives at `prebid-server-{go,java}/port-{source}2{target}/test-fixtures/` (Phase D will create those directories).

---

## 10. Open questions (deferred)

- **Multi-bidder ports**: should `port-java2go` accept a comma-separated bidder list to port an entire alias-empire (e.g., teqblaze + 10 aliases) in one invocation? The current design assumes one bidder per invocation; a follow-up ADR can amend.
- **Streaming vs batch port-report**: large alias-empire ports may produce 100+ rules-consumed entries. Streaming output (NDJSON) might be useful for very large runs. Defer to Phase D implementation feedback.
- **Cross-version replay**: Phase F's reflection loop wants to replay an old port report against a newer rules version. The schema's `port_translation_rules_version` field supports this; the implementation lives in Phase F, not D.
- **Code generation backend**: does the port skill emit code via templates (Jinja-style), via direct string composition, or by transforming an AST? The choice affects how easily future schema additions land. Recommend templates for v1; switch to AST transforms when complexity demands.

---

## Sources

- [`port-translation-rules.yaml`](../../prebid-server-go/read/skills/shared/port-translation-rules.yaml) — the 49 rules the port skills consume.
- [`adapter-spec.schema.json`](../../prebid-server-go/read/skills/shared/adapter-spec.schema.json) — the spec contract both read-skills and port-skills share.
- [`port-report.schema.json`](../../prebid-server-go/read/skills/shared/port-report.schema.json) — the port output contract Phase F consumes.
- [`reflection-loop.md`](reflection-loop.md) — Phase F's consumption of port reports + ADR amendment protocol.
- [`end-to-end-flow.md`](end-to-end-flow.md) — Teal flow CLI invocations + failure modes.
- [`pr-triage` SKILL.md `prior_source_spec` section](../../prebid-server-go/review/skills/pr-triage/SKILL.md) — reviewer-side consumption of cross-language port-fidelity divergences.
