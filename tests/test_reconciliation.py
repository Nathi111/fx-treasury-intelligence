from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src import pipeline
from src.quality.reconciliation import (
    ReconciliationResult,
    build_reconciliation_result,
    fx_filter_and_duplicate_counts,
    macro_filter_and_duplicate_counts,
    persist_reconciliation_result,
)


def test_fx_reconciliation_counts_filtered_and_duplicate_rows():
    payload = [
        {"date": "2026-09-29", "base": "ZAR", "quote": "USD", "rate": 0.061},
        {"date": "2026-09-29", "base": "ZAR", "quote": "USD", "rate": 0.061},
        {"date": "2026-09-29", "base": "ZAR", "quote": "GBP", "rate": 0},
        {"date": "2026-09-29", "base": "ZAR", "quote": "EUR", "rate": -0.1},
    ]

    filtered, deduplicated = fx_filter_and_duplicate_counts(payload)

    assert filtered == 2
    assert deduplicated == 1


def test_macro_reconciliation_counts_nulls_and_duplicate_business_keys():
    payload = [
        {
            "countryiso3code": "ZAF",
            "indicator": {"id": "FP.CPI.TOTL.ZG"},
            "date": "2024",
            "value": 4.4,
        },
        {
            "countryiso3code": "ZAF",
            "indicator": {"id": "FP.CPI.TOTL.ZG"},
            "date": "2024",
            "value": 4.5,
        },
        {
            "countryiso3code": "ZAF",
            "indicator": {"id": "FP.CPI.TOTL.ZG"},
            "date": "2025",
            "value": None,
        },
    ]

    filtered, deduplicated = macro_filter_and_duplicate_counts(payload)

    assert filtered == 1
    assert deduplicated == 1


def test_balanced_reconciliation_passes():
    result = build_reconciliation_result(
        dataset_name="frankfurter_fx",
        extracted_record_count=10,
        bronze_payload_count=1,
        transformed_record_count=7,
        filtered_record_count=2,
        deduplicated_record_count=1,
        loaded_record_count=7,
    )

    assert result.status == "PASS"
    assert result.unexplained_variance_count == 0


def test_reconciliation_fails_on_unexplained_load_variance():
    result = build_reconciliation_result(
        dataset_name="world_bank_macro",
        extracted_record_count=10,
        bronze_payload_count=1,
        transformed_record_count=8,
        filtered_record_count=2,
        deduplicated_record_count=0,
        loaded_record_count=7,
    )

    assert result.status == "FAIL"
    assert result.unexplained_variance_count == 1
    assert "load_variance=1" in result.details


def test_reconciliation_fails_on_unexplained_source_variance():
    result = build_reconciliation_result(
        dataset_name="frankfurter_fx",
        extracted_record_count=10,
        bronze_payload_count=1,
        transformed_record_count=6,
        filtered_record_count=2,
        deduplicated_record_count=1,
        loaded_record_count=6,
    )

    assert result.status == "FAIL"
    assert result.unexplained_variance_count == 1
    assert "source_variance=1" in result.details


def test_persist_reconciliation_result_links_to_run():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    result = ReconciliationResult(
        dataset_name="frankfurter_fx",
        extracted_record_count=10,
        bronze_payload_count=1,
        transformed_record_count=10,
        filtered_record_count=0,
        deduplicated_record_count=0,
        loaded_record_count=10,
        unexplained_variance_count=0,
        status="PASS",
        details="balanced",
    )

    persist_reconciliation_result(engine, 123, result)

    params = conn.execute.call_args.args[1]
    assert params["run_id"] == 123
    assert params["dataset_name"] == "frankfurter_fx"
    assert params["status"] == "PASS"


def test_pipeline_reconciliation_gate_allows_balanced_counts():
    engine = MagicMock()
    result = ReconciliationResult(
        dataset_name="frankfurter_fx",
        extracted_record_count=10,
        bronze_payload_count=1,
        transformed_record_count=10,
        filtered_record_count=0,
        deduplicated_record_count=0,
        loaded_record_count=10,
        unexplained_variance_count=0,
        status="PASS",
        details="balanced",
    )

    with patch.object(pipeline, "reconcile_and_persist", return_value=result) as reconcile:
        pipeline.record_reconciliation(
            engine,
            55,
            dataset_name="frankfurter_fx",
            extracted_record_count=10,
            transformed_record_count=10,
            filtered_record_count=0,
            deduplicated_record_count=0,
            loaded_record_count=10,
        )

    reconcile.assert_called_once()


def test_pipeline_reconciliation_gate_raises_after_persisted_failure():
    engine = MagicMock()
    result = ReconciliationResult(
        dataset_name="world_bank_macro",
        extracted_record_count=10,
        bronze_payload_count=1,
        transformed_record_count=8,
        filtered_record_count=1,
        deduplicated_record_count=0,
        loaded_record_count=8,
        unexplained_variance_count=1,
        status="FAIL",
        details="source mismatch",
    )

    with (
        patch.object(pipeline, "reconcile_and_persist", return_value=result),
        pytest.raises(RuntimeError, match="world_bank_macro"),
    ):
        pipeline.record_reconciliation(
            engine,
            56,
            dataset_name="world_bank_macro",
            extracted_record_count=10,
            transformed_record_count=8,
            filtered_record_count=1,
            deduplicated_record_count=0,
            loaded_record_count=8,
        )
