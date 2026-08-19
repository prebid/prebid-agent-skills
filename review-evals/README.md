# review-evals — measuring what the review skills actually catch

Every other gate in this repository detects **absence** (a check was never
written) or **staleness** (a check drifted from upstream). None of them can
detect a **calibration error**: a check that is present, runs, reaches a
finding, and then rates or dismisses it wrongly.

That is the failure that produced this harness. On
[prebid/prebid-server#4765](https://github.com/prebid/prebid-server/pull/4765)
the skills did not miss most of the maintainers' findings. They *saw* them and
dispositioned them toward source-fidelity ("the Java original defaults to
banner") and toward "more artifacts = higher quality". Recall was fine.
Severity was wrong. A gate that only counts checks cannot see that.

This harness scores a review run against what real maintainers actually said,
finding by finding, with severity as a first-class metric.

```
scripts/score_review_evals.py   the scorer          (offline, hermetic)
review-evals/capture_fixture.py the fixture capture (the only networked part)
review-evals/fixtures/          the corpus
review-evals/baseline.yaml      committed floors
review-evals/actual/            where you put a run's output
scripts/tests/test_score_review_evals.py   self-tests for the scorer
```

---

## The four dispositions

An actual finding lands in exactly one of these, in this order:

| class | what it means | counts toward |
|---|---|---|
| `expected` | a maintainer raised it on that PR | recall |
| `forbidden` | a maintainer ruled it out. `forbidden_at_or_above: WARN` forbids only a blocking verdict, leaving a note tolerated | a hard false positive |
| `additional` | this repo's own documented rules require it and no maintainer raised it on that PR. Each entry MUST cite the rule in `rule:` | nothing; reported |
| `unexpected` | the residual | the false-positive ceiling |

`additional` exists because the ceiling was measuring the wrong thing. On
`prebid-server-4765` all ten findings scored as unexpected cited a rule that exists
in the skills — the alias-GVL rule, the two re-validation anti-patterns, the
destructive-clobber rule — so the gate was penalising the suite for finding true
things the maintainers did not. A review assistant exceeding the human review is the
point, not a defect.

The `rule:` citation is what separates classifying a finding from raising the
ceiling. An entry without one is an instrument error, not a pass.

`additional` describes what a correct review MAY report, never what it must: an
unreported `additional` entry does not reduce recall. Only `expected` does.

### Two rules the classification has to follow

**Neutralisation wins.** The order is neutralised, then additional, then unexpected.
"The rule did not exist yet" is a stronger statement than "documented and unraised",
so an `additional` entry must not claim an epoch-exempt finding and take it out of
the neutralised report. Writing `prebid-server-java-4428`'s entries produced exactly
that error before the order was fixed.

**Severity direction decides borderline cases.** A finding rated *below* its
sanctioned severity is still `additional` — the subject is right and
`severity_agreement` records the gap. A finding rated *above* it is not, because the
over-rating is the harm: a blocking comment where a note is sanctioned. Three
findings on `prebid-server-4287` stay `unexpected` for that reason or because the
rule they name explicitly excludes them:

- a supplemental-coverage absence reported at WARN where the rule says "as a single
  INFO … never as a FAIL";
- a test-runner endpoint literal, where the reference is explicit that "a
  test-runner endpoint is not a finding at any severity";
- a 204 fixture with no expected errors, where the rule says "Do NOT flag a fixture
  asserting graceful degradation … This covers HTTP 204 / no-content".

All three quote pre-calibration wording, so the recorded run predates the
re-scoping now in the skills. A citation must match the rule **as currently
scoped**, not merely name it.

## The corpus

Nine fixtures. Six Go, three Java; six carry defects a maintainer raised, three
are PRs where the correct outcome is no blocking finding.

| Fixture | Repo |
|---|---|
| `prebid-server-4765` | prebid/prebid-server |
| `prebid-server-4287` | prebid/prebid-server |
| `prebid-server-4614` | prebid/prebid-server |
| `prebid-server-4502` | prebid/prebid-server |
| `prebid-server-4216` | prebid/prebid-server |
| `prebid-server-4211` | prebid/prebid-server |
| `prebid-server-4651` | prebid/prebid-server |
| `prebid-server-java-4552` | prebid/prebid-server-java |
| `prebid-server-java-4428` | prebid/prebid-server-java |

Which fixtures carry which defects, how many findings each expects, and which
check families they cover live in [`CORPUS.md`](CORPUS.md) — **do not read it
while recording a run.** Both of the first two recorded runs reported that this
README had already told them the family vocabulary and the per-fixture counts
before they scanned a single file, which is contamination by the document that
is required reading. It does not do that any more.

### Forbidden findings are the point of the clean fixtures

Recall alone rewards a reviewer that flags everything. A `forbidden` entry records
a verdict the maintainers explicitly ruled out, in writing, on that PR -- a
construct someone raised in review and the repo adjudicated as acceptable, then
merged unchanged. A run that re-raises it is not being thorough; it is
relitigating a settled question at the author's expense.

The ceiling is 0 and it is enforced from day one, unlike the recall floor.

> The specific verdicts are deliberately NOT listed here. This file is required
> reading for anyone producing a run, so anything it names is disclosed to the
> thing being measured. The entries live in each fixture's `expected.yaml`, which
> a run must not read. If you are recording a run, stop at this paragraph -- you
> have everything you need from `## Output format` below.

## How to capture a new fixture

1. **Find the review SHA.** Not the head — the commit the finding was raised
   against.

   ```bash
   gh api --paginate repos/prebid/prebid-server/pulls/4765/comments \
     --jq '.[] | [.user.login, .created_at[0:10], .original_commit_id, .path] | @tsv'
   ```

2. **Capture.**

   ```bash
   python3 review-evals/capture_fixture.py \
     --repo prebid/prebid-server --pr 4765 \
     --review-sha 6367a39cc3118e21f57642a53912d9c096591ae8 \
     --outcome defective --language go
   ```

   Writes `meta.yaml` and `files.json`. Never writes `expected.yaml`.

3. **Hand-author `expected.yaml`.** Every entry needs `id`, `path`, `anchor`,
   `family`, `severity`, `source`, `why_it_matters`. The `source` must be a
   real review-comment URL or a real merged-diff fact. **Do not invent
   maintainer findings.** If a PR's threads are thin, a smaller honest corpus
   beats a padded one — `prebid-server-4502` carries two findings and earns its
   place by isolating one check family.

   Use `anchor: "<file>"` when the finding is about a file's existence rather
   than a line in it (a non-canonical artifact, a redundant fixture, a bidder
   name). File-level entries match on `(path, family)`, so both sides must
   carry a family.

4. **Validate.** This is not optional: a fixture whose anchor does not occur in
   its own captured patch is unscorable, because no reviewer could reach that
   finding from the snapshot.

   ```bash
   python3 review-evals/capture_fixture.py --validate prebid-server-4765
   python3 scripts/score_review_evals.py --validate-only     # whole corpus
   ```

5. **Add a floor** for the new fixture in `baseline.yaml`. A fixture with no
   entry is scored against the global defaults silently; a self-test fails if
   one is missing.

---

## How to produce an actual-findings file

1. Run the review skills against the **snapshot**, not the live PR:
   `review-evals/fixtures/<id>/files.json` is the file list with patches that
   `pr-triage` would otherwise fetch. Feeding it the live PR defeats the point
   — the live head is the fixed state, and the run stops being reproducible.

2. Transcribe what the skills emitted into
   `review-evals/actual/<fixture-id>.yaml`, following
   `review-evals/actual/TEMPLATE.yaml`. Transcribe, do not curate: a file
   edited to match `expected.yaml` measures your editing.

3. Three keys are load-bearing:

   - `files_scanned` — **required**. The run's scan set. `0` is an ERROR, not a
     clean verdict. A detector's scan set is part of its claim, so a review
     that examined nothing has cleared nothing.
   - `findings` — **required, may be empty**. `findings: []` asserts the run
     looked and found nothing. Omitting the key is an ERROR: absent is not
     empty.
   - `anchor` — a symbol or a quoted line, **never a line number**. The matcher
     never reads one.

4. Score:

   ```bash
   python3 scripts/score_review_evals.py \
     --actual review-evals/actual \
     --json scripts/output/review-evals.json
   ```

   Add `--fixture <id>` (repeatable) to score a subset.

---

## How to read a score

```
fixture                    out        exp  hit  recall  forb  unexp     sev      scan
prebid-server-4765         defective   12    9   75.0%     0      2   66.7%  27/27
```

| Column | Meaning |
|---|---|
| `exp` / `hit` | expected findings, and how many the run reproduced |
| `recall` | `hit / exp`. `n/a` on a fixture with no expected findings |
| `forb` | findings matching a **named non-finding**. A hard false positive: the run reached a verdict the maintainers ruled out in writing. Ceiling is 0 everywhere and it is not negotiable |
| `unexp` | findings matching neither list. A drift alarm, not a correctness claim — an extra INFO note is not automatically wrong. Read them; they are printed individually |
| `sev` | of the matched findings, the share rated at the maintainer's severity. **Under-rating is the calibration failure**, and it is reported separately from over-rating |
| `scan` | `files_scanned / files in fixture`. A partial scan is annotated, not silently accepted |

Then the per-family breakdown, which is where a regression is legible: a drop
concentrated in one family points at one check, a drop spread across families
points at routing or triage.

**Recall at 100% with severity agreement at 60% is the #4765 signature.** The
run found everything and rated it too low. That combination is the specific
thing this harness exists to catch, and a recall-only gate is blind to it.

Exit codes are three-valued on purpose, so CI can tell a regression from a
harness that never ran:

| Code | Meaning |
|---|---|
| `0` | every committed floor met |
| `1` | FAIL — recall below a floor, or false positives above a ceiling |
| `2` | ERROR — the instrument did not run: missing or empty scan set, unknown fixture, or a fixture whose anchors do not resolve |

---

## The baseline is a floor, not a certification

`baseline.yaml` records "no worse than the last recorded run". Nothing in it
says the skills are good enough.

Two gates are live from day one because they need no measurement:
`max_forbidden_hits: 0` (a named non-finding is already-settled ground) and
`max_unexpected` (a generous per-fixture cap).

`min_recall` and `min_severity_agreement` ship at `0.0` with
`status: unmeasured`, because **no review-skill run has been scored against
this corpus yet**. An unmeasured floor cannot fail, and the scorer prints a
banner saying exactly that, so a green run is never mistaken for evidence.
Record real floors from a run you are prepared to defend:

```bash
python3 scripts/score_review_evals.py --actual review-evals/actual \
    --record-baseline --margin 0.05
```

Commit the `review-evals/actual/` files a floor was recorded from. Lowering a
floor is a decision to accept a regression; it belongs in the PR description
that lowers it, not in a quiet edit.

---

## Testing the instrument

A scorer nobody has tested is worth nothing — it can report 100% recall against
a corpus it never opened.

```bash
python3 -m unittest scripts.tests.test_score_review_evals -v
```

47 tests. Both arms of every gate: a perfect run scores 1.0 **and** a missed
finding goes red; an empty scan set errors **and** an explicitly-empty findings
list with a real scan set passes; a wrong family fails a file-level match
**and** the right family passes.

The suite was mutation-tested: 15 single-line mutations to the scorer — the
empty-scan-set gate, one-to-one assignment, path equality, the short-anchor
guard, each of the four floor comparisons, the anchor-presence validator, the
severity under/over split, the baseline recorder — **all 15 turned the suite
red**, with the test count stable at 47 across every run. Re-run that check
after changing the matcher.

---

## What this harness does NOT prove

Be specific about this. It is a narrow instrument and it is easy to over-read.

1. **It does not prove the skills are good.** It compares one run to nine
   snapshots. A green run means nothing recorded has regressed — not that the
   skills would catch the next adapter's bug.

2. **It does not prove the corpus is representative.** Nine PRs out of hundreds,
   chosen for coverage of distinct check families and for having *legible*
   threads. PRs where maintainers stayed silent, or where the real objection
   happened on Slack or in a docs PR, are invisible here. The corpus is biased
   toward findings someone bothered to write down.

3. **The maintainers are not ground truth, only the best available proxy.** They
   miss things too. `expected.yaml` records what they *said*, not what was
   *true*. A defect nobody caught in review is absent from this corpus by
   construction, and no score here will ever surface it.

4. **`forbidden` is scoped to its own PR.** *"http is permitted"* was settled on
   one PR, at one time, for one adapter shape. It is not a timeless rule, and it
   is not a licence to stop looking at that construct.

5. **It does not measure the skills end to end.** It scores a *transcription* of
   what a run emitted. Routing (did `pr-triage` hand the file to the right
   skill?), prose quality, and whether a finding would actually be actionable to
   an author are all outside it. `files_scanned` is a declaration, not an
   observation — an operator who declares 27 and reviewed 3 is not caught here.

6. **Matching is textual, so it can be gamed.** A run that emits every line of
   the diff as a finding scores high recall. `max_unexpected` and the forbidden
   ceiling push back, but neither is a substitute for reading a red run.

7. **A missed finding is not always a skill defect.** It can be a fixture whose
   anchor is too narrow, or a real disagreement with the maintainer. Diagnose
   before adjusting; and never adjust `expected.yaml` to make a run green —
   that inverts the instrument.

8. **Severity agreement is measured against one repo's merge bar at one point in
   time.** prebid-server Go and prebid-server-java rate the same construct
   differently, and both move.

9. **Nothing here is a merge gate for an actual PR.** It grades the reviewer,
   not the pull request.
