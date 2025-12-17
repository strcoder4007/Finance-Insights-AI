from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    db_path: str = Field(default_factory=lambda: str(_repo_root() / "app.db"), validation_alias="DB_PATH")
    data1_path: str = Field(default_factory=lambda: str(_repo_root() / "data1.json"), validation_alias="DATA1_PATH")
    data2_path: str = Field(default_factory=lambda: str(_repo_root() / "data2.json"), validation_alias="DATA2_PATH")

    primary_source: Literal["quickbooks", "rootfi"] = Field(default="rootfi", validation_alias="PRIMARY_SOURCE")
    merge_tolerance: float = Field(default=1.0, validation_alias="MERGE_TOLERANCE")

    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")

    cors_origins: str = Field(default="http://localhost:5173", validation_alias="CORS_ORIGINS")
    chat_history_limit: int = Field(default=20, validation_alias="CHAT_HISTORY_LIMIT")

    def cors_origins_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if not raw:
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if str(x).strip()]
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in raw.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
