from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import requests
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
    upsert_products,
    upsert_purchase_orders,
    upsert_suppliers,
)
from src.transform.fx import transform_fx_rates
from src.transform.macro import transform_world_bank
from src.transform.purchase_orders import transform_purchase_orders
from src.transform.reference import transform_products, transform_suppliers
from src.quality.freshness import collect_freshness_results, persist_freshness_results
from src.quality.reconciliation import (
    fx_filter_and_duplicate_counts,
    macro_filter_and_duplicate_counts,
    reconcile_and_persist,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("fx-treasury-etl")
ROOT = Path(__file__).resolve().parents[1]


def bootstrap_audit_database(engine) -> None:
    for filename in (
        "001_create_schemas.sql",
        "005_create_ops.sql",
        "006_create_freshness.sql",
        "007_create_reconciliation.sql",
    ):
        run_sql_file(engine, ROOT / "sql" / filename)


def bootstrap_database(engine) -> None:
    for filename in (
        "010_create_bronze.sql",
        "020_create_silver.sql",
        "025_add_settlement_fields.sql",
        "030_create_gold.sql",
        "040_quality_views.sql",
    ):
        run_sql_file(engine, ROOT / "sql" / filename)


def get_fx_incremental_start(
    engine,
    configured_start: date,
    overlap_days: int,
) -> tuple[date, date | None]:
    """Return overlap-aware FX extraction start and latest stored FX date."""
    with engine.connect() as conn:
        latest = conn.execute(text("SELECT MAX(rate_date) FROM silver.fx_rate")).scalar_one_or_none()

    if latest is None:
        return configured_start, None

    overlap_start = latest - timedelta(days=overlap_days)
    return max(configured_start, overlap_start), latest


def cached_macro_is_fresh(engine, settings, as_of_year: int) -> bool:
    """Return whether cached macro rows cover every configured indicator within SLA."""
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT indicator_code, MAX(year) AS latest_year
                FROM silver.macro_indicator
                WHERE country_code = :country_code
                GROUP BY indicator_code
                """
            ),
            {"country_code": settings.world_bank_country},
        ).mappings().all()

    latest_by_indicator = {row["indicator_code"]: row["latest_year"] for row in rows}

    for indicator_code in settings.world_bank_indicators:
        latest_year = latest_by_indicator.get(indicator_code)
        if latest_year is None:
            LOGGER.error(
                "Cannot use cached World Bank data: no stored rows for %s.",
                indicator_code,
            )
            return False
        if latest_year > as_of_year:
            LOGGER.error(
                "Cannot use cached World Bank data: %s latest year %s is after run year %s.",
                indicator_code,
                latest_year,
                as_of_year,
            )
            return False
        if as_of_year - latest_year > settings.macro_freshness_years:
            LOGGER.error(
                "Cannot use cached World Bank data: %s latest year %s exceeds the %s-year freshness tolerance.",
                indicator_code,
                latest_year,
                settings.macro_freshness_years,
            )
            return False

    return True


def fetch_world_bank_with_cache_fallback(engine, settings, as_of_date: date):
    """Fetch macro data, falling back only to already-fresh stored observations."""
    try:
        return fetch_indicators(
            settings.world_bank_country,
            settings.world_bank_indicators,
            settings.world_bank_start_year,
            as_of_date.year,
        )
    except requests.RequestException as exc:
        if not cached_macro_is_fresh(engine, settings, as_of_date.year):
            LOGGER.error(
                "World Bank API unavailable and cached macro data is missing or stale; failing the ETL."
            )
            raise

        LOGGER.warning(
            "World Bank API unavailable after retries (%s). "
            "Continuing with existing macro data because it is within the configured freshness SLA.",
            exc,
        )
        return None


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


def record_reconciliation(
    engine,
    run_id: int,
    *,
    dataset_name: str,
    extracted_record_count: int,
    transformed_record_count: int,
    filtered_record_count: int,
    deduplicated_record_count: int,
    loaded_record_count: int,
) -> None:
    result = reconcile_and_persist(
        engine,
        run_id,
        dataset_name=dataset_name,
        extracted_record_count=extracted_record_count,
        bronze_payload_count=1,
        transformed_record_count=transformed_record_count,
        filtered_record_count=filtered_record_count,
        deduplicated_record_count=deduplicated_record_count,
        loaded_record_count=loaded_record_count,
    )

    log_fn = LOGGER.info if result.status == "PASS" else LOGGER.error
    log_fn("Reconciliation %s: %s - %s", result.status, dataset_name, result.details)

    if result.status == "FAIL":
        raise RuntimeError(
            f"Bronze-to-Silver reconciliation failed for {dataset_name} "
            f"with {result.unexplained_variance_count} unexplained record(s)."
        )


def run_pipeline(engine, settings, counts: dict[str, int], run_id: int) -> None:
    bootstrap_database(engine)

    today = date.today()
    fx_start, latest_fx_date = get_fx_incremental_start(
        engine,
        settings.fx_start_date,
        settings.fx_overlap_days,
    )
    if latest_fx_date is None:
        LOGGER.info(
            "No stored FX data found; extracting from configured start %s to %s",
            fx_start,
            today,
        )
    else:
        LOGGER.info(
            "Latest stored FX date: %s; overlap window: %s day(s); extracting from %s to %s",
            latest_fx_date,
            settings.fx_overlap_days,
            fx_start,
            today,
        )

    raw_fx = fetch_fx_rates(fx_start, today, settings.fx_quotes)
    load_raw_payload(engine, "frankfurter", FX_URL, raw_fx)
    fx_df = transform_fx_rates(raw_fx)
    counts["fx"] = upsert_fx(engine, fx_df)
    fx_filtered, fx_deduplicated = fx_filter_and_duplicate_counts(raw_fx)
    record_reconciliation(
        engine,
        run_id,
        dataset_name="frankfurter_fx",
        extracted_record_count=len(raw_fx),
        transformed_record_count=len(fx_df),
        filtered_record_count=fx_filtered,
        deduplicated_record_count=fx_deduplicated,
        loaded_record_count=counts["fx"],
    )

    LOGGER.info("Extracting World Bank indicators")
    raw_macro = fetch_world_bank_with_cache_fallback(engine, settings, today)
    if raw_macro is not None:
        load_raw_payload(engine, "world_bank", WB_URL, raw_macro)
        macro_df = transform_world_bank(raw_macro)
        counts["macro"] = upsert_macro(engine, macro_df)
        macro_filtered, macro_deduplicated = macro_filter_and_duplicate_counts(raw_macro)
        record_reconciliation(
            engine,
            run_id,
            dataset_name="world_bank_macro",
            extracted_record_count=len(raw_macro),
            transformed_record_count=len(macro_df),
            filtered_record_count=macro_filtered,
            deduplicated_record_count=macro_deduplicated,
            loaded_record_count=counts["macro"],
        )
    else:
        LOGGER.warning(
            "Skipped World Bank Bronze/Silver refresh for run %s; freshness gate will validate cached macro data.",
            run_id,
        )

    supplier_path = ROOT / "data" / "reference" / "suppliers.csv"
    product_path = ROOT / "data" / "reference" / "products.csv"
    supplier_df = transform_suppliers(supplier_path)
    product_df = transform_products(product_path)
    supplier_count = upsert_suppliers(engine, supplier_df)
    product_count = upsert_products(engine, product_df)
    LOGGER.info(
        "Loaded synthetic reference masters: %s suppliers, %s products",
        supplier_count,
        product_count,
    )

    po_path = ROOT / "data" / "reference" / "purchase_orders.csv"
    po_df = transform_purchase_orders(po_path)
    counts["po"] = upsert_purchase_orders(engine, po_df)
    run_sql_file(engine, ROOT / "sql" / "026_validate_settlement_constraint.sql")

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
