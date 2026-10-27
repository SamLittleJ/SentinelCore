.PHONY: help demo demo-clean images lock lock-scanners verify tools up down cluster-check deploy-lint scan scan-images verify-images

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-14s %s\n", $$1, $$2}'

demo: ## A fresh demo database with 90 days of a synthetic organization, then the app on it
	@./scripts/demo.sh

# The commit the images are built from (12 characters, the same everywhere,
# as GHCR tags them), marked when the tree has changes or new files.
REVISION := $(shell git rev-parse --short=12 HEAD)$(shell test -z "$$(git status --porcelain)" || echo -dirty)

verify: ## Every check before a commit, one line each (logs in .verify/)
	@./scripts/verify.sh

images: ## Build the backend and console images, tagged with the commit
	docker build --build-arg REVISION=$(REVISION) -t sentinelcore-backend:$(REVISION) backend
	docker build --build-arg REVISION=$(REVISION) -t sentinelcore-console:$(REVISION) frontend

lock: ## Pin the backend's runtime dependencies, with hashes, for the image
	cd backend && .venv/bin/uv pip compile pyproject.toml --generate-hashes \
		--python-version 3.12 --python-platform x86_64-manylinux_2_28 \
		--no-header --quiet -o requirements.lock

lock-scanners: ## Pin the scanners of `make scan` (security/scanners.in), with hashes
	backend/.venv/bin/uv pip compile security/scanners.in --universal --generate-hashes \
		--python-version 3.12 --no-header --quiet -o security/scanners.lock

tools: ## Download the cluster's and the checks' tools, pinned and checked, into .tools/
	@./scripts/tools.sh >/dev/null

# `make up` builds the images; `make up FROM=registry` takes this commit's
# published ones instead, only once their signature and attestations check
# out (scripts/verify-images.sh).
ifeq ($(FROM),registry)
UP_IMAGES := verify-images
else ifeq ($(FROM),)
UP_IMAGES := images
else
$(error FROM can only be empty or registry, not '$(FROM)')
endif

up: $(UP_IMAGES) ## SentinelCore on a local kind cluster, at http://localhost:8080 (FROM=registry: the signed GHCR images)
	@REVISION=$(REVISION) ./scripts/cluster.sh up

verify-images: ## Check the signature and attestations of this commit's GHCR images, then pull them
	@./scripts/verify-images.sh $(REVISION)

down: ## Delete the kind cluster and its data (asks first)
	@./scripts/cluster.sh down

deploy-lint: ## Lint the charts, manifests, Dockerfiles and scripts, without a cluster
	@./scripts/deploy-lint.sh

scan: ## Scan dependencies and deployment files; open findings fail (security/exceptions.yaml)
	@./scripts/scan.sh

scan-images: images ## Build the images, then an SBOM of each and its known vulnerabilities (.scan/)
	@REVISION=$(REVISION) ./scripts/scan-images.sh

cluster-check: ## Check the running cluster's security properties, one line each
	@./scripts/cluster-check.sh

demo-clean: ## Remove the demo database and .demo/
	@docker exec sentinelcore-postgres psql -q -U sentinelcore -d postgres \
		-c "DROP DATABASE IF EXISTS sentinelcore_demo WITH (FORCE)"
	@rm -rf .demo
