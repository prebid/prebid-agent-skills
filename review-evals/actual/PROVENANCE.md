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
