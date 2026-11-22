"""A preview's Secrets (app/preview_secrets.py): created once, all or none,
never replaced."""

import base64

import pytest

from app import preview_secrets

NAMES = {
    "sentinelcore-postgresql",
    "sentinelcore-migrations",
    "sentinelcore-api",
    "preview-owner",
}


class FakeApi:
    """The Kubernetes API's Secrets in one namespace."""

    def __init__(
        self, existing: set[str] = frozenset(), create_status: int = 201
    ) -> None:
        self.secrets: dict[str, dict] = {name: {} for name in existing}
        self.create_status = create_status
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str, body: dict | None) -> int:
        self.calls.append((method, path))
        if method == "GET":
            return 200 if path.rsplit("/", 1)[1] in self.secrets else 404
        assert method == "POST"
        assert path == "/api/v1/namespaces/preview-7/secrets"
        assert body is not None
        if self.create_status == 201:
            self.secrets[body["metadata"]["name"]] = body
        return self.create_status


def decoded(secret: dict) -> dict[str, str]:
    return {
        key: base64.b64decode(value).decode() for key, value in secret["data"].items()
    }


def test_creates_every_secret_when_none_exists() -> None:
    api = FakeApi()

    assert preview_secrets.ensure("preview-7", api) == "created"

    assert set(api.secrets) == NAMES
    owner = decoded(api.secrets["sentinelcore-postgresql"])["password"]
    migrations = decoded(api.secrets["sentinelcore-migrations"])
    assert migrations["MIGRATIONS_DATABASE_URL"] == (
        f"postgresql+psycopg://sentinelcore:{owner}"
        "@sentinelcore-postgresql:5432/sentinelcore_demo"
    )
    keys = decoded(api.secrets["sentinelcore-api"])
    assert set(keys) == {
        "SECRET_KEY",
        "AUDIT_CHAIN_KEY",
        "METRICS_TOKEN",
        "DATABASE_URL",
    }
    assert keys["DATABASE_URL"].startswith("postgresql+psycopg://sentinelcore_app:")
    assert keys["DATABASE_URL"].endswith(
        "@sentinelcore-postgresql:5432/sentinelcore_demo"
    )
    assert (
        len(decoded(api.secrets["preview-owner"])["SENTINELCORE_OWNER_PASSWORD"])
        == 64
    )


def test_every_value_is_new_and_long() -> None:
    api = FakeApi()
    preview_secrets.ensure("preview-7", api)

    values = [
        decoded(api.secrets["sentinelcore-api"])[key]
        for key in ("SECRET_KEY", "AUDIT_CHAIN_KEY", "METRICS_TOKEN")
    ]
    assert len(set(values)) == 3
    assert all(len(value) == 64 for value in values)


def test_changes_nothing_when_all_exist() -> None:
    api = FakeApi(existing=NAMES)

    assert preview_secrets.ensure("preview-7", api) == "present"

    assert all(method == "GET" for method, _ in api.calls)


@pytest.mark.parametrize(
    "existing", [{"sentinelcore-api"}, NAMES - {"preview-owner"}]
)
def test_stops_without_writing_when_only_some_exist(existing: set[str]) -> None:
    api = FakeApi(existing=existing)

    with pytest.raises(SystemExit, match="Only some"):
        preview_secrets.ensure("preview-7", api)

    assert all(method == "GET" for method, _ in api.calls)


def test_a_refused_creation_fails_the_job() -> None:
    with pytest.raises(SystemExit, match="failed with 403"):
        preview_secrets.ensure("preview-7", FakeApi(create_status=403))


def test_the_secrets_are_labelled_and_opaque() -> None:
    secret = preview_secrets.manifest("sentinelcore-api", {"A": "b"})

    assert secret["type"] == "Opaque"
    assert secret["metadata"] == {
        "name": "sentinelcore-api",
        "labels": {"app.kubernetes.io/part-of": "sentinelcore"},
    }
