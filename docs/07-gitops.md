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

## Canary

On the GitOps cluster the API is an Argo Rollouts `Rollout`, not a `Deployment` (`deploy/sentinelcore.yaml` turns it on; `make up` keeps the `Deployment`). Argo Rollouts' controller is an application of its own (`argo-rollouts`, chart pinned by digest, values in `argo-rollouts/values.yaml`), synced before the API.

A new version, from a merged `make deploy-pr`, goes out in steps:

1. **20%**: one new pod of five. With no ingress or service mesh, the traffic is split by the number of pods behind the API's Service.
2. **Analysis**, about two minutes: a Job sends five requests a second for two minutes to the new pods only, through the Service `sentinelcore-backend-canary`. Prometheus reads, after 90 seconds and then every 30 seconds, four times in all, the new pods' share of 5xx (without `/health` and `/metrics`, as the SLOs) and how many requests they answered. The first reading waits for the traffic Job, which starts only once Kyverno has checked its image.
3. **60%**: three new pods of five, then the same analysis.
4. **100%**: the new version becomes the stable one.

Argo Rollouts puts the new version's hash in that Service's selector; Argo CD is told to leave that key alone (`ignoreDifferences` in `deploy/templates/applications.yaml`), since a selector is replaced whole on apply and its self-heal would otherwise send the traffic to every pod.

A step passes below 1% of 5xx and with at least 100 requests: an analysis that saw no traffic fails, it does not pass. The traffic uses only a request that reads the database and writes nothing: an ingestion batch with a well-formed key that does not exist, which the API looks up and refuses with 401. Failed sign-ins were not used: each would write a security event, spend the address's sign-in budget and could raise an alert. The script (`backend/app/canary_traffic.py`, linked into the chart) runs with the Python of the signed backend image, whatever its version, and holds no Secret.

When an analysis fails, Argo Rollouts stops the canary: the new pods go, the stable version keeps all five, and Argo CD shows the application as Degraded. Git is not changed: `deploy/images.yaml` still names the version that was stopped until the next `make deploy-pr`, with a good version or the previous one.

To follow a canary:

```bash
export KUBECONFIG=.kind/gitops/kubeconfig
.tools/kubectl-argo-rollouts get rollout sentinelcore-backend -n sentinelcore --watch
```

## Previews

A pull request of this repository labelled `preview` gets a copy of the application of its own, on the GitOps cluster, in the namespace `preview-<number>`:

1. **Images.** `.github/workflows/preview-images.yml` builds the pull request's head commit (not GitHub's merge of it into `main`), scans it as `images-ci.yml` does on `main`, and publishes the backend and console to GHCR as `pr-<head commit>`, signed with cosign and attested (SLSA provenance and the SBOM), on every push while the label is on. It runs whatever the pull request changes. Pull requests from forks get no token to publish or sign with, and Dependabot's none either, so only this repository's own branches can have a preview.
2. **Applications.** Argo CD's ApplicationSet controller asks GitHub's API every five minutes, without a token, for the open pull requests with the label (`deploy/templates/previews.yaml`), and makes two applications for each:
   - `preview-<n>-base`, always from `main`: the namespace, under the "restricted" Pod Security Standard and Kyverno's preview policies; the network policies; the Job that creates its Secrets; and its database, named `sentinelcore_demo`, without backups (`charts/preview`, `charts/postgresql`, `deploy/preview-postgresql.yaml`);
   - `preview-<n>`, from the pull request's head commit: the application with one API pod, no canary, no traces, no Falco token and no NodePort (`charts/sentinelcore`, `deploy/preview.yaml`), and a Job that creates the first owner after each sync. Its migrations need the database, so its first syncs fail and are retried until the base is ready.
3. **Admission.** In the previews' namespaces Kyverno accepts our images signed by `preview-images.yml` on a pull request or by `images-ci.yml` on `main`, and resolves the `pr-<commit>` tag to the digest it checked (`kyverno/previews.yaml`). `sentinelcore` keeps accepting `main`'s signature only. The pod rules are those of `sentinelcore`, except that the Secrets' Job, under its own account, may mount a token.
4. **Updates and deletion.** A new push gives a new head commit, new images and an updated preview. Closing or merging the pull request, or removing the label, deletes both applications, and Argo CD deletes everything they made, the namespace included.

To open one, once Argo CD has made it:

```bash
make preview PR=<number>          # http://127.0.0.1:8090, owner owner@sim.example.com
make preview PR=<number> SEED=1   # first loads the demo's ninety days of data
```

`make preview` waits for both applications, writes the owner's password to `.kind/gitops/preview-<n>.txt` (mode 600) and forwards a port to the console until Ctrl-C. With `SEED=1` it first runs `make demo`'s simulator from this machine through port-forwards to the preview's API and database, once per preview. Through a port-forward every request arrives from the pod's own loopback address, so the simulator names each attacker's address in `X-Forwarded-For` (`--forwarded-for`), which the preview's API, and only a preview's, trusts from `127.0.0.1`.

What a pull request can change is limited by where each part comes from and by its Argo CD project (`previews`): its application may create nothing outside its namespace and no network policy, role or quota in it. The base, the policies and the ApplicationSets come from `main`.

## Checks

- `make cluster-check CLUSTER=gitops` runs every check of `make up`'s cluster on the GitOps one, plus its own: an image of ours that CI did not sign is refused, a change made by hand (the API's replicas) is reverted from Git within a minute, and the canary's checks (`scripts/canary-check.sh`).
- **The canary drill** in those checks: a copy of the API under its own name, never behind the real Service, run with the API's own `AnalysisTemplate` and a shorter analysis (one minute of traffic, two readings). A harmless change must be promoted; a version on a database role without rights on the tables, ready but answering 500, must be stopped with the previous version kept. Its metrics are renamed `sentinelcore_drill_*`, so its 500s never reach the SLOs. It also checks that the traffic wrote no event, key usage or audit record, and removes the copy, its Secret and the role at the end.
- `make deploy-lint` renders `deploy/` and requires Kyverno, then its policies, to sync before every other application and Argo Rollouts before the API; it checks that every query of the analysis reads the new pods only, that it requires a minimum of requests and that every step is analysed, and that the Terraform is formatted and valid.
- **The preview drill** in those checks: `preview-0`, made from the ApplicationSets' own templates as if pull request 0 were open at the revision the cluster reads, with `main`'s signed images, so nothing asks GitHub. It must become synced and healthy with its Secrets and its owner; keep every Secret when their Job runs again; reach its own database but neither `sentinelcore`'s API or database nor the internet, and not be reached from `sentinelcore`; refuse a pod with a token other than the Secrets' Job, a writable root filesystem or an unsigned image of ours; give the Secrets' account no right but reading and creating Secrets in its namespace; and disappear, namespace included, when its applications are deleted (`scripts/preview-check.sh`).
- `make deploy-lint` also checks that a preview's base is read from `main`, that the pull request's project allows no cluster resource, network policy or role, that the preview pods meet the same container rules as `sentinelcore`'s, and that `sentinelcore` accepts no image signed on a pull request.
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
- **Turning the API into a Rollout stops it briefly, once.** Argo CD deletes the old Deployment as it creates the Rollout, so on that first sync the API has no pod for some tens of seconds. A `Rollout` with a `workloadRef` to the Deployment would avoid it, at the cost of two objects for one workload.
- **The canary is split by pods, not by requests.** Twenty percent means one pod of five behind the Service; with few users, the new version may get more or fewer of their requests in a step. Its analysis does not depend on them, since it sends its own traffic.
- **Kyverno's check of a new image is close to its time limit.** For each pod of ours it verifies the signature, the provenance and the SBOM online with Sigstore: 17 to 28 seconds on kind for an image, against the admission webhook's 30 seconds, and it keeps no result for this kind of policy, so a second pod pays again. When several pods start at once (the migrations, then five replicas), the checks time out and are retried without end. The network to GitHub and Sigstore answers in about 0.3 seconds from inside the cluster; each check takes about 5.5 seconds from this machine too. `make gitops-up` restarts Kyverno's admission controller once when it sees such a timeout, which has let them through; the canary's steps, one pod and then two more, are themselves gentle on it. Checking the SBOM only before deployment (`make deploy-pr`) would cut a third of the time; that would change the admission rule of phase C, so it is left for a decision of its own. In CI it passes.
- **The development cluster follows the revision it was built with.** A cluster built from a branch (`GITOPS_REVISION=feat/...`) keeps reading that branch after it is merged and deleted: rebuild it on `main` with `make gitops-up`. `make gitops-up` now waits for every application to report the target commit, not just to be synced.
- **A preview runs a pull request's code.** Its images are signed, scanned and admitted by the same rules, its namespace is apart on the network and its project narrow, but the code is the pull request's: only the owner labels a pull request, and only this repository's branches can be previewed (T-91).
- **A preview appears up to five minutes after the label or a push**, plus the time to build and sign its images: GitHub cannot send webhooks to a local cluster, and without a token Argo CD may ask GitHub's API 60 times an hour (T-93). Its first syncs fail until its base is ready, and Kyverno checks each new image online, so a preview takes a few minutes more to be healthy.
- **A sync that fails is retried before a newer commit is synced.** Argo CD retries a preview's sync up to 20 times; while it does, a newer push waits. The images' runs are never cancelled for that reason, so every commit gets complete images.
- **No limit on how many previews run.** Each reserves about 0.3 CPU and 0.6 GiB; the kind cluster holds a few.
- **The `pr-*` images stay in GHCR** after the pull request closes. They are public, as the code is (T-94); nothing deletes them.
- **A preview's base follows `main`.** A pull request that changes `charts/preview`, `charts/postgresql` or the preview policies does not see its change in its own preview; the drill in `make cluster-check CLUSTER=gitops` checks them at the commit under test.
- **`make gitops-down` deletes the whole cluster**, not the applications one by one: some charts' delete hooks would wait for namespaces already gone.
