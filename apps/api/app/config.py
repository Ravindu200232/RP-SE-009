"""Application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = .../apps/api/app/config.py -> parents[3]
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", "apps/api/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Ollama ───────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_primary_model: str = "nemotron-3-super:cloud"
    ollama_fallback_model: str = "nemotron-3-super:cloud"
    ollama_request_timeout: int = 600
    ollama_num_ctx: int = 8192
    llm_allow_offline_fallback: bool = True
    # Fewer retries keeps slow local models tolerable; raise for stronger models.
    llm_max_repair_attempts: int = 2

    # ── MongoDB ──────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017/agentforge"
    mongodb_db: str = "agentforge"
    mongodb_allow_memory_fallback: bool = True

    # ── Storage ──────────────────────────────────────────────
    storage_dir: str = "./generated"
    samples_dir: str = "./samples"

    # ── API server ───────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # ── Diagrams ─────────────────────────────────────────────
    mermaid_cli: str = "mmdc"

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        if not p.is_absolute():
            p = REPO_ROOT / self.storage_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def samples_path(self) -> Path:
        p = Path(self.samples_dir)
        if not p.is_absolute():
            p = REPO_ROOT / self.samples_dir
        return p

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def project_dir(self, project_id: str) -> Path:
        p = self.storage_path / project_id
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
