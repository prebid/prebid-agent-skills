# Makefile for prebid-agent-skills.
#
# Common targets used during development and CI. Most underlying scripts
# live in scripts/ and scripts/tests/. The Makefile is a thin convenience
# layer; the scripts themselves are the authoritative entry points.

.PHONY: help install ci test audit-goldens audit-pr coverage clean

help:
	@echo "Available targets:"
	@echo "  install         pip install -r requirements.txt"
	@echo "  ci              Run unit tests + schema-contract + round-trip-ci (mirrors GH Actions)"
	@echo "  test            Run unit tests only (scripts/tests/)"
	@echo "  audit-goldens   Phase 1.5 golden-vs-upstream audit (all 22 goldens)"
	@echo "  audit-pr URL=…  Phase 4.2 PR audit (requires CLAUDE_API_KEY for novelty classification)"
	@echo "  coverage        Phase 4.3 per-rule, per-empire coverage report (markdown)"
	@echo "  clean           Remove __pycache__ and .pyc files"

install:
	pip install -r requirements.txt

ci: test
	python3 scripts/tests/test_schema_contract.py
	@PAIRS=$$(grep -vE '^\s*(#|$$)' .github/known-broken-pairs.txt | tr '\n' ',' | sed 's/,$$//'); \
	python3 scripts/round-trip-ci.py --strict-r3 --allow-known-broken-pairs "$$PAIRS"; \
	EXIT=$$?; \
	if [ $$EXIT -le 2 ]; then exit 0; else exit $$EXIT; fi

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

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
