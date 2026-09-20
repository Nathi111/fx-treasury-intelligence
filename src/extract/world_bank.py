from __future__ import annotations

from datetime import date
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

BASE_URL = "https://api.worldbank.org/v2"


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _get_json(url: str, params: dict[str, Any]) -> list[Any]:
    response = requests.get(url, params=params, timeout=30)
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
