# Architecture decision records

The decisions that shape SentinelCore's architecture, one file each, in the [MADR](https://adr.github.io/madr/) format: the context, the options considered, the decision and its consequences. They were written in November 2026 from the [decisions log](../02-decisions-log.md), which stays the complete record of every decision, small ones included; each record links to its sections there, and its date is when the decision first reached the code. Where the log does not record the alternatives that were weighed, the options listed are the ones the decision rules out, stated afterwards.

A decision that is changed later keeps its file, marked *Superseded by* the record that replaces it.

| # | Decision | Date | Status |
|---|---|---|---|
| [0001](0001-sessions.md) | Browser sessions: a token bound to a revocable session, in an httpOnly cookie | 2026-10-06 | Accepted |
| [0002](0002-organizations.md) | Several organizations, isolated in the application and by PostgreSQL row-level security | 2026-10-12 | Accepted |
| [0003](0003-detection-alerts-only.md) | Detection rules raise alerts and never block, each mapped to MITRE ATT&CK | 2026-10-08 | Accepted |
| [0004](0004-ingestion-keys.md) | Ingestion with hashed, expiring API keys and a token bucket in PostgreSQL | 2026-10-09 | Accepted |
| [0005](0005-invitations.md) | Accounts join by invitation, not by public sign-up | 2026-10-09 | Accepted |
| [0006](0006-sealed-audit-history.md) | A sealed audit history: an HMAC chain per organization | 2026-10-20 | Accepted |
| [0007](0007-kind-and-helm.md) | Kubernetes on kind with Helm, and PostgreSQL from a chart of its own | 2026-10-20 | Accepted |
| [0008](0008-supply-chain.md) | Signed images with SLSA provenance and an SBOM, verified at admission by Kyverno | 2026-10-26 | Accepted |
| [0009](0009-default-deny-network.md) | Default-deny networking with every allowed flow named | 2026-11-03 | Accepted |
| [0010](0010-falco-via-ingestion.md) | Falco's runtime alerts enter SentinelCore as platform detections | 2026-11-06 | Accepted |
| [0011](0011-gitops.md) | GitOps with Argo CD: a deployment is a merged pull request naming verified digests | 2026-11-21 | Accepted |
| [0012](0012-progressive-delivery-and-previews.md) | Progressive delivery: a canary by pods with synthetic traffic, and previews whose isolation comes from main | 2026-11-22 | Accepted |
