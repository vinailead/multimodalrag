"""Runtime configuration loaded from environment variables (never hardcoded secrets)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings. All values overridable via `MMRAG_*` env vars or `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="MMRAG_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    use_stub_model: bool = True

    flash_model: str = "gemini-2.5-flash"
    pro_model: str = "gemini-2.5-pro"
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    min_confidence_threshold: float = 0.70
    max_crag_hops: int = 2
    max_sub_queries: int = 3
    top_k: int = 6
    rrf_k: int = 60

    usd_to_inr_rate: float = 84.0
    max_daily_budget_usd: float = 5.00
    max_pdf_size_mb: int = 50

    data_dir: Path = Path("data")
    logs_dir: Path = Path("logs")

    @property
    def raw_policies_dir(self) -> Path:
        return self.data_dir / "raw_policies"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def crops_dir(self) -> Path:
        return self.cache_dir / "crops"

    @property
    def audit_log_path(self) -> Path:
        return self.logs_dir / "audit_trail.jsonl"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
