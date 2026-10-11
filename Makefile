.PHONY: help demo demo-clean

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-12s %s\n", $$1, $$2}'

demo: ## A fresh demo database with 90 days of a synthetic organization, then the app on it
	@./scripts/demo.sh

demo-clean: ## Remove the demo database and .demo/
	@docker exec sentinelcore-postgres psql -q -U sentinelcore -d postgres \
		-c "DROP DATABASE IF EXISTS sentinelcore_demo WITH (FORCE)"
	@rm -rf .demo
