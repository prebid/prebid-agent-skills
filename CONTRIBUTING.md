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

## Versioning policy

All `version` fields use SemVer string format `X.Y.Z`:

- **SKILL frontmatter `version`**: present on all read-skill SKILL.md files. Bump policy:
  - **Patch** (`1.0.0 → 1.0.1`): typo, prose-only fix, no behavioral change
  - **Minor** (`1.0.0 → 1.1.0`): new field, new enum value, new reference doc, additive change that doesn't break callers
  - **Major** (`1.0.0 → 2.0.0`): renamed field, removed field, changed enum semantics, schema-affecting change

- **Golden spec `adapter_spec_version`** + **`taxonomy_version`** (added Phase 2): same SemVer policy. Changes here are coordinated with corresponding migration scripts in `scripts/migrate/`.

- **Port-translation rules `port_translation_rules_version`** (added Phase 2): same. Add a CHANGELOG entry for any minor/major bump.

When in doubt, prefer a higher bump — version migrations are easier to reason about than silent semantic shifts.

## Adding a port-translation rule

- Edit `prebid-server-go/read/skills/shared/port-translation-rules.md`.
- Each rule lists Go ↔ Java translation, at least one worked example, and a lossy/lossless flag.
- Update the rule count in the doc's intro.

## Adding a port skill or port fixture

Phase D introduced two port skills (`port-go2java`, `port-java2go`) plus their supporting infrastructure. When extending or adding to that surface:

### Adding a new port skill (e.g., `port-go2js`, future)

1. Create the skill directory under the **artifact-language** tree (port-go2java lives at `prebid-server-java/port-go2java/` because it produces Java; port-go2js would live at `prebid-server-js/port-go2js/`).
2. Author `SKILL.md` with frontmatter `version: 0.1.0` and a description that explicitly names the source-vs-artifact-language inversion.
3. Author the 7-step pipeline body following [`docs/methodology/port-skills-design.md`](docs/methodology/port-skills-design.md) §3 with TODO placeholders for the language-specific Steps 3 and 4.
4. Add per-skill `references/` and `templates/` subdirectories. Per-skill is the convention — these are NOT shared `/templates/`.
5. Author the emission references for the new target language (artifact shapes, registration rules, PR shape, porting guide if no upstream equivalent exists). Mirror the structure at `prebid-server-{go,java}/port-{source}2{target}/references/`.
6. Wire the skill into [`prebid-server-go/read/skills/shared/cross-skill-integration.md`](prebid-server-go/read/skills/shared/cross-skill-integration.md) as a new top-level section parallel to §3 + §4.
7. Bump [`ROADMAP.md`](ROADMAP.md) Phase D section to list the new skill.

### Adding a port fixture (test corpus expansion)

Port fixtures live alongside the cross-language pair fixtures at `cross-language-pairs/{bidder}.dual-spec-assertions.yaml`. To add coverage for a new bidder pair:

1. Run the Go-side and Java-side read orchestrators; persist the goldens at `prebid-server-{go,java}/read/test-fixtures/{bidder}.golden.spec.yaml`.
2. Author the dual-spec assertions file mapping cross-language equivalence + divergence (severity: pass/warn/fail per dual-spec convention).
3. Verify `python3 scripts/round-trip-ci.py` passes the new pair (R5 strict + form-divergent + advisory-divergent keys).
4. Add the bidder to the relevant MVP corpus when applicable (per [`docs/execution-plan-phase-d.md`](docs/execution-plan-phase-d.md) §D2.3 / §D3.3 acceptance tables).

### Authoring a port-engine helper

[`scripts/lib/port_engine.py`](scripts/lib/port_engine.py) hosts the small set of mechanical helpers the port skills consume. New helpers join when a port-translation rule or a cross-language operation is structurally mechanical (NOT prose-driven). Contract:

- **Pure function with dependency-injection hooks**. State that varies (filesystem paths, subprocess invocations, upstream API responses) is accepted as keyword arguments so tests can mock it. Existing precedent: `gofmt_post_process(file_paths, *, runner=None)`, `prefix_uniqueness_check(target_lang, bidder_name, *, existing_names=None, table_path=None)`.
- **Return type captures the helper's contract**, not just success/failure. Existing precedent: `byte_copy → bool`, `prefix_uniqueness_check → (bool, List[str])`, `r5_check_at_port_time → R5Result` (rich dataclass).
- **Tests in [`scripts/tests/test_port_engine.py`](scripts/tests/test_port_engine.py)**. One test class per helper; cover happy path, edge cases, and invalid-input rejection (`ValueError` / `TypeError`). Filesystem helpers use `TemporaryDirectory`; subprocess helpers use the injected runner.
- **No silent fallbacks for missing data**. When a data source is absent (e.g., the bidder-constant table is missing), return a sentinel value (`(True, [])` for `prefix_uniqueness_check`) and document the best-effort behavior in the docstring. Callers can check the result and decide.
- **R5 helpers** consume `scripts/lib/r5_check.py` (the harness-shared comparator); do not duplicate the comparator logic.

When a helper changes its public signature, bump the corresponding port skill's `version` field per the [Versioning policy](#versioning-policy) above.

## Adding or modifying a CI rule

- R1–R10 are documented in `prebid-server-go/read/skills/shared/adapter-spec.md` (Validation rules section).
- A new rule lands in three places atomically: spec doc, `scripts/round-trip-ci.py`, and a unit test under `scripts/tests/`.

## PR checklist

See `.github/PULL_REQUEST_TEMPLATE.md`.

## Style

- No emojis unless the user explicitly requests them.
- Don't add comments that explain *what* the code does — names should carry that. Comments are for *why* (hidden constraints, surprising invariants).
- For shell commands in docs, prefer absolute or repo-relative paths.
