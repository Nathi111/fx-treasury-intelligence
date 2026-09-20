from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    fx_start_date: date
    fx_quotes: tuple[str, ...]
    world_bank_country: str
    world_bank_start_year: int
    world_bank_indicators: tuple[str, ...]


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip().upper() for x in os.getenv(name, default).split(",") if x.strip())


def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required. Copy .env.example to .env and add your PostgreSQL connection string.")

    return Settings(
        database_url=database_url,
        fx_start_date=date.fromisoformat(os.getenv("FX_START_DATE", "2024-01-01")),
        fx_quotes=_csv_env("FX_QUOTES", "USD,GBP,EUR"),
        world_bank_country=os.getenv("WORLD_BANK_COUNTRY", "ZAF").upper(),
        world_bank_start_year=int(os.getenv("WORLD_BANK_START_YEAR", "2018")),
        world_bank_indicators=_csv_env(
            "WORLD_BANK_INDICATORS",
            "FP.CPI.TOTL.ZG,NY.GDP.MKTP.KD.ZG",
        ),
    )
