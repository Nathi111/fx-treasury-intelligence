from __future__ import annotations

from pathlib import Path

import pandas as pd


SUPPLIER_TIERS = {"Strategic", "Core"}
PRODUCT_UOMS = {"EA", "SET", "KIT"}


def _parse_synthetic_flag(series: pd.Series) -> pd.Series:
    values = series.astype(str).str.strip().str.lower()
    invalid = ~values.isin({"true", "false"})
    if invalid.any():
        raise ValueError("is_synthetic must contain only true/false values")
    return values.eq("true")


def transform_suppliers(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "supplier_id",
        "supplier_name",
        "country_code",
        "country_name",
        "region",
        "supplier_tier",
        "payment_terms_days",
        "is_synthetic",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing supplier columns: {sorted(missing)}")

    df = df[list(required)].copy()
    text_columns = [
        "supplier_id",
        "supplier_name",
        "country_code",
        "country_name",
        "region",
        "supplier_tier",
    ]
    for column in text_columns:
        df[column] = df[column].astype(str).str.strip()

    df["country_code"] = df["country_code"].str.upper()
    df["payment_terms_days"] = pd.to_numeric(df["payment_terms_days"], errors="raise").astype(int)
    df["is_synthetic"] = _parse_synthetic_flag(df["is_synthetic"])

    if df["supplier_id"].duplicated().any():
        raise ValueError("Duplicate supplier IDs found")
    if (df["supplier_name"] == "").any():
        raise ValueError("supplier_name cannot be blank")
    if (~df["country_code"].str.fullmatch(r"[A-Z]{3}")).any():
        raise ValueError("country_code must be a three-letter ISO-style code")
    invalid_tiers = sorted(set(df["supplier_tier"]) - SUPPLIER_TIERS)
    if invalid_tiers:
        raise ValueError(f"Unexpected supplier tiers: {invalid_tiers}")
    if (df["payment_terms_days"] <= 0).any():
        raise ValueError("payment_terms_days must be positive")
    if not df["is_synthetic"].all():
        raise ValueError("Portfolio supplier master must remain explicitly synthetic")

    return df.sort_values("supplier_id").reset_index(drop=True)


def transform_products(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "product_id",
        "product_name",
        "brand_name",
        "category",
        "subcategory",
        "unit_of_measure",
        "is_synthetic",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing product columns: {sorted(missing)}")

    df = df[list(required)].copy()
    text_columns = [
        "product_id",
        "product_name",
        "brand_name",
        "category",
        "subcategory",
        "unit_of_measure",
    ]
    for column in text_columns:
        df[column] = df[column].astype(str).str.strip()

    df["unit_of_measure"] = df["unit_of_measure"].str.upper()
    df["is_synthetic"] = _parse_synthetic_flag(df["is_synthetic"])

    if df["product_id"].duplicated().any():
        raise ValueError("Duplicate product IDs found")
    if (df["product_name"] == "").any():
        raise ValueError("product_name cannot be blank")
    invalid_uoms = sorted(set(df["unit_of_measure"]) - PRODUCT_UOMS)
    if invalid_uoms:
        raise ValueError(f"Unexpected units of measure: {invalid_uoms}")
    if not df["is_synthetic"].all():
        raise ValueError("Portfolio product master must remain explicitly synthetic")

    return df.sort_values("product_id").reset_index(drop=True)
