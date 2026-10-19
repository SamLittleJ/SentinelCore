from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
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
    # Failed sign-ins per address, of any email: an address may fail this
    # many times at once, then this many an hour
    # (services/sign_in_limit_service.py).
    login_address_burst: int = Field(default=20, ge=1)
    login_address_failures_per_hour: int = Field(default=6, ge=1)
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
    # An API key's volume spike: an hour in which the key sent at least FACTOR
    # times its usual busiest hour, and at least MIN_EVENTS events. The usual
    # busiest hour is the median of each day's busiest hour, over the days of
    # the last LOOKBACK_DAYS on which the key sent anything; with fewer than
    # MIN_DAYS such days, the key is still learning and is not judged.
    detection_volume_factor: float = Field(default=3.0, gt=1)
    detection_volume_min_events: int = Field(default=100, ge=1)
    detection_volume_lookback_days: int = Field(default=14, ge=1)
    detection_volume_min_days: int = Field(default=7, ge=1)
    # Ingestion rate limit, per API key: a key may send this many events at
    # once, then this many a minute (services/ingestion_service.py). The burst
    # holds at least the largest batch (MAX_EVENTS_PER_REQUEST in
    # schemas/ingest.py), so every valid batch fits sooner or later.
    ingest_burst_events: int = Field(default=5000, ge=500)
    ingest_events_per_minute: int = Field(default=1000, ge=1)
    # Each key's hourly event counts are kept this many whole days, for the
    # volume spike rule's lookback.
    api_key_usage_retention_days: int = Field(default=30, ge=1)
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

    @model_validator(mode="after")
    def check_volume_days(self) -> Self:
        # Otherwise the rule would never have enough days to judge a key, or
        # the cleanup would delete days it still compares with.
        if self.detection_volume_min_days > self.detection_volume_lookback_days:
            raise ValueError(
                "DETECTION_VOLUME_MIN_DAYS must not exceed "
                "DETECTION_VOLUME_LOOKBACK_DAYS"
            )
        if self.api_key_usage_retention_days < self.detection_volume_lookback_days:
            raise ValueError(
                "API_KEY_USAGE_RETENTION_DAYS must be at least "
                "DETECTION_VOLUME_LOOKBACK_DAYS"
            )
        return self

    @model_validator(mode="after")
    def check_address_burst(self) -> Self:
        # Otherwise an address would be stopped before it fails on enough
        # emails to raise the spray alert, or on one email enough times to
        # lock it.
        if self.login_address_burst <= self.detection_spray_min_accounts:
            raise ValueError(
                "LOGIN_ADDRESS_BURST must exceed DETECTION_SPRAY_MIN_ACCOUNTS"
            )
        if self.login_address_burst < self.login_max_failed_attempts:
            raise ValueError(
                "LOGIN_ADDRESS_BURST must be at least LOGIN_MAX_FAILED_ATTEMPTS"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore
