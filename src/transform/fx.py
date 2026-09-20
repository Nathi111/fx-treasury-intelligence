from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any

import pandas as pd

FX_COLUMNS = [
    "rate_date",
    "base_currency",
    "foreign_currency",
    "foreign_per_zar",
    "zar_per_unit",
    "provider_count",
    "payload_hash",
    "extracted_at_utc",
]


def transform_fx_rates(payload: list[dict[str, Any]]) -> pd.DataFrame:
    """Normalize Frankfurter v2 rows and derive ZAR per foreign currency."""
    extracted_at = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []

    for row in payload:
        rate = row.get("rate")
        if rate in (None, 0):
            continue
        fx_rate = Decimal(str(rate))
        if fx_rate <= 0:
            continue

        base = str(row.get("base", "")).upper()
        quote = str(row.get("quote", "")).upper()
        if base != "ZAR":
            raise ValueError(f"Expected ZAR base, got {base!r}")

        canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        providers = row.get("providers") or []
        records.append(
            {
                "rate_date": pd.to_datetime(row["date"]).date(),
                "base_currency": base,
                "foreign_currency": quote,
                "foreign_per_zar": fx_rate,
                "zar_per_unit": Decimal("1") / fx_rate,
                "provider_count": len(providers),
                "payload_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "extracted_at_utc": extracted_at,
            }
        )

    if not records:
        return pd.DataFrame(columns=FX_COLUMNS)

    df = pd.DataFrame.from_records(records, columns=FX_COLUMNS)
    df = df.drop_duplicates(subset=["rate_date", "base_currency", "foreign_currency"], keep="last")
    return df.sort_values(["rate_date", "foreign_currency"]).reset_index(drop=True)
