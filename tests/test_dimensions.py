from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.load.postgres import upsert_products, upsert_suppliers
from src.transform.reference import transform_products, transform_suppliers


ROOT = Path(__file__).resolve().parents[1]


def test_supplier_master_is_valid_and_synthetic():
    df = transform_suppliers(ROOT / "data" / "reference" / "suppliers.csv")

    assert len(df) == 4
    assert df["supplier_id"].is_unique
    assert df["supplier_name"].notna().all()
    assert set(df["region"]) == {"Europe", "North America"}
    assert df["is_synthetic"].all()


def test_product_master_is_valid_and_synthetic():
    df = transform_products(ROOT / "data" / "reference" / "products.csv")

    assert len(df) == 12
    assert df["product_id"].is_unique
    assert df["product_name"].notna().all()
    assert set(df["category"]) == {
        "Packaging",
        "Production Components",
        "Automation Equipment",
    }
    assert df["is_synthetic"].all()


def test_reference_dimensions_cover_all_purchase_order_keys():
    po = pd.read_csv(ROOT / "data" / "reference" / "purchase_orders.csv")
    suppliers = transform_suppliers(ROOT / "data" / "reference" / "suppliers.csv")
    products = transform_products(ROOT / "data" / "reference" / "products.csv")

    assert set(po["supplier_id"]).issubset(set(suppliers["supplier_id"]))
    assert set(po["product_id"]).issubset(set(products["product_id"]))


def test_non_synthetic_reference_rows_are_rejected(tmp_path):
    path = tmp_path / "suppliers.csv"
    pd.DataFrame(
        [
            {
                "supplier_id": "SUP-1",
                "supplier_name": "Example",
                "country_code": "ZAF",
                "country_name": "South Africa",
                "region": "Africa",
                "supplier_tier": "Core",
                "payment_terms_days": 30,
                "is_synthetic": False,
            }
        ]
    ).to_csv(path, index=False)

    with pytest.raises(ValueError, match="explicitly synthetic"):
        transform_suppliers(path)


def test_supplier_upsert_uses_stable_supplier_key():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    df = transform_suppliers(ROOT / "data" / "reference" / "suppliers.csv").head(1)

    assert upsert_suppliers(engine, df) == 1
    sql_text = str(conn.execute.call_args.args[0])
    assert "ON CONFLICT (supplier_id)" in sql_text
    assert "supplier_name = EXCLUDED.supplier_name" in sql_text


def test_product_upsert_uses_stable_product_key():
    engine = MagicMock()
    conn = MagicMock()
    engine.begin.return_value.__enter__.return_value = conn
    df = transform_products(ROOT / "data" / "reference" / "products.csv").head(1)

    assert upsert_products(engine, df) == 1
    sql_text = str(conn.execute.call_args.args[0])
    assert "ON CONFLICT (product_id)" in sql_text
    assert "product_name = EXCLUDED.product_name" in sql_text


def test_gold_dimensions_keep_existing_fact_relationship_keys():
    sql = (ROOT / "sql" / "030_create_gold.sql").read_text(encoding="utf-8")

    assert "CREATE OR REPLACE VIEW gold.dim_supplier" in sql
    assert "FROM silver.supplier" in sql
    assert "CREATE OR REPLACE VIEW gold.dim_product" in sql
    assert "FROM silver.product" in sql
    assert "po.supplier_id" in sql
    assert "po.product_id" in sql
