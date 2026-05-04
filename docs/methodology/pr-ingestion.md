# PR ingestion workflow

How upstream `prebid/prebid-server` and `prebid/prebid-server-java` PRs
flow into this repo's taxonomy + rules + edge-case catalog.

The bottleneck is **novelty classification** — deciding whether a PR
introduces a behavioral, structural, or port-translation pattern that
isn't yet captured in our existing artifacts. Phase 4.2 ships
`scripts/audit-pr.py` as the standard tool.

## Workflow

### 1. Identify candidate PRs

The `prebid-server-{go,java}/references/new-bid-adapter-prs.md` files
maintain a curated list of PRs worth ingesting (new adapter PRs,
parent-rebrand events, alias migrations, novel patterns). Maintainers
add to this list when they notice an upstream PR that warrants attention.

For routine drift (an adapter's endpoint URL changes, a new alias is
added under an existing parent), the **weekly sync** job
(`scripts/sync-from-upstream.py` per Phase 4.1) catches it without
human review. PR audit is for the cases that don't reduce to byte-fact
comparison.

### 2. Run the audit

```sh
# API mode (preferred):
export CLAUDE_API_KEY=sk-ant-...
python3 scripts/audit-pr.py https://github.com/prebid/prebid-server/pull/4639

# OR via Make:
make audit-pr URL=https://github.com/prebid/prebid-server/pull/4639
```

The script:

1. Parses the PR URL and fetches the diff via `gh pr view + gh pr diff`
   (requires `gh` installed and authed).
2. Loads the current taxonomy taxa (50+), port-translation rules (46),
   and Java edge-case catalog (#18–#34).
3. Builds a prompt asking Claude to classify novelty against those.
4. Calls the Anthropic Messages API (when `CLAUDE_API_KEY` is set);
   otherwise writes the prompt to disk for manual paste-into-Claude
   workflow.
5. Writes structured findings to `scripts/output/audit-<PR-NUMBER>.json`
   and a human summary to `scripts/output/audit-<PR-NUMBER>.md`.

### 3. Read the verdict

The script's exit code signals novelty:

- `0` — no novelty detected. The PR matches existing taxa/rules/edge cases. Action: tag the PR in `references/new-bid-adapter-prs.md` with the matching `Patterns Demonstrated` tags.
- `2` — novelty detected (informational). Action: see step 4.

### 4. (If novel) Open a follow-up PR

The audit's JSON output includes a `novel_pattern_proposal` block when
`verdict: novel-pattern`. The proposal has:

- `name` — short kebab-case identifier for the new pattern.
- `description` — one-paragraph definition.
- `extends_existing` — closest existing taxon/rule/edge case (or null).
- `proposed_artifact` — `taxon` | `rule` | `edge_case`.
- `rationale_for_promotion` — why this needs its own entry.

Open a PR adding the proposed entry:

| If `proposed_artifact` is | Edit |
|---|---|
| `taxon` | `prebid-server-go/read/skills/shared/behavior-taxonomy.yaml`'s `quirks_taxa` array; re-render with `make render-taxonomy`. |
| `rule` | `prebid-server-go/read/skills/shared/port-translation-rules.yaml`'s appropriate `sections[].rules[]`; re-render with `make render-port-rules`; bump `rules_version`. |
| `edge_case` | `prebid-server-java/references/java-edge-cases.md`'s table; bump the next-available number (#35, #36, ...). |

Each PR adding new artifacts MUST cite the source upstream PR URL in the
commit message, and reference the audit-pr verdict's rationale.

### 5. Update the references file

Append the upstream PR to `prebid-server-{go,java}/references/new-bid-adapter-prs.md`
with the matching `Patterns Demonstrated` tags. This keeps the master
list current and feeds future audit runs (the audit prompt loads the
references file).

## Modes

### API mode (default with key)

`CLAUDE_API_KEY` set → script calls Anthropic Messages API directly via
`urllib.request` (no SDK dependency). Default model is the latest Opus
(`claude-opus-4-7`); override with `--model=...`.

### Manual mode (no key)

`CLAUDE_API_KEY` unset → script writes the prompt to
`scripts/output/audit-<N>.prompt.txt` and prints instructions to paste
the prompt into Claude.ai or claude-code. Save Claude's JSON response,
then re-run the script with `--manual-answer=path/to/response.txt` to
render the report.

### Print-only mode (no Claude at all)

`--print-prompt` writes the prompt to disk AND prints it to stdout, then
exits. Useful for debugging the prompt construction or for offline
review.

## CI integration

The audit is **NOT** CI-blocking and **NOT** on the default `make ci`
path. Reasons:

- Each invocation costs an Anthropic API request (or a manual round-trip).
- False-positive novelty classification is acceptable if it surfaces a
  pattern worth a human read; false-negative is also acceptable
  (catchable later via sync-from-upstream's structural diffs).
- The audit's value is human-in-the-loop, not gate-keeping.

The Makefile target `make audit-pr URL=...` runs the audit on demand.
The optional GitHub Actions job in
`.github/workflows/upstream-sync.yml` (Phase 4.7) MAY add an audit-pr
step gated on a PR-comment trigger, but is out of scope for Phase 4.2.

## Limitations + caveats

- **`gh` dependency**: the script shells out to `gh pr view` and
  `gh pr diff`. Without `gh` installed and authed (e.g., via `gh auth
  login`), the script fails with a clear error.
- **Diff truncation**: very large PRs (10000+ char diffs) are truncated
  in the prompt to keep the API request size reasonable. The maintainer
  may want to manually invoke for those cases with the full diff
  pasted.
- **Cost awareness**: each audit-pr API call is roughly 4–8K tokens of
  prompt + ~1–2K tokens of response. Run on demand, not per PR.
- **Quality bound**: novelty classification has a tail of ambiguous
  cases. Treat the verdict as a recommendation, not a decree. Maintainers
  override when needed.

## Sources

- ADR-007 (novel pattern fields F1–F5): the most recent batch of
  novelty additions came from Round 3 reconnaissance — that was a manual,
  multi-day analysis. The audit-pr.py script is the durable
  one-PR-at-a-time replacement for that ad-hoc workflow.
- ADR-008: Phase 5 fixture priorities — the audit-pr verdict on each
  Phase 5 candidate PR informs whether it gets a golden + dual-spec
  pair.
- `prebid-server-{go,java}/references/new-bid-adapter-prs.md`: the
  curated PR list audit-pr loads as the reference frame.
