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
    finish_etl_run,
    load_raw_payload,
    make_engine,
    run_sql_file,
    start_etl_run,
    upsert_fx,
    upsert_macro,
    upsert_purchase_orders,
)
from src.transform.fx import transform_fx_rates
from src.transform.macro import transform_world_bank
from src.transform.purchase_orders import transform_purchase_orders
from src.quality.freshness import collect_freshness_results, persist_freshness_results

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("fx-treasury-etl")
ROOT = Path(__file__).resolve().parents[1]


def bootstrap_audit_database(engine) -> None:
    for filename in (
        "001_create_schemas.sql",
        "005_create_ops.sql",
        "006_create_freshness.sql",
    ):
        run_sql_file(engine, ROOT / "sql" / filename)


def bootstrap_database(engine) -> None:
    for filename in (
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


def run_freshness_gate(engine, settings, run_id: int, as_of_date: date) -> None:
    results = collect_freshness_results(engine, settings, as_of_date)
    persist_freshness_results(engine, run_id, results)

    for result in results:
        log_fn = LOGGER.info if result.status == "PASS" else LOGGER.error
        log_fn("Freshness %s: %s - %s", result.status, result.dataset_name, result.details)

    failures = [result for result in results if result.status == "FAIL"]
    if failures:
        failed_datasets = ", ".join(result.dataset_name for result in failures)
        raise RuntimeError(f"Data freshness SLA failed for: {failed_datasets}.")


def run_pipeline(engine, settings, counts: dict[str, int], run_id: int) -> None:
    bootstrap_database(engine)

    today = date.today()
    fx_start = get_fx_incremental_start(engine, settings.fx_start_date)
    LOGGER.info("Extracting FX data from %s to %s", fx_start, today)

    raw_fx = fetch_fx_rates(fx_start, today, settings.fx_quotes)
    load_raw_payload(engine, "frankfurter", FX_URL, raw_fx)
    fx_df = transform_fx_rates(raw_fx)
    counts["fx"] = upsert_fx(engine, fx_df)

    LOGGER.info("Extracting World Bank indicators")
    raw_macro = fetch_indicators(
        settings.world_bank_country,
        settings.world_bank_indicators,
        settings.world_bank_start_year,
        today.year,
    )
    load_raw_payload(engine, "world_bank", WB_URL, raw_macro)
    macro_df = transform_world_bank(raw_macro)
    counts["macro"] = upsert_macro(engine, macro_df)

    po_path = ROOT / "data" / "reference" / "purchase_orders.csv"
    po_df = transform_purchase_orders(po_path)
    counts["po"] = upsert_purchase_orders(engine, po_df)

    with engine.connect() as conn:
        failures = conn.execute(text("SELECT COUNT(*) FROM gold.v_data_quality_failures")).scalar_one()
    if failures:
        raise RuntimeError(f"Data-quality gate failed with {failures} issue(s).")

    run_freshness_gate(engine, settings, run_id, today)


def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)

    # Bootstrap only the operational audit objects before recording the run.
    # If the remaining schema setup or ETL fails, the failure can still be audited.
    bootstrap_audit_database(engine)
    run_id = start_etl_run(engine)
    counts = {"fx": 0, "macro": 0, "po": 0}

    LOGGER.info("Started ETL run %s", run_id)

    try:
        run_pipeline(engine, settings, counts, run_id)
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"[:4000]
        try:
            finish_etl_run(
                engine,
                run_id,
                status="FAILED",
                fx_rows_processed=counts["fx"],
                macro_rows_processed=counts["macro"],
                po_rows_processed=counts["po"],
                error_message=error_message,
            )
        except Exception:
            LOGGER.exception("Failed to finalize audit record for ETL run %s", run_id)
        LOGGER.exception("ETL run %s failed", run_id)
        raise

    finish_etl_run(
        engine,
        run_id,
        status="SUCCESS",
        fx_rows_processed=counts["fx"],
        macro_rows_processed=counts["macro"],
        po_rows_processed=counts["po"],
    )
    LOGGER.info(
        "Pipeline complete for run %s: %s FX rows, %s macro rows, %s purchase orders",
        run_id,
        counts["fx"],
        counts["macro"],
        counts["po"],
    )


if __name__ == "__main__":
    main()
