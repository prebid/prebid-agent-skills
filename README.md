# prebid-agent-skills

[![round-trip-ci](https://github.com/prebid/prebid-agent-skills/actions/workflows/round-trip-ci.yml/badge.svg)](https://github.com/prebid/prebid-agent-skills/actions/workflows/round-trip-ci.yml)

Agent skills, reference documentation, golden test fixtures, and a CI harness for analyzing and porting [prebid-server](https://github.com/prebid/prebid-server) bidder adapters across language implementations.

## What's here

- **Read skills** that extract a structured Adapter Specification (a YAML document capturing provenance, code-level behavior, schema, test inventory, and cross-language port concerns) from any Go or Java bidder adapter:
  - `prebid-server-go/read/skills/` — for `prebid/prebid-server`
  - `prebid-server-java/read/skills/` — for `prebid/prebid-server-java`
- **Canonical references** at `prebid-server-go/read/skills/shared/` — the schema (`adapter-spec.md`), the closed enumeration registry (`behavior-taxonomy.md`), and 43 cross-language port-translation rules (`port-translation-rules.md`). The Java suite links to these as source of truth.
- **Golden fixtures** at `prebid-server-{go,java}/read/test-fixtures/` — hand-authored Adapter Specification YAMLs pinned to specific upstream commits, used as round-trip determinism oracles (R4) and cross-language consistency contracts (R5).
- **Cross-language pairs** at `cross-language-pairs/` — dual-spec assertion files declaring per-bidder cross-language equivalence and divergence.
- **CI harness** at `scripts/round-trip-ci.py` — validates R1–R10 spec rules and the dual-spec assertions.
- **Existing Go review skills** at `prebid-server-go/review/skills/` — PR-routing and per-domain reviewers (predate the read suite; integration is a Phase E item).

## Status

| Phase | Description | Status |
|---|---|---|
| A | Acceptance-gate goldens | complete |
| B | Go read-skill suite | complete (PR #1) |
| C | Java read-skill suite | complete (PR #1) |
| D | Porting skills (Go ↔ Java) | next |
| E | Review-skill expansion + cross-skill integration | planned |

See [`ROADMAP.md`](ROADMAP.md) for details.

## Audience

Agents and human contributors building tooling on top of prebid-server. Skills are intended to be invoked through Anthropic Claude (or compatible) skill-aware harnesses; the schema and taxonomy can be read as standalone documentation.

## Local development

```bash
pip install -r requirements.txt

# R1-R10 validation across all goldens + dual-spec assertions
python3 scripts/round-trip-ci.py --strict-r3

# Unit tests for the CI harness itself
python3 -m unittest discover -s scripts/tests -v

# Schema contract test (catches phantom field references in SKILL.md docs)
python3 scripts/tests/test_schema_contract.py
```

## License

[Apache 2.0](LICENSE) — matches upstream prebid-server licensing. See [`NOTICE`](NOTICE) for the derivative-work statement.
