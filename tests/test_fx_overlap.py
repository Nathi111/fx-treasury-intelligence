from datetime import date
from unittest.mock import MagicMock

import pandas as pd

from src.load.postgres import upsert_fx
from src.pipeline import get_fx_incremental_start


def _engine_with_latest(latest):
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    result = MagicMock()
    result.scalar_one_or_none.return_value = latest
    conn.execute.return_value = result
    return engine


def test_first_fx_load_uses_configured_start():
    engine = _engine_with_latest(None)

    start, latest = get_fx_incremental_start(
        engine,
        configured_start=date(2024, 1, 1),
        overlap_days=7,
    )

    assert start == date(2024, 1, 1)
    assert latest is None


def test_incremental_fx_load_refetches_seven_calendar_days():
    engine = _engine_with_latest(date(2026, 9, 29))

    start, latest = get_fx_incremental_start(
        engine,
        configured_start=date(2024, 1, 1),
        overlap_days=7,
    )

    assert latest == date(2026, 9, 29)
    assert start == date(2026, 9, 22)


def test_fx_overlap_never_moves_before_configured_start():
    engine = _engine_with_latest(date(2024, 1, 4))

    start, latest = get_fx_incremental_start(
        engine,
        configured_start=date(2024, 1, 1),
        overlap_days=7,
    )

    assert latest == date(2024, 1, 4)
    assert start == date(2024, 1, 1)


def test_zero_overlap_reproduces_latest_date_behaviour():
    engine = _engine_with_latest(date(2026, 9, 29))

    start, latest = get_fx_incremental_start(
        engine,
        configured_start=date(2024, 1, 1),
        overlap_days=0,
    )

    assert latest == date(2026, 9, 29)
    assert start == date(2026, 9, 29)


def test_fx_upsert_remains_idempotent_for_overlapping_rows():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn

    df = pd.DataFrame(
        [
            {
                "rate_date": date(2026, 9, 29),
                "base_currency": "ZAR",
                "foreign_currency": "USD",
                "foreign_per_zar": 0.061,
                "zar_per_unit": 16.39344262,
                "provider_count": 1,
                "payload_hash": "a" * 64,
                "extracted_at_utc": "2026-09-30T00:00:00+00:00",
            }
        ]
    )

    count = upsert_fx(engine, df)

    assert count == 1
    sql_text = str(conn.execute.call_args.args[0])
    assert "ON CONFLICT (rate_date, base_currency, foreign_currency)" in sql_text
    assert "DO UPDATE SET" in sql_text
