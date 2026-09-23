# FX Treasury Intelligence — API ETL + Power BI

An end-to-end analytics engineering portfolio project that models the foreign-exchange exposure of a South African importer with purchase orders denominated in USD, GBP and EUR and management reporting in ZAR.

The project combines **live public API data**, **Python ETL**, **PostgreSQL/Neon**, **automated data-quality controls**, a **Gold reporting layer**, and a four-page **Power BI treasury dashboard**.

> The procurement dataset is synthetic and created for portfolio demonstration. FX and macroeconomic data are sourced from public APIs.

## Business problem

A South African importer commits to purchase orders in foreign currencies while ultimately funding and reporting those commitments in ZAR. Exchange-rate movements between budgeting and settlement can materially change expected landed cost.

The solution is designed to answer four practical questions:

1. **How much open FX exposure does the business currently carry?**
2. **How do current rates compare with budget assumptions?**
3. **Which currencies, suppliers, products and purchase orders drive the exposure?**
4. **What macroeconomic and market context sits behind the FX environment?**

## Solution architecture

~~~text
Frankfurter FX API ───────┐
                          ├─> Python Extract ─> Bronze ─> Python Transform ─> Silver ─> SQL Gold ─> Power BI
World Bank Indicators API ┘

Synthetic Purchase Orders ────────────────────────────────────────────────┘
~~~

See [docs/architecture.md](docs/architecture.md) for the detailed architecture.

## Technology stack

| Layer | Technology |
|---|---|
| API extraction | Python, Requests, Tenacity |
| Transformation | Python, Pandas, Decimal |
| Database | PostgreSQL on Neon |
| Data modelling | Bronze / Silver / Gold |
| SQL access | SQLAlchemy + psycopg |
| Testing | pytest |
| Orchestration | GitHub Actions |
| BI / semantic layer | Power BI, DAX |
| Version control | GitHub |

## Data sources

### Frankfurter v2

Public FX-rate API used to ingest historical rates for:

- USD/ZAR
- GBP/ZAR
- EUR/ZAR

Rates are transformed into **ZAR per foreign-currency unit** for treasury reporting.

### World Bank Indicators API v2

Public macroeconomic data for South Africa:

- Inflation, consumer prices (annual %)
- GDP growth (annual %)

### Synthetic procurement data

A deterministic synthetic purchase-order dataset is included for the commercial exposure scenario.

It contains:

- purchase order ID
- supplier ID
- product ID
- order date
- expected arrival date
- foreign currency
- foreign value
- budget FX rate
- order status

No confidential or employer data is used.

## Data architecture

### Bronze

Raw API payloads are retained for traceability and replay.

~~~text
bronze.api_payload
~~~

### Silver

Typed, validated and deduplicated analytical tables:

~~~text
silver.fx_rate
silver.macro_indicator
silver.purchase_order
~~~

### Gold

Reporting-ready dimensions, facts and analytical views:

~~~text
gold.dim_date
gold.dim_currency
gold.dim_supplier
gold.dim_product
gold.fact_purchase_order_exposure
gold.v_fx_rates
gold.v_latest_fx_rates
gold.v_macro_indicators
gold.v_data_quality_failures
~~~

The date dimension follows an **April-to-March fiscal year**, with April as fiscal month 1.

## FX exposure logic

At purchase-order level:

~~~text
Budget ZAR Value  = Foreign Value × Budget FX Rate
Current ZAR Value = Foreign Value × Current FX Rate
FX Variance ZAR   = Current ZAR Value - Budget ZAR Value
~~~

For this importer scenario:

- a **negative FX variance** is favourable because the current expected ZAR cost is below budget;
- a **positive FX variance** is unfavourable because the current expected ZAR cost is above budget.

Only open purchase orders are included in current exposure.

## Power BI report

The completed report contains four pages.

### 1. Treasury Executive Overview

Executive view of:

- open FX exposure
- open purchase-order count
- FX cost variance
- exposure by currency
- budget vs current FX cost
- upcoming exposure by expected arrival month
- FX variance contribution by currency

### 2. Currency Risk Analysis

Market and budget-rate analysis including:

- latest EUR/ZAR, GBP/ZAR and USD/ZAR rates
- historical FX-rate trend
- weighted budget rate vs current rate
- 30-day FX movement by currency

### 3. Procurement Exposure

Operational concentration analysis covering:

- open supplier count
- open product count
- exposure by supplier
- exposure by product
- detailed open purchase-order drill-down
- currency filtering

### 4. Macro & Market Context

External context using South African macroeconomic indicators:

- latest inflation
- latest GDP growth
- inflation and GDP-growth history
- annual/YTD average FX rates vs ZAR

## Example refresh snapshot

Because the APIs refresh over time, dashboard outputs change as new market data arrives.

A recent captured refresh showed approximately:

| Metric | Value |
|---|---:|
| Open purchase orders | 130 |
| Open FX exposure | R102.56m |
| FX variance | -R10.12m |
| FX variance % | -8.98% |
| Open suppliers | 4 |
| Open products | 12 |
| Latest EUR/ZAR | R18.62 |
| Latest GBP/ZAR | R21.70 |
| Latest USD/ZAR | R16.22 |
| Latest SA inflation | 3.21% |
| Latest SA GDP growth | 1.11% |

These values are a **point-in-time portfolio snapshot**, not static assumptions.

## Power BI screenshots

Final screenshots will be stored in the screenshots/ folder using:

~~~text
screenshots/
├── 01-treasury-executive-overview.png
├── 02-currency-risk-analysis.png
├── 03-procurement-exposure.png
└── 04-macro-market-context.png
~~~

The Power BI .pbix file is **available on request**.

## Data quality and reconciliation

The pipeline includes:

- primary-key enforcement
- duplicate checks
- positive FX-rate validation
- null filtering for macro observations
- deterministic FX inversion testing
- purchase-order validation
- SQL data-quality view
- pipeline failure when Gold-layer quality checks return failures
- Power BI KPI reconciliation against the Gold layer

gold.v_data_quality_failures is retained as an operational control rather than loaded into the business-facing Power BI model.

## Automation

GitHub Actions runs:

- unit tests on development and pull-request workflows
- the ETL pipeline on its scheduled/manual workflow
- the database load only when the required database secret is available

The GitHub repository secret is named DATABASEURL and is mapped into the application as DATABASE_URL.

No database credentials are committed to the repository.

## Tests

The project currently includes tests covering:

- FX-rate inversion
- FX deduplication
- macro null handling
- synthetic PO integrity
- invalid-currency rejection
- PostgreSQL/Neon URL normalization

Run locally with:

~~~bash
python -m pytest -q
~~~

## Quick start

~~~bash
python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Add your PostgreSQL/Neon DATABASE_URL to .env

python -m pytest -q
python -m src.pipeline
~~~

## Environment variables

| Variable | Purpose |
|---|---|
| DATABASE_URL | PostgreSQL/Neon SQLAlchemy connection string |
| FX_START_DATE | Initial FX-history start date |
| FX_QUOTES | Foreign currencies tracked against ZAR |
| WORLD_BANK_COUNTRY | World Bank ISO3 country code; defaults to ZAF |
| WORLD_BANK_START_YEAR | First macroeconomic year to extract |
| WORLD_BANK_INDICATORS | Comma-separated World Bank indicator codes |

## Repository structure

~~~text
.
├── .github/workflows/
├── data/
│   └── reference/
├── docs/
├── sql/
├── src/
│   ├── extract/
│   ├── load/
│   └── transform/
├── tests/
├── .env.example
├── requirements.txt
└── README.md
~~~

## Portfolio outcomes

This project demonstrates an end-to-end workflow rather than a dashboard-only exercise:

- API integration
- Python data engineering
- incremental and idempotent loading
- PostgreSQL modelling
- SQL transformations
- cloud database deployment
- data-quality controls
- CI/CD-style orchestration
- dimensional modelling
- DAX measures
- Power BI report design
- finance/treasury analysis
- reconciliation between source warehouse and BI outputs

## Roadmap

### Completed

- [x] ETL repository scaffold
- [x] Frankfurter v2 extractor
- [x] World Bank v2 extractor with pagination
- [x] Bronze / Silver / Gold PostgreSQL structure
- [x] synthetic purchase-order generation
- [x] FX exposure fact model
- [x] automated data-quality gate
- [x] unit tests
- [x] scheduled GitHub Actions workflow
- [x] Neon deployment and live pipeline validation
- [x] Power BI star-schema model
- [x] core DAX measure layer
- [x] Treasury Executive Overview
- [x] Currency Risk Analysis
- [x] Procurement Exposure
- [x] Macro & Market Context
- [x] Power BI-to-Neon KPI reconciliation

### Potential enhancements

- [ ] ETL run-audit table with row counts and run status
- [ ] automated freshness SLA check
- [ ] Bronze-to-Silver reconciliation logging
- [ ] deliberate incremental overlap for upstream FX revisions
- [ ] realized FX variance using settlement rates
- [ ] richer supplier and product attributes
- [ ] Power BI Service deployment and scheduled semantic-model refresh
