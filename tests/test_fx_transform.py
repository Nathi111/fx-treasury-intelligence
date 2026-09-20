from decimal import Decimal

from src.transform.fx import transform_fx_rates


def test_transform_fx_inverts_zar_base_rate():
    payload = [
        {
            "date": "2026-09-18",
            "base": "ZAR",
            "quote": "USD",
            "rate": 0.0625,
            "providers": ["example"],
        }
    ]
    df = transform_fx_rates(payload)
    assert len(df) == 1
    assert df.iloc[0]["foreign_currency"] == "USD"
    assert df.iloc[0]["zar_per_unit"] == Decimal("16")


def test_transform_fx_deduplicates_business_key():
    row = {
        "date": "2026-09-18",
        "base": "ZAR",
        "quote": "EUR",
        "rate": 0.05,
        "providers": [],
    }
    df = transform_fx_rates([row, row])
    assert len(df) == 1
