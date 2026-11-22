# SentinelCoreAvailabilityBurnRate

**Severity:** page (1 h and 5 min windows over 14.4×, or 6 h and 30 min over 6×) or ticket (1 d and 2 h over 3×). **Fires when:** the API's 5xx, outside `/health` and `/metrics`, spend the 30-day budget of 0.5% that fast, with at least 20 requests in the long window.

## What it means
The API answers with server errors. 4xx and 429 are not errors here: a refused request is the API working.

## Impact
Some requests fail: sign-ins, console pages or ingestion batches, which senders retry. A page-level burn spends 2% of the month's budget in an hour.

## First checks
1. Which windows are high and since when: Grafana, dashboard "SentinelCore SLOs", availability row.
2. Which routes fail:
   ```bash
   prom 'query?query=sum by (route, status_code) (rate(sentinelcore_http_requests_total{status_code=~"5.."}[5m]))' | jq '.data.result'
   ```
3. Why: the API's logs, `k logs -n sentinelcore -l app.kubernetes.io/name=sentinelcore-backend -c backend --since=15m | grep '"status_code": 5'`; a line's `trace_id` finds the request in Tempo (Grafana, Explore, Tempo), with its SQL.
4. The database: `k get pods -n sentinelcore`, `curl -s http://localhost:8080/api/health/ready`, and `make cluster-check` (the API reaches the database, the API's role does not bypass row-level security).
5. A new version: on the GitOps cluster, `.tools/kubectl-argo-rollouts get rollout sentinelcore-backend -n sentinelcore`; a canary normally stops itself above 1%.

## Stop the damage
- A bad version: roll back (`k rollout undo deploy/sentinelcore-backend -n sentinelcore` on `make up`; on GitOps, `make deploy-pr` with the previous good commit, or abort the canary: `.tools/kubectl-argo-rollouts abort sentinelcore-backend -n sentinelcore`).
- The database: restart nothing by guess; if it lost its data, restore it ([`docs/06-backups.md`](../06-backups.md)).
- One route: if a single route fails and the others are healthy, it is a bug; open an issue with the trace.

## It is over when
The 5 min error ratio is back under the threshold: `prom 'query?query=sentinelcore:slo_availability_error_ratio:rate5m'`; the page clears soon after, as its short window falls.

## Escalate
If 5xx come from every route at once and the database is healthy, look at the API's resources (`k top pod -n sentinelcore` where metrics exist, or OOMKilled in `k describe pod`).

## Links
[`docs/05-slos.md`](../05-slos.md#sentinelcoreavailabilityburnrate), `observability/slo-rules.yaml`, `observability/slo-rules.test.yaml`.
