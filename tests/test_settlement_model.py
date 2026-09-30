from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from src.load.postgres import upsert_purchase_orders


ROOT = Path(__file__).resolve().parents[1]


def test_gold_exposure_view_exposes_realized_and_unrealized_variance():
    sql = (ROOT / "sql" / "030_create_gold.sql").read_text(encoding="utf-8")

    assert "settlement_fx_rate" in sql
    assert "settled_zar_value" in sql
    assert "unrealized_fx_variance_zar" in sql
    assert "unrealized_fx_variance_pct" in sql
    assert "realized_fx_variance_zar" in sql
    assert "realized_fx_variance_pct" in sql
    assert "CASE WHEN po.status = 'Open' THEN fx.zar_per_unit END AS current_fx_rate" in sql


def test_purchase_order_upsert_includes_settlement_fields():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn

    df = pd.DataFrame(
        [
            {
                "po_id": "PO-1",
                "supplier_id": "S1",
                "product_id": "P1",
                "order_date": "2026-01-01",
                "expected_arrival_date": "2026-02-01",
                "currency": "USD",
                "foreign_value": 1000,
                "budget_fx_rate": 18.0,
                "status": "Received",
                "settlement_date": "2026-02-03",
                "settlement_fx_rate": 18.5,
            }
        ]
    )

    count = upsert_purchase_orders(engine, df)

    assert count == 1
    sql_text = str(conn.execute.call_args.args[0])
    assert "settlement_date" in sql_text
    assert "settlement_fx_rate" in sql_text
    assert "settlement_date = EXCLUDED.settlement_date" in sql_text
    assert "settlement_fx_rate = EXCLUDED.settlement_fx_rate" in sql_text


def test_existing_open_variance_columns_remain_for_power_bi_compatibility():
    sql = (ROOT / "sql" / "030_create_gold.sql").read_text(encoding="utf-8")

    assert "AS fx_variance_zar" in sql
    assert "AS fx_variance_pct" in sql
    assert "AS open_exposure_zar" in sql
