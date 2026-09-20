from __future__ import annotations

from datetime import date
from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

BASE_URL = "https://api.frankfurter.dev/v2/rates"


@retry(
    retry=retry_if_exception_type(requests.RequestException),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def fetch_fx_rates(
    start_date: date,
    end_date: date,
    quotes: tuple[str, ...] = ("USD", "GBP", "EUR"),
    base: str = "ZAR",
) -> list[dict[str, Any]]:
    """Fetch Frankfurter v2 FX observations.

    We request ZAR as the base and convert the returned quote-per-ZAR rate
    into ZAR-per-foreign-currency during transformation.
    """
    params = {
        "base": base.lower(),
        "quotes": ",".join(q.lower() for q in quotes),
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
        "expand": "providers",
    }
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if not isinstance(payload, list):
        raise ValueError(f"Unexpected Frankfurter response type: {type(payload).__name__}")
    return payload
