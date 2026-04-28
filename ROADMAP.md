# Roadmap

This repo's work is organized into phases A–E. Phases A–C (read-skill foundation) are complete in PR #1. Phase D (porting skills) is the next milestone.

## Phase A — Acceptance-gate goldens (complete)

The first Adapter Specification fixtures, hand-authored as the canonical shape contract:

- `optidigital` (clean baseline, Go)
- `kobler` (cross-language port pair, Go + Java)

Living at `prebid-server-{go,java}/read/test-fixtures/`.

## Phase B — Go read-skill suite (complete in PR #1)

Four skills under `prebid-server-go/read/skills/`:

- `read-adapter-orchestrator` — discovery, fetch, dispatch, assembly
- `read-adapter-code` — parses `adapters/{bidder}/*.go`
- `read-bidder-info` — parses `static/bidder-info/{bidder}.yaml`
- `read-bidder-params` — parses `static/bidder-params/{bidder}.json` + `openrtb_ext/imp_{bidder}.go` + `params_test.go`

## Phase C — Java read-skill suite (complete in PR #1)

Four parallel skills under `prebid-server-java/read/skills/`:

- `read-bidder-orchestrator`
- `read-bidder-class` — parses `src/main/java/org/prebid/server/bidder/{xyz}/*.java` + JUnit tests
- `read-bidder-config` — parses `src/main/resources/bidder-config/{xyz}.yaml` + Spring `@Configuration`
- `read-bidder-params-java` — parses `src/main/resources/static/bidder-params/{xyz}.json` + `ExtImp{Xyz}.java`

The Java suite shares the canonical schema, taxonomy, and port-translation rules with Go via `prebid-server-go/read/skills/shared/`. A future Java-specific schema would land at `prebid-server-java/read/skills/shared/adapter-spec-java.md` if divergence demands it.

## Phase D — Porting skills (next)

Bidirectional Go ↔ Java translation:

- `port-go2java/` — Go-source spec → Java artifacts (will live under `prebid-server-java/`)
- `port-java2go/` — Java-source spec → Go artifacts (will live under `prebid-server-go/`)

Both consume the cross-language translation rules at `prebid-server-go/read/skills/shared/port-translation-rules.md`. Cross-language pair fixtures at `cross-language-pairs/` are the round-trip safety net.

## Phase E — Review-skill expansion + cross-skill integration

- Java review-skill suite (`prebid-server-java/review/skills/`) — currently absent
- Implement `--- PRIOR SPEC COMPARISON ---` consumption in the 3 downstream Go review skills (the hook is authored in `pr-triage` but no consumer reads it as of PR #1)
- `write/` skills — generate adapters from a spec
- `diff-spec` skills — compare two specs across commits

## Phase 2 (orthogonal — reconnaissance)

References to "Phase 2" in some SKILL files refer to the master-plan reconnaissance pass that derived the canonical taxonomy and the 17+17 edge-case enumeration across both languages. It is separate from the user-facing A–E numbering.

## Out of scope

- `prebid-js/`, `prebid-dcos/` — directories existed as exploratory stubs before PR #1; deleted in PR #1. Future suites for these surfaces are not currently planned.
