# 0004. Ingestion with hashed, expiring API keys and a token bucket in PostgreSQL

- **Status:** Accepted
- **Date:** 2026-10-09

## Context and problem

Other systems send sign-in events to `POST /ingest/events`. A key is a long-lived secret held outside the platform, and a valid key can flood the detection engine.

## Considered options

- Keys stored in clear, no expiry: simple, but a database read leaks every key and a lost key works forever.
- A rate limit per request, in memory or in Redis: per-process buckets or a new service to secure, and full batches dodge a per-request limit.
- Hashed, expiring, revocable keys; a token bucket of events per key on the key's row (chosen).

## Decision

Keys are a random 32-byte secret shown once, stored as a prefix and a SHA-256 hash, compared in constant time, with a mandatory expiry of 30, 90 or 365 days. Each key may send a burst of 5,000 events, then 1,000 a minute, counted in events, kept in two columns of its row under a row lock and the database clock. Every failure gives the same answer, and the response never reveals the alerts raised.

## Consequences

- Good: A database leak yields no usable key; a lost key stops working by itself.
- Good: Every API replica shares one bucket per key with no new service.
- Bad: Every ingestion batch takes a row lock on its key.
- Bad: A key holder can still shape the history it reports, within the burst and the year accepted.

## More information

Written in November 2026 from the decisions log: [Event ingestion](../02-decisions-log.md#event-ingestion), [Ingestion rate limit](../02-decisions-log.md#ingestion-rate-limit), [API key volume alert](../02-decisions-log.md#api-key-volume-alert).
