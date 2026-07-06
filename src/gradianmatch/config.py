# src/gradianmatch/config.py
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RUBRICS_DIR = PROJECT_ROOT / "rubrics"
WEB_DIR = PROJECT_ROOT / "web"
AGENTS_DIR = Path(__file__).resolve().parent / "agents"

# Default model for the direct-API backend. Chosen for quality on CV tailoring;
# override with GM_MODEL (e.g. claude-sonnet-5) for faster / cheaper runs.
DEFAULT_API_MODEL = "claude-opus-4-8"


@dataclass
class Config:
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    jooble_key: str | None = None
    github_token: str | None = None
    # AI backend
    anthropic_api_key: str | None = None
    model: str | None = None            # GM_MODEL — overrides the per-backend default
    backend: str = "auto"               # GM_BACKEND — auto | cli | api


def load_config() -> Config:
    load_dotenv(PROJECT_ROOT / ".env")

    def g(k: str) -> str | None:
        return os.environ.get(k) or None

    backend = (g("GM_BACKEND") or "auto").strip().lower()
    if backend not in ("auto", "cli", "api"):
        backend = "auto"
    return Config(
        adzuna_app_id=g("ADZUNA_APP_ID"),
        adzuna_app_key=g("ADZUNA_APP_KEY"),
        jooble_key=g("JOOBLE_KEY"),
        github_token=g("GITHUB_TOKEN"),
        anthropic_api_key=g("ANTHROPIC_API_KEY"),
        model=g("GM_MODEL"),
        backend=backend,
    )
