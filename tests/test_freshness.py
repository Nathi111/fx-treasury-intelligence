from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src import pipeline
from src.quality.freshness import (
    FreshnessResult,
    business_day_lag,
    evaluate_fx_freshness,
    evaluate_macro_freshness,
    persist_freshness_results,
)


def test_business_day_lag_ignores_weekend():
    assert business_day_lag(date(2026, 9, 25), date(2026, 9, 27)) == 0


def test_business_day_lag_counts_monday_after_friday():
    assert business_day_lag(date(2026, 9, 25), date(2026, 9, 28)) == 1


def test_fx_freshness_passes_within_business_day_tolerance():
    result = evaluate_fx_freshness(
        "USD",
        date(2026, 9, 25),
        date(2026, 9, 28),
        tolerance_business_days=1,
    )

    assert result.status == "PASS"
    assert result.lag_value == 1
    assert result.lag_unit == "business_days"


def test_fx_freshness_fails_when_stale():
    result = evaluate_fx_freshness(
        "USD",
        date(2026, 9, 24),
        date(2026, 9, 28),
        tolerance_business_days=1,
    )

    assert result.status == "FAIL"
    assert result.lag_value == 2


def test_macro_freshness_allows_publication_lag():
    result = evaluate_macro_freshness(
        "FP.CPI.TOTL.ZG",
        latest_year=2024,
        as_of_year=2026,
        tolerance_years=2,
    )

    assert result.status == "PASS"
    assert result.lag_value == 2
    assert result.lag_unit == "years"


def test_macro_freshness_fails_when_older_than_tolerance():
    result = evaluate_macro_freshness(
        "NY.GDP.MKTP.KD.ZG",
        latest_year=2023,
        as_of_year=2026,
        tolerance_years=2,
    )

    assert result.status == "FAIL"
    assert result.lag_value == 3


def test_missing_observation_fails_clearly():
    fx = evaluate_fx_freshness("EUR", None, date(2026, 9, 30), 1)
    macro = evaluate_macro_freshness("TEST", None, 2026, 2)

    assert fx.status == "FAIL"
    assert "No FX observations" in fx.details
    assert macro.status == "FAIL"
    assert "No macro observations" in macro.details


def test_persist_freshness_results_writes_run_linked_rows():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    result = FreshnessResult(
        dataset_name="fx:USD",
        latest_available_date=date(2026, 9, 29),
        latest_available_year=None,
        lag_value=1,
        tolerance_value=1,
        lag_unit="business_days",
        status="PASS",
        details="fresh",
    )

    count = persist_freshness_results(engine, 55, [result])

    assert count == 1
    rows = conn.execute.call_args.args[1]
    assert rows[0]["run_id"] == 55
    assert rows[0]["dataset_name"] == "fx:USD"
    assert rows[0]["status"] == "PASS"


def test_freshness_gate_persists_passes_without_raising():
    engine = MagicMock()
    settings = SimpleNamespace()
    results = [
        FreshnessResult(
            dataset_name="fx:USD",
            latest_available_date=date(2026, 9, 29),
            latest_available_year=None,
            lag_value=1,
            tolerance_value=1,
            lag_unit="business_days",
            status="PASS",
            details="fresh",
        )
    ]

    with (
        patch.object(pipeline, "collect_freshness_results", return_value=results),
        patch.object(pipeline, "persist_freshness_results") as persist,
    ):
        pipeline.run_freshness_gate(engine, settings, 77, date(2026, 9, 30))

    persist.assert_called_once_with(engine, 77, results)


def test_freshness_gate_raises_after_persisting_failure():
    engine = MagicMock()
    settings = SimpleNamespace()
    results = [
        FreshnessResult(
            dataset_name="macro:TEST",
            latest_available_date=None,
            latest_available_year=2022,
            lag_value=4,
            tolerance_value=2,
            lag_unit="years",
            status="FAIL",
            details="stale",
        )
    ]

    with (
        patch.object(pipeline, "collect_freshness_results", return_value=results),
        patch.object(pipeline, "persist_freshness_results") as persist,
        pytest.raises(RuntimeError, match="macro:TEST"),
    ):
        pipeline.run_freshness_gate(engine, settings, 78, date(2026, 9, 30))

    persist.assert_called_once_with(engine, 78, results)
