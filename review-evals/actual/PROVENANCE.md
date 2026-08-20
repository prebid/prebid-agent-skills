# Recorded runs — provenance and known contamination

These nine files are the FIRST measurement of the review skills against the
corpus, recorded 2026-08-18 against branch `feature/deployed-surface-correctness`
after the review-suite corrections landed.

## Contamination disclosure

Both runs reported, unprompted, that `README.md` had already disclosed part of
the answer key before they reached the fixtures: the per-fixture expected and
forbidden counts, the check-family vocabulary, and three forbidden verdicts. The
README is required reading for the output schema, so the harness was leaking to
every run by construction.

That leak is closed (the characterisation now lives in `CORPUS.md`, which a
runner is told not to open), but these runs predate the fix. Treat their numbers
as a first datapoint, not a floor. `baseline.yaml` therefore stays `unmeasured`;
the next run, recorded against the de-leaked README, is the one that sets it.

A second, unavoidable channel: several checks require verifying a parent bidder
or a prevalence count against upstream, and upstream master shows the MERGED
state — i.e. what the maintainers ended up demanding. Both runs reported
reaching each finding from the skill text first and using upstream only as
confirmation. This channel cannot be closed without pinning every fixture's
verification corpus to its own review SHA.

## What the first run measured

Corpus recall 70% (21/30), one forbidden hit, 38 unexpected findings.

The result worth acting on is `prebid-server-java-4428`: **0 of 4**, with eight
unexpected findings that are individually plausible. Expected and actual do not
near-miss — they are about different things entirely. The maintainers raised a
parse-helper shape, a gpid fallback, a stream idiom and a device-null pattern;
the skills raised an IT fixture placeholder, a schema/POJO mismatch, an error-type
misuse and a dropped currency.

Against the Go corpus the same suites score 91.7% on the Teal PR this program was
built from. The gap is not depth, it is coverage of what Java reviewers actually
raise — consistent with the Java suite having been derived from the Go suite's
architecture rather than from Java review history.

## A third contamination channel, recorded 2026-08-19

The branch that added checks 8 and 9 to `bidder-class-pr-review` (the helper-naming
and redundant-construction classes) was authored by an agent that had read
`prebid-server-java-4428`'s complete `expected.yaml` — all four findings, quoted, with
their discussion URLs — and then wrote checks aimed at those sites. It also read the
full `expected.yaml` of `prebid-server-4765`, `-4287`, `-4614`, `-java-4552`, and the
`forbidden` lists of `-4211`, `-4216`, `-4651`.

**No run was recorded from that session.** A run produced by a reader of the answer
key is not a measurement of the skills, and recording one would have consumed the
one blind pass this corpus has left and set a floor on a number that measured nothing.
`baseline.yaml` stays `unmeasured` for the reason stated above, plus this one.

What that session established instead, by reading the skill text against the
fixture's own captured patch rather than by scoring a run — checkable by anyone,
independent of who wrote the checks:

- **The trigger fires for all four sites.** `Workflow: Private Helper Changed` is
  scoped to "a `private` (or package-private) method on the bidder class is added or
  modified", and all four enclosing methods in the patch are private:
  `tryParseImpExt`, `modifyImpExt`, `bidsFromResponse`, `makeHeaders`.
- **Each site has a step that names its shape.** Check 8 covers the helper name;
  check 9's three bullets cover a builder reproducing its input, a guard for a state
  the path cannot reach, and a local bound once and used once.
- **Text coverage is necessary, not sufficient.** Check 9's bullets require reading
  the method body and its caller, and say so. A reviewer directed to the right method
  may still not reach the finding. Whether the checks fire is what the next blind run
  measures; this establishes only that a reviewer following the skill is pointed at
  each of the four methods, which was not true before.

The next blind run should be performed by a reader who has not opened any fixture's
`expected.yaml` or `CORPUS.md`.
