.PHONY: help demo demo-clean images lock verify

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-12s %s\n", $$1, $$2}'

demo: ## A fresh demo database with 90 days of a synthetic organization, then the app on it
	@./scripts/demo.sh

# The commit the images are built from, marked when the tree has changes.
REVISION := $(shell git rev-parse --short HEAD)$(shell git diff --quiet HEAD -- || echo -dirty)

verify: ## Every check before a commit, one line each (logs in .verify/)
	@./scripts/verify.sh

images: ## Build the backend and console images, tagged with the commit
	docker build --build-arg REVISION=$(REVISION) -t sentinelcore-backend:$(REVISION) backend
	docker build --build-arg REVISION=$(REVISION) -t sentinelcore-console:$(REVISION) frontend

lock: ## Pin the backend's runtime dependencies, with hashes, for the image
	cd backend && .venv/bin/uv pip compile pyproject.toml --generate-hashes \
		--python-version 3.12 --python-platform x86_64-manylinux_2_28 \
		--no-header --quiet -o requirements.lock

demo-clean: ## Remove the demo database and .demo/
	@docker exec sentinelcore-postgres psql -q -U sentinelcore -d postgres \
		-c "DROP DATABASE IF EXISTS sentinelcore_demo WITH (FORCE)"
	@rm -rf .demo
