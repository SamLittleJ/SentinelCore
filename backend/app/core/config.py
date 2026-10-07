from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelCore API"
    app_env: str = "development"
    app_debug: bool = True
    database_url: str
    secret_key: str
    # Only HMAC algorithms: tokens are signed and verified with SECRET_KEY.
    algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "sentinelcore"
    jwt_audience: str = "sentinelcore-api"
    access_token_expire_minutes: int = 30
    login_max_failed_attempts: int = 5
    login_failure_window_minutes: int = 15
    login_lockout_minutes: int = 15
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
