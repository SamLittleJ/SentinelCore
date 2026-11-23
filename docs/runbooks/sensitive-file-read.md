# Sensitive file read (SENSITIVE_FILE_READ)

**Severity:** incident. **MITRE ATT&CK:** T1003.008 (/etc/passwd and /etc/shadow). **Comes from:** Falco's rule "Read sensitive file untrusted". Message: `Sensitive file <file> read in container <container> of pod <pod> (namespace <namespace>)`.

## What it means
A process that should not read credential files (`/etc/shadow`, `/etc/sudoers` and similar) read one in a container. Our containers do not run as root, so `/etc/shadow` itself is usually unreadable to them; the alert means something tried, or a container runs as root.

## Impact
The read itself may have failed. What matters is who tried: it is the step an attacker takes right after getting code to run, looking for credentials to move on with.

## First checks
1. The alert and its file: `sql "SELECT id, occurred_at, message FROM security_events WHERE source = 'falco' AND event_type = 'SENSITIVE_FILE_READ' ORDER BY id DESC LIMIT 5"`.
2. The process: `k logs -n falco ds/falco -c falco --since=1h | grep 'Sensitive file' | grep '<pod>'` (`proc.cmdline`, `user.uid`, the parent).
3. The container's user: `k get pod -n <namespace> <pod> -o jsonpath='{.spec.securityContext.runAsUser} {.spec.containers[0].securityContext}'`; Kyverno and the "restricted" standard refuse root in `sentinelcore`, so root there means the policies were bypassed.
4. A shell before it: the same pod in the [container shell](container-shell.md) runbook's first check.

## Stop the damage
Replace the pod (`k delete pod -n <namespace> <pod>`) and follow the [container shell](container-shell.md) runbook's steps if a shell or anything you did not run preceded the read.

## It is over when
No further read or shell alert from that workload; `make cluster-check` passes, including its refusal of a pod running as root.

## Escalate
A read in a pod running as root in `sentinelcore` means admission failed: check `k get validatingpolicy,imagevalidatingpolicy` and Kyverno's pods.

## Links
`falco/values.yaml`, `kyverno/pod-rules.yaml`, [`docs/04-threat-model.md`](../04-threat-model.md).
