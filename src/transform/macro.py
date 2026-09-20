from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

MACRO_COLUMNS = [
    "country_code",
    "country_name",
    "indicator_code",
    "indicator_name",
    "year",
    "value",
    "unit",
    "obs_status",
    "extracted_at_utc",
]


def transform_world_bank(payload: list[dict[str, Any]]) -> pd.DataFrame:
    extracted_at = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []

    for row in payload:
        if row.get("value") is None:
            continue
        records.append(
            {
                "country_code": row.get("countryiso3code"),
                "country_name": (row.get("country") or {}).get("value"),
                "indicator_code": (row.get("indicator") or {}).get("id"),
                "indicator_name": (row.get("indicator") or {}).get("value"),
                "year": int(row["date"]),
                "value": float(row["value"]),
                "unit": row.get("unit") or None,
                "obs_status": row.get("obs_status") or None,
                "extracted_at_utc": extracted_at,
            }
        )

    if not records:
        return pd.DataFrame(columns=MACRO_COLUMNS)

    df = pd.DataFrame.from_records(records, columns=MACRO_COLUMNS)
    return (
        df.drop_duplicates(subset=["country_code", "indicator_code", "year"], keep="last")
        .sort_values(["indicator_code", "year"])
        .reset_index(drop=True)
    )
