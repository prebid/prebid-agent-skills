# Review-Pattern Transfer Policy

Why review-pattern matchers — encodings of "reviewers on this repo always ask for X" — MUST NOT be auto-transferred between the Go and Java review skills, even though both repos host the same canonical Adapter Specification format.

This document is the canonical reference for the transfer ban. It is consumed by:

- The Go review suite (`prebid-server-go/review/skills/`), which must not import Java-derived expectations.
- The Java review suite (`prebid-server-java/review/skills/`), which must not import Go-derived expectations.
- Cross-language port PR authors, who need to know which conventions carry across a port and which do not.

---

## 1. The ban

**Rule**: a review expectation derived from one repo's review history MUST NOT be applied to the other repo's PRs without independent evidence from that repo.

The two servers are different programs. They differ in framework (net/http + `adapters.Bidder` vs Vert.x + Spring DI + Lombok), in test harness (JSON fixture corpus vs JUnit + Wiremock 4-file IT), in style enforcement (`gofmt -s` + `go vet` vs a 70-module checkstyle ruleset bound to the `validate` phase), in release cadence, and in what their CI actually blocks on. A convention that a reviewer raises in one repo is evidence about that repo's merge bar and nothing else.

This is structural, so it does not decay. Concretely:

- A Go-side maintainer-email convention is evidence for Go only; the Java bidder-config `meta-info.maintainer-email` field has its own constraints (`@NotBlank`, enforced at bind time).
- A Java-side 4-file IT fixture expectation cannot apply to Go, which has no such artifact (Rule 36: Go uses a single flat `httpCalls[]` fixture).
- A port-fidelity expectation ("this differs from the other language's implementation without justification") is asymmetric by construction — see §3.

### 1.1 What DOES transfer

The language-neutral layer transfers freely, because it is one artifact consumed by both sides:

- The Adapter Specification schema and the behavior taxonomy — both languages emit the same shape and the same enumerated values.
- The port-translation rules, which are bidirectional by definition.
- **Framework-agnostic defect classes.** A defect that is about program behavior rather than repo convention — a silent bid-type fallback that mis-types a bid, a destructive overwrite of caller-owned JSON, a request-level value derived from the first valid impression while divergent siblings are ignored — is a real defect in both languages. When one suite gains such a check, the other should gain it or record why the class cannot occur there. The ban is about *whose review history justifies a check*, not about whether a defect class is real.

### 1.2 What does NOT transfer

- Per-repo process conventions (PR splitting rules, changelog hygiene, label requirements, docs-PR linkage).
- Framework-shaped expectations (Spring DI wiring, Lombok annotation choice, `gofmt` grouping, checkstyle module behavior).
- Severity calibration. The same finding can be blocking in one repo and a nit in the other, because the merge bars differ.

---

## 2. Do not encode reviewer identity

Review skills MUST NOT key checks on individual reviewer names, and MUST NOT maintain rosters of who reviews what.

Rosters rot silently. A skill that says "this reviewer always asks for X" keeps asserting it after that person stops reviewing, and stays silent about whoever replaced them — so the skill's confidence is highest exactly where its evidence is weakest. Worse, a name in a review comment is an unfalsifiable appeal: the author cannot check it, and the reviewer it names never agreed to it.

Anchor a check to something checkable instead:

1. **Upstream source or config** — the strongest anchor. `config/bidderinfo.go:461` rejects `whiteLabelOnly` on an alias; that is true regardless of who reviews the PR.
2. **A merged PR** — cite the PR number and what the merged diff shows. If the point is that a convention was requested during review, quote the requirement, not the requester.
3. **A corpus count** — "N of M upstream adapters do X", with the command that regenerates it and the commit it was run at.

Where an existing check quotes review discussion, keep the technical content and the PR anchor and drop the attribution. The evidence is the PR; the name adds nothing a contributor can verify.

> **Spec-field note.** `cross_language.reviewer_cohort` is gone. It held upstream maintainers' GitHub usernames, it was already inert, and `adapter_spec_version` 2.0.0 removed it from the schema and from all 42 goldens — a field that no check may read is a roster waiting to be misused.

---

## 3. Port-fidelity is asymmetric, and that asymmetry is structural

For a Go → Java port, the Go adapter exists first and is the source of truth for behavior, so a Java reviewer can legitimately ask "the Go side does X; why does this not?" The reverse question does not arise on the Go side for the same port, because there is nothing yet to be faithful to.

This means a Java review skill may carry a port-fidelity check for `port-from-go` PRs, and a Go review skill must not mirror it — mirroring would flag every Go adapter that has no Java counterpart, which is most of them.

Two constraints on that check:

- Fidelity is the means, not the end. Where source fidelity conflicts with the target repo's own norms, target conformance wins, and the divergence is recorded rather than silently resolved. See the disposition system in each suite's `framework-utilities` reference (ADR-009).
- Fidelity is not a licence to reproduce a source-side defect. A latent bug faithfully ported is still a bug the target reviewer will block.

---

## 4. Automatic cross-language validation

R5 (cross-language structural parity for port pairs) is the spec-level enforcement of fidelity, and it is independent of human review: a `bidder_params_sha256` mismatch is a divergence regardless of whether anyone noticed it.

R5 complements review; it does not replace it. It sees structural and byte-level divergence and is blind to behavioral divergence that both specs record identically — including framework-default back-fill, where two artifacts that look equal in spec form behave differently at runtime (Rule 49).

A port skill's emitted PR description should carry the R5 result so a reviewer does not have to re-run the read.

---

## 5. Authoring a new review skill for either language

Start from that language's own upstream source, config, and merged-PR corpus — never from a copy of the other suite's checks.

The existing suites are a reference for *architecture*: single-pass PR fetch in triage, per-domain skills over a shared framework reference, a routing manifest as the single source of truth, one disposition ladder. They are not a template for content.

The reference corpora are `prebid-server-go/references/new-bid-adapter-prs.md` and `prebid-server-java/references/new-bid-adapter-prs.md`. Cite them by PR, and verify a citation supports the claim attached to it before relying on it.

---

## 6. Limits of this policy

- **The ban targets automated or unexamined transfer.** An author who knowingly translates a defect class into the other language's idiom, and verifies it against that language's upstream, is doing the right thing. Blind copying of a check is what this forbids.
- **"No counterexample found" is not proof.** A check that cannot be anchored to upstream source, a merged PR, or a regenerable count should say so in its own text rather than borrow authority from the other suite.
- **A shared canonical artifact is not a shared convention.** Both repos consume the same Adapter Specification; that makes the *spec* transferable, not the review expectations built on top of it.
