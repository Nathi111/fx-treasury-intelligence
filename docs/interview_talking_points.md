# Interview Talking Points

## 90-second project story

I built FX Treasury Intelligence as an end-to-end analytics engineering portfolio project for a simulated South African importer that buys in USD, GBP and EUR but reports in ZAR. The business problem is that exchange-rate movements between budgeting and settlement can materially change the expected ZAR cost of open purchase orders.

I used the Frankfurter API for live FX history and the World Bank API for South African inflation and GDP growth, then built a Python ETL pipeline with retry handling, validation and idempotent PostgreSQL upserts. Raw API responses are retained in a Bronze layer, typed and deduplicated records are stored in Silver, and SQL Gold views calculate reporting-ready FX exposure and variance.

The pipeline runs against Neon Postgres and is tested and orchestrated through GitHub Actions. I then connected Power BI directly to the Gold layer and built a star-schema model with four report pages covering executive treasury exposure, currency risk, procurement concentration and macro context.

A key part of the project was reconciliation: I checked Power BI KPIs back to the Gold layer before finalising the report. I also implemented a SQL data-quality gate so the ETL fails if duplicate keys, invalid FX rates or open purchase orders without a current rate are detected.

## Business problem

**Question:** What problem were you solving?

**Answer:** A business can raise a purchase order at one budget rate but ultimately fund it when the market rate has moved. The project quantifies the current ZAR value of open foreign-currency commitments and shows the difference from budget, while also identifying which currencies, suppliers, products and arrival periods drive the risk.

## Why Bronze / Silver / Gold?

**Question:** Why did you use a medallion-style architecture for a relatively small project?

**Answer:** I wanted the architecture to separate lineage, transformation and consumption. Bronze preserves the raw API response so I can audit or replay source data. Silver creates typed, deduplicated business-grain records. Gold contains reporting-ready logic and dimensions. That makes the pipeline easier to test and allows Power BI to stay focused on semantic modelling and analysis rather than source cleaning.

## Why Python and SQL rather than Power Query?

**Answer:** I deliberately moved repeatable ingestion and business transformations upstream. Python handles API extraction, retry behaviour, validation and loading. SQL handles relational reporting logic and Gold views. Power Query therefore stays light, which makes the BI layer simpler and demonstrates separation of responsibilities.

## Idempotency

**Question:** What happens if the pipeline runs twice?

**Answer:** Silver loads use PostgreSQL `ON CONFLICT` upserts against stable business keys. Re-running the pipeline updates or reuses the same keys rather than creating duplicates. The quality view also checks for duplicate business keys.

## FX-rate transformation

**Question:** What did you have to do with the API rate?

**Answer:** The source representation is transformed into ZAR per one unit of the foreign currency because that is the intuitive rate for this business scenario. I used Decimal arithmetic for the inversion and added a unit test to verify the calculation.

## FX variance

**Question:** How is FX variance calculated?

**Answer:**

```text
Budget ZAR Value  = Foreign Value × Budget FX Rate
Current ZAR Value = Foreign Value × Latest FX Rate
FX Variance ZAR   = Current ZAR Value - Budget ZAR Value
```

For an importer, a negative result is favourable because the current ZAR requirement is lower than budget. A positive result is unfavourable.

## Why only open POs are revalued

**Answer:** The dataset has an order status but no actual settlement FX rate. Revaluing received POs using today's market rate would create a false realized variance, so received POs return null for current revaluation measures. In production I would store settlement date/rate and calculate realized versus unrealized variance separately.

## Power BI model

**Question:** How did you model the report?

**Answer:** The purchase-order exposure view is the primary fact, filtered by date, currency, supplier and product dimensions. The FX-rate view acts as a second fact sharing date and currency. Macro indicators are annual grain and remain separate rather than being forced into a daily relationship. Relationships use one-to-many, single-direction filtering.

## April-to-March fiscal year

**Answer:** Fiscal attributes are generated upstream in the Gold date dimension, with April as fiscal month 1. That makes the reporting rule reusable across reports and avoids repeating fiscal logic in DAX.

## Reconciliation

**Question:** How did you know the dashboard was right?

**Answer:** I reconciled the core Power BI KPIs—open PO count, open FX exposure and variance—against the Gold-layer outputs in Neon before styling the report. I treated reconciliation as a build step, not just a final visual check.

## Data quality

**Question:** What controls did you implement?

**Answer:** I used database constraints, transformation validation, pytest unit tests and a Gold SQL quality view. The quality view checks non-positive FX rates, duplicate business keys, duplicate PO IDs and open POs without an FX rate. The pipeline raises an exception if the view returns failures.

## Automation

**Answer:** GitHub Actions runs tests on development/pull-request workflows and executes the ETL on its scheduled/manual path. The database credential is stored as a GitHub secret and mapped into the application's environment variable; it is never committed to the repository.

## Key trade-offs

- Public API data is real; procurement data is synthetic so the project can be shared safely.
- Supplier and product dimensions intentionally start simple and can be enriched later.
- Macro data is annual, so it is kept at its natural grain.
- Received POs do not show realized FX variance because settlement rates are not modeled yet.
- The current incremental FX load could be hardened with a small overlap window for provider revisions.

## What I would add in production

1. ETL-run audit table with run ID, timestamps, status and row counts.
2. Data-freshness SLA and automated alerting.
3. Bronze-to-Silver reconciliation logging.
4. A 3–7 day incremental extraction overlap to capture revised upstream observations.
5. Settlement rates and realized/unrealized FX variance.
6. Richer supplier/product master data and commercial hierarchies.
7. Power BI Service deployment with controlled refresh and access governance.

## Strong technical follow-up questions to expect

- Why use `Decimal` for FX calculations?
- How would you handle API schema drift?
- How would you backfill missing rate dates?
- How would you distinguish transaction, translation and economic FX exposure?
- What would change if the number of purchase orders increased from hundreds to millions?
- Would you still use views, or materialize Gold tables?
- How would you implement incremental refresh in Power BI?
- How would you secure the database for production reporting?
- How would you calculate realized variance once settlement data becomes available?
