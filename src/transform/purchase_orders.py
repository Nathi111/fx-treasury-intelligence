from __future__ import annotations

from pathlib import Path

import pandas as pd

ALLOWED_CURRENCIES = {"USD", "GBP", "EUR"}
ALLOWED_STATUSES = {"Open", "Received"}


def transform_purchase_orders(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "po_id",
        "supplier_id",
        "product_id",
        "order_date",
        "expected_arrival_date",
        "currency",
        "foreign_value",
        "budget_fx_rate",
        "status",
        "settlement_date",
        "settlement_fx_rate",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing purchase-order columns: {sorted(missing)}")

    df = df[list(required)].copy()
    df["currency"] = df["currency"].str.upper().str.strip()
    df["status"] = df["status"].str.strip()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="raise").dt.date
    df["expected_arrival_date"] = pd.to_datetime(df["expected_arrival_date"], errors="raise").dt.date
    df["settlement_date"] = pd.to_datetime(df["settlement_date"], errors="coerce").dt.date
    df["foreign_value"] = pd.to_numeric(df["foreign_value"], errors="raise")
    df["budget_fx_rate"] = pd.to_numeric(df["budget_fx_rate"], errors="raise")
    df["settlement_fx_rate"] = pd.to_numeric(df["settlement_fx_rate"], errors="coerce")

    invalid_currency = sorted(set(df["currency"]) - ALLOWED_CURRENCIES)
    if invalid_currency:
        raise ValueError(f"Unexpected currencies: {invalid_currency}")

    invalid_status = sorted(set(df["status"]) - ALLOWED_STATUSES)
    if invalid_status:
        raise ValueError(f"Unexpected statuses: {invalid_status}")

    if (df["foreign_value"] <= 0).any() or (df["budget_fx_rate"] <= 0).any():
        raise ValueError("foreign_value and budget_fx_rate must both be positive")

    if (df["expected_arrival_date"] < df["order_date"]).any():
        raise ValueError("expected_arrival_date cannot be before order_date")

    open_mask = df["status"].eq("Open")
    received_mask = df["status"].eq("Received")

    if df.loc[open_mask, "settlement_date"].notna().any() or df.loc[
        open_mask, "settlement_fx_rate"
    ].notna().any():
        raise ValueError("Open purchase orders cannot contain settlement data")

    if df.loc[received_mask, "settlement_date"].isna().any() or df.loc[
        received_mask, "settlement_fx_rate"
    ].isna().any():
        raise ValueError("Received purchase orders require settlement_date and settlement_fx_rate")

    if (df.loc[received_mask, "settlement_fx_rate"] <= 0).any():
        raise ValueError("settlement_fx_rate must be positive for received purchase orders")

    invalid_settlement_date = received_mask & (
        df["settlement_date"] < df["order_date"]
    )
    if invalid_settlement_date.any():
        raise ValueError("settlement_date cannot be before order_date")

    if df["po_id"].duplicated().any():
        raise ValueError("Duplicate purchase-order IDs found")

    # psycopg expects Python None rather than pandas NaN/NaT for nullable fields.
    df["settlement_date"] = df["settlement_date"].astype(object).where(
        df["settlement_date"].notna(), None
    )
    df["settlement_fx_rate"] = df["settlement_fx_rate"].astype(object).where(
        df["settlement_fx_rate"].notna(), None
    )

    return df.sort_values("order_date").reset_index(drop=True)
