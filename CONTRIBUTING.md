# Contributing

This repo holds agent skills (Markdown SKILL.md files + references), golden Adapter Specification fixtures, and a CI harness that validates the skills against those fixtures.

## Layout

- `prebid-server-go/read/skills/` — read-skill suite for `prebid/prebid-server`
- `prebid-server-java/read/skills/` — read-skill suite for `prebid/prebid-server-java`
- `prebid-server-go/read/skills/shared/` — canonical schema, taxonomy, port-translation rules (Java side links to these as source of truth)
- `prebid-server-{go,java}/read/test-fixtures/` — golden Adapter Specification YAMLs pinned to specific upstream commits
- `cross-language-pairs/` — dual-spec assertion files declaring per-bidder cross-language equivalence and divergence
- `scripts/round-trip-ci.py` — CI harness validating R1–R10 spec rules and dual-spec assertions
- `prebid-server-go/review/skills/` — existing Go review skills (PR-routing + per-domain reviewers)

## Local setup

```bash
pip install -r requirements.txt
python3 scripts/round-trip-ci.py --strict-r3
```

## Adding a new fixture

1. Run the read-orchestrator skill against the bidder at a pinned upstream commit.
2. Save the emitted YAML to `prebid-server-{go,java}/read/test-fixtures/{bidder}.golden.spec.yaml`.
3. Verify `python3 scripts/round-trip-ci.py` passes for the new fixture.
4. If the bidder exists in both repos, also add a `cross-language-pairs/{bidder}.dual-spec-assertions.yaml`.
5. Add a one-line description to the relevant `test-fixtures/README.md`.

## Editing a SKILL.md

- Keep SKILL.md bodies under 500 lines (per Anthropic skill-creator guidance). Use `references/` files for depth.
- Reference fields by their canonical schema path. The schema lives at `prebid-server-go/read/skills/shared/adapter-spec.md`. Do not invent fields; if the field is missing from the schema, propose an addition first.
- Use the closed taxonomy at `prebid-server-go/read/skills/shared/behavior-taxonomy.md` for enumerated values. Adding a new enum value requires updating the taxonomy in the same change.
- Use imperative form ("emit", "parse", "verify") — prefer explanation of *why* over heavy-handed "MUSTs".

## Adding a port-translation rule

- Edit `prebid-server-go/read/skills/shared/port-translation-rules.md`.
- Each rule lists Go ↔ Java translation, at least one worked example, and a lossy/lossless flag.
- Update the rule count in the doc's intro.

## Adding or modifying a CI rule

- R1–R10 are documented in `prebid-server-go/read/skills/shared/adapter-spec.md` (Validation rules section).
- A new rule lands in three places atomically: spec doc, `scripts/round-trip-ci.py`, and a unit test under `scripts/tests/`.

## PR checklist

See `.github/PULL_REQUEST_TEMPLATE.md`.

## Style

- No emojis unless the user explicitly requests them.
- Don't add comments that explain *what* the code does — names should carry that. Comments are for *why* (hidden constraints, surprising invariants).
- For shell commands in docs, prefer absolute or repo-relative paths.
