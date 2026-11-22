# 0006. A sealed audit history: an HMAC chain per organization

- **Status:** Accepted
- **Date:** 2026-10-20

## Context and problem

The audit log records who did what. Whoever controls the database (or the owner of its tables) could rewrite it, and a plain hash chain stored next to it can simply be recomputed.

## Considered options

- A plain SHA-256 hash chain in the database: recomputable by whoever can change the rows.
- An external append-only store: strongest, but a new service to run.
- An HMAC-SHA256 chain per organization, keyed by a secret the database never holds, checked periodically (chosen).

## Decision

Every audit record is sealed on flush with an HMAC over its fields and the previous seal, keyed by `AUDIT_CHAIN_KEY`. Writers of one chain are serialized by an advisory lock. The API checks every chain periodically and raises `audit_chain_broken` (T1070); chain lengths go to the logs and Prometheus, so truncation is visible. Backups are proved by comparing the restored chains with the live ones.

## Consequences

- Good: Changing or deleting a sealed record without the key is detected.
- Good: Organizations write their chains independently.
- Bad: Whoever holds both the key and the database can still reseal.
- Bad: The key cannot be rotated without resealing the history.

## More information

Written in November 2026 from the decisions log: [Sealed audit history](../02-decisions-log.md#sealed-audit-history), [Backups (E6)](../02-decisions-log.md#backups-e6).
