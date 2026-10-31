"""Application settings: secrets are read from .env, never hard-coded."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# src/tft_meta/config.py -> the project root is two folders up
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # repr=False: keep the key out of logs if settings are printed
    riot_api_key: str = field(repr=False)
    platform: str = "euw1"  # league requests (e.g. euw1, tr1, kr)
    region: str = "europe"  # match requests (e.g. europe, asia)
    db_path: Path = PROJECT_ROOT / "data" / "tft.db"


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    riot_api_key = os.getenv("RIOT_API_KEY", "").strip()
    if not riot_api_key:
        raise RuntimeError("RIOT_API_KEY not found: check your .env file.")

    return Settings(riot_api_key=riot_api_key)
