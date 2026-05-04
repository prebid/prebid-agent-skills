## Summary

<1–3 bullets on what changed and why>

## Scope

<which skills / fixtures / shared docs / CI rules are touched>

## Validation

- [ ] `python3 scripts/round-trip-ci.py --strict-r3` passes
- [ ] If goldens changed: regenerated against pinned upstream commits (see `prebid-server-{go,java}/read/test-fixtures/README.md`)
- [ ] If the canonical schema or taxonomy changed: contract test (`scripts/tests/test_schema_contract.py`) passes
- [ ] If a new R-rule was added: documented in `adapter-spec.md` AND implemented in `scripts/round-trip-ci.py` AND has a unit test

## Breaking changes

<any changes that affect downstream skill consumers; otherwise "none">
