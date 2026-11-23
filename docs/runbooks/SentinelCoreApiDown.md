# SentinelCoreApiDown

**Severity:** page. **Fires when:** `(sum(up{job="sentinelcore-backend"}) or vector(0)) == 0` for two minutes: Prometheus has scraped no API pod.

## What it means
No API pod answers Prometheus' scrape. Either no pod is running or ready, or every pod runs but Prometheus cannot reach or authenticate to `/metrics`. The availability SLO shows nothing meanwhile, since no request is recorded.

## Impact
If the pods are down: the console and ingestion are down, and so is detection. If only the scrape fails: users are served, but the SLOs and their alerts are blind.

## First checks
1. Are the pods running and ready?
   ```bash
   k get pods -n sentinelcore -l app.kubernetes.io/name=sentinelcore-backend
   k get deploy,rollout -n sentinelcore 2>/dev/null
   ```
   A Deployment or Rollout with `0` replicas was scaled down; `CrashLoopBackOff` or `Pending` points to the pod itself.
2. Why a pod does not start: `k describe pod -n sentinelcore <pod>` (events at the end: image pull, a refusal by Kyverno, resources) and `k logs -n sentinelcore <pod> -c backend --previous`.
3. Does the API answer users? `curl -s http://localhost:8080/api/health/ready` should give `{"status":"ok","database":"ok"}`.
4. If the pods are ready, the scrape: `prom targets | jq '.data.activeTargets[] | select(.labels.job=="sentinelcore-backend") | {health, lastError}'`. A `401` means the metrics token in `prometheus-metrics-token` no longer matches the API's `METRICS_TOKEN`; a timeout points to the network policy (`network-policies/sentinelcore.yaml`, Prometheus → API on 8000).

## Stop the damage
- Scaled to zero: `k scale deploy/sentinelcore-backend -n sentinelcore --replicas=2` on `make up`; on the GitOps cluster, Argo CD restores the replicas from Git by itself.
- A bad version: on `make up`, `k rollout undo deploy/sentinelcore-backend -n sentinelcore`; on the GitOps cluster, open a `make deploy-pr` with the previous good commit.
- The database down: see `k get pods -n sentinelcore sentinelcore-postgresql-0` first; the API is not ready without it.
- A token mismatch: `make up` again copies the API's token to Prometheus (`create_observability_secrets` in `scripts/cluster.sh`).

## It is over when
`prom 'query?query=sum(up{job="sentinelcore-backend"})'` returns the number of pods, the alert is gone from `prom alerts`, and `make cluster-check` passes.

## Escalate
If the pods are ready and the scrape works but the alert stays, Prometheus itself may be stuck: `k get pods -n observability` and `prom 'status/runtimeinfo'`.

## Links
[`docs/05-slos.md`](../05-slos.md#sentinelcoreapidown), `observability/slo-rules.yaml`.
