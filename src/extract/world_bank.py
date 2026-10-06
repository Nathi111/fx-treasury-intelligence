from __future__ import annotations

import logging
from datetime import date
from typing import Any

import requests
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_random_exponential

BASE_URL = "https://api.worldbank.org/v2"
CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 60
MAX_ATTEMPTS = 5
LOGGER = logging.getLogger(__name__)


def _is_retryable_world_bank_error(exc: BaseException) -> bool:
    if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
        return True

    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500

    return False


@retry(
    retry=retry_if_exception(_is_retryable_world_bank_error),
    stop=stop_after_attempt(MAX_ATTEMPTS),
    wait=wait_random_exponential(multiplier=2, max=30),
    before_sleep=before_sleep_log(LOGGER, logging.WARNING),
    reraise=True,
)
def _get_json(url: str, params: dict[str, Any]) -> list[Any]:
    response = requests.get(
        url,
        params=params,
        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        headers={"User-Agent": "fx-treasury-intelligence/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2:
        raise ValueError("Unexpected World Bank API response")
    return payload


def fetch_indicators(
    country: str,
    indicators: tuple[str, ...],
    start_year: int,
    end_year: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch World Bank indicators with explicit pagination."""
    end_year = end_year or date.today().year
    rows: list[dict[str, Any]] = []

    for indicator in indicators:
        page = 1
        while True:
            url = f"{BASE_URL}/country/{country}/indicator/{indicator}"
            payload = _get_json(
                url,
                {
                    "format": "json",
                    "date": f"{start_year}:{end_year}",
                    "per_page": 100,
                    "page": page,
                },
            )
            meta, data = payload[0], payload[1] or []
            rows.extend(data)

            if page >= int(meta.get("pages", 1)):
                break
            page += 1

    return rows
