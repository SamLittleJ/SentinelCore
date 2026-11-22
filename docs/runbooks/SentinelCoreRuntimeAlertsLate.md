# SentinelCoreRuntimeAlertsLate

**Severity:** ticket. **Fires when:** at least one of Falco's alerts reached the API more than 60 s after the action it reports, within the last 30 minutes.

## What it means
The runtime detection path (Falco → falcosidekick → API) is slow, so a shell in a container shows in the console later than the detection-freshness SLO allows. The alert arrived; it was late.

## Impact
Response to a runtime attack starts later. Nothing is lost unless the delay grows into a stop, which no alert catches (T-76).

## First checks
1. A recent restart: `k get pods -n falco` (falcosidekick's `AGE` and `RESTARTS`). After falcosidekick restarts, Falco's output can stall for one to two minutes on kind.
2. Failed or slow posts: `k logs -n falco -l app.kubernetes.io/name=falcosidekick --since=30m | grep -iE 'error|webhook'`.
3. The delays recorded: `prom 'query?query=histogram_quantile(0.99, sum by (le) (rate(sentinelcore_runtime_alert_delay_seconds_bucket[30m])))' | jq '.data.result'`.
4. The path is still open: falcosidekick → API on 8000 in `network-policies/sentinelcore.yaml`; `make cluster-check` proves a shell reaches the API within 30 s.

## Stop the damage
If falcosidekick keeps failing, restart it once: `k rollout restart deploy/falco-falcosidekick -n falco`, and expect one late batch right after.

## It is over when
`make cluster-check`'s runtime check passes and the alert clears after 30 minutes without a late alert.

## Escalate
Alerts that never come raise nothing at all: Falco may stop reporting shells in long-running containers while it still reports new ones ([container shell](container-shell.md#when-you-expected-an-alert-and-none-came)). If Falco itself is down (`k get pods -n falco`, the DaemonSet), nothing is reported at all: treat it as a gap in detection until it is back.

## Links
[`docs/05-slos.md`](../05-slos.md#sentinelcoreruntimealertslate), `falco/values.yaml`, `network-policies/falco.yaml`.
