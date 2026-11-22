# Postmortem: a password spray, then a shell in the API's container

- **Date:** 2026-11-22, 16:31:38 to 16:36:50 UTC
- **Kind:** a drill, played with `make incident` on the `make up` cluster (backend `a5822bc9615b-dirty`, Falco 0.45.1), and answered by hand with the runbooks in [`docs/runbooks/`](../runbooks/README.md)
- **Status:** closed; actions below
- **Blameless:** the timeline records what the system and the responder did, not who should have done better

## Summary

An attacker sprayed one wrong password over twelve accounts of a new organization from one address, then opened a shell with a terminal in a running API container. SentinelCore raised the spray as an incident within a second of the tenth account. **Falco did not report the shell**: on that day it no longer reported shells in containers that had been running for about 23 hours, and reported them at once in new ones. The responder found the gap by testing Falco with a fresh pod, replaced the API pod as the runbook says, and restored detection in the old pods by restarting Falco. No data was changed; the audit history verified intact and `make cluster-check` passed afterwards.

## Impact

- **Identity:** twelve failed sign-ins for members of the drill's organization; none succeeded, and none counted against the members' own lockout (the spray stays under the address's limit of twenty).
- **Runtime:** the shell ran `id` and `hostname`. In a real attack, a shell in the API's container holds the API's secrets (`DATABASE_URL`, `SECRET_KEY`, `AUDIT_CHAIN_KEY`, `METRICS_TOKEN`); here it went unreported for as long as nobody looked, which is the finding of this drill.
- **Users:** none affected. Replacing the API pod kept one of the two pods serving.

## Timeline (UTC)

| Time | What happened |
|---|---|
| 16:31:38 | `make incident` starts on the `make up` cluster. |
| 16:31:39 | The owner creates the organization `northwind-11221631` ("Northwind (incident drill)"). |
| 16:31:44 | Fourteen members have joined by invitation. The spray starts: one wrong password per account. |
| 16:31:48.116 | **`PASSWORD_SPRAY_DETECTED`** (event 349), incident severity: "failed sign-ins for 10 different emails within 15 minutes" from 172.19.0.1, the address all of the host's traffic comes from on kind. Detected 0.1 s after the tenth failure, 4 s after the first. |
| 16:31:48 | The spray ends (twelve accounts). A shell with a terminal opens in `sentinelcore-backend-6b8845d4b-f8dk2`, container `backend`: `id; hostname`. |
| 16:31:55 | Response starts ([container shell](../runbooks/container-shell.md), first checks): the spray alert is there; **no shell alert**. |
| 16:32:02 | Still none in the database, none in Falco's own log, and falcosidekick posted nothing after 16:29. |
| 16:32:10 | A second shell in the same pod, interactively: no alert either. |
| 16:32:56 | The responder checks Falco itself with a shell in a new probe pod: **reported** (event 352). Falco is running and the path to the API works. |
| about 16:33 | `sh -c true`, `bash -c true` and an interactive `sh` in the old pod: none reported. |
| 16:34:03 | **Stop the damage:** the API pod is deleted; its Deployment starts `sentinelcore-backend-6b8845d4b-f56bn`, ready at 16:34:08. |
| 16:34:08 | A shell in the new pod: **reported** (event 353). |
| about 16:34 | A shell in the other API pod, `…-jxv76`, also about 23 hours old: not reported. |
| 16:34:48 | Falco's DaemonSet is restarted, ready at 16:35:15. |
| 16:35:15 | A shell in `…-jxv76`: **reported** (event 354). |
| 16:35:34 | Persistence checks: no new API key, account or role but the drill's own; every audit chain verifies (`verify-audit-chain`). |
| 16:35:54 | `make cluster-check`: 46 of 46 by 16:36:50. **Closed.** |

## Detection

| Signal | Time to detect | How |
|---|---|---|
| Password spray | 0.1 s after the tenth account (4 s after the spray began) | Detection rule on the API's own sign-ins, T1110.003 |
| Shell in a 23-hour-old container | Not detected | Falco reported nothing until restarted |
| Shell in a new container | Under 1 s | Falco → falcosidekick → `/ingest/runtime`, T1059 |

## Response

The responder followed [container shell](../runbooks/container-shell.md) in order: the alerts, Falco's own log, the image, replacing the pod, persistence, the audit chain, `make cluster-check`. The runbook assumed an alert to start from; with none, the responder had to suspect Falco itself, which the runbook did not say to do (fixed, below).

## Causes

- **The shell was not reported** because Falco 0.45.1, after running for about 28 hours on this node, no longer raised "Terminal shell in container" for processes in containers started five hours after it, while it still did for containers started after the drill began and for host events. A restart of Falco restored it at once. Why its view of the older containers lapsed is **not known**: the evidence fits Falco no longer attributing those processes to a container, but this drill did not prove it.
- **The gap was invisible to the checks**: `make cluster-check` proves runtime detection with a shell in a new probe pod each run, so it passes in exactly the case that worked here.
- **Context, not a cause:** on kind every request from the host arrives from the bridge's address (172.19.0.1), so the spray alert names that address, not the attacker's; this is known (`scripts/cluster-check.sh`, "the one address all local traffic comes from").

## What went well

- The spray was detected within a second and named as an incident in the right organization.
- The runbook's first checks found the missing alert within 7 seconds of the response starting, and a fresh probe pod told a Falco outage from a Falco blind spot.
- Replacing the pod, as the runbook says, also restored detection for the new pod.
- Nothing needed restoring: read-only root filesystems, the sealed audit history and the default-deny network bounded what the shell could have done.

## What went badly

- A shell in a running container went unreported, and nothing alerts on Falco's silence (T-76).
- The runbooks, as first written, read Falco's log with `kubectl logs -l …`, which shows only the last ten lines; found while preparing the drill and fixed before it.
- The `make up` cluster had been installed before Prometheus' lifecycle API was turned on (D1b), so it could not reload the rules with the runbooks' new links until restarted; a fresh `make up` has it.

## Actions

| Action | Kind | Where |
|---|---|---|
| The container shell and runtime-late runbooks now say to suspect Falco when an expected alert is missing, to test it with a fresh pod and with a shell in an old one, and to restart it | Done in this pull request | `docs/runbooks/` |
| T-76 records the blind spot for long-running containers | Done in this pull request | `docs/04-threat-model.md` |
| `make cluster-check` should also open a shell in an existing API pod, so the blind spot fails a check | Code, later | noted in `docs/00` |
| Find why Falco stops reporting for older containers (version, container plugin, the node being shared by two kind clusters) | Investigation, later | noted in `docs/00` |
| An alert on Falco's silence, once Alertmanager exists (D2) | Code, later | T-76, noted in `docs/00` |

## Reproduce

```bash
make up            # if the cluster is not running
make incident      # the spray, then the shell; prints each step's time
```

Falco stores the same alert for a pod once in ten minutes, so a second run within ten minutes shows no new shell alert.
