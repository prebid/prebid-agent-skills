# Templates

Author-time scaffolds for new artifacts. These files are NOT shipped to
runtime — they exist as starting points humans copy when adding a new
bidder, taxon, or rule to the corpus.

## Adapter spec scaffolds

- [`empty-adapter-spec-go.yaml`](empty-adapter-spec-go.yaml) — Go-source spec template (211 lines). All required fields scaffolded with placeholder values; Java-only blocks (`spring_config`, `bidder_class`) are nulled per the schema's `if/then/else` discrimination.
- [`empty-adapter-spec-java.yaml`](empty-adapter-spec-java.yaml) — Java-source spec template. Required `spring_config` and `bidder_class` blocks pre-scaffolded for non-alias bidders.

### Workflow

1. Copy the appropriate template to `prebid-server-{go,java}/read/test-fixtures/<bidder>.golden.spec.yaml`.
2. Replace every `TODO` and `0000…` placeholder.
3. Validate against the schema:
   ```sh
   python3 -m unittest scripts.tests.test_schema_jsonschema
   python3 scripts/audit-golden.py --bidder=<bidder>
   ```
4. If the bidder is paired with the other language's golden, also create the dual-spec assertion at `cross-language-pairs/<bidder>.dual-spec-assertions.yaml`.

### Schema reference

The canonical schema lives at [`../prebid-server-go/read/skills/shared/adapter-spec.schema.json`](../prebid-server-go/read/skills/shared/adapter-spec.schema.json). Worked examples live in the `test-fixtures/` directories alongside each language's read skills.

### Phase 5 fixture authoring

Phase 5 of the execution plan ([`../docs/execution-plan.md`](../docs/execution-plan.md) and [`../docs/decisions/008-phase-5-pair-fixtures.md`](../docs/decisions/008-phase-5-pair-fixtures.md)) lists 7+2 prioritized pairs to add. Each new pair uses these templates as the starting point.
