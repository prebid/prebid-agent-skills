# ADR-009: Lean-Conformance Doctrine for Adapter Ports

**Date**: 2026-06-03
**Status**: Accepted (doctrine decided 2026-06-03 after the Teal #4765 review; execution in progress — this ADR is Phase 0 of the port-skills hardening program, Phases 1–2 pending)
**Context**: The port + review skills were built on an "above-and-beyond" philosophy — emit MORE than the target repo merges (package `doc.go`, `*_fuzz_test.go`, `*_bench_test.go`, large stand-alone Go unit-test files) and reproduce the source adapter's behavior faithfully, latent anti-patterns included. This was an explicit, documented mandate, not an accident:

- `ROADMAP.md` (L56) celebrates Teal as "the only adapter in the entire 267-adapter prebid-server-go corpus with fuzz tests, benchmarks, AND `doc.go`" under a "best-in-class mandate," with "TOP QUARTILE on every quality dimension."
- `docs/methodology/canary-runbook.md` §4 (L544) and §5 (L548–559) set numerical quality-bar minimums of **≥1 fuzz function** and **≥2 benchmarks**; L571 instructs that "Fuzz/bench/doc.go are corpus-unique to canary 8; future canaries should preserve this advantage"; §10 (L949) frames "passing 8 gates is the FLOOR, not the ceiling."
- `docs/runs/d3.8-teal-reflection.md` §2c (L158) recommends "the SKILL should ship fuzz harnesses by default"; §3c (L191–197) poses a "Phase F decision point" between above-and-beyond mode (SKILL emits ≥95%) and canary mode (≥70%) and argues for above-and-beyond; PR 5 (L236–239) and PR 6 (L243–246) propose emitting `fuzz_test.go.j2`, `doc.go.j2`, and `bench_test.go.j2` companions **by default**.

When that philosophy met a real maintainer review (prebid/prebid-server#4765, "New Adapter: Teal," a Java→Go port), it was rejected. Of the 8 review threads, ~6 trace directly to the skills steering toward source-fidelity + extra artifacts against the Go target repo's lean-conformance bar: non-standard files flagged for deletion (`doc.go`, fuzz, bench), a silently-defaulting `getBidType`, a code↔config media-type mismatch, oversized Go unit tests that belong in JSON fixtures. The maintainer wanted exactly the canonical corpus upstream merges — no more, no less. Crucially, our reviews did not "miss" most of these: they SAW them and resolved them *toward* fidelity + "more artifacts = quality." The calibration itself was wrong.

**Options considered**:

1. **Status quo (above-and-beyond)** — keep emitting fuzz/bench/doc.go + maximal coverage; keep source-fidelity as the top priority. Rejected: empirically rejected by the real target maintainer; produces PRs that don't merge one-shot and generate review churn.
2. **Pure source-fidelity** — reproduce the source adapter exactly, anti-patterns included. Rejected: propagates latent source bugs the target reviewer blocks (Teal's Java `getBidType` returned `BidType.banner` silently for an undeterminable type — faithfully porting that ships the bug).
3. **Lean-conformance + ADR (CHOSEN)** — emit exactly the canonical corpus the target repo merges; when source fidelity conflicts with target-repo norms, target conformance wins; record every divergence and ADR every reversal of prior strategy.

## Decision

Adopt **lean-conformance + ADR** as the governing doctrine for both port directions (Java→Go and Go→Java) and both review directions:

1. **Emit the canonical corpus, nothing more.** A port PR contains only what the target repo merges (the Go corpus list is in [[reference-port-fidelity-vs-target-norms]]). `doc.go`, `*_fuzz_test.go`, `*_bench_test.go`, and large stand-alone Go unit-test files are NOT PR artifacts.

2. **Fuzz/bench/doc are dev-time aids, not deliverables.** They retain real value — a fuzz harness found Teal's nil-map panic (teal-reflection F-new-45, L156). The doctrine reframes WHERE they live, not whether to use them: run them during development; pin any bug they find with a NORMAL unit test (or a JSON supplemental fixture); strip the harness before the PR. Coverage is demonstrated through the JSON test corpus, not bespoke Go tests.

3. **Target-conformance beats source-fidelity.** Fidelity is the means; a merge-ready, idiomatic target PR is the end. Where they conflict, the target norm wins. Record the divergence in `port-report.json` `quirks[]` and file an upstream issue against the source repo so both sides re-align deliberately. (Nuance preserved — this does NOT mean "discard the source's real defaults": see the `getBidType` consequence below.)

4. **ADR every reversal.** This decision reverses a documented strategy; it is recorded here. Future strategy reversals get their own ADR.

## Consequences

This reverses prior guidance. The following surfaces must change, tracked by the hardening program ([[project-port-skills-hardening]]):

- **Templates** (`prebid-server-go/port-java2go/templates/bidder.go.j2`, `prebid-server-java/port-go2java/templates/bidder.java.j2`): stop emitting doc.go/fuzz/bench companions; do NOT adopt teal-reflection PR 5 / PR 6. (Phase 1)
- **Review skills** (both directions): a non-canonical artifact (doc.go/fuzz/bench/oversized unit test) becomes a FLAGGED finding, not praised quality. Add the genuinely-missing detections (perf nested-loop; request-level "first-valid-wins" silent divergence). Add a shared disposition system + a "target-conformance-beats-source-fidelity" tie-breaker to `review/skills/shared/framework-utilities.md` (Go) and `framework-utilities-java.md` (Java). The tie-breaker must NOT auto-promote WARN-by-design defensive checks (Site/App-ID guards, forward-compat branches). (Phase 1)
- **`getBidType` template nuance** (corrected from the blunt first cut): error-on-miss is the upstream MAJORITY default (verified 135/261 adapters) and the template default, BUT a constant fallback matching the source's REAL default is legitimate (e.g. `adkernelAdn`→`BidTypeVideo`, 63/261). The current template hardcodes a media-type priority (teal-reflection L52/L222 default `["video","native","audio","banner"]`) — that priority must be operator-supplied, and the catch-all must ERROR rather than silently pick a type. Review flags SILENT / unvouched / mis-typing fallbacks, NOT every constant fallback. Do NOT force `(BidType,error)` or an `impsByID` map unconditionally (only 14/261 adapters use the map). (Phase 1)
- **Methodology docs reframed** (Phase 1, "B6"): `canary-runbook.md` §5 quality-bar rows + §10, `teal-reflection.md` §2c / §3c / PR 5 / PR 6, and `ROADMAP.md` L56 — the "preserve this advantage" / "FLOOR not ceiling" / "above-and-beyond" framing is replaced by lean-conformance, with the dev-time-aid reframe noted in place rather than deleted.
- **Pre-submission self-review gate** becomes mandatory in both porting skills: run the matching review skill against the emitted artifact BEFORE the PR is opened.
- **Net effect**: future ports emit merge-ready PRs (closer to one-shot), and reviews catch the whole failure class instead of waving it through.

Coverage/quality is NOT abandoned — it moves into the corpus the target repo actually runs (JSON exemplary/supplemental fixtures, sentinel-error `errors.Is` cases). The bar is "what a senior target-repo maintainer merges without comment," not "more artifacts than any adapter in the corpus."

## References

- prebid/prebid-server#4765 — Teal (Java→Go port); the review that surfaced the doctrine failure. Workstream A fixed the PR; this ADR opens Workstream B (harden the skills).
- Reversed prior guidance: `ROADMAP.md` L56; `docs/methodology/canary-runbook.md` §4 (L544) / §5 (L548–571) / §10 (L949); `docs/runs/d3.8-teal-reflection.md` §2c (L158) / §3c (L191–197) / PR 5 (L236–239) / PR 6 (L243–246).
- Failure taxonomy: the 8 Teal review findings generalized to classes C1–C9; one-shot archetype gaps C10–C18 (enumerated in the hardening-program audit).
- Memory: [[reference-port-fidelity-vs-target-norms]], [[project-port-skills-hardening]], [[project-teal-pr-remediation]].
- Related ADRs: this is the first doctrine-level (vs schema/rule-level) ADR; ADR-001…008 remain Accepted and unaffected.
