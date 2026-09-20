from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from sqlalchemy import text

from src.config import get_settings
from src.extract.frankfurter import BASE_URL as FX_URL
from src.extract.frankfurter import fetch_fx_rates
from src.extract.world_bank import BASE_URL as WB_URL
from src.extract.world_bank import fetch_indicators
from src.load.postgres import (
    load_raw_payload,
    make_engine,
    run_sql_file,
    upsert_fx,
    upsert_macro,
    upsert_purchase_orders,
)
from src.transform.fx import transform_fx_rates
from src.transform.macro import transform_world_bank
from src.transform.purchase_orders import transform_purchase_orders

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("fx-treasury-etl")
ROOT = Path(__file__).resolve().parents[1]


def bootstrap_database(engine) -> None:
    for filename in (
        "001_create_schemas.sql",
        "010_create_bronze.sql",
        "020_create_silver.sql",
        "030_create_gold.sql",
        "040_quality_views.sql",
    ):
        run_sql_file(engine, ROOT / "sql" / filename)


def get_fx_incremental_start(engine, configured_start: date) -> date:
    with engine.connect() as conn:
        latest = conn.execute(text("SELECT MAX(rate_date) FROM silver.fx_rate")).scalar_one_or_none()
    return latest or configured_start


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    bootstrap_database(engine)

    today = date.today()
    fx_start = get_fx_incremental_start(engine, settings.fx_start_date)
    LOGGER.info("Extracting FX data from %s to %s", fx_start, today)

    raw_fx = fetch_fx_rates(fx_start, today, settings.fx_quotes)
    load_raw_payload(engine, "frankfurter", FX_URL, raw_fx)
    fx_df = transform_fx_rates(raw_fx)
    fx_count = upsert_fx(engine, fx_df)

    LOGGER.info("Extracting World Bank indicators")
    raw_macro = fetch_indicators(
        settings.world_bank_country,
        settings.world_bank_indicators,
        settings.world_bank_start_year,
        today.year,
    )
    load_raw_payload(engine, "world_bank", WB_URL, raw_macro)
    macro_df = transform_world_bank(raw_macro)
    macro_count = upsert_macro(engine, macro_df)

    po_path = ROOT / "data" / "reference" / "purchase_orders.csv"
    po_df = transform_purchase_orders(po_path)
    po_count = upsert_purchase_orders(engine, po_df)

    with engine.connect() as conn:
        failures = conn.execute(text("SELECT COUNT(*) FROM gold.v_data_quality_failures")).scalar_one()
    if failures:
        raise RuntimeError(f"Data-quality gate failed with {failures} issue(s).")

    LOGGER.info("Pipeline complete: %s FX rows, %s macro rows, %s purchase orders", fx_count, macro_count, po_count)


if __name__ == "__main__":
    main()
