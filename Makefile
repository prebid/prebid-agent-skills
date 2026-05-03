# Makefile for prebid-agent-skills.
#
# Common targets used during development and CI. Most underlying scripts
# live in scripts/ and scripts/tests/. The Makefile is a thin convenience
# layer; the scripts themselves are the authoritative entry points.

.PHONY: help install ci test audit-goldens audit-pr coverage sync render-taxonomy render-port-rules lint-port-rules clean

help:
	@echo "Available targets:"
	@echo "  install            pip install -r requirements.txt"
	@echo "  ci                 Run unit tests + schema-contract + round-trip-ci + port-rule lints"
	@echo "  test               Run unit tests only (scripts/tests/)"
	@echo "  audit-goldens      Phase 1.5 golden-vs-upstream audit (all goldens)"
	@echo "  audit-pr URL=…     Phase 4.2 PR audit (requires CLAUDE_API_KEY for novelty classification)"
	@echo "  coverage           Phase 4.3 per-rule, per-empire coverage report (markdown)"
	@echo "  sync               Phase 4.1 drift detection vs upstream prebid-server / prebid-server-java"
	@echo "  render-taxonomy    Phase 2.4 regenerate behavior-taxonomy.md from .yaml source"
	@echo "  render-port-rules  Phase 2.5 regenerate port-translation-rules.md from .yaml source"
	@echo "  lint-port-rules    Phase 2.6 mechanizable port-rule lints (Rules 5/9/33/36/38/44/46)"
	@echo "  clean              Remove __pycache__ and .pyc files"

install:
	pip install -r requirements.txt

ci: test
	python3 scripts/render-taxonomy.py --check
	python3 scripts/render-port-rules.py --check
	python3 scripts/coverage-report.py --check
	python3 scripts/tests/test_schema_contract.py
	@python3 scripts/audit-golden.py --all; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ] || [ $$EXIT -eq 2 ]; then : ; else exit $$EXIT; fi
	@PAIRS=$$(grep -vE '^\s*(#|$$)' .github/known-broken-pairs.txt | tr '\n' ',' | sed 's/,$$//'); \
	python3 scripts/round-trip-ci.py --strict-r3 --allow-known-broken-pairs "$$PAIRS"; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ] || [ $$EXIT -eq 2 ]; then : ; else exit $$EXIT; fi
	@python3 scripts/lib/lint-port-rules.py; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ] || [ $$EXIT -eq 2 ]; then exit 0; else exit $$EXIT; fi

test:
	python3 -m unittest discover -s scripts/tests -v

audit-goldens:
	python3 scripts/audit-golden.py --all

audit-pr:
	@if [ -z "$(URL)" ]; then \
		echo "Usage: make audit-pr URL=https://github.com/prebid/prebid-server/pull/NNNN"; \
		exit 1; \
	fi
	python3 scripts/audit-pr.py "$(URL)"

coverage:
	python3 scripts/coverage-report.py

sync:
	python3 scripts/sync-from-upstream.py
	@echo ""
	@echo "Drift report: scripts/output/drift-report.{json,md}"

render-taxonomy:
	python3 scripts/render-taxonomy.py

render-port-rules:
	python3 scripts/render-port-rules.py

lint-port-rules:
	python3 scripts/lib/lint-port-rules.py

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
