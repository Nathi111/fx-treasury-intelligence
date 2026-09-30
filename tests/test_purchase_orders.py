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

    received = df[df["status"] == "Received"]
    open_pos = df[df["status"] == "Open"]

    assert len(received) == 50
    assert len(open_pos) == 130
    assert received["settlement_date"].notna().all()
    assert received["settlement_fx_rate"].notna().all()
    assert (received["settlement_fx_rate"] > 0).all()
    assert open_pos["settlement_date"].isna().all()
    assert open_pos["settlement_fx_rate"].isna().all()


def _base_row(**overrides):
    row = {
        "po_id": "PO-1",
        "supplier_id": "S1",
        "product_id": "P1",
        "order_date": "2026-01-01",
        "expected_arrival_date": "2026-02-01",
        "currency": "USD",
        "foreign_value": 1000,
        "budget_fx_rate": 18.0,
        "status": "Open",
        "settlement_date": "",
        "settlement_fx_rate": "",
    }
    row.update(overrides)
    return row


def test_invalid_currency_is_rejected(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([_base_row(currency="JPY")]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Unexpected currencies"):
        transform_purchase_orders(path)


def test_received_po_requires_settlement_fields(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([_base_row(status="Received")]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="require settlement_date"):
        transform_purchase_orders(path)


def test_open_po_rejects_settlement_fields(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([
        _base_row(
            settlement_date="2026-02-05",
            settlement_fx_rate=18.5,
        )
    ]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Open purchase orders cannot contain settlement data"):
        transform_purchase_orders(path)


def test_settlement_date_cannot_precede_order_date(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame([
        _base_row(
            status="Received",
            settlement_date="2025-12-31",
            settlement_fx_rate=18.5,
        )
    ]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="settlement_date cannot be before order_date"):
        transform_purchase_orders(path)
