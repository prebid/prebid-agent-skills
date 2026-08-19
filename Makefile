# Makefile for prebid-agent-skills.
#
# Common targets used during development and CI. Most underlying scripts
# live in scripts/ and scripts/tests/. The Makefile is a thin convenience
# layer; the scripts themselves are the authoritative entry points.

.PHONY: help install ci test audit-goldens audit-pr coverage sync render-taxonomy render-port-rules lint-port-rules lint-java-roles verify-claims verify-claims-upstream review-evals clean

help:
	@echo "Available targets:"
	@echo "  install            pip install -r requirements.txt"
	@echo "  ci                 Run unit tests + schema-contract + round-trip-ci + port-rule lints"
	@echo "  test               Run unit tests only (scripts/tests/)"
	@echo "  audit-goldens      Manual upstream-signature audit. Requires \`gh auth login\` (calls gh api). Run before submitting fixture-touching PRs. NOT part of \`make ci\` — see test-fixtures READMEs."
	@echo "  audit-pr URL=…     Phase 4.2 PR audit (requires CLAUDE_API_KEY for novelty classification)"
	@echo "  coverage           Phase 4.3 per-rule, per-empire coverage report (markdown)"
	@echo "  sync [TIER=full]   Drift detection vs upstream prebid-server / prebid-server-java (default tier: source)"
	@echo "  render-taxonomy    Phase 2.4 regenerate behavior-taxonomy.md from .yaml source"
	@echo "  render-port-rules  Phase 2.5 regenerate port-translation-rules.md from .yaml source"
	@echo "  lint-port-rules    Phase 2.6 mechanizable port-rule lints (Rules 5/9/33/36/38/44/46)"
	@echo "  lint-java-roles    Wave 4 file-role enum gate (Java + Go via --include-go)"
	@echo "  verify-claims      Hermetic: registered upstream claims are still anchored in the skills"
	@echo "  verify-claims-upstream GO=<checkout> JAVA=<checkout>  Re-derive every claim from upstream source"
	@echo "  review-evals       Score a recorded review run against the eval corpus (corpus integrity when none recorded)"
	@echo "  clean              Remove __pycache__ and .pyc files"

install:
	pip install -r requirements.txt

ci: test
	python3 scripts/render-taxonomy.py --check
	python3 scripts/render-port-rules.py --check
	python3 scripts/coverage-report.py --check
	python3 scripts/tests/test_schema_contract.py
	python3 scripts/verify-upstream-claims.py --check-sites
	python3 scripts/score_review_evals.py --validate-only
	@PAIRS=$$(grep -vE '^\s*(#|$$)' .github/known-broken-pairs.txt | tr '\n' ',' | sed 's/,$$//'); \
	python3 scripts/round-trip-ci.py --strict-r3 --allow-known-broken-pairs "$$PAIRS"; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ] || [ $$EXIT -eq 2 ]; then : ; else exit $$EXIT; fi
	@python3 scripts/lib/lint-port-rules.py; \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ] || [ $$EXIT -eq 2 ]; then : ; else exit $$EXIT; fi
	@python3 scripts/lib/lint-java-roles.py --include-go; \
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

# Local convenience runs the cheap tier: the two per-bidder config artifacts,
# ~84 upstream paths. The weekly workflow runs --scan-tier=full (~610 paths,
# every artifact the goldens actually pin) because it has a token, a tree cache
# and no one waiting on it. Override here with TIER=full when you want parity.
sync:
	python3 scripts/sync-from-upstream.py --scan-tier=$(if $(TIER),$(TIER),source)
	@echo ""
	@echo "Drift report: scripts/output/drift-report.{json,md}"
	@echo "Tier: $(if $(TIER),$(TIER),source)  (make sync TIER=full for the weekly job's surface)"

render-taxonomy:
	python3 scripts/render-taxonomy.py

render-port-rules:
	python3 scripts/render-port-rules.py

lint-port-rules:
	python3 scripts/lib/lint-port-rules.py

lint-java-roles:
	python3 scripts/lib/lint-java-roles.py --include-go

review-evals:
	python3 scripts/score_review_evals.py --validate-only
	@if ls review-evals/actual/*.yaml 2>/dev/null | grep -qv TEMPLATE; then \
		python3 scripts/score_review_evals.py --actual review-evals/actual \
			--json scripts/output/review-evals.json; \
	else \
		echo "review-evals: no recorded run in review-evals/actual/ -- corpus integrity only"; \
	fi

verify-claims:
	python3 scripts/verify-upstream-claims.py --check-sites

# Networked: needs local checkouts of both upstream repos. This is the check that
# catches upstream moving under the skills; --check-sites cannot see that.
verify-claims-upstream:
	@if [ -z "$(GO)" ] && [ -z "$(JAVA)" ]; then \
		echo "Usage: make verify-claims-upstream GO=/path/to/prebid-server JAVA=/path/to/prebid-server-java"; \
		exit 1; \
	fi
	@python3 scripts/verify-upstream-claims.py --upstream \
		$(if $(GO),--go-checkout $(GO),) $(if $(JAVA),--java-checkout $(JAVA),); \
	EXIT=$$?; \
	if [ $$EXIT -eq 0 ] || [ $$EXIT -eq 2 ]; then exit 0; else exit $$EXIT; fi

clean:
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
