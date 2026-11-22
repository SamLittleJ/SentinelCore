# 0011. GitOps with Argo CD: a deployment is a merged pull request naming verified digests

- **Status:** Accepted
- **Date:** 2026-11-21

## Context and problem

`make up` installs from a developer's machine. A deployment should come from Git alone, be reviewable, and revert changes made by hand.

## Considered options

- CI pushes to the cluster: CI then holds cluster credentials, and the cluster drifts from Git.
- Terraform for the cluster and Argo CD, Argo CD for everything else from `main` (chosen).

## Decision

Terraform creates the kind cluster and installs Argo CD; an app of apps installs everything else from `main`, with sync waves (Kyverno and its policies first), prune and self-heal. External charts come from OCI by digest. Images are named by digest in `deploy/images.yaml`, written by `make deploy-pr` after `verify-images.sh` passes, as a pull request opened from the developer's machine so that the required checks run.

## Consequences

- Good: What runs is what `main` says, and a change by hand is reverted.
- Good: A deployment is reviewed like any change.
- Bad: Argo CD holds near cluster-admin rights.
- Bad: A merge to `main` deploys; only review and CI stand before it.

## More information

Written in November 2026 from the decisions log: [GitOps (D1a)](../02-decisions-log.md#gitops-d1a).
