# 0002. Several organizations, isolated in the application and by PostgreSQL row-level security

- **Status:** Accepted
- **Date:** 2026-10-12

## Context and problem

SentinelCore went from one company to several on one platform. A missed filter in one query would show a company another's security events, which for this product is the worst possible bug.

## Considered options

- A database or schema per organization: strong isolation, but migrations, the detection engine and the platform owner's views multiply.
- A tenant column, filtered in the application only: simple, but one forgotten `WHERE` leaks.
- A tenant column filtered in one place per kind of record, backed by row-level security in PostgreSQL (chosen).

## Decision

Every record names its organization. Reads go through one scope per kind of record, and PostgreSQL's row-level security, keyed on a setting of the transaction, refuses other organizations' rows to the API's role even if a query forgets. Another organization's record answers `404`, as a missing one does. One platform owner belongs to no organization and manages them all.

## Consequences

- Good: Two independent layers must both fail for a leak.
- Good: Other organizations' records are indistinguishable from missing ones, so ids cannot be probed.
- Bad: The API's database role must never bypass row-level security, which `make cluster-check` checks.
- Bad: Platform-wide work (the owner, the cross-organization spray rule) needs explicit paths around the scope.

## More information

Written in November 2026 from the decisions log: [Several organizations](../02-decisions-log.md#several-organizations).
