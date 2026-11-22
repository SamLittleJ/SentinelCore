# Runbooks

What to do when an alert fires, one file per alert. The four Prometheus alerts (`observability/slo-rules.yaml`) link here through their `runbook_url`; the three runtime alerts come from Falco and appear in the console as platform alerts of the owner ([`docs/04`](../04-threat-model.md), E3).

| Runbook | Fires when | Severity |
|---|---|---|
| [SentinelCoreApiDown](SentinelCoreApiDown.md) | Prometheus has reached no API pod for two minutes | page |
| [SentinelCoreAvailabilityBurnRate](SentinelCoreAvailabilityBurnRate.md) | 5xx spend the 30-day availability budget too fast | page, ticket |
| [SentinelCoreSignInLatencyBurnRate](SentinelCoreSignInLatencyBurnRate.md) | Too many sign-ins take over 0.5 s | page, ticket |
| [SentinelCoreRuntimeAlertsLate](SentinelCoreRuntimeAlertsLate.md) | A Falco alert reached the API over 60 s late | ticket |
| [Container shell](container-shell.md) | `CONTAINER_SHELL_DETECTED` (T1059): a shell with a terminal in one of our containers | incident |
| [Sensitive file read](sensitive-file-read.md) | `SENSITIVE_FILE_READ` (T1003.008): `/etc/shadow` or a file like it read in a container | incident |
| [Network tool in a container](container-network-tool.md) | `CONTAINER_NETWORK_TOOL` (T1059.004): a shell redirected to the network, or netcat | warning |

Every runbook has the same parts: what the alert means, its impact, the first checks with the exact commands, how to stop the damage, how to know it is over, when to escalate, and links. The commands assume the `make up` cluster; on the GitOps cluster use `.kind/gitops/kubeconfig`, and remember that Argo CD reverts changes made by hand within a minute (`docs/07-gitops.md`).

Two helpers used throughout, from the repository's root:

```bash
export KUBECONFIG=.kind/kubeconfig     # or .kind/gitops/kubeconfig
alias k=.tools/kubectl
# A query to the database as the owner of the tables, which sees every organization.
sql() { k exec -n sentinelcore sentinelcore-postgresql-0 -- psql -U sentinelcore -d sentinelcore -tAc "$1"; }
# Prometheus' HTTP API, through the Kubernetes API (no port to open).
prom() { k get --raw "/api/v1/namespaces/observability/services/prometheus-server:80/proxy/api/v1/$1"; }
```

`make grafana` opens Grafana at http://127.0.0.1:3001 (user admin, password in `.kind/grafana.txt`), with the overview and SLO dashboards and the traces in Tempo.

The drill in [`docs/postmortems/`](../postmortems/) followed the shell runbook end to end; what it found missing was fixed here.
