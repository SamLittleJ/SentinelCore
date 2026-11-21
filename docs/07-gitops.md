# SentinelCore - GitOps on kind

How the GitOps cluster runs SentinelCore from Git, next to `make up`'s cluster, and how a new version is deployed. Phase D1a; the decisions are in `docs/02` ("GitOps (D1a)").

## Two ways to run the cluster

| | `make up` | `make gitops-up` |
|---|---|---|
| **For** | Daily work: what is in your working tree | What is merged: what `main` describes |
| **Cluster** | `sentinelcore`, console at http://localhost:8080 | `sentinelcore-gitops`, console at http://localhost:8081 |
| **Created by** | `kind` from `scripts/cluster.sh` | Terraform (`gitops/main.tf`) |
| **Installs the rest** | `helm` and `kubectl`, from the script | Argo CD, from Git |
| **Images** | Built locally (or `FROM=registry`) | The signed images in `deploy/images.yaml` only |
| **State** | `.kind/` | `.kind/gitops/` (Terraform's state too) |

Both can run at once. On Linux two kind clusters need more inotify instances than the usual default of 128 (kube-proxy then fails with "too many open files"):

```bash
sudo sysctl -w fs.inotify.max_user_instances=512 fs.inotify.max_user_watches=524288
echo -e 'fs.inotify.max_user_instances=512\nfs.inotify.max_user_watches=524288' | sudo tee /etc/sysctl.d/99-kind.conf
```

## What `make gitops-up` does

1. **Terraform** (`gitops/`, pinned with its providers in `gitops/.terraform.lock.hcl`) creates the kind cluster and installs Argo CD from its chart, which `scripts/tools.sh` downloads and checks by SHA-256. No Secret is created here: Terraform's state keeps everything in plain text.
2. **The namespaces and the Secrets**, generated as for `make up` (`scripts/cluster.sh prepare`) and never written to Git or to the state. Argo CD's own admin password is copied to `.kind/gitops/argocd.txt`.
3. **The root application** (`deploy/root.yaml`): Argo CD renders `deploy/` into one application per component and syncs them in waves (Kyverno, then its policies and the network policies, then Falco and the observability ConfigMaps, then the observability stack and PostgreSQL, then SentinelCore), each wave healthy before the next.
4. **The first owner**, as for `make up`; its password goes to `.kind/gitops/owner.txt`.

`GITOPS_REVISION` chooses the Git revision Argo CD reads (default `main`); CI gives it the commit under test.

## What Argo CD manages

- **Everything that `make up` installs**, except the Secrets and the first owner. Sync is automated, with `prune` (what leaves Git leaves the cluster) and `selfHeal` (a change made by hand is reverted).
- **External charts** come from their publishers' OCI registries, pinned by digest (`deploy/values.yaml`): Kyverno, Falco, the Collector, Tempo, Prometheus and Grafana, at the same versions `scripts/tools.sh` pins for `make up`. Falco, the Collector, Tempo and Prometheus are byte for byte the files `tools.sh` checks; Kyverno's and Grafana's OCI packages differ in their packaging but render the same manifests.
- **Values are not copied**: each application reads the same values files as `make up`, at the same revision.
- **SLO rules and dashboards** come from `charts/observability-config`, a small chart both paths install, whose files are links to `observability/slo-rules.yaml` and the dashboards. Prometheus' config reloader picks up a change of the rules.

## Deploying a new version

The images in `deploy/images.yaml` are what the GitOps cluster runs. After a merge to `main` has published signed images:

```bash
make deploy-pr REVISION=<12-character commit of main>
```

It checks the images' signature and attestations as `make up FROM=registry` does (`scripts/verify-images.sh`), writes their digests to `deploy/images.yaml` on a branch `deploy/<commit>` and opens a pull request. Merging it deploys the version: Argo CD reads `main` every three minutes, and Kyverno checks the signature again before each pod starts.

The pull request is opened from your machine, with your `gh` login, because one opened by a workflow with its own token would not start the checks that `main` requires.

## Checks

- `make cluster-check CLUSTER=gitops` runs every check of `make up`'s cluster on the GitOps one, plus two of its own: an image of ours that CI did not sign is refused, and a change made by hand (the API's replicas) is reverted from Git within a minute.
- `make deploy-lint` renders `deploy/` and requires Kyverno, then its policies, to sync before every other application, and checks that the Terraform is formatted and valid.
- Cluster CI runs `make gitops-up` with Argo CD reading the commit under test, then `make cluster-check CLUSTER=gitops`.

## Reaching Argo CD

```bash
make argocd   # http://127.0.0.1:3002, user admin, password in .kind/gitops/argocd.txt
```

There is no NodePort; the UI is reached only through this port-forward.

## Limits

- **Argo CD can change anything in the cluster.** It installs CRDs and namespaces, so it holds near cluster-admin rights. On kind it is reachable only through a port-forward, with a password kept locally (T-84).
- **A merge to `main` deploys.** Review and CI stand between a change and the cluster, and only images signed by CI on `main` run (T-85).
- **Charts are trusted by digest, not by SHA-256 of a file.** A digest pins the exact OCI artifact; a registry that served other bytes under it would be caught (T-86).
- **`make gitops-down` deletes the whole cluster**, not the applications one by one: some charts' delete hooks would wait for namespaces already gone.
