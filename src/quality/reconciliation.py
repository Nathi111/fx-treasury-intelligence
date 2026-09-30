from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class ReconciliationResult:
    dataset_name: str
    extracted_record_count: int
    bronze_payload_count: int
    transformed_record_count: int
    filtered_record_count: int
    deduplicated_record_count: int
    loaded_record_count: int
    unexplained_variance_count: int
    status: str
    details: str


def fx_filter_and_duplicate_counts(payload: list[dict[str, Any]]) -> tuple[int, int]:
    """Count rows intentionally filtered or deduplicated by the FX transform."""
    filtered = 0
    valid_keys: list[tuple[Any, Any, Any]] = []

    for row in payload:
        rate = row.get("rate")
        if rate in (None, 0):
            filtered += 1
            continue

        fx_rate = Decimal(str(rate))
        if fx_rate <= 0:
            filtered += 1
            continue

        valid_keys.append(
            (
                row.get("date"),
                str(row.get("base", "")).upper(),
                str(row.get("quote", "")).upper(),
            )
        )

    deduplicated = len(valid_keys) - len(set(valid_keys))
    return filtered, deduplicated


def macro_filter_and_duplicate_counts(payload: list[dict[str, Any]]) -> tuple[int, int]:
    """Count null-filtered and duplicate World Bank business-grain rows."""
    filtered = 0
    valid_keys: list[tuple[Any, Any, Any]] = []

    for row in payload:
        if row.get("value") is None:
            filtered += 1
            continue

        valid_keys.append(
            (
                row.get("countryiso3code"),
                (row.get("indicator") or {}).get("id"),
                row.get("date"),
            )
        )

    deduplicated = len(valid_keys) - len(set(valid_keys))
    return filtered, deduplicated


def build_reconciliation_result(
    *,
    dataset_name: str,
    extracted_record_count: int,
    bronze_payload_count: int,
    transformed_record_count: int,
    filtered_record_count: int,
    deduplicated_record_count: int,
    loaded_record_count: int,
) -> ReconciliationResult:
    source_variance = (
        extracted_record_count
        - filtered_record_count
        - deduplicated_record_count
        - transformed_record_count
    )
    load_variance = transformed_record_count - loaded_record_count
    unexplained_variance = abs(source_variance) + abs(load_variance)
    status = "PASS" if unexplained_variance == 0 else "FAIL"

    details = (
        f"extracted={extracted_record_count}, bronze_payloads={bronze_payload_count}, "
        f"filtered={filtered_record_count}, deduplicated={deduplicated_record_count}, "
        f"transformed={transformed_record_count}, loaded={loaded_record_count}, "
        f"source_variance={source_variance}, load_variance={load_variance}"
    )

    return ReconciliationResult(
        dataset_name=dataset_name,
        extracted_record_count=extracted_record_count,
        bronze_payload_count=bronze_payload_count,
        transformed_record_count=transformed_record_count,
        filtered_record_count=filtered_record_count,
        deduplicated_record_count=deduplicated_record_count,
        loaded_record_count=loaded_record_count,
        unexplained_variance_count=unexplained_variance,
        status=status,
        details=details,
    )


def persist_reconciliation_result(
    engine: Engine,
    run_id: int,
    result: ReconciliationResult,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ops.etl_reconciliation (
                    run_id,
                    dataset_name,
                    extracted_record_count,
                    bronze_payload_count,
                    transformed_record_count,
                    filtered_record_count,
                    deduplicated_record_count,
                    loaded_record_count,
                    unexplained_variance_count,
                    status,
                    details
                ) VALUES (
                    :run_id,
                    :dataset_name,
                    :extracted_record_count,
                    :bronze_payload_count,
                    :transformed_record_count,
                    :filtered_record_count,
                    :deduplicated_record_count,
                    :loaded_record_count,
                    :unexplained_variance_count,
                    :status,
                    :details
                )
                """
            ),
            {
                "run_id": run_id,
                "dataset_name": result.dataset_name,
                "extracted_record_count": result.extracted_record_count,
                "bronze_payload_count": result.bronze_payload_count,
                "transformed_record_count": result.transformed_record_count,
                "filtered_record_count": result.filtered_record_count,
                "deduplicated_record_count": result.deduplicated_record_count,
                "loaded_record_count": result.loaded_record_count,
                "unexplained_variance_count": result.unexplained_variance_count,
                "status": result.status,
                "details": result.details,
            },
        )


def reconcile_and_persist(
    engine: Engine,
    run_id: int,
    *,
    dataset_name: str,
    extracted_record_count: int,
    bronze_payload_count: int,
    transformed_record_count: int,
    filtered_record_count: int,
    deduplicated_record_count: int,
    loaded_record_count: int,
) -> ReconciliationResult:
    result = build_reconciliation_result(
        dataset_name=dataset_name,
        extracted_record_count=extracted_record_count,
        bronze_payload_count=bronze_payload_count,
        transformed_record_count=transformed_record_count,
        filtered_record_count=filtered_record_count,
        deduplicated_record_count=deduplicated_record_count,
        loaded_record_count=loaded_record_count,
    )
    persist_reconciliation_result(engine, run_id, result)
    return result
