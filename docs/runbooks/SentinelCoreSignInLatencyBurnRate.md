# SentinelCoreSignInLatencyBurnRate

**Severity:** page or ticket, on the same windows as availability. **Fires when:** more than 5% of `POST /auth/login` take over 0.5 s fast enough to spend the 30-day budget, with at least 20 sign-ins in the long window.

## What it means
Sign-ins are slow. The password hash (Argon2id) is meant to cost CPU, so slowness usually means many sign-ins at once or too little CPU.

## Impact
People wait to sign in; a flood can also delay every other request on the same pods.

## First checks
1. A burst? A spray or a flood is a security matter first (T-80):
   ```bash
   prom 'query?query=sum(rate(sentinelcore_http_requests_total{route="/auth/login"}[5m]))' | jq '.data.result'
   prom 'query?query=sum(rate(sentinelcore_login_refused_total[5m]))' | jq '.data.result'
   ```
   and the console's alerts (password spray, sprays across organizations).
2. CPU against the limits: `k describe pod -n sentinelcore <api pod>` (limits 500m) and the throttling in the overview dashboard if shown.
3. Where the time goes: a slow sign-in's trace in Tempo, SQL against hashing.

## Stop the damage
- A spray or flood: the per-address limit already refuses after 20 failures; contain the targeted accounts from the console if needed (Organization → Users).
- Too little CPU: raise `backend.resources.limits.cpu` in `charts/sentinelcore/values.yaml` through a pull request, or more replicas.

## It is over when
`prom 'query?query=sentinelcore:slo_sign_in_slow_ratio:rate5m'` is under the threshold and the alert clears.

## Escalate
Slow sign-ins with no burst and idle CPU point to the database: its trace spans and `k logs -n sentinelcore sentinelcore-postgresql-0`.

## Links
[`docs/05-slos.md`](../05-slos.md#sentinelcoresigninlatencyburnrate), `observability/slo-rules.yaml`.
