from pathlib import Path

import pandas as pd
import pytest

from src.transform.purchase_orders import transform_purchase_orders


def test_reference_purchase_orders_are_valid():
    path = Path(__file__).resolve().parents[1] / "data" / "reference" / "purchase_orders.csv"
    df = transform_purchase_orders(path)
    assert len(df) == 180
    assert set(df["currency"]) == {"USD", "GBP", "EUR"}
    assert not df["po_id"].duplicated().any()


def test_invalid_currency_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([
        {
            "po_id": "PO-1",
            "supplier_id": "S1",
            "product_id": "P1",
            "order_date": "2026-01-01",
            "expected_arrival_date": "2026-02-01",
            "currency": "JPY",
            "foreign_value": 1000,
            "budget_fx_rate": 0.12,
            "status": "Open",
        }
    ]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Unexpected currencies"):
        transform_purchase_orders(path)
