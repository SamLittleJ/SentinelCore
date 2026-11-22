# 0010. Falco's runtime alerts enter SentinelCore as platform detections

- **Status:** Accepted
- **Date:** 2026-11-06

## Context and problem

Falco sees shells and sensitive reads in the cluster's containers. Its alerts are worth most where the operator already looks: SentinelCore's own console.

## Considered options

- Falco's alerts in its own UI or logs: a second place to watch.
- Falco's alerts through the ingestion API with an API key: keys belong to an organization, and these alerts belong to the platform.
- falcosidekick's webhook to an internal endpoint with a deployment token (chosen).

## Decision

falcosidekick sends Falco's payload to `POST /ingest/runtime`, reachable only from falcosidekick (NetworkPolicy, and 404 through nginx), with `FALCO_INGEST_TOKEN`. The server keeps four rules as three alert types with MITRE techniques, stores only Kubernetes names and the file path, never the command line, deduplicates within ten minutes and answers every alert the same way.

## Consequences

- Good: Runtime attacks appear beside identity attacks, on the owner's overview.
- Good: A stolen token reveals nothing about which rules are kept.
- Bad: The token has no expiry or revocation of its own.
- Bad: Falco itself stopping raises no alert.

## More information

Written in November 2026 from the decisions log: [Runtime detection (E3)](../02-decisions-log.md#runtime-detection-e3).
