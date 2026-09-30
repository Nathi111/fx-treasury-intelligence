"""Generate deterministic synthetic purchase-order data for the portfolio model.

The external FX and macro observations are real API data. Purchase orders are
synthetic by design so the repository does not imply access to confidential
commercial transactions.
"""
from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).resolve().parents[1] / "data" / "reference" / "purchase_orders.csv"

currencies = ["USD", "GBP", "EUR"]
suppliers = ["SUP-UK-01", "SUP-US-01", "SUP-EU-01", "SUP-EU-02"]
products = [f"SKU-{i:03d}" for i in range(1, 13)]
start = date(2025, 1, 1)
settlement_snapshot_date = date(2026, 9, 30)

rows = []
for i in range(1, 181):
    order_date = start + timedelta(days=random.randint(0, 620))
    currency = random.choice(currencies)
    supplier_id = random.choice(suppliers)
    product_id = random.choice(products)
    expected_arrival_date = order_date + timedelta(days=random.randint(21, 75))
    foreign_value = round(random.uniform(2_500, 85_000), 2)
    budget_fx_rate = round(
        {"USD": 18.2, "GBP": 23.4, "EUR": 20.1}[currency] * random.uniform(0.94, 1.06),
        4,
    )
    status = random.choice(["Open", "Open", "Open", "Received"])

    settlement_date = ""
    settlement_fx_rate = ""
    if status == "Received":
        settlement_date = min(
            expected_arrival_date + timedelta(days=(i % 11) - 5),
            settlement_snapshot_date,
        ).isoformat()
        settlement_factor = 1 + (((i * 37) % 101) - 50) / 1000
        settlement_fx_rate = round(budget_fx_rate * settlement_factor, 4)

    rows.append(
        {
            "po_id": f"PO-{i:05d}",
            "supplier_id": supplier_id,
            "product_id": product_id,
            "order_date": order_date.isoformat(),
            "expected_arrival_date": expected_arrival_date.isoformat(),
            "currency": currency,
            "foreign_value": foreign_value,
            "budget_fx_rate": budget_fx_rate,
            "status": status,
            "settlement_date": settlement_date,
            "settlement_fx_rate": settlement_fx_rate,
        }
    )

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to {OUT}")
