"""Generate deterministic synthetic supplier and product master data."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPLIER_OUT = ROOT / "data" / "reference" / "suppliers.csv"
PRODUCT_OUT = ROOT / "data" / "reference" / "products.csv"

suppliers = [
    {
        "supplier_id": "SUP-UK-01",
        "supplier_name": "Northbridge Components Ltd",
        "country_code": "GBR",
        "country_name": "United Kingdom",
        "region": "Europe",
        "supplier_tier": "Strategic",
        "payment_terms_days": 60,
        "is_synthetic": True,
    },
    {
        "supplier_id": "SUP-US-01",
        "supplier_name": "Atlantic Industrial Supply Inc",
        "country_code": "USA",
        "country_name": "United States",
        "region": "North America",
        "supplier_tier": "Core",
        "payment_terms_days": 45,
        "is_synthetic": True,
    },
    {
        "supplier_id": "SUP-EU-01",
        "supplier_name": "Rheinmark Manufacturing GmbH",
        "country_code": "DEU",
        "country_name": "Germany",
        "region": "Europe",
        "supplier_tier": "Strategic",
        "payment_terms_days": 60,
        "is_synthetic": True,
    },
    {
        "supplier_id": "SUP-EU-02",
        "supplier_name": "Iberia Packaging Solutions SL",
        "country_code": "ESP",
        "country_name": "Spain",
        "region": "Europe",
        "supplier_tier": "Core",
        "payment_terms_days": 45,
        "is_synthetic": True,
    },
]

products = [
    ("SKU-001", "Premium Glass Bottle 750ml", "Atlas", "Packaging", "Primary Packaging", "EA"),
    ("SKU-002", "Aluminium Closure Cap", "Atlas", "Packaging", "Primary Packaging", "EA"),
    ("SKU-003", "Printed Carton Case 6x750ml", "Meridian", "Packaging", "Secondary Packaging", "EA"),
    ("SKU-004", "Premium Label Set", "Meridian", "Packaging", "Labelling", "SET"),
    ("SKU-005", "Stainless Valve Assembly", "Orion", "Production Components", "Flow Control", "EA"),
    ("SKU-006", "Pump Seal Kit", "Orion", "Production Components", "Maintenance Parts", "KIT"),
    ("SKU-007", "Temperature Sensor Module", "Nova", "Production Components", "Instrumentation", "EA"),
    ("SKU-008", "Conveyor Belt Segment", "Nova", "Production Components", "Material Handling", "EA"),
    ("SKU-009", "Filling Nozzle Unit", "Apex", "Automation Equipment", "Filling Equipment", "EA"),
    ("SKU-010", "Industrial Barcode Scanner", "Apex", "Automation Equipment", "Traceability", "EA"),
    ("SKU-011", "Pallet Wrapper Drive Module", "Vector", "Automation Equipment", "Warehouse Equipment", "EA"),
    ("SKU-012", "Quality Inspection Camera", "Vector", "Automation Equipment", "Quality Control", "EA"),
]
product_rows = [
    {
        "product_id": product_id,
        "product_name": product_name,
        "brand_name": brand_name,
        "category": category,
        "subcategory": subcategory,
        "unit_of_measure": unit_of_measure,
        "is_synthetic": True,
    }
    for product_id, product_name, brand_name, category, subcategory, unit_of_measure in products
]

for path, rows in ((SUPPLIER_OUT, suppliers), (PRODUCT_OUT, product_rows)):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")
