# Methodology

Durable policy that survives across Phase commits. Each document captures
a slow-changing decision space — versioning, upstream snapshots, rollback —
that consumers and contributors need long after any specific Phase commit
has shipped.

| Document | Purpose | Phase introduced |
|---|---|---|
| [`pr-ingestion.md`](pr-ingestion.md) | `scripts/audit-pr.py` workflow: novelty classification of upstream PRs against existing taxonomy/rules/edge cases. API + manual modes. | Phase 4.2 |
| [`schema-versioning.md`](schema-versioning.md) | SemVer increment rules for the three independently-versioned artifacts (schema, taxonomy, port-rules). What's MAJOR vs MINOR vs PATCH. Migration script protocol. | Phase 4.4 |
| [`repo-rules.md`](repo-rules.md) | Snapshot of upstream `prebid/prebid-server` and `prebid/prebid-server-java` policies the read skills depend on (naming, GVL, fixture structure, default-enabled). With provenance + update cadence. | Phase 4.5 |
| [`rollback.md`](rollback.md) | Per-commit revert-safety guarantees. Fix-forward vs revert policy. The Phase 2.7 migration's irreversibility caveats. | Phase 4.6 |
| [`port-skills-design.md`](port-skills-design.md) | Design for the future Phase D port skills (`port-go2java`, `port-java2go`): pipeline, rule application order, conflict resolution, novel-pattern handling, R5-strict check at port time, port-report output. | Phase D (proposed; design-only in this PR) |
| [`reflection-loop.md`](reflection-loop.md) | Design for the future Phase F reflection loop: triage matrix mapping issue type → fix location, ADR amendment protocol, cross-version replay, output as PRs against this repo. | Phase F (proposed; design-only in this PR) |
| [`end-to-end-flow.md`](end-to-end-flow.md) | The Teal flow: read → port → review → reflect orchestration. CLI invocations, run-scoped artifact layout under `.tmp/full-loop/{run-id}/`, 5 documented failure modes, success-path narrative. | Phase D + E + F integration (proposed) |

Future additions:

- `coverage-protocol.md` — Phase 4.3 coverage report consumption (how to read `docs/coverage-report.md`).

## How to use these docs

When you're about to:

- **Bump a version** (schema, taxonomy, or rules) → consult `schema-versioning.md` for whether your change is MAJOR / MINOR / PATCH and what the CHANGELOG entry must say.
- **Add a new bidder golden or port-translation rule** → consult `repo-rules.md` for the upstream conventions the read skills assume (naming, fixtures, GVL).
- **Revert a recent commit** → consult `rollback.md` for revert-safety + fix-forward guidance.
- **Plan a Phase D port skill** or amend the design → consult `port-skills-design.md` and update via ADR amendment.
- **Run the Teal flow** or interpret a `.tmp/full-loop/{run-id}/port-report.json` → consult `end-to-end-flow.md` for invocations + failure modes; consult `reflection-loop.md` for the triage matrix that turns port findings into amendment PRs.

These docs are deliberately small and prescriptive — they're policy, not
tutorial. The detailed worked examples live in ADRs (`docs/decisions/`) and
the read-skill SKILL.md files; this directory captures only the rules.
