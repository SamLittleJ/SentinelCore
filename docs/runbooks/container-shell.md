# Container shell (CONTAINER_SHELL_DETECTED)

**Severity:** incident. **MITRE ATT&CK:** T1059 (Command and Scripting Interpreter). **Comes from:** Falco's rule "Terminal shell in container", through falcosidekick to `POST /ingest/runtime`, as a platform alert of the owner. Message: `Shell with a terminal in container <container> of pod <pod> (namespace <namespace>)`.

## When you expected an alert and none came
Falco can stop reporting shells in containers that have run for a long time while it still reports them in new ones (the drill in [`docs/postmortems/`](../postmortems/2026-11-22-spray-and-shell.md)). If you suspect a shell that was not reported:
1. Test Falco with a new pod: `make cluster-check` reports a shell in a fresh probe pod within 30 s.
2. Test it on the old pod: `python3 -c 'import pty, sys; sys.exit(pty.spawn(sys.argv[1:]) >> 8)' .tools/kubectl exec -it -n sentinelcore <pod> -c backend -- sh -c true`, then look for the alert.
3. If only the old pod is silent, restart Falco (`k rollout restart ds/falco -n falco`) and treat every container as unwatched since it started: follow this runbook for each one that matters.

## What it means
Someone ran an interactive shell inside one of the cluster's containers. Our images start no shell, so it came from outside: `kubectl exec -it` by someone with that right, or an attacker who has code running in the container.

## Impact
Whoever holds that shell acts as the container: the API's container holds `DATABASE_URL`, `SECRET_KEY`, `AUDIT_CHAIN_KEY` and `METRICS_TOKEN` in its environment, and reaches the database. Treat it as a possible theft of those secrets until shown otherwise.

## First checks
1. The alert: in the console, signed in as the owner, Organization → Events, source `falco`, or
   ```bash
   sql "SELECT id, occurred_at, message FROM security_events WHERE source = 'falco' ORDER BY id DESC LIMIT 5"
   ```
   Note the pod, the container and the time.
2. What ran: Falco's own log keeps the command line, which SentinelCore never stores:
   ```bash
   k logs -n falco ds/falco -c falco --since=1h | grep 'Terminal shell' | grep '<pod>'
   ```
   Its `output_fields` give `proc.cmdline` (what ran) and `proc.pname`, the parent: `containerd-shim` for `kubectl exec`, the application's own process (`uvicorn`, `python`) for a shell it started. For example `... | jq '.output_fields | {"proc.cmdline", "proc.pname"}'`.
3. Who could exec: on kind, whoever has `.kind/kubeconfig` (cluster-admin); for any other account, `k auth can-i create pods/exec -n sentinelcore --as <account>`. kind keeps no API audit log, so the exec itself leaves no record but Falco's.
4. Anything else from that pod around the same time: other Falco alerts (`sql "SELECT occurred_at, event_type, message FROM security_events WHERE source = 'falco' AND message LIKE '%<pod>%'"`) and the API's logs (`k logs -n sentinelcore <pod> -c backend --since=1h`).
5. The image is the one it should be: `k get pod -n sentinelcore <pod> -o jsonpath='{.spec.containers[0].image}'` against `charts/sentinelcore` (local build) or `deploy/images.yaml` (GitOps, by digest).

## Stop the damage
1. Replace the pod: `k delete pod -n sentinelcore <pod>`. Its Deployment or Rollout starts a clean one from the same image; whatever the shell changed in memory or `/tmp` is gone, and the root filesystem is read-only.
2. If the shell was not an operator's own `kubectl exec`, rotate what the container held: the database passwords and the keys. `SECRET_KEY` signs out every session; `AUDIT_CHAIN_KEY` cannot be rotated without resealing the history (T-45), so check the chain first (below).
3. Look for persistence: new accounts or roles (`sql "SELECT created_at, event_type, message FROM audit_logs ORDER BY id DESC LIMIT 20"`), new API keys, and the privileged role alerts in the console.

## It is over when
- no new shell alert for that pod's replacement or any other pod;
- the audit history verifies: `k exec -n sentinelcore deploy/sentinelcore-backend -c backend -- python -m app.cli verify-audit-chain` exits with 0;
- `make cluster-check` passes.

## Escalate
A shell whose parent is the application's process (`uvicorn`, `python`), or any alert you did not cause yourself, is a compromise of the API: rotate every secret and rebuild from a known commit.

## Links
[`docs/04-threat-model.md`](../04-threat-model.md) (T-73, T-76), `falco/values.yaml`, `backend/app/services/runtime_alert_service.py`, the drill in [`docs/postmortems/`](../postmortems/).
