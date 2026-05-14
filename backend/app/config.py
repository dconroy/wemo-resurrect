from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WEMO_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dashboard_host: str = Field(default="127.0.0.1")
    dashboard_port: int = Field(default=8765)
    dashboard_bind_lan: bool = Field(default=False)
    admin_password: str | None = Field(default=None)
    database_path: Path = Field(default=Path("data/wemo_dashboard.db"))
    log_level: str = Field(default="INFO")

    @field_validator("dashboard_bind_lan", mode="before")
    @classmethod
    def parse_dashboard_bind_lan(cls, v: object) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        s = str(v).strip().lower()
        return s in {"1", "true", "yes", "on"}

    @property
    def uvicorn_host(self) -> str:
        if self.dashboard_bind_lan:
            return "0.0.0.0"
        return self.dashboard_host


@lru_cache
def get_settings() -> Settings:
    return Settings()
