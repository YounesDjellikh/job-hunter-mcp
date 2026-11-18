"""Configuration loading.

Settings come from a YAML file (default: ~/.job-hunter/config.yaml, or the path in
JOB_HUNTER_CONFIG) with environment variables taking priority for secrets, so API
keys never have to live in a file you might commit by mistake.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .countries import SELF_EMPLOYED_KEYWORDS, normalise

DEFAULT_HOME = Path(os.environ.get("JOB_HUNTER_HOME", Path.home() / ".job-hunter"))


@dataclass
class SearchDefaults:
    country: str = "gb"           # gb, fr, de, es, it, nl, be, at, ch, pl
    location: str = ""
    distance_miles: int = 10      # used in the UK
    distance_km: int | None = None  # set this instead outside the UK (overrides miles)
    temp_only: bool = False
    min_hourly: float | None = None
    max_results: int = 25
    # Jobs whose title or description contain any of these words are dropped.
    # Default: self-employed / freelance / commission-only wording in 7 languages.
    exclude_keywords: list[str] = field(default_factory=lambda: list(SELF_EMPLOYED_KEYWORDS))


@dataclass
class Config:
    reed_api_key: str | None = None
    adzuna_app_id: str | None = None
    adzuna_app_key: str | None = None
    data_dir: Path = DEFAULT_HOME
    gmail_credentials: Path = DEFAULT_HOME / "credentials.json"
    gmail_token: Path = DEFAULT_HOME / "token.json"
    search: SearchDefaults = field(default_factory=SearchDefaults)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tracker.db"

    @property
    def excel_path(self) -> Path:
        return self.data_dir / "job_tracker.xlsx"


def _config_path() -> Path:
    return Path(os.environ.get("JOB_HUNTER_CONFIG", DEFAULT_HOME / "config.yaml"))


def load_config(path: Path | None = None) -> Config:
    path = path or _config_path()
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    search_raw = raw.get("search", {}) or {}
    search = SearchDefaults(**{k: v for k, v in search_raw.items() if k in SearchDefaults.__dataclass_fields__})

    data_dir = Path(os.path.expanduser(raw.get("data_dir", str(DEFAULT_HOME))))
    cfg = Config(
        reed_api_key=os.environ.get("REED_API_KEY") or raw.get("reed_api_key"),
        adzuna_app_id=os.environ.get("ADZUNA_APP_ID") or raw.get("adzuna_app_id"),
        adzuna_app_key=os.environ.get("ADZUNA_APP_KEY") or raw.get("adzuna_app_key"),
        data_dir=data_dir,
        gmail_credentials=Path(os.path.expanduser(raw.get("gmail_credentials", str(data_dir / "credentials.json")))),
        gmail_token=Path(os.path.expanduser(raw.get("gmail_token", str(data_dir / "token.json")))),
        search=search,
    )
    # Backwards compatibility: older configs set the country at the top level.
    if "adzuna_country" in raw and "country" not in search_raw:
        cfg.search.country = raw["adzuna_country"]
    cfg.search.country = normalise(cfg.search.country)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    return cfg
