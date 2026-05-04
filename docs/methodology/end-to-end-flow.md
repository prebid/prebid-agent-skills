# End-to-end flow ("Teal flow") — design

The Teal flow is the canonical one-shot orchestration: read a Java adapter spec → port to Go → review the Go PR → reflect findings back to SKILLs / rules / taxonomy / ADRs. Named for the first bidder this flow was designed against (Teal, an alias-only adapter on the Java side that exemplifies the alias-graph inversion port concern).

Status: **proposed design** (Phase D + Phase F not yet started; Phase E review-skill expansion is the runtime). Wave 5 of PR #1 hardening landed the `prior_source_spec` slot and `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` convention to support this flow.

---

## 1. CLI invocations

Run as a single orchestrator command, or as four explicit steps:

### One-shot (orchestrator-driven)

```bash
$ orchestrator full-loop \
    --bidder=teal \
    --source-lang=java \
    --target-lang=go \
    --upstream-pr=https://github.com/prebid/prebid-server-java/pull/4567 \
    --target-branch=feat/teal-go-port

# Behind the scenes the orchestrator runs the four steps and writes
# all transient artifacts to .tmp/full-loop/2026-05-03T1430Z-a3f9/
# (the {run-id} is generated at orchestrator start).
```

### Four explicit steps

```bash
# Step 1 — read the Java source adapter
$ /read-bidder-orchestrator \
    --lang=java --bidder=teal \
    --output=.tmp/full-loop/$RUN_ID/java/teal.yaml

# Step 2 — port to Go
$ /port-java2go \
    --bidder=teal \
    --source-spec=.tmp/full-loop/$RUN_ID/java/teal.yaml \
    --target-branch=feat/teal-go-port \
    --port-report=.tmp/full-loop/$RUN_ID/port-report.json

# Step 3 — review the Go PR (the port skill auto-pushed the branch + opened the PR)
$ FULL_LOOP_RUN_ID=$RUN_ID /pr-triage --pr=https://github.com/prebid/prebid-server/pull/{N}
# pr-triage's Wave 5 prior_source_spec discovery picks up
# .tmp/full-loop/$RUN_ID/java/teal.yaml automatically (resolution tier 3).

# Step 4 — reflection loop
$ /reflect \
    --port-report=.tmp/full-loop/$RUN_ID/port-report.json \
    --review-output=.tmp/full-loop/$RUN_ID/review.json
# Emits proposed PR(s) against prebid-agent-skills.
```

The `$RUN_ID` value is the same `run_id` recorded in `port-report.json::port_run.run_id` and used by `pr-triage`'s `${FULL_LOOP_RUN_ID}` env-var resolution (Wave 5 convention). Format: ISO-like timestamp + short hash, e.g., `2026-05-03T1430Z-a3f9`.

---

## 2. Run-scoped artifact layout

All transient artifacts live under `.tmp/full-loop/{run-id}/` (gitignored — Wave 5 added `.tmp/` to `.gitignore`):

```
.tmp/full-loop/2026-05-03T1430Z-a3f9/
├── java/
│   └── teal.yaml                 # Step 1 output — Java source spec
├── go/
│   └── teal.yaml                 # Step 2 output — destination spec (re-read post-port)
├── port-report.json              # Step 2 output — per port-report.schema.json
├── review.json                   # Step 3 output — pr-triage routing manifest + reviewer findings
└── reflect-proposals/            # Step 4 output — PR drafts
    ├── taxonomy-amendment.diff
    ├── rule-35-clarification.diff
    └── adr-009-draft.md
```

Persisted artifacts (not under `.tmp/`):

- The actual ported code (target-branch on `prebid/prebid-server` clone).
- The PR opened upstream against `prebid/prebid-server`.
- Eventually: PRs opened against `prebid-agent-skills` from the reflect step.

---

## 3. Failure modes

Five documented failure modes. Each has a detected signal, a remediation, and a fix-forward path.

### Failure mode 1 — Java spec extraction failure (Step 1)

**Signal**: `read-bidder-orchestrator` exits non-zero, or emits a spec that fails `adapter-spec.schema.json` validation.

**Remediation**: orchestrator surfaces the validation error to the user. The flow halts at Step 1; no port runs.

**Fix-forward**: amend the read-skill (the relevant Java SKILL.md extraction step), re-run from Step 1. The Java SKILL gaps fixed in Wave 4 of PR #1 hardening were detected via this failure mode (the file-role enum mismatch would have caused Step 1 to emit invalid roles, which the new Wave 4 lint catches before write-out).

### Failure mode 2 — Port skill produces R5-strict fail (Step 2)

**Signal**: `port-report.json::r5_check.state == "fail-semantic-divergence"`.

**Remediation**: port skill STILL ships its artifacts (per the design — semantic divergences are often KNOWN upstream bugs, see aax minLength). `human_todos[]` populates with category `upstream-confirmation`. The flow continues to Step 3.

**Fix-forward**: in Step 4 reflection, route the divergence to the matrix row "R5 semantic divergence — upstream PR" (per `reflection-loop.md` §2). File the upstream fix; update the dual-spec assertion file with `severity: fail` if not already.

### Failure mode 3 — pr-triage finds prior_source_spec missing (Step 3)

**Signal**: `pr-triage` runs but doesn't emit a `--- PRIOR SOURCE SPEC COMPARISON ---` block because it couldn't resolve the spec.

**Remediation**: orchestrator MUST set `${FULL_LOOP_RUN_ID}` env-var so `pr-triage`'s Wave 5 tier-3 discovery resolves `.tmp/full-loop/$RUN_ID/java/teal.yaml`. If that resolution fails (env-var unset, or file missing), `pr-triage` proceeds without the cross-language comparison and the manifest documents `prior_source_spec not present — section omitted`.

**Fix-forward**: orchestrator sets the env-var. If the file is genuinely missing (Step 1 didn't write it), Step 1 has a bug — see Failure mode 1.

### Failure mode 4 — Port report references rules version newer than current (Step 4)

**Signal**: `port-report.json::port_translation_rules_version` is greater than the version in the current `port-translation-rules.yaml`. Possible if the port ran on a feature branch with version-bumped rules and the reflection loop runs on main.

**Remediation**: `reflect` warns and skips the run (cross-version replay is meaningful only when rules ≥ port_report's version, not when rules < port_report's version). 

**Fix-forward**: rebase the reflection branch onto the rules-version-bump commit. Or wait for the rules version to land on main. Or use `--ignore-version-check` to force the replay (lossy — the rule set has gaps).

### Failure mode 5 — Reflection proposes a taxonomy amendment that conflicts with an in-flight port

**Signal**: Two parallel Teal-flow runs both produce reflection proposals that touch the same `behavior-taxonomy.yaml` `quirks_taxa[]` entry — one wants to amend description, the other wants to add a sibling.

**Remediation**: the second `reflect` run detects the conflict via git pre-PR diff and surfaces both proposals to the operator. No auto-merge.

**Fix-forward**: human review resolves the conflict. One PR lands first; the second rebases onto it.

---

## 4. The success path: Teal in a single sentence

> Run `/orchestrator full-loop --bidder=teal --source-lang=java --target-lang=go`, walk away, and an hour later a draft Go PR exists upstream + a draft amendment PR exists in `prebid-agent-skills` capturing what the port revealed.

The "walk away" is aspirational for v1 — the operator should review intermediate artifacts. As confidence builds (rules become more complete; novel-pattern frequency drops), the flow approaches unattended operation, but human review remains in the loop for the upstream PR and for any reflection-proposed amendments.

---

## 5. Why "Teal"?

The Teal adapter (Java-side, alias-only at the time of design) exemplifies several port concerns the flow needs to handle gracefully:

- **Alias graph inversion** — Teal is a Java alias under a parent. Go alias graph differs (Rule 33).
- **Bidder-config YAML idiom** — parent's `aliases: { teal: ~ }` block (Wave 7 documents the correct mechanism vs the incorrect `aliasOf:` claim that was in `new-bid-adapter-prs.md` until it was fixed).
- **Test fixture inventory parity** — Java alias still ships its own integration test class + JSON fixtures (Rule 36). The Go-side translation depends on whether Teal becomes a primary or stays an alias.
- **Naming convention normalization** — if Teal goes through `Rule 46` (camelCase → lowercase), the cross-language YAML names diverge.

Designing the flow against Teal early caught these concerns. Future bidders may add new concerns; the failure-modes section grows as we encounter them.

---

## Sources

- [`port-skills-design.md`](port-skills-design.md) — Phase D port skill design (Step 2).
- [`reflection-loop.md`](reflection-loop.md) — Phase F reflection design (Step 4).
- [`port-report.schema.json`](../../prebid-server-go/read/skills/shared/port-report.schema.json) — port-report contract.
- [`pr-triage` SKILL.md `prior_source_spec` section](../../prebid-server-go/review/skills/pr-triage/SKILL.md) — Step 3 cross-language comparison.
- Wave 5 of PR #1 hardening (commit `efa3de6`) — landed `prior_source_spec` slot, `.tmp/full-loop/{run-id}/{lang}/{bidder}.yaml` convention, and `.gitignore` entry for `.tmp/`.
