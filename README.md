# FX Treasury Intelligence — API ETL + Power BI Portfolio Project

An end-to-end analytics engineering portfolio project for a South African importer with foreign-currency exposure.

## Business problem

Purchase orders are raised in USD, GBP and EUR while management reports in ZAR. Currency movements can change the expected landed cost before an order is settled. This project builds a reproducible pipeline for FX and macroeconomic data, then prepares a reporting layer for Power BI treasury and procurement insights.

## What this project demonstrates

- REST API extraction with Python
- retry and HTTP error handling
- incremental / idempotent data loading
- raw-data lineage (Bronze)
- typed and deduplicated transformations (Silver)
- SQL reporting views (Gold)
- PostgreSQL / Neon-compatible loading
- automated data-quality gates
- synthetic procurement transactions with explicit provenance
- April-to-March fiscal date dimension
- PO-level FX exposure / revaluation fact view
- pytest unit tests
- GitHub Actions orchestration
- Power BI semantic-model readiness

## Sources

1. **Frankfurter v2** — public exchange-rate API, no API key required.
2. **World Bank Indicators API v2** — public macroeconomic indicators, no API key required.

The commercial purchase-order dataset used later in the project is synthetic and is clearly labelled as such.

## Architecture

```text
REST APIs -> Python Extract -> Bronze -> Python Transform -> Silver -> SQL Gold -> Power BI
```

See [`docs/architecture.md`](docs/architecture.md).

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add your PostgreSQL/Neon DATABASE_URL
pytest -q
python -m src.pipeline
```

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL/Neon SQLAlchemy connection string |
| `FX_START_DATE` | Initial history start date |
| `FX_QUOTES` | Foreign currencies tracked against ZAR |
| `WORLD_BANK_COUNTRY` | ISO3 country code, default `ZAF` |
| `WORLD_BANK_START_YEAR` | First macro year to extract |
| `WORLD_BANK_INDICATORS` | Comma-separated World Bank indicator codes |

## Quality controls

The MVP includes:
- primary-key duplicate prevention
- positive-rate constraints
- null filtering for macro observations
- deterministic FX inversion test
- SQL duplicate checks
- automated test-before-load workflow

## Portfolio roadmap

- [x] ETL repository scaffold
- [x] Frankfurter v2 extractor
- [x] World Bank v2 extractor with pagination
- [x] Bronze / Silver / Gold PostgreSQL structure
- [x] unit tests
- [x] scheduled GitHub Actions workflow
- [x] load synthetic purchase orders
- [x] build FX exposure fact model
- [ ] add reconciliation and freshness tests
- [ ] build Power BI star schema
- [ ] add DAX measures and executive dashboard
- [ ] document insights and interview talking points
