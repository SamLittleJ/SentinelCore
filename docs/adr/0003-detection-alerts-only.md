# 0003. Detection rules raise alerts and never block, each mapped to MITRE ATT&CK

- **Status:** Accepted
- **Date:** 2026-10-08

## Context and problem

Detection rules judge sign-ins and role changes. A false positive that blocked would lock real people out, and an attacker who knew the rules could use them to lock others out.

## Considered options

- Rules that block or lock accounts automatically: faster response, but every false positive is an outage and a denial-of-service lever.
- Rules that alert, with containment left to people (chosen).

## Decision

Rules (password spray, dormant account, privileged role, unfamiliar network and device, cross-organization spray, key volume) only write alerts with the source `detection`; operators contain accounts through the console. Each alert type maps to one MITRE ATT&CK technique in code. Windows are measured from the event's own time. Only the brute-force protection, which predates the rules, blocks, and only on the application's own sign-ins.

## Consequences

- Good: A false positive costs a look, not a locked account.
- Good: Every alert names a technique, which the console and the evaluation report use.
- Bad: An attack runs until someone acts on the alert.
- Bad: Thresholds must be tuned to keep alerts worth reading (the evaluation reports false positives).

## More information

Written in November 2026 from the decisions log: [Detection rules](../02-decisions-log.md#detection-rules), [Evasive attack variants](../02-decisions-log.md#evasive-attack-variants).
