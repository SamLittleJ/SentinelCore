# 0007. Kubernetes on kind with Helm, and PostgreSQL from a chart of its own

- **Status:** Accepted
- **Date:** 2026-10-20

## Context and problem

The project needs a cluster for its DevSecOps phases (admission, network policies, runtime detection, GitOps) without cloud billing until the end.

## Considered options

- Docker Compose only: no admission control, network policies or rollouts to show.
- A managed cloud cluster from the start: realistic, but billed for months of development.
- kind with two Helm charts of our own (PostgreSQL, then the application) (chosen).

## Decision

`make up` builds the images, creates a kind cluster and installs `charts/postgresql` (a StatefulSet of the official image, by digest) and then `charts/sentinelcore`, whose migrations run first as a Job. Secrets are generated once by the script, never in values or Git. Tools are pinned by SHA-256 in `.tools/`.

## Consequences

- Good: Everything runs locally and in CI, the same way.
- Good: The database is separate, as a managed one would be in the cloud (phase D2).
- Bad: One node: no disruption budgets or real high availability.
- Bad: A cloud cluster will need its own Terraform and secrets (D2).

## More information

Written in November 2026 from the decisions log: [Phase B: containers and local Kubernetes](../02-decisions-log.md#phase-b-containers-and-local-kubernetes), [Local cluster (B2)](../02-decisions-log.md#local-cluster-b2).
