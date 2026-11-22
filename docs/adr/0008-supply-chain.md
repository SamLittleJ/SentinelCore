# 0008. Signed images with SLSA provenance and an SBOM, verified at admission by Kyverno

- **Status:** Accepted
- **Date:** 2026-10-26

## Context and problem

Whoever can push an image under our name could run code in the cluster. The images must be traceable to the commit and workflow that built them, and that must be checked where they run.

## Considered options

- Trust the registry and the tag: a moved tag or a stolen push token runs anything.
- cosign with a long-lived key pair: a key to store, rotate and lose.
- Keyless cosign signatures and GitHub attestations, verified by a script and again by Kyverno at admission (chosen).

## Decision

CI scans the images (Grype on the Syft SBOM) and publishes only the scanned ones; cosign signs each digest keyless with the workflow's OIDC identity, and `actions/attest` adds SLSA v1 provenance and the SBOM. `scripts/verify-images.sh` checks all three against the exact repository, workflow, branch and commit; in the cluster Kyverno checks them again before every pod, by digest, failing closed. The project claims SLSA Build Level 2.

## Consequences

- Good: An image not built by CI on `main` cannot run in `sentinelcore`.
- Good: Each image carries what it contains and how it was built.
- Bad: Admission takes 17 to 28 seconds per new image on kind, close to the webhook's limit.
- Bad: Level 3 would need an isolated reusable build workflow.

## More information

Written in November 2026 from the decisions log: [Image scans (C2)](../02-decisions-log.md#image-scans-c2), [Image signing (C3)](../02-decisions-log.md#image-signing-c3), [Admission policies (E1)](../02-decisions-log.md#admission-policies-e1).
