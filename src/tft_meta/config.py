"""Application settings: secrets are read from .env, never hard-coded."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# src/tft_meta/config.py -> the project root is two folders up
PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    # repr=False: keep secrets out of logs if settings are printed
    riot_api_key: str = field(repr=False)
    database_url: str = field(repr=False)
    platform: str = "euw1"  # league requests (e.g. euw1, tr1, kr)
    region: str = "europe"  # match requests (e.g. europe, asia)


def _read_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} not found: check your .env file.")
    return value


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    return Settings(
        riot_api_key=_read_required("RIOT_API_KEY"),
        database_url=_read_required("DATABASE_URL"),
    )
