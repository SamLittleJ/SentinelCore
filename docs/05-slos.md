# SentinelCore - Service Level Objectives

What SentinelCore promises about its own service on the kind cluster, how each promise is measured, and what to check when an alert fires. Phase E5; the decisions are in `docs/02` ("SLOs and alerts (E5)").

- **Where:** the cluster only (`make up`). Docker Compose has no SLO rules.
- **Rules:** [`observability/slo-rules.yaml`](../observability/slo-rules.yaml), loaded by `make up` into the cluster's Prometheus; unit tests in [`observability/slo-rules.test.yaml`](../observability/slo-rules.test.yaml), run by `make deploy-lint` with promtool.
- **Dashboard:** "SentinelCore SLOs" in Grafana (`make grafana`, folder SentinelCore).
- **Alerts:** firing alerts show in Prometheus and on the dashboard. There is no Alertmanager, so nothing is sent; it comes with a real receiver in phase D2.

## Terms

- **SLI** (service level indicator): the measured share of good events, for example requests without a 5xx.
- **SLO** (service level objective): the target for the SLI over a window, for example 99.5% over 30 days.
- **Error budget:** what the objective allows to go wrong: 0.5% of requests for 99.5%.
- **Burn rate:** how fast the budget is spent compared with spending it exactly over the window. 1 spends it in 30 days; 14.4 spends 2% of it in an hour.

## The objectives

| SLO | Good event | Objective | Budget | Source |
|---|---|---|---|---|
| Availability | A request answered without a 5xx. `/health`, `/health/ready` and `/metrics` are left out; 4xx and 429 are answers, not errors. | 99.5% over 30 days | 0.5% | `sentinelcore_http_requests_total` |
| Sign-in latency | A `POST /auth/login` handled within 0.5 s. | 95% over 30 days | 5% | `sentinelcore_http_request_duration_seconds`, bucket `le="0.5"` |
| Detection freshness | One of Falco's alerts reaching the API within 60 s of Falco seeing the action. | 99% over 30 days | 1% | `sentinelcore_runtime_alert_delay_seconds`, bucket `le="60"` |

Detection rules run inside the request that brings their event, so the time from an event to its alert is milliseconds. The only path with a real delay is Falco → falcosidekick → `POST /ingest/runtime`, which is what the third SLO measures. Every alert received counts, whether it is stored, ignored or a duplicate: the delay belongs to the path, not to the decision. A time from Falco a little ahead of the API's clock counts as no delay.

On 2026-11-21, 40 sign-ins on kind took 0.40 s at the median and 0.47 s at the 95th percentile, measured from the client through nginx. The hash of the password (Argon2) is slow on purpose, so the objective has little room: a slower node or several sign-ins at once can spend the budget.

## The alerts

Burn rates follow the multi-window method of the Google SRE Workbook (chapter 5). A long window shows that enough budget is gone; a short one shows that it is still going, so the alert ends soon after the problem does, without a `for:` clause.

| Severity | Windows | Burn rate | Budget spent |
|---|---|---|---|
| page | 1h and 5m | 14.4 | 2% in an hour |
| page | 6h and 30m | 6 | 5% in six hours |
| ticket | 1d and 2h | 3 | 10% in a day |

A burn-rate alert also needs at least 20 requests in its long window: with almost no traffic, one 5xx in three requests would page. A real outage with no traffic at all is caught by `SentinelCoreApiDown`.

### SentinelCoreAvailabilityBurnRate

**Means:** the API answers with 5xx fast enough to spend the 30-day budget within days (page) or about three times too fast (ticket).

**First checks:**
1. The dashboard's availability row: which window is high, and since when.
2. Which routes fail: in Prometheus, `sum by (route, status_code) (rate(sentinelcore_http_requests_total{status_code=~"5.."}[5m]))`.
3. The API's logs for those requests: `kubectl logs -n sentinelcore -l app.kubernetes.io/name=sentinelcore-backend`; a log line's `trace_id` finds its trace in Tempo.
4. The database: `kubectl get pods -n sentinelcore` and `make cluster-check` (the API reaches the database).

### SentinelCoreSignInLatencyBurnRate

**Means:** too many sign-ins take longer than 0.5 s.

**First checks:**
1. Whether sign-ins come in a burst (a spray or a flood): the overview dashboard's failed logins, and refused sign-ins (`sentinelcore_login_refused_total`). A flood is a security matter first (T-80).
2. The API pods' CPU against their limits: the password hash is CPU-bound.
3. A slow sign-in's trace in Tempo: the time spent in SQL against the time spent hashing.

### SentinelCoreRuntimeAlertsLate

**Means:** at least one of Falco's alerts reached the API more than 60 s after the action, within the last 30 minutes (ticket).

**First checks:**
1. Whether falcosidekick restarted recently: `kubectl get pods -n falco`. After a restart, Falco's output can stall for one to two minutes (T-76); the alerts arrive late, not lost.
2. falcosidekick's logs for failed posts: `kubectl logs -n falco -l app.kubernetes.io/name=falcosidekick`.
3. The API's policy still lets falcosidekick in (`network-policies/sentinelcore.yaml`).

### SentinelCoreApiDown

**Means:** Prometheus has reached no API pod for two minutes. The availability ratio shows nothing then, because no request is recorded.

**First checks:**
1. `kubectl get pods -n sentinelcore`: are the API pods running and ready?
2. Prometheus' targets (`/targets`): an error there, for example a 401, points to the metrics token rather than the API.
3. The API's policy still lets Prometheus in (`network-policies/sentinelcore.yaml`).

## Limits

- **No 30-day budget on kind.** Prometheus keeps two days in an `emptyDir` and loses everything with `make down`, so the alerts use windows of a day at most, the Workbook's 3d/6h pair is left out, and the dashboard shows the budget spent in the data it keeps, assuming steady traffic. Durable storage comes with phase D2.
- **Nobody is notified.** No Alertmanager (D2).
- **Nothing watches Prometheus.** If Prometheus itself is down, no alert fires (T-79).
- **Low traffic.** Below 20 requests in the long window, burn-rate alerts stay silent.
- **A slow 5xx sign-in counts against latency too:** the histogram has no status label.
- **Falco's alerts are few,** so the freshness SLO is a plain threshold alert, not a burn rate.
