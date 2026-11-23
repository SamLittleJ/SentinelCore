# Network tool in a container (CONTAINER_NETWORK_TOOL)

**Severity:** warning. **MITRE ATT&CK:** T1059.004 (Unix Shell). **Comes from:** Falco's rules "Redirect STDOUT/STDIN to Network Connection in Container" and "Netcat Remote Code Execution in Container". Message: `Shell input or output sent over the network in container <container> of pod <pod> (namespace <namespace>)`.

## What it means
A shell's input or output was wired to a network connection, or netcat ran with a command: the shape of a reverse shell.

## Impact
If it connected out, someone outside may control a shell in the container. In our namespaces nothing may reach the internet (default deny, ADR 0009), so the connection most likely failed or stayed inside the cluster.

## First checks
1. The alert: `sql "SELECT id, occurred_at, message FROM security_events WHERE source = 'falco' AND event_type = 'CONTAINER_NETWORK_TOOL' ORDER BY id DESC LIMIT 5"`.
2. Where it tried to connect: `k logs -n falco ds/falco -c falco --since=1h | grep -iE 'Redirect|Netcat' | grep '<pod>'` (`fd.name` holds the address and port).
3. Whether that address is reachable from the pod's namespace at all: the namespace's policies (`k get networkpolicy -n <namespace>`); `make cluster-check` proves the API cannot reach the internet.
4. A shell before it: the [container shell](container-shell.md) runbook.

## Stop the damage
Replace the pod (`k delete pod -n <namespace> <pod>`). If the address was inside the cluster, check that pod too. If any policy let the connection out, close it in `network-policies/` before anything else.

## It is over when
No further alert from that workload, and `make cluster-check`'s refused flows all pass.

## Escalate
A connection that succeeded to an address outside the cluster means a network policy is missing or wrong: treat the pod's secrets as stolen ([container shell](container-shell.md), step 2 of stopping the damage).

## Links
`network-policies/`, `falco/values.yaml`, [ADR 0009](../adr/0009-default-deny-network.md).
