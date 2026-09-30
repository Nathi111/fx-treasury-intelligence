from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.config import Settings


@dataclass(frozen=True)
class FreshnessResult:
    dataset_name: str
    latest_available_date: date | None
    latest_available_year: int | None
    lag_value: int | None
    tolerance_value: int
    lag_unit: str
    status: str
    details: str


def business_day_lag(latest_date: date, as_of_date: date) -> int:
    """Count weekdays after the latest observation through the run date."""
    if latest_date > as_of_date:
        raise ValueError("Latest observation date cannot be in the future.")

    lag = 0
    current = latest_date + timedelta(days=1)
    while current <= as_of_date:
        if current.weekday() < 5:
            lag += 1
        current += timedelta(days=1)
    return lag


def evaluate_fx_freshness(
    currency: str,
    latest_date: date | None,
    as_of_date: date,
    tolerance_business_days: int,
) -> FreshnessResult:
    dataset_name = f"fx:{currency}"

    if latest_date is None:
        return FreshnessResult(
            dataset_name=dataset_name,
            latest_available_date=None,
            latest_available_year=None,
            lag_value=None,
            tolerance_value=tolerance_business_days,
            lag_unit="business_days",
            status="FAIL",
            details=f"No FX observations found for {currency}.",
        )

    if latest_date > as_of_date:
        return FreshnessResult(
            dataset_name=dataset_name,
            latest_available_date=latest_date,
            latest_available_year=None,
            lag_value=None,
            tolerance_value=tolerance_business_days,
            lag_unit="business_days",
            status="FAIL",
            details=f"Latest FX date {latest_date} is after run date {as_of_date}.",
        )

    lag = business_day_lag(latest_date, as_of_date)
    status = "PASS" if lag <= tolerance_business_days else "FAIL"
    details = (
        f"Latest {currency} FX date {latest_date}; "
        f"{lag} business day(s) behind run date {as_of_date}; "
        f"tolerance {tolerance_business_days}."
    )
    return FreshnessResult(
        dataset_name=dataset_name,
        latest_available_date=latest_date,
        latest_available_year=None,
        lag_value=lag,
        tolerance_value=tolerance_business_days,
        lag_unit="business_days",
        status=status,
        details=details,
    )


def evaluate_macro_freshness(
    indicator_code: str,
    latest_year: int | None,
    as_of_year: int,
    tolerance_years: int,
) -> FreshnessResult:
    dataset_name = f"macro:{indicator_code}"

    if latest_year is None:
        return FreshnessResult(
            dataset_name=dataset_name,
            latest_available_date=None,
            latest_available_year=None,
            lag_value=None,
            tolerance_value=tolerance_years,
            lag_unit="years",
            status="FAIL",
            details=f"No macro observations found for {indicator_code}.",
        )

    if latest_year > as_of_year:
        return FreshnessResult(
            dataset_name=dataset_name,
            latest_available_date=None,
            latest_available_year=latest_year,
            lag_value=None,
            tolerance_value=tolerance_years,
            lag_unit="years",
            status="FAIL",
            details=f"Latest macro year {latest_year} is after run year {as_of_year}.",
        )

    lag = as_of_year - latest_year
    status = "PASS" if lag <= tolerance_years else "FAIL"
    details = (
        f"Latest {indicator_code} observation year {latest_year}; "
        f"{lag} year(s) behind run year {as_of_year}; "
        f"tolerance {tolerance_years}."
    )
    return FreshnessResult(
        dataset_name=dataset_name,
        latest_available_date=None,
        latest_available_year=latest_year,
        lag_value=lag,
        tolerance_value=tolerance_years,
        lag_unit="years",
        status=status,
        details=details,
    )


def collect_freshness_results(
    engine: Engine,
    settings: Settings,
    as_of_date: date,
) -> list[FreshnessResult]:
    with engine.connect() as conn:
        fx_rows = conn.execute(
            text(
                """
                SELECT foreign_currency, MAX(rate_date) AS latest_date
                FROM silver.fx_rate
                GROUP BY foreign_currency
                """
            )
        ).mappings().all()
        macro_rows = conn.execute(
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

    fx_latest = {row["foreign_currency"]: row["latest_date"] for row in fx_rows}
    macro_latest = {row["indicator_code"]: row["latest_year"] for row in macro_rows}

    results = [
        evaluate_fx_freshness(
            currency,
            fx_latest.get(currency),
            as_of_date,
            settings.fx_freshness_business_days,
        )
        for currency in settings.fx_quotes
    ]
    results.extend(
        evaluate_macro_freshness(
            indicator_code,
            macro_latest.get(indicator_code),
            as_of_date.year,
            settings.macro_freshness_years,
        )
        for indicator_code in settings.world_bank_indicators
    )
    return results


def persist_freshness_results(
    engine: Engine,
    run_id: int,
    results: list[FreshnessResult],
) -> int:
    if not results:
        return 0

    rows = [
        {
            "run_id": run_id,
            "dataset_name": result.dataset_name,
            "latest_available_date": result.latest_available_date,
            "latest_available_year": result.latest_available_year,
            "lag_value": result.lag_value,
            "tolerance_value": result.tolerance_value,
            "lag_unit": result.lag_unit,
            "status": result.status,
            "details": result.details,
        }
        for result in results
    ]

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ops.data_freshness_check (
                    run_id,
                    dataset_name,
                    latest_available_date,
                    latest_available_year,
                    lag_value,
                    tolerance_value,
                    lag_unit,
                    status,
                    details
                ) VALUES (
                    :run_id,
                    :dataset_name,
                    :latest_available_date,
                    :latest_available_year,
                    :lag_value,
                    :tolerance_value,
                    :lag_unit,
                    :status,
                    :details
                )
                """
            ),
            rows,
        )
    return len(rows)
