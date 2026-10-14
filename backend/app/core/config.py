from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelCore API"
    app_env: str = "development"
    app_debug: bool = True
    # The API signs in as `sentinelcore_app`, which row-level security binds
    # (core/row_security.py). Migrations sign in as the owner of the tables,
    # with MIGRATIONS_DATABASE_URL; without it, they use DATABASE_URL.
    database_url: str
    migrations_database_url: str | None = None
    secret_key: str
    # Only HMAC algorithms: tokens are signed and verified with SECRET_KEY.
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "sentinelcore"
    jwt_audience: str = "sentinelcore-api"
    access_token_expire_minutes: int = 30
    login_max_failed_attempts: int = 5
    login_failure_window_minutes: int = 15
    login_lockout_minutes: int = 15
    # Password spray: failed sign-ins for this many different emails from one
    # address within the window raise an incident.
    detection_spray_min_accounts: int = Field(default=10, ge=2)
    detection_spray_window_minutes: int = Field(default=15, ge=1)
    # A sign-in after this many days without one is flagged.
    detection_dormant_days: int = Field(default=90, ge=1)
    # A sign-in from a network and a device not seen in the account's sign-ins
    # of this many days is flagged, once it has this many to compare with.
    detection_unfamiliar_lookback_days: int = Field(default=90, ge=1)
    detection_unfamiliar_min_sign_ins: int = Field(default=3, ge=1)
    # How long an invitation link works before it must be issued again.
    invitation_expire_hours: int = Field(default=72, ge=1, le=30 * 24)
    # Expired or revoked sessions are kept this long for investigations.
    session_retention_days: int = Field(default=30, ge=1)
    # How often the API deletes old sessions; 0 disables the periodic task.
    session_cleanup_interval_minutes: int = Field(default=60, ge=0)
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    # Browser session cookies are sent only over HTTPS. Browsers treat
    # http://localhost as secure, so this stays on in local development.
    auth_cookie_secure: bool = True
    # When set, /metrics requires `Authorization: Bearer <token>`.
    metrics_token: SecretStr | None = None
    # Strict-Transport-Security max-age, in seconds: browsers then refuse to
    # reach the host over plain HTTP. 0 sends no header; set it only once the
    # host is served over HTTPS, since browsers remember it.
    hsts_max_age: int = Field(default=0, ge=0)
    # Swagger UI (/docs), ReDoc (/redoc) and the schema (/openapi.json). The
    # pages run code from a public CDN and the schema maps every route, so they
    # are off unless turned on, for development.
    api_docs_enabled: bool = False

    @field_validator("secret_key")
    @classmethod
    def check_secret_key_length(cls, value: str) -> str:
        # HMAC-SHA256 keys shorter than the hash output weaken the signature.
        if len(value.encode()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 bytes long")
        return value

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore
