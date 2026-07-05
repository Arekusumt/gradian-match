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

@dataclass
class Config:
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    jooble_key: str | None = None
    github_token: str | None = None

def load_config() -> Config:
    load_dotenv(PROJECT_ROOT / ".env")
    def g(k: str) -> str | None:
        return os.environ.get(k) or None
    return Config(
        adzuna_app_id=g("ADZUNA_APP_ID"),
        adzuna_app_key=g("ADZUNA_APP_KEY"),
        jooble_key=g("JOOBLE_KEY"),
        github_token=g("GITHUB_TOKEN"),
    )
