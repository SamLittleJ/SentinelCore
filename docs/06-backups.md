# SentinelCore - Backups

How the kind cluster's database is backed up, how a backup is proven to restore, and how to restore one for real. Phase E6; the decisions are in `docs/02` ("Backups (E6)").

## In short

| | |
|---|---|
| **What** | A `pg_dump` of the whole database, in PostgreSQL's custom format, with its SHA-256 beside it. |
| **When** | Every night at 02:00 UTC (`sentinelcore-backup`, a CronJob), and on demand with `make backup`. |
| **Kept** | The newest 7, on the volume `sentinelcore-backups`. |
| **RPO** (recovery point objective: how much may be lost) | 24 hours: the time between two dumps. |
| **RTO** (recovery time objective: how long recovery takes) | Measured on kind on 2026-11-21 with a 50 KB dump: 1 second to restore, the API serving again 5 seconds after the restore began. It grows with the database; `make backup-check` prints the restore's time on every run. |
| **Proven by** | `make backup-check`, which restores the newest dump and compares it with the live database; Cluster CI runs it on every change to the deployment. |

## What a dump holds

- Every table and every row, read as the owner of the tables, so row-level security hides nothing; the schema, its policies and grants.
- **Not the roles.** `sentinelcore_app` and the others, with their passwords, are created by `make up` and its migrations. `pg_dumpall --globals` would add the roles' password hashes to every file.
- Everything personal the database keeps: emails, sign-in addresses, the hashes of passwords and API keys. A dump is as sensitive as the database (threat model, T-81).

The dump is written as `sentinelcore-<UTC time>.dump.partial` and renamed only once complete, so a failed run leaves no file that looks whole. Older dumps beyond seven are deleted only after a new one is written.

## Commands

```bash
make backup         # a dump now, waited for; prints its name and size
make backup-check   # the newest dump restored and compared with the live database
```

`make backup-check` runs a Job of two containers, then removes it and the restored database, whatever happened:

1. **restore** (PostgreSQL's image, pinned by digest): the newest dump's SHA-256 matches; the dump is at most 26 hours old, so a CronJob that stopped is noticed; it restores into a database of its own, `sentinelcore_restore_check`, and reports how long that took.
2. **compare** (the backend's image): `python -m app.cli compare-restore` checks that the copy's audit chains verify with the key, that each chain's last restored record is in the live database with the same seal, so the copy is a prefix of the real history and not just any history sealed with the key, and that the audit log and the security events hold rows, no more than live. It prints counts, never contents.

Any problem fails the check with a line starting `PROBLEM`.

## Restoring for real

This replaces the live data with the dump's. It was exercised on kind on 2026-11-21: the restore took 1 second, the API served again 5 seconds later, the row counts matched those before, and `make cluster-check` passed 46 of 46. The exercise also found that `pg_restore` needs `--dbname`, which these steps now give.

```bash
export KUBECONFIG=.kind/kubeconfig
NS=sentinelcore

# 1. Choose the dump and check it.
kubectl -n $NS get pods -l app.kubernetes.io/name=sentinelcore-backup   # any running backup must finish first
make backup-check                                                       # the newest restores and matches

# 2. Stop everything that writes: the API.
kubectl -n $NS scale deployment sentinelcore-backend --replicas=0

# 3. Restore over the live database, as the owner, from a pod that mounts
#    the backups (the same pod as the nightly backup, waiting).
kubectl -n $NS get cronjob sentinelcore-backup -o json |
  jq '{apiVersion: "v1", kind: "Pod", metadata: {name: "restore", labels: .spec.jobTemplate.spec.template.metadata.labels},
       spec: (.spec.jobTemplate.spec.template.spec | .containers[0].command = ["sleep", "3600"])}' |
  kubectl -n $NS apply -f -
kubectl -n $NS wait --for=condition=Ready pod/restore
kubectl -n $NS exec restore -- bash -c '
  printf "*:*:*:*:%s\n" "$(cat /run/secrets/postgresql/password)" >/tmp/pgpass && export PGPASSFILE=/tmp/pgpass
  dump="$(ls -1 /backups/sentinelcore-*.dump | sort | tail -1)"
  pg_restore --clean --if-exists --exit-on-error --single-transaction --dbname="$PGDATABASE" "$dump"'
kubectl -n $NS delete pod restore

# 4. Start the API again and check the cluster.
kubectl -n $NS scale deployment sentinelcore-backend --replicas=2
kubectl -n $NS rollout status deployment sentinelcore-backend
make cluster-check
```

`--single-transaction` makes the restore all or nothing: if it fails halfway, the database stays as it was. Sessions issued after the dump are gone with it, so everyone signs in again; audit records written after the dump are lost too, which the audit chains show as shorter.

## Limits

- **`make down` deletes the backups with the database.** On kind the volume lives and dies with the cluster, so a backup protects against a broken database or data deleted by mistake, not against losing the cluster. A copy outside it comes with phase D2 (Azure Blob).
- **Not encrypted apart from the disk.** The volume sits on the same disk, with the same trust, as the database's own; whoever reads one reads the other. Encryption is decided in D2, once dumps leave the cluster (T-81).
- **No alert when backups stop.** Prometheus cannot see whether a CronJob succeeded without kube-state-metrics; `make backup-check` fails once the newest dump is over 26 hours old (T-83).
- **The SHA-256 catches damage, not forgery.** Someone who can write the volume can rewrite a dump and its sum; the audit chain and the comparison with the live database still catch a changed audit history (T-82).
- **No `make restore`.** A command that replaces the database is too easy to run by mistake; the steps above are deliberate.
