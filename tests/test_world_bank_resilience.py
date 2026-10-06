from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from src import pipeline


def _settings():
    return SimpleNamespace(
        world_bank_country="ZAF",
        world_bank_indicators=("FP.CPI.TOTL.ZG", "NY.GDP.MKTP.KD.ZG"),
        world_bank_start_year=2018,
        macro_freshness_years=2,
    )


def _engine_with_macro_rows(rows):
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.mappings.return_value.all.return_value = rows
    return engine


def test_cached_macro_is_fresh_when_all_indicators_are_within_sla():
    engine = _engine_with_macro_rows(
        [
            {"indicator_code": "FP.CPI.TOTL.ZG", "latest_year": 2025},
            {"indicator_code": "NY.GDP.MKTP.KD.ZG", "latest_year": 2024},
        ]
    )

    assert pipeline.cached_macro_is_fresh(engine, _settings(), 2026)


def test_cached_macro_is_not_fresh_when_an_indicator_is_missing():
    engine = _engine_with_macro_rows(
        [{"indicator_code": "FP.CPI.TOTL.ZG", "latest_year": 2025}]
    )

    assert not pipeline.cached_macro_is_fresh(engine, _settings(), 2026)


def test_cached_macro_is_not_fresh_when_an_indicator_exceeds_sla():
    engine = _engine_with_macro_rows(
        [
            {"indicator_code": "FP.CPI.TOTL.ZG", "latest_year": 2025},
            {"indicator_code": "NY.GDP.MKTP.KD.ZG", "latest_year": 2023},
        ]
    )

    assert not pipeline.cached_macro_is_fresh(engine, _settings(), 2026)


def test_world_bank_timeout_uses_fresh_cache():
    engine = MagicMock()
    settings = _settings()

    with (
        patch.object(
            pipeline,
            "fetch_indicators",
            side_effect=requests.ReadTimeout("World Bank timed out"),
        ),
        patch.object(pipeline, "cached_macro_is_fresh", return_value=True) as cache_check,
    ):
        result = pipeline.fetch_world_bank_with_cache_fallback(
            engine,
            settings,
            date(2026, 10, 6),
        )

    assert result is None
    cache_check.assert_called_once_with(engine, settings, 2026)


def test_world_bank_timeout_fails_when_cache_is_not_usable():
    engine = MagicMock()
    settings = _settings()

    with (
        patch.object(
            pipeline,
            "fetch_indicators",
            side_effect=requests.ReadTimeout("World Bank timed out"),
        ),
        patch.object(pipeline, "cached_macro_is_fresh", return_value=False),
        pytest.raises(requests.ReadTimeout, match="World Bank timed out"),
    ):
        pipeline.fetch_world_bank_with_cache_fallback(
            engine,
            settings,
            date(2026, 10, 6),
        )
