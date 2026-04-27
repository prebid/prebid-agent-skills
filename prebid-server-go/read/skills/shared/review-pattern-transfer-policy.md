# Review-Pattern Transfer Policy

Why review-pattern matchers (per-reviewer fingerprints — "this reviewer always asks for X before approving") MUST NOT be auto-transferred between Go and Java review skills, even though both repos host the same canonical Adapter Specification format. The Phase 2 reconnaissance found that the Go and Java reviewer cohorts are wholly disjoint apart from a single cross-language coordinator. Review patterns are specific to their language's reviewer pool; transferring them is a category error.

This document is the canonical reference for the disjoint-reviewer-cohort finding and the transfer ban it implies. It is consumed by:

- A future Java pr-triage skill (which must NOT auto-import Go pr-triage's reviewer fingerprints).
- A future Go pr-triage skill enhancement (which must NOT incorporate Java reviewer fingerprints if/when Java review skills are authored).
- Cross-language port PR authors (who SHOULD explicitly cc the cross-language coordinator).

---

## 1. The disjoint-reviewer-cohort finding

Phase 2 of the master plan validated the cross-language hypothesis by running 3 parallel reconnaissance subagents against the prebid-server (Go) and prebid-server-java repos. Agent 2 sampled 10 Java new-adapter PRs and recorded their reviewers; Agent 1 cross-referenced against the Go reviewer pool already documented by the existing Go review skills.

The finding was unambiguous: the two reviewer cohorts share exactly one human (`@bretg`). Every other reviewer in each pool is disjoint from the other.

This is structural, not coincidental. The Go pool is staffed by core maintainers who own the Go server runtime; the Java pool is staffed by Magnite engineers who own the Java port. The two repos have different release cadences, different test harnesses, different patches in flight, and different review priorities. A reviewer's fingerprint (the recurring concerns they bring up before approving) reflects their repo's idiosyncrasies, not a transferable pattern.

The Go review skills already encode this fingerprint at the Go-pool level. A Java review skill must encode an entirely separate fingerprint at the Java-pool level. The two are not interchangeable.

---

## 2. Go reviewer cohort

Active reviewers on prebid/prebid-server new-adapter and adapter-modification PRs (sampled via Phase 1 + the existing Go review skills' reference data):

| Reviewer | GitHub handle | Notes |
|---|---|---|
| Brian Sardo | `bsardo` | Core maintainer; primary reviewer on most new-adapter PRs. Author of canonical reviewer comments in PRs #4214, #4592 (test-harness cascade), #4321 (personal-email rejection). Drives the test_json.go architecture. |
| SyntaxNode | `SyntaxNode` | Core maintainer; co-reviews new adapters. Frequent commenter on framework-level changes (macros.EndpointTemplateParams, ptrutil, jsonutil). |
| hhhjort | `hhhjort` | Core maintainer; co-reviews new adapters. Often catches mutation-correctness issues (shallow vs deep copy on Site/App/Source). |
| pm-isha-bharti | `pm-isha-bharti` | Project manager / process reviewer. Drives the one-alias-per-PR rule (PR #4215) and changelog hygiene. |
| Brett (cross-language coordinator) | `bretg` | See §4. The only reviewer who appears in both pools. |

Additional sporadic reviewers appear on specific PRs but are not consistent enough to encode as fingerprint matchers. The Go review skills' shared/framework-utilities.md and bidder-info-pr-review/references/* canonicalize the patterns these reviewers raise (maintainer-email policy, white-label policy, anti-pattern catalog, EndpointTemplateParams 18-field list).

Source: [`prebid-server-go/references/new-bid-adapter-prs.md`](../../../references/new-bid-adapter-prs.md) — canonical list of 89 new-adapter and alias-only PRs with `Patterns Demonstrated` tags. The PRs cite the reviewers directly.

---

## 3. Java reviewer cohort

Active reviewers on prebid/prebid-server-java new-adapter and adapter-modification PRs (sampled via Phase 2's 10-PR Java sample):

| Reviewer | GitHub handle | Notes |
|---|---|---|
| Olena Sulzhenko | `osulzhenko` | Core Magnite reviewer; primary on most new-adapter PRs. |
| Mykola Bodnar | `CTMBNara` | Core Magnite reviewer; co-reviews new adapters. Frequent commenter on Spring DI patterns and `BidderConfigurationProperties` subclass usage. |
| Anton Antokhin | `AntoxaAntoxic` | Core Magnite reviewer; covers proto/POJO patterns (Lombok `@Value @Builder`, `@JsonAlias`, `@JsonDeserialize`). |
| Emil Nadimanov | `EmilNadimanov` | Core Magnite reviewer; covers test infrastructure (Wiremock IT 4-file fixture pattern, per-alias IT classes). |
| Sandro Garbella | `sangarbe` | Core Magnite reviewer; co-reviews new adapters. Frequent commenter on test-application.properties registry hygiene. |
| Brett (cross-language coordinator) | `bretg` | See §4. Sole shared reviewer. |

The dominant Java review theme is **port-fidelity**. Reviewers cite "I don't see that in Go" or "the Go side does this differently" as a blocker. This is unique to Java — Go reviewers do NOT cite Java equivalence (because Java is the port destination, not the source-of-truth).

Source: [`prebid-server-java/references/new-bid-adapter-prs.md`](../../../../prebid-server-java/references/new-bid-adapter-prs.md) — 49 reference PRs with `Patterns Demonstrated` tags. PRs explicitly tagged `port-from-go` (Adverxo #3705, Connatix #3781, Ogury #3788, Kobler #3684, FeedAd #3869, Seedtag #3916, Kueez #3930, Mobkoi #3942, Adagio #4027, Optidigital #4054, Mediasquare #4031, etc.) attract dense port-fidelity review.

---

## 4. The cross-language coordinator: @bretg

`@bretg` (Brett) is the only reviewer active across both repos. His role is structurally unique:

- He coordinates cross-language adapter rollouts (a Go adapter that has a planned Java port).
- He approves spec divergences (e.g., when Java intentionally departs from Go due to framework differences).
- He arbitrates port-fidelity disputes (when a Java reviewer says "I don't see that in Go" but the Go side intentionally varies).
- His review carries authoritative weight on both sides for cross-language port PRs.

Implication for cross-language port PRs:

> When a Go adapter is being ported to Java (or vice versa), the spec's `cross_language.port_lineage.{source_pr, destination_pr}` populates, and the destination PR's author SHOULD explicitly cc `@bretg`. The `cross_language.reviewer_cohort.cross_language_coordinator: bretg` field captures this assignment.

Worked example — Kobler (Go #3904 → Java #3684). Both PRs carry @bretg's review. The Go side approved with `bsardo` and `SyntaxNode`; the Java side approved with `CTMBNara`, `AntoxaAntoxic`, AND `bretg` for cross-language coordination. The spec at [`/Users/quantum/Documents/GitHub/prebid-agent-skills/prebid-server-go/read/test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) records this in `cross_language.reviewer_cohort` and `cross_language.port_lineage`.

@bretg's pattern fingerprints differ between repos. On Go PRs he focuses on adoption-readiness (will this adapter be ported to Java soon?). On Java PRs he focuses on port-fidelity vs. legitimate divergence. Encoding his fingerprint requires per-repo handling — even @bretg's review patterns do NOT transfer cleanly between languages, despite his being the same human.

---

## 5. The transfer ban

**Rule**: Review-pattern matchers MUST NOT be auto-transferred between Go and Java review skills.

A "review-pattern matcher" is any encoding of "this reviewer always asks for X" — for example, `bsardo always asks for the personal-email check on new-adapter maintainer fields`, or `CTMBNara always asks for the `BidderConfigurationProperties` subclass when there are extra YAML fields`. These matchers are useful when the reviewer pool is fixed; they are misleading when the pool changes.

Specifically:

- A Go review skill MAY encode `bsardo`'s personal-email check fingerprint. A Java review skill MUST NOT inherit it — `osulzhenko` does not consistently raise that issue (Java's maintainer email policy differs from Go's).
- A Java review skill MAY encode `EmilNadimanov`'s 4-file IT fixture pattern fingerprint. A Go review skill MUST NOT inherit it — Go has no 4-file IT fixture pattern (Go uses single-file `httpCalls[]` per Rule 36).
- A Java review skill MAY encode the port-fidelity theme. A Go review skill MUST NOT — port-fidelity is asymmetric (Java is the port destination; Go is the source-of-truth).

The ban is structural, not a soft preference. The reviewer cohorts are disjoint; their fingerprints reflect repo-specific concerns; transferring them generates noise, not signal.

### 5.1 What CAN be transferred

The Adapter Specification format is shared. Both languages emit the SAME schema. The 37 port-translation rules apply to both directions. The behavior taxonomy enumerates the same values. These are language-neutral and DO transfer.

What does NOT transfer is the human reviewer fingerprints — the patterns that reflect a specific reviewer's recurring concerns. These are repo-specific.

### 5.2 What about the spec's behavioral findings?

The spec's `cross_language.reviewer_cohort` block records the per-language reviewer pool and the cross-language coordinator. It is read-only context. A consumer (e.g., a future Java pr-triage skill) can READ the field to know who to cc on a PR — it does NOT use the field to import Go reviewer fingerprints.

The spec's `cross_language.port_lineage.fidelity_review_themes[]` records observed Java review themes (port-fidelity, currency-conversion-bidrequest-context, mutation-idiom-tobuilder, dev-endpoint-config-promotion). These are themes specific to the Java port destination and DO NOT translate to Go review themes.

---

## 6. Implications

### 6.1 Java review skills must be authored with Java-specific reviewer fingerprints

The plan's Phase E explicitly defers Java review skills as future work. When they ARE authored, they MUST start from the Java reviewer cohort fingerprints — not from a copy/translate of the Go review skills. Specifically:

- A Java pr-triage skill canonicalizes `osulzhenko`, `CTMBNara`, `AntoxaAntoxic`, `EmilNadimanov`, `sangarbe` patterns — NOT `bsardo`, `SyntaxNode`, `hhhjort` patterns.
- A Java bidder-config-pr-review skill (analog of Go's bidder-info-pr-review) canonicalizes the unified `bidder-config/{xyz}.yaml` patterns — NOT the split `static/bidder-info/{xyz}.yaml` patterns.
- A Java adapter-class-pr-review skill (analog of Go's adapter-code-pr-review) canonicalizes Spring DI + Lombok + Jackson patterns — NOT Go pointer patterns + jsonutil.

The `prebid-server-java/references/new-bid-adapter-prs.md` reference list is the corpus from which Java fingerprints are derived. PRs tagged `port-from-go` are especially load-bearing — they show the dominant port-fidelity theme.

### 6.2 Cross-language port PRs should explicitly cc @bretg

When a port PR ships (Go → Java or Java → Go), the destination PR's author SHOULD explicitly cc `@bretg`. The spec's `cross_language.reviewer_cohort.cross_language_coordinator: bretg` and `cross_language.port_lineage.{source_pr, destination_pr}` capture the lineage; the human action (cc on PR) is the operationalization.

A future Java port-go2java skill MUST surface this in its output PR template:

```markdown
## Port Lineage
- Source PR: prebid/prebid-server#3904 (Kobler, Go)
- Destination PR: this PR
- Cross-language coordinator: @bretg
- Per-language reviewer cohort:
  - Go: @bsardo, @SyntaxNode
  - Java: @CTMBNara, @AntoxaAntoxic
```

The Go pr-triage skill's existing reviewer-feedback parsing (`Step 1d`) already detects the `@bretg` mention pattern. A Java analog must do the same on the Java PR.

### 6.3 Port-fidelity is the #1 Java review theme

Phase 2 quantified this: across the 10 Java PR sample, the most-cited reviewer comment theme was port-fidelity — "this differs from the Go implementation in ways that aren't justified" or "the Go side has X; this PR doesn't". The themes appear under `cross_language.port_lineage.fidelity_review_themes[]` per spec.

Java review skills should weight this theme heavily — heavier than any single theme weighted in Go review skills. A Java pr-triage that encodes port-fidelity as a top-priority concern (alongside framework-utility usage and reviewer-fingerprint dedup) will produce more accurate triage manifests than one that imports Go's theme weighting.

Go review skills should NOT mirror this — Go does not have a port-fidelity concern (Go is the source-of-truth that Java ports follow). A Go pr-triage that imports a port-fidelity theme would generate false-positives.

### 6.4 The existing Go review skills are the reference implementation, not the template

The completed Go review skills under `prebid-server-go/review/skills/` are the reference implementation for Go-only review. They canonicalize the Go reviewer cohort's fingerprints. They are NOT a template for cross-language transfer. A Java skill author should consult them for ARCHITECTURE (single-pass file fetch in pr-triage; per-domain skills with shared framework-utilities; routing manifest as single source of truth) but MUST start with Java-specific patterns from scratch.

---

## 7. Validation: dual-spec assertions catch fidelity violations

The cross-language R5 rule (cross-language structural parity for port pairs) is the spec-level enforcement of port-fidelity. It is independent of human reviewers — a `bidder_params_sha256` mismatch is a port-fidelity violation regardless of which reviewer flagged it.

Worked example — Optidigital, Appnexus. Both port pairs FAIL R5 due to whitespace divergence in the bidder-params JSON. The spec records the failure as a `cross-language-params-sha-divergence` warning. A reviewer (typically a Java reviewer, sometimes @bretg) is expected to flag this and request reformatting.

But human reviewers don't always catch byte-level divergence. The `read/` orchestrator's R5 check is automatic and deterministic. This complements the human review process — it does NOT replace reviewer fingerprint matching.

A future port-go2java skill output must include the R5 check result in its generated PR description, so reviewers don't have to re-run the read manually. A Go pr-triage analog can do the same when invoked on a port pair (loads both specs as `prior_spec` and `paired_spec` and flags the divergence).

---

## 8. What this policy does NOT cover

- **The reviewer cohorts are not stable in practice.** Reviewers join and leave; the cohort lists in §2 and §3 are accurate as of Phase 2 (April 2026) but will drift. A skill that encodes reviewer fingerprints MUST refresh against the live cohort periodically. The reference lists at `prebid-server-go/references/new-bid-adapter-prs.md` and `prebid-server-java/references/new-bid-adapter-prs.md` are the canonical corpus to refresh from.
- **Process reviewers (e.g., `pm-isha-bharti`) have separate fingerprints from technical reviewers.** Process fingerprints (one-alias-per-PR rule, changelog hygiene, docs PR linkage) ALSO do not transfer. Java has a different process reviewer pool (or no dedicated process reviewer at all in some periods).
- **The cross-language coordinator role is not transferable to a successor.** If `@bretg` rotates off, the cross-language coordinator field MUST be re-determined empirically (sample dual-language reviewer overlap). A skill MUST NOT default to a successor without explicit verification.
- **The ban applies to AUTOMATED transfer.** A human cross-skill author who knowledgeably translates a Go pattern into a Java equivalent (recognizing the per-language idiom differences) is fine. The ban targets blind copy/paste of fingerprint patterns by automation or by a human who hasn't recognized the cohort disjointness.

---

## 9. Summary

The Go and Java reviewer cohorts are wholly disjoint apart from `@bretg`. Review-pattern matchers (per-reviewer fingerprints) MUST NOT be auto-transferred between languages — the patterns reflect repo-specific concerns. Port-fidelity is the dominant Java review theme and does NOT transfer to Go. Cross-language port PRs SHOULD cc `@bretg`, and the spec's `cross_language.reviewer_cohort.cross_language_coordinator` field captures this. Java review skills, when authored, MUST start from the Java cohort fingerprints, NOT from a translation of the Go review skills.

The Adapter Specification format itself, the 37 port-translation rules, and the behavior taxonomy ARE shared — those are language-neutral. Reviewer fingerprints are not.

---

## Sources

- Master plan: `/Users/quantum/.claude/plans/you-are-right-lets-mighty-wombat.md` — Phase 2 reconnaissance findings (cross-language reviewer cohort disjointness; port-fidelity as #1 Java review theme), Phase E section "Document the review-pattern transfer ban".
- Go reference list: [`../../../references/new-bid-adapter-prs.md`](../../../references/new-bid-adapter-prs.md) — 89 PRs with reviewer attribution; canonical Go cohort corpus.
- Java reference list: [`../../../../prebid-server-java/references/new-bid-adapter-prs.md`](../../../../prebid-server-java/references/new-bid-adapter-prs.md) — 49 PRs with `Patterns Demonstrated` tags; `port-from-go` tag identifies port pairs.
- Spec schema: [`adapter-spec.md`](adapter-spec.md) — `cross_language.reviewer_cohort.{go, java, cross_language_coordinator}` field definitions; `port_lineage.fidelity_review_themes[]`.
- Cross-skill integration: [`cross-skill-integration.md`](cross-skill-integration.md) — section §8.4 references this policy as the authority on cohort disjointness.
- Existing Go review skills: [`../../../review/skills/`](../../../review/skills/) — reference implementation of Go-pool fingerprints; NOT a template for Java.
- Worked example specs: [`../../test-fixtures/kobler.golden.spec.yaml`](../../test-fixtures/kobler.golden.spec.yaml) (Go-source Kobler with `cross_language.reviewer_cohort` populated), [`../../../../prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml`](../../../../prebid-server-java/read/test-fixtures/kobler.golden.spec.yaml) (Java-source Kobler with same cohort + cross-language coordinator).
- Phase 2 subagent findings (in master plan): Agent 2's 10-PR Java sample (CTMBNara, AntoxaAntoxic, EmilNadimanov, sangarbe, osulzhenko); Agent 1's Go cohort (bsardo, SyntaxNode, hhhjort); confirmation of `@bretg` as sole cross-language reviewer.
