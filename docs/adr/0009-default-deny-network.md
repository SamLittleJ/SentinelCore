# 0009. Default-deny networking with every allowed flow named

- **Status:** Accepted
- **Date:** 2026-11-03

## Context and problem

Inside a cluster every pod can reach every other and the internet by default, so one compromised pod reaches the database and can send data out.

## Considered options

- No network policies: the default: everything open.
- Calico in place of kind's own network plugin: not needed, as kindnet enforces NetworkPolicy, which a negative test written first proved.
- NetworkPolicy: deny all, then one policy per kind of pod (chosen).

## Decision

Each of our namespaces denies all ingress and egress except DNS, then allows only the flows the application needs (console → API → PostgreSQL, the Jobs → PostgreSQL, Prometheus → API, falcosidekick → API). Nothing reaches the internet. kindnet enforces it; `make cluster-check` proves each allowed and refused flow from inside the pods.

## Consequences

- Good: A compromised pod reaches only what its role needs.
- Good: Every new flow is a reviewed change to `network-policies/`.
- Bad: A compromised API still reaches PostgreSQL, which it needs.
- Bad: Policies do not cut connections already open.

## More information

Written in November 2026 from the decisions log: [Network policies (E2)](../02-decisions-log.md#network-policies-e2).
