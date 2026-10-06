from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentinelCore API"
    app_env: str = "development"
    app_debug: bool = True
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    login_max_failed_attempts: int = 5
    login_failure_window_minutes: int = 15
    login_lockout_minutes: int = 15
    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "json"
    # When set, /metrics requires `Authorization: Bearer <token>`.
    metrics_token: SecretStr | None = None

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # type: ignore
