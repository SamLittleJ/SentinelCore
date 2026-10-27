# SentinelCore

An API-first platform for identity and access management, audit logging and security event monitoring (SIEM-light), built as a modular monolith.

## Repository layout

```text
.
├── backend/              # FastAPI API, SQLAlchemy models, Alembic migrations, tests
├── frontend/             # web app (React, TypeScript, Vite, Tailwind CSS, shadcn/ui)
├── docs/                 # project documentation, by stage, and the detection evaluation
├── infra/                # Prometheus and Grafana configuration
├── charts/               # Helm charts: postgresql, then sentinelcore (make up)
├── kind/                 # the local kind cluster's configuration
├── scripts/              # make verify, make screenshots, make up / down / cluster-check, make deploy-lint, make scan / scan-images / verify-images, pinned tools
├── security/             # scanners locked by hash and expiring scan exceptions
├── .github/workflows/    # backend, frontend, deployment, cluster, supply chain, images and CodeQL
├── SECURITY.md           # private vulnerability reporting and supported versions
└── docker-compose.yml    # PostgreSQL, Prometheus and Grafana for local development
```

## Quick start

Requirements: Docker, Python 3.12+, Node.js (frontend only).

```bash
# Local PostgreSQL and a separate database for tests
docker compose up -d
docker exec sentinelcore-postgres createdb -U sentinelcore sentinelcore_test

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
python -m alembic upgrade head
python -m app.cli grant-api-login
python -m app.cli create-owner --email owner@example.com --username owner
python -m uvicorn app.main:app --reload
```

Before the migrations, set `SECRET_KEY` and `AUDIT_CHAIN_KEY` in `.env` to two different random values: the second seals the audit history (see `backend/README.md`). `create-owner` asks for the owner's password and creates the organization's first account. There is no public sign-up: the owner and admins invite everyone else from the Users page, and the person invited picks a username and a password at `/invite`.

The API runs at `http://localhost:8000`. Its interactive docs, which `API_DOCS_ENABLED=true` in `.env` turns on for development, are at `http://127.0.0.1:8000/docs`: another host than the web app's `localhost`, so the docs' code from a CDN never gets the web app's cookies. PostgreSQL listens on `localhost` only, because the development password in `docker-compose.yml` is public.

Frontend, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

The web app runs at `http://localhost:5173`. Details: [frontend/README.md](frontend/README.md).

In Swagger UI, the **Authorize** button takes the email in the `username` field, plus the password.

## Demo

One command shows SentinelCore with ninety days of three synthetic organizations behind it:

```bash
make demo
```

It needs the Quick start done once (Docker, `backend/.venv` with `backend/.env`, `npm install` in `frontend/`), the `make` tool, and ports 8000 and 5173 free. It then:

1. starts PostgreSQL and recreates a separate `sentinelcore_demo` database, leaving the development one alone;
2. creates the owner `owner@sim.example.com` with a random password, written only to `.demo/owner.txt` (readable by you alone, ignored by git) and never printed;
3. fills ninety days, ending now, through the API, for three organizations, each with its own email domain, office address and VPN key:
   - **Acme**, the attacked one: 36 people joining by invitation, an admin and an analyst, their routine sign-ins, and the attack simulator's attacks spread across the days at random hours (password sprays, stolen passwords used on dormant accounts and from unknown places, and the evasive variants the rules miss);
   - **Globex**: 12 people and an admin who only keep to their routine;
   - **Initech**: 6 people and an admin, also quiet, suspended by the owner at the end of the run;
4. plays today's events live: brute force against two Acme accounts, an admin role granted, the operators' response (sessions closed, an account locked, the dormant accounts deactivated, a promotion, new invitations, a retired API key), a few failed sign-ins on emails no account has, which belong to the platform, and Initech's suspension;
5. writes each admin's password to `.demo/acme-admin.txt`, `.demo/globex-admin.txt` and `.demo/initech-admin.txt`, as for the owner;
6. runs the backend and the frontend until Ctrl+C. Open `http://localhost:5173` and sign in with the details in `.demo/owner.txt`.

While the demo runs, `make screenshots` in another terminal signs in as the owner and the admins of Acme and Globex in headless Firefox and saves four pages, in the dark theme, to `docs/images/`.

Each run starts from scratch with the same seed, so the organizations and their history are the same, shifted to end at the time of the run. `make demo-clean` removes the database and `.demo/`.

A short walk through the organizations:

1. As the owner, the console is the **Platform**: the overview ranks Acme (an active incident), Globex and Initech (each with the alert its admin raised by joining) and the platform's own failed sign-ins. The organization picker in the sidebar narrows every page to one of them.
2. As Globex's admin, the console is **Globex**: its people and events only, nothing of Acme's.
3. As Initech's admin, sign-in is refused, as for a deactivated account: the organization is suspended.

What to know about the data:

- Everything is synthetic, made by `backend/simulator` from one seed. Email addresses use domains reserved for examples (`acme.example`, `globex.example`, `initech.example`, and `sim.example.com` for the owner), and network addresses come from documentation ranges.
- Accounts, invitations and operator actions go through the API at the time of the run, so the accounts show today as their joining date and today's log holds them all. Their sign-ins go back ninety days.
- Alerts raised from the history are moved, in the demo database only, to the time of the event that raised them plus a few seconds, as if SentinelCore had watched the ninety days live. Without this, every one of them would carry the time of the run. The application itself always keeps the detection time.

## Checks

```bash
make verify        # every check due before a commit, one line each; logs in .verify/
make scan          # dependencies and deployment files; open findings fail
make scan-images   # builds, SBOMs and image vulnerabilities; outside make verify
```

It runs Ruff, Bandit, Pyright, the lockfile check, the migrations up and down on a database of its own, the frontend's lint, types, tests, build and `npm audit --audit-level=high`, deployment lint, `make scan`, Gitleaks, and the backend tests on Python 3.12 with the image's pinned dependencies (in a container, so Docker and the PostgreSQL of `docker-compose.yml` must be running). `VERIFY_SKIP="pytest gitleaks"` skips named checks.

## Container images

```bash
make images        # sentinelcore-backend:<12-char sha> and sentinelcore-console:<12-char sha>
make scan-images   # builds both, writes SBOMs and vulnerability reports to .scan/
```

- **`sentinelcore-backend`** (`backend/Dockerfile`): the API, its migrations and its command line, on `python:3.12-slim`, with every dependency pinned by hash in `backend/requirements.lock` (`make lock` writes it). It runs as UID 10001 and writes only to `/tmp`. Behind a proxy, `FORWARDED_ALLOW_IPS` names the proxy's addresses.
- **`sentinelcore-console`** (`frontend/Dockerfile`): the production build served by unprivileged nginx on port 8080, with the same security headers as `vite preview` and `/api` passed to a backend reachable as `sentinelcore-backend:8000`. It replaces the client's `X-Forwarded-For` with the address it saw, keeps `/api/metrics` inside, and limits each address to 20 ingestion requests a second.

Base images are pinned by digest and the images are tagged with the 12-character commit SHA (`-dirty` when the tree has changes). `make scan-images` uses pinned Syft and Grype to write an SPDX JSON SBOM per image and scan it against current advisories. Only Critical and High findings with a fixed version fail unless covered by an expiring exception; the other findings are counted. Results go to `.scan/`, ignored by git. Image builds take minutes, so this target stays outside `make verify`.

Every push to `main` publishes the scanned images as `ghcr.io/samlittlej/sentinelcore-backend:<12-char sha>` and `ghcr.io/samlittlej/sentinelcore-console:<12-char sha>`. There is no `latest` tag; the publication job's summary records the digests.

### Verifying the images

Each published image is signed with cosign, keyless through Sigstore, and carries two GitHub attestations on its digest: SLSA v1 build provenance (Build Level 2) and the SPDX SBOM Grype scanned. `make verify-images` checks all three for the current commit and pulls the images only if they pass:

```bash
gh auth login                       # once: gh refuses to verify without a GitHub token
make verify-images                  # this commit's images; the tree must be clean
make verify-images REVISION=<sha>   # another commit of main, 12 characters
```

The same checks by hand, for an image `IMAGE@DIGEST` of commit `SHA` (full 40 characters):

```bash
cosign verify IMAGE@DIGEST \
  --certificate-identity https://github.com/SamLittleJ/SentinelCore/.github/workflows/images-ci.yml@refs/heads/main \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://IMAGE@DIGEST --bundle-from-oci --repo SamLittleJ/SentinelCore \
  --signer-workflow SamLittleJ/SentinelCore/.github/workflows/images-ci.yml \
  --source-ref refs/heads/main --source-digest SHA --deny-self-hosted-runners
# again with --predicate-type https://spdx.dev/Document/v2.3 for the SBOM
```

Images published before signing began (C3) have no signature and are refused.

## Local Kubernetes cluster

```bash
make up              # the images, a kind cluster and both Helm charts; then http://localhost:8080
make up FROM=registry  # the same, with this commit's signed GHCR images instead of a local build
make cluster-check   # the running cluster's security properties, one line each
make down            # deletes the cluster and its data, after typing its name
make deploy-lint     # the charts, rendered manifests, Dockerfiles and scripts, without a cluster
```

Needs Docker and `openssl`. `make up` downloads kind, Helm and kubectl at pinned versions, checked against their SHA-256, into `.tools/`, and keeps the cluster's kubeconfig in `.kind/kubeconfig`, leaving `~/.kube/config` alone (`export KUBECONFIG=$PWD/.kind/kubeconfig` to use `kubectl` on it). It installs `charts/postgresql`, then `charts/sentinelcore`, whose migrations run first as a Job, and creates the first owner, `owner@example.com`, with a random password written only to `.kind/owner.txt`. The secret key, the audit chain key, the database passwords and the metrics token are generated once as Kubernetes Secrets and never printed. Run `make up` again after a change: it rebuilds the images and replaces the pods whose image changed. `make up FROM=registry` builds nothing: it runs `make verify-images` and stops, with nothing loaded, unless the signature and both attestations pass; it needs `gh auth login` and a clean tree, or `REVISION=<sha>`.

## Continuous integration

Backend CI runs lint, format, Bandit, the lockfile check, migrations, tests against PostgreSQL and Gitleaks over the full history. Frontend CI runs the dependency audit, lint, type check, tests and build. Actions are pinned by commit SHA; Gitleaks is a pinned binary and images are pinned by digest.

CI checks the deployment twice: `make deploy-lint` on every pull request (Helm lint, the rendered manifests against Kubernetes 1.35's schemas with kubeconform, hadolint and shellcheck, all at pinned versions), and `make up` followed by `make cluster-check` on a real kind cluster when a pull request changes the charts, the images or the scripts.

Supply chain CI (`.github/workflows/supply-chain-ci.yml`) runs `make scan` on pull requests to `main`, pushes to `main` and weekly. pip-audit reads the backend lock without installing it; Checkov checks rendered charts, Dockerfiles and workflows. The scanners have their own hashed, wheel-only lock in `security/`; exceptions name a check and resource, with a reason and expiry. CodeQL (`.github/workflows/codeql.yml`) runs `security-extended` queries for Python, JavaScript/TypeScript and workflows on the same triggers. Both also run on demand.

Images CI (`.github/workflows/images-ci.yml`) builds and scans on pull requests touching the images and their scan files, and on every push to `main`. A separate publish job loads the scanned images saved by the read-only scan job, pushes them to GHCR, signs them with cosign, attests their provenance and SBOM with `actions/attest`, then verifies them back from the registry with `scripts/verify-images.sh`; only that job has `packages: write`, `id-token: write` and `attestations: write`. A weekly job verifies main's published images the same way, then rescans them. SBOMs and reports are kept as artifacts for 90 days; the saved images for one day. The workflow also runs on demand.

Dependabot checks actions, Python, npm, Dockerfiles and Compose weekly, with grouped updates and a seven-day cooldown; security updates skip the wait. Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Monitoring

```bash
docker compose up -d prometheus grafana
```

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (user `admin`, password `sentinelcore`, local only), dashboard **SentinelCore Overview**

Prometheus scrapes the backend running locally on port 8000. The services use host networking, which is fully supported on Linux.

Backend, tests and checks: [backend/README.md](backend/README.md).

## Documentation

- [00 - Project Foundation](docs/00-project-foundation.md): purpose, architecture, roles, MVP and current status
- [01 - Backend Foundation](docs/01-backend-foundation.md): the technical journal of every backend stage
- [02 - Decisions Log](docs/02-decisions-log.md): the technical decisions made along the way
- [03 - Frontend Foundation](docs/03-frontend-foundation.md): the technical journal of the frontend
- [04 - Threat Model](docs/04-threat-model.md): a STRIDE analysis of the system, with the boundary between organizations at its centre, each mitigation linked to the test that proves it
- [Detection evaluation](docs/evaluation/report.md): detection rate, false positives and time to detect, measured by the attack simulator

## License

[MIT](LICENSE)
