"""Application configuration and secret handling."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

DATA_RAW: Path = PROJECT_ROOT / "data" / "raw"
DATA_INTERIM: Path = PROJECT_ROOT / "data" / "interim"
DATA_PROCESSED: Path = PROJECT_ROOT / "data" / "processed"
DATA_PROVENANCE: Path = PROJECT_ROOT / "data" / "provenance"
DOCS_VERIFICATION: Path = PROJECT_ROOT / "docs" / "verification"


class Settings(BaseSettings):
    """Runtime settings, populated from environment variables or ``.env``."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="REIN_",
        case_sensitive=False,
        extra="forbid",
        frozen=True,
    )

    env: Literal["dev", "ci", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"

    google_maps_api_key: SecretStr | None = Field(
        default=None,
        description="Google Maps Platform key with Map Tiles API enabled. Browser-"
        "visible by necessity, so it MUST carry HTTP-referrer and API restrictions.",
    )

    # Network hygiene
    http_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    http_max_requests: int = Field(
        default=400,
        gt=0,
        description="Hard ceiling on requests per verification run. Prevents an "
        "accidental unbounded crawl against a metered third-party API.",
    )
    user_agent: str = Field(
        default="rein-verification/0.1 (+https://github.com/Mizunandayo/rein)",
        description="Identifying UA. OSM's usage policy requires a real one.",
    )

    @field_validator("google_maps_api_key", mode="after")
    @classmethod
    def _reject_placeholder(cls, v: SecretStr | None) -> SecretStr | None:
        """Fail loudly if ``.env.example`` was copied without editing."""
        if v is None:
            return None
        raw = v.get_secret_value().strip()
        if not raw:
            return None
        placeholders = {"changeme", "your-key-here", "xxx", "todo"}
        if raw.lower() in placeholders:
            msg = "REIN_GOOGLE_MAPS_API_KEY is still a placeholder value."
            raise ValueError(msg)
        return v

    def require_google_key(self) -> str:
        """Return the Google key, or raise with an actionable message."""
        if self.google_maps_api_key is None:
            msg = (
                "REIN_GOOGLE_MAPS_API_KEY is not set.\n"
                "  1. Create a key in Google Cloud Console\n"
                "  2. Enable 'Map Tiles API' on the project\n"
                "  3. Restrict the key (API restriction + HTTP referrer)\n"
                "  4. Copy .env.example to .env and set the value"
            )
            raise RuntimeError(msg)
        return self.google_maps_api_key.get_secret_value()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
