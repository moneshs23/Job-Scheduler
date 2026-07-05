from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Distributed Job Scheduler"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    database_url: str = "postgresql+asyncpg://scheduler:scheduler@localhost:5432/scheduler"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    worker_concurrency: int = 10
    worker_poll_interval_ms: int = 500
    worker_heartbeat_interval_sec: int = 5
    worker_drain_timeout_sec: int = 30

    scheduler_scan_interval_sec: int = 1
    scheduler_leader_lock_ttl_sec: int = 15

    rate_limit_requests: int = 100
    rate_limit_window_sec: int = 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
