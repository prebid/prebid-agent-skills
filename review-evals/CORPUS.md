# Corpus characterisation — answer key

**Do not read this while recording a run.** It names, per fixture, how many
findings are expected, how many verdicts are forbidden, and which check families
are in play. A run that has seen this is measuring its own memory.

It exists because that information was previously in `README.md`, which a runner
must read for the output schema — so the harness was disclosing its own answers
to every run. Both of the first two recorded runs flagged it independently.

Read this when you are curating the corpus, reviewing a score, or deciding what
to capture next. Not when you are producing `review-evals/actual/`.

---

Nine fixtures, 30 expected findings, 6 named non-findings.


| Fixture | Lang | Outcome | Expected | Forbidden | Check families |
|---|---|---|---|---|---|
| `prebid-server-4765` | Go | defective | 12 | — | bid-type-resolution, mediatype-config-drift, request-mutation, error-handling, stdlib-idiom, canonical-artifacts, pr-scope, perf |
| `prebid-server-java-4552` | Java | defective | 3 | — | framework-idiom, upstream-api-drift |
| `prebid-server-4287` | Go | defective | 4 | — | framework-idiom, test-coverage, bid-type-resolution |
| `prebid-server-4614` | Go | defective | 4 | — | error-handling, test-coverage |
| `prebid-server-java-4428` | Java | defective | 4 | — | naming-conventions, framework-idiom, error-handling |
| `prebid-server-4502` | Go | defective | 2 | — | endpoint-config |
| `prebid-server-4216` | Go | clean | 1 | 1 | maintainer-metadata / naming-conventions |
| `prebid-server-4211` | Go | clean | 0 | 2 | endpoint-config, naming-conventions |
| `prebid-server-4651` | Go | clean | 0 | 3 | endpoint-config, maintainer-metadata, pr-scope |

`outcome: clean` means **no blocking finding is correct** — not that the PR was
silent. `prebid-server-4216` carries one non-blocking INFO and one forbidden
verdict on the same three-line file, so a reviewer cannot score well on it by
saying nothing *or* by flagging everything.


### Forbidden verdicts, by fixture

Each is a construct raised in review on that PR and adjudicated acceptable, then
merged unchanged:

- `prebid-server-4211` — the `http://` endpoint scheme, and an underscore in the
  bidder name. Both raised, both permitted.
- `prebid-server-4216` — the six-character prefix collision with the parent it
  aliases, raised and waived in the same comment.
- `prebid-server-4651` — the five-alias bundle as a single PR, the `http://`
  scheme, and the aliases inheriting the parent's maintainer email.

`prebid-server-4651`'s pr-scope entry is deliberately in tension with
`prebid-server-4765`'s alias finding: one is an alias bundle shipped alone, the
other an alias riding along with a brand-new adapter. A run that cannot tell
those apart fails one or the other.

---

## Rule epochs

The skills are pinned to current upstream master; these fixtures are historical.
A rule can be correct today and an anachronism against a PR reviewed before the
upstream change that created it.

`rule-epochs.yaml` records, per rule family, the date its upstream fact became
true. For a fixture whose `epoch` (in `meta.yaml`) is earlier, findings in that
family are neutralised: they count neither toward recall nor against the
unexpected ceiling, and the score reports them separately with the upstream PR
that granted the exemption.

Two entries today, both Java, both from July 2026 — the `UsersyncerCreator`
deletion and the `UriTemplate` macro migration. `prebid-server-java-4428` was
reviewed in March, so a literal application of the pinned rules would fault it
for an API that still existed and a macro form that was still correct.

This is not an amnesty for misses. It covers only findings that COULD NOT have
been raised, because the fact they rest on did not exist yet. A rule with no
entry applies to every fixture, and a miss against it is a real miss — the
`test_rule_older_than_fixture_still_applies` case pins that arm.

Every future upstream migration makes today's fixtures anachronistic in turn, so
expect this file to grow. If you cannot name the PR that changed a fact, the rule
is not epoch-sensitive.
