# Reflection loop — design (Phase F)

After a port runs and (typically) after a human reviews the resulting PR, the reflection loop reads the port report, the review findings, and any post-merge upstream signal, and decides what to update in the SKILLs / rules / taxonomy / ADRs so the NEXT port produces fewer human-todos and tighter R5-strict equivalence.

Status: **proposed design** (Phase F not yet started). Phase D's port reports are the input; Phase F's output is one or more pull requests against this repository (NOT against prebid-server-{go,java}).

---

## 1. When the reflection loop runs

Three triggers, in priority order:

1. **Post-port** — after a `port-{source}2{target}` skill emits a `port-report.json` with at least one `human_todos[]` entry, or `unresolved_translations[]` entry, or `r5_check.state ∈ {warn-byte-only-divergence, fail-semantic-divergence}`. The reflection loop runs over the report immediately.
2. **Post-merge** — after the ported PR merges upstream (the human review concluded). The reflection loop reads the final code, diffs against what the port emitted, and records any human-edits that reveal where the port made the wrong call.
3. **Periodic sweep** — weekly run that scans accumulated port reports across all bidders and surfaces patterns that recur (e.g., "Rule 35 produced `verdict: applied-with-warning` on 5 of 7 recent ports — consider amending the rule").

Phase F implements all three. Trigger 1 is invoked via the orchestrator (Teal flow); triggers 2 and 3 run on a schedule (GitHub Actions weekly cron).

---

## 2. Triage matrix

For each issue surfaced in a port report, the reflection loop classifies it and routes to the appropriate fix location.

| Issue type | Source signal | Fix location | Fix shape |
|---|---|---|---|
| Novel pattern not in taxonomy | `unresolved_translations[].reason: novel-quirk` OR `human_todos[].category: novel-pattern` | `behavior-taxonomy.yaml` `quirks_taxa[]` | Add a new entry with `id, description, surfaces_in: [quirks]`. Bump `taxonomy_version` MINOR. |
| Novel pattern needing schema field | `unresolved_translations[].reason: novel-pattern-needs-schema-addition` | `adapter-spec.schema.json` (and an ADR) | Add a `$def` or extend an existing one. Following ADR-007 precedent: `additionalProperties: true` and NOT `$ref`-wired in the first release; tighten in the next minor. Bump `adapter_spec_version` MINOR. |
| Existing rule produces wrong direction | `port_run` data shows the rule's `summary` doesn't match the human-edited final code (post-merge trigger) | `port-translation-rules.yaml` rule body OR an ADR amendment | Edit the rule's `body` and `notes`, OR file an ADR amendment if the rule's intent itself is wrong. Bump `port_translation_rules_version` PATCH (body refinement) or MINOR (decision change). |
| Rule conflict (lower-id wins but human chose differently) | `unresolved_translations[].reason: conflicting-rules` + post-merge diff shows reviewer overrode the port | An ADR documenting the precedence change | Codify the new precedence in an ADR; update both rules' notes to cross-reference. Bump `port_translation_rules_version` PATCH. |
| Two rules ambiguous (both matched) | `unresolved_translations[].reason: ambiguous-rule-match` | `port-translation-rules.yaml` rule disambiguation | Tighten one or both rules' `spec_field_driver` so they're mutually exclusive. Bump `port_translation_rules_version` PATCH. |
| R5 byte-only divergence (Rule 38) | `r5_check.state: warn-byte-only-divergence` | `port-translation-rules.yaml` Rule 38 notes OR upstream PR | If the divergence is repeatable across bidders (e.g., 4-space vs 6-space indent inconsistency), amend Rule 38 with the canonical formatting choice. If it's a one-off (specific bidder, specific upstream PR), file an upstream fix. |
| R5 semantic divergence | `r5_check.state: fail-semantic-divergence` | Upstream PR (NOT this repo) | The port is correct; the divergence is an upstream port-fidelity bug. File against `prebid/prebid-server` or `prebid/prebid-server-java`. Update the dual-spec assertion file at `cross-language-pairs/{bidder}.dual-spec-assertions.yaml` to record the divergence with `severity: fail` if not already recorded. |
| Read-skill missed a field | The destination spec, when re-read, doesn't include data the port skill expected | `prebid-server-{lang}/read/skills/{skill}/SKILL.md` extraction step | Amend the relevant SKILL.md step. Bump nothing (read skills aren't versioned independently). The new field path may need to be added to the Wave 6 `test_doc_count_claims.py` if it's a count-claim. |
| Lint missed a class of bug | The port-report includes a `human_todos[].category: framework-asymmetry` that a static lint could have caught | `scripts/lib/lint-{port-rules,java-roles,...}.py` | Add a check to the appropriate lint. Bump nothing. |
| ADR text drifted from execution reality | Periodic sweep finds an ADR's status is `Proposed` or its decision narrative is future-tense, but the work is done | `docs/decisions/{NNN}-{name}.md` | Status flip + past-tense rewrite. Wave 7 of PR #1 hardening did this for 8 ADRs. |

The matrix is not exhaustive but covers the common cases. Novel matrix rows can be added by Phase F itself (it's reflective).

---

## 3. ADR amendment protocol

When the reflection loop's triage produces an ADR amendment (rather than a simple rule/taxonomy edit), the protocol:

1. **Locate the existing ADR** by topic. If no existing ADR covers the decision space, author a new one with the next-available number.
2. **Capture the trigger**: which port report, which review finding, which upstream PR motivated the amendment. Cite the exact `run_id` from the port report and the SHA of the post-merge commit.
3. **Refine** the ADR's body. Use a "refined" annotation in the `**Date**` line (precedent: ADR-005, ADR-006, ADR-007 already carry refinement annotations from prior audits). The `**Date**` line carries dates of all refinements separated by semicolons.
4. **Link** the amendment in CHANGELOG. Add an entry under `## Unreleased — ADR corrections` (precedent: existing entries from 2026-05-03 audit + Phase 5 reclassifications). ADR refinements without rule/schema/taxonomy version bumps live in `Unreleased — ADR corrections` indefinitely; the next versioned release bundle can elide them or reference them.
5. **Cross-reference** the port report. The ADR's `## References` section adds a line: `Phase F triage of port-report {.tmp/full-loop/{run-id}/port-report.json or its persisted analog}`.

The protocol intentionally does NOT require a new ADR for every refinement — minor body edits stay in the existing ADR with a refinement annotation. New ADRs (ADR-009, 010, ...) are reserved for genuinely-new decision spaces.

---

## 4. Cross-version replay

Old port reports (with their pinned `port_translation_rules_version`) can be REPLAYED against a newer rules version to surface what would now be different. Mechanic:

1. Load the old port report.
2. Locate the source spec at the SHA recorded in `port_run.source_spec_sha` (re-fetch from upstream if not cached).
3. Re-run the port skill against the same source, but with the current rules version.
4. Diff the new port report against the old. Surface deltas: rules now applied that weren't, rules now skipped that were applied, R5 check state changes, etc.

Cross-version replay is a Phase F tool, not a port-skill responsibility. Implementation lives at `scripts/replay-port.py` (future).

---

## 5. Reflection-loop output: pull requests

The reflection loop's output is one or more PRs against THIS repository (`prebid-agent-skills`). PR shape:

- One PR per fix category (taxonomy update vs rule amendment vs SKILL edit) — keeps reviews focused.
- The PR description cites the triggering port report run_id(s) and the matrix row from §2 that classifies the fix.
- The PR includes any necessary version bumps (taxonomy MINOR for novel quirk; rules PATCH/MINOR depending on category).
- CHANGELOG.md entries are part of every PR.

The reflection loop does NOT auto-merge. Human review of the proposed amendments remains in the loop. Phase F's value is in the structured proposal, not in unattended merging.

---

## 6. Failure modes

| Failure mode | Detection | Response |
|---|---|---|
| Source spec SHA changed since port ran | `port_run.source_spec_sha` mismatches re-fetched current SHA | Skip cross-version replay; surface to operator that the source has drifted. The old port report still has historical value but the replay would be apples-to-oranges. |
| Port report references a deleted bidder | `meta.bidder_name` no longer in upstream | Mark the report as historical-only. Don't propose amendments based on a bidder that's been removed. |
| Two reflection runs propose contradictory amendments | Same triage matrix row produces opposite fixes for different bidders | The PR descriptions cross-reference each other; human review resolves. The reflection loop does not auto-resolve. |
| Triage matrix row is novel — not yet covered | An issue surfaces that doesn't fit any matrix row | Phase F authors a NEW matrix row (in this doc) and proposes an ADR documenting the new fix-category. Self-bootstrapping. |

---

## Sources

- [`port-skills-design.md`](port-skills-design.md) — Phase D produces the port reports Phase F consumes.
- [`port-report.schema.json`](../../prebid-server-go/read/skills/shared/port-report.schema.json) — the data Phase F reads.
- [`schema-versioning.md`](schema-versioning.md) — what triggers MINOR vs PATCH bumps on the three artifacts.
- [`end-to-end-flow.md`](end-to-end-flow.md) — Teal flow integration: how reflection plugs into the read → port → review → reflect cycle.
- ADR amendment precedent: [`docs/decisions/005-rule-46-naming-convention-normalization.md`](../decisions/005-rule-46-naming-convention-normalization.md), [`006-rule-43-sub-categorization.md`](../decisions/006-rule-43-sub-categorization.md), [`007-novel-pattern-schema-additions.md`](../decisions/007-novel-pattern-schema-additions.md) — all carry refinement annotations from prior audits.
