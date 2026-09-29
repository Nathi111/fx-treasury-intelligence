from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def normalise_database_url(database_url: str) -> str:
    """Use SQLAlchemy's psycopg v3 dialect for standard Neon/Postgres URLs."""
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    return database_url


def make_engine(database_url: str) -> Engine:
    return create_engine(normalise_database_url(database_url), pool_pre_ping=True)


def run_sql_file(engine: Engine, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))



def start_etl_run(engine: Engine) -> int:
    """Create a RUNNING audit record and return its generated run ID."""
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                INSERT INTO ops.etl_run (status)
                VALUES ('RUNNING')
                RETURNING run_id
                """
            )
        )
        return int(result.scalar_one())


def finish_etl_run(
    engine: Engine,
    run_id: int,
    *,
    status: str,
    fx_rows_processed: int,
    macro_rows_processed: int,
    po_rows_processed: int,
    error_message: str | None = None,
) -> None:
    """Finalize one audit record with status, row counts, and an optional error."""
    if status not in {"SUCCESS", "FAILED"}:
        raise ValueError("ETL audit status must be SUCCESS or FAILED.")

    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                UPDATE ops.etl_run
                SET
                    completed_at_utc = NOW(),
                    status = :status,
                    fx_rows_processed = :fx_rows_processed,
                    macro_rows_processed = :macro_rows_processed,
                    po_rows_processed = :po_rows_processed,
                    error_message = :error_message
                WHERE run_id = :run_id
                """
            ),
            {
                "run_id": run_id,
                "status": status,
                "fx_rows_processed": fx_rows_processed,
                "macro_rows_processed": macro_rows_processed,
                "po_rows_processed": po_rows_processed,
                "error_message": error_message,
            },
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Expected to update ETL run {run_id}, updated {result.rowcount} rows.")

def load_raw_payload(engine: Engine, source_name: str, endpoint: str, payload: Any) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO bronze.api_payload (source_name, endpoint, payload)
                VALUES (:source_name, :endpoint, CAST(:payload AS jsonb))
                """
            ),
            {
                "source_name": source_name,
                "endpoint": endpoint,
                "payload": json.dumps(payload, default=str),
            },
        )


def upsert_fx(engine: Engine, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    sql = text(
        """
        INSERT INTO silver.fx_rate (
            rate_date, base_currency, foreign_currency, foreign_per_zar,
            zar_per_unit, provider_count, payload_hash, extracted_at_utc
        ) VALUES (
            :rate_date, :base_currency, :foreign_currency, :foreign_per_zar,
            :zar_per_unit, :provider_count, :payload_hash, :extracted_at_utc
        )
        ON CONFLICT (rate_date, base_currency, foreign_currency)
        DO UPDATE SET
            foreign_per_zar = EXCLUDED.foreign_per_zar,
            zar_per_unit = EXCLUDED.zar_per_unit,
            provider_count = EXCLUDED.provider_count,
            payload_hash = EXCLUDED.payload_hash,
            extracted_at_utc = EXCLUDED.extracted_at_utc
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


def upsert_macro(engine: Engine, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    sql = text(
        """
        INSERT INTO silver.macro_indicator (
            country_code, country_name, indicator_code, indicator_name,
            year, value, unit, obs_status, extracted_at_utc
        ) VALUES (
            :country_code, :country_name, :indicator_code, :indicator_name,
            :year, :value, :unit, :obs_status, :extracted_at_utc
        )
        ON CONFLICT (country_code, indicator_code, year)
        DO UPDATE SET
            country_name = EXCLUDED.country_name,
            indicator_name = EXCLUDED.indicator_name,
            value = EXCLUDED.value,
            unit = EXCLUDED.unit,
            obs_status = EXCLUDED.obs_status,
            extracted_at_utc = EXCLUDED.extracted_at_utc
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


def upsert_purchase_orders(engine: Engine, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = df.to_dict(orient="records")
    sql = text(
        """
        INSERT INTO silver.purchase_order (
            po_id, supplier_id, product_id, order_date, expected_arrival_date,
            currency, foreign_value, budget_fx_rate, status
        ) VALUES (
            :po_id, :supplier_id, :product_id, :order_date, :expected_arrival_date,
            :currency, :foreign_value, :budget_fx_rate, :status
        )
        ON CONFLICT (po_id)
        DO UPDATE SET
            supplier_id = EXCLUDED.supplier_id,
            product_id = EXCLUDED.product_id,
            order_date = EXCLUDED.order_date,
            expected_arrival_date = EXCLUDED.expected_arrival_date,
            currency = EXCLUDED.currency,
            foreign_value = EXCLUDED.foreign_value,
            budget_fx_rate = EXCLUDED.budget_fx_rate,
            status = EXCLUDED.status,
            loaded_at_utc = NOW()
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)
