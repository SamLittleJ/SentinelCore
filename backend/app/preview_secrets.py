"""The Secrets of a pull request's preview (docs/07-gitops.md, Previews).

Argo CD keeps no Secret in Git, and a chart's random values would change on
every sync, so a Job runs this before the preview's database starts: it
creates the Secrets `make up` would, once, through the Kubernetes API, with
the Job's own service account, which may only read and create Secrets in its
namespace. Standard library only: it runs from a ConfigMap in main's backend
image, whatever that image's own code.

    python preview_secrets.py

Once all exist it changes nothing. If only some exist it stops, since the
database holds the passwords and the audit history is sealed with
AUDIT_CHAIN_KEY: new values would not match them. No value is printed.
"""

from __future__ import annotations

import base64
import json
import secrets
import ssl
import sys
import urllib.error
import urllib.request
from collections.abc import Callable

ACCOUNT = "/var/run/secrets/kubernetes.io/serviceaccount"
API = "https://kubernetes.default.svc"
DATABASE = "sentinelcore_demo"
HOST = "sentinelcore-postgresql:5432"

# (method, path, body) -> status code
Call = Callable[[str, str, dict[str, object] | None], int]


def random() -> str:
    """As `openssl rand -hex 32` in scripts/cluster.sh."""
    return secrets.token_hex(32)


def wanted() -> dict[str, dict[str, str]]:
    """Each Secret's keys, with fresh values: the names and keys of
    scripts/cluster.sh, plus the owner's password."""
    owner, app = random(), random()
    database = f"{HOST}/{DATABASE}"
    return {
        "sentinelcore-postgresql": {"password": owner},
        "sentinelcore-migrations": {
            "MIGRATIONS_DATABASE_URL": (
                f"postgresql+psycopg://sentinelcore:{owner}@{database}"
            )
        },
        "sentinelcore-api": {
            "SECRET_KEY": random(),
            "AUDIT_CHAIN_KEY": random(),
            "METRICS_TOKEN": random(),
            "DATABASE_URL": f"postgresql+psycopg://sentinelcore_app:{app}@{database}",
        },
        "preview-owner": {"SENTINELCORE_OWNER_PASSWORD": random()},
    }


def manifest(name: str, data: dict[str, str]) -> dict[str, object]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": name,
            "labels": {"app.kubernetes.io/part-of": "sentinelcore"},
        },
        "type": "Opaque",
        "data": {
            key: base64.b64encode(value.encode()).decode()
            for key, value in data.items()
        },
    }


def ensure(namespace: str, call: Call) -> str:
    """Create the Secrets if none exists; returns what was done."""
    base = f"/api/v1/namespaces/{namespace}/secrets"
    secrets_ = wanted()
    present = [name for name in secrets_ if call("GET", f"{base}/{name}", None) == 200]
    if len(present) == len(secrets_):
        return "present"
    if present:
        raise SystemExit(
            "Only some of the preview's Secrets exist: delete the preview's "
            "namespace to start it again."
        )
    for name, data in secrets_.items():
        status = call("POST", base, manifest(name, data))
        if status != 201:
            raise SystemExit(f"Creating the Secret {name} failed with {status}.")
    return "created"


def kubernetes() -> Call:
    """Calls to the API server as this pod's service account."""
    with open(f"{ACCOUNT}/token") as file:
        token = file.read().strip()
    context = ssl.create_default_context(cafile=f"{ACCOUNT}/ca.crt")

    def call(method: str, path: str, body: dict[str, object] | None) -> int:
        request = urllib.request.Request(
            API + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(  # nosec B310
                request, context=context, timeout=10
            ) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    return call


def main() -> int:
    with open(f"{ACCOUNT}/namespace") as file:
        namespace = file.read().strip()
    result = ensure(namespace, kubernetes())
    print(f"The preview's Secrets are {result} in {namespace}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
