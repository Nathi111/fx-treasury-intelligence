# Data Dictionary

This dictionary documents the implemented operational, Bronze, Silver and Gold objects used by the FX Treasury Intelligence project.

## Operational metadata

### `ops.etl_run`

Grain: one row per ETL pipeline execution.

| Column | Type | Description |
|---|---|---|
| `run_id` | BIGSERIAL | Unique pipeline-run identifier |
| `started_at_utc` | TIMESTAMPTZ | UTC timestamp when the run audit record was created |
| `completed_at_utc` | TIMESTAMPTZ | UTC completion timestamp; null while running |
| `status` | TEXT | `RUNNING`, `SUCCESS`, or `FAILED` |
| `fx_rows_processed` | INTEGER | FX rows processed during the run |
| `macro_rows_processed` | INTEGER | Macro rows processed during the run |
| `po_rows_processed` | INTEGER | Purchase-order rows processed during the run |
| `error_message` | TEXT | Captured exception type/message for failed runs |

The audit row is created before the main ETL/schema work starts, then finalized on success or failure. Partial row counts are retained if a later pipeline stage fails.

### `ops.data_freshness_check`

Grain: one freshness result per dataset/currency/indicator per ETL run.

| Column | Type | Description |
|---|---|---|
| `check_id` | BIGSERIAL | Unique freshness-check identifier |
| `run_id` | BIGINT | Foreign key to `ops.etl_run` |
| `dataset_name` | TEXT | Checked dataset, e.g. `fx:USD` or `macro:FP.CPI.TOTL.ZG` |
| `latest_available_date` | DATE | Latest FX observation date when applicable |
| `latest_available_year` | INTEGER | Latest macro observation year when applicable |
| `lag_value` | INTEGER | Observed lag in the relevant unit |
| `tolerance_value` | INTEGER | Configured SLA tolerance |
| `lag_unit` | TEXT | `business_days` or `years` |
| `status` | TEXT | `PASS` or `FAIL` |
| `details` | TEXT | Human-readable freshness result |
| `checked_at_utc` | TIMESTAMPTZ | UTC timestamp of the check |

FX freshness is evaluated separately for each configured currency. Weekends are excluded from the lag count. Macro freshness is evaluated separately for each configured World Bank indicator using an annual publication-lag tolerance.


### `ops.etl_reconciliation`

Grain: one Bronze-to-Silver reconciliation result per API dataset per ETL run.

| Column | Type | Description |
|---|---|---|
| `reconciliation_id` | BIGSERIAL | Unique reconciliation identifier |
| `run_id` | BIGINT | Foreign key to `ops.etl_run` |
| `dataset_name` | TEXT | Reconciled API dataset |
| `extracted_record_count` | INTEGER | Raw records returned by the source API |
| `bronze_payload_count` | INTEGER | Raw payloads written to Bronze |
| `transformed_record_count` | INTEGER | Records remaining after filtering/deduplication |
| `filtered_record_count` | INTEGER | Rows intentionally removed by transform rules |
| `deduplicated_record_count` | INTEGER | Duplicate business-grain rows removed |
| `loaded_record_count` | INTEGER | Rows passed to the Silver upsert |
| `unexplained_variance_count` | INTEGER | Absolute unexplained source/load variance |
| `status` | TEXT | `PASS` or `FAIL` |
| `details` | TEXT | Count equation and variance detail |
| `checked_at_utc` | TIMESTAMPTZ | UTC reconciliation timestamp |

The reconciliation equation is:

```text
Extracted = Filtered + Deduplicated + Transformed
Transformed = Loaded
```

A non-zero unexplained variance produces `FAIL` and stops the pipeline. Synthetic purchase orders are validated separately because they originate from a reference CSV rather than the Bronze API layer.

## Bronze layer

### `bronze.api_payload`

Grain: one raw API response payload per extraction event.

| Column | Type | Description |
|---|---|---|
| `payload_id` | BIGSERIAL | Surrogate identifier for the raw payload |
| `source_name` | TEXT | Source system/API name |
| `endpoint` | TEXT | API endpoint used for extraction |
| `payload` | JSONB | Raw response body retained for lineage/replay |
| `extracted_at_utc` | TIMESTAMPTZ | UTC extraction timestamp |

## Silver layer

### `silver.fx_rate`

Grain: one observation per rate date, ZAR base currency and foreign currency.

| Column | Type | Description |
|---|---|---|
| `rate_date` | DATE | FX observation date |
| `base_currency` | CHAR(3) | Base currency, ZAR in this project |
| `foreign_currency` | CHAR(3) | USD, GBP or EUR |
| `foreign_per_zar` | NUMERIC(18,8) | Foreign-currency units per ZAR from the source transformation |
| `zar_per_unit` | NUMERIC(18,8) | Reporting rate: ZAR required per one unit of foreign currency |
| `provider_count` | INTEGER | Number of contributing providers returned by the API |
| `payload_hash` | CHAR(64) | SHA-256 hash used for payload traceability |
| `extracted_at_utc` | TIMESTAMPTZ | Source extraction timestamp |

Primary key: `rate_date, base_currency, foreign_currency`.

### `silver.macro_indicator`

Grain: one country / indicator / year observation.

| Column | Type | Description |
|---|---|---|
| `country_code` | CHAR(3) | ISO3 country code, ZAF |
| `country_name` | TEXT | Country name |
| `indicator_code` | TEXT | World Bank indicator code |
| `indicator_name` | TEXT | Human-readable indicator name |
| `year` | INTEGER | Observation year |
| `value` | NUMERIC(24,8) | Indicator value as returned by World Bank |
| `unit` | TEXT | Unit metadata when supplied |
| `obs_status` | TEXT | Observation status metadata |
| `extracted_at_utc` | TIMESTAMPTZ | Extraction timestamp |

Primary key: `country_code, indicator_code, year`.

### `silver.purchase_order`

Grain: one synthetic purchase order.

| Column | Type | Description |
|---|---|---|
| `po_id` | TEXT | Purchase-order identifier |
| `supplier_id` | TEXT | Synthetic supplier identifier |
| `product_id` | TEXT | Synthetic product/SKU identifier |
| `order_date` | DATE | Date the purchase order was raised |
| `expected_arrival_date` | DATE | Expected goods arrival date |
| `currency` | CHAR(3) | Purchase-order currency: USD, GBP or EUR |
| `foreign_value` | NUMERIC(18,2) | Purchase-order value in foreign currency |
| `budget_fx_rate` | NUMERIC(18,6) | Budgeted ZAR-per-unit FX rate |
| `status` | TEXT | `Open` or `Received` |
| `settlement_date` | DATE | Settlement date for received POs; null for open POs |
| `settlement_fx_rate` | NUMERIC(18,6) | Settled ZAR-per-unit FX rate for received POs |
| `loaded_at_utc` | TIMESTAMPTZ | Database load timestamp |

Primary key: `po_id`.

## Gold dimensions

### `gold.dim_date`

Daily calendar dimension spanning the relevant PO, FX and expected-arrival period.

| Column | Description |
|---|---|
| `date` | Calendar date |
| `calendar_year` | Calendar year |
| `month_number` | Calendar month number |
| `month_short` | Three-character month label |
| `year_month` | YYYY-MM reporting key |
| `fiscal_year_start` | Start year of April-to-March fiscal year |
| `fiscal_year_end` | End year of April-to-March fiscal year |
| `fiscal_month_number` | Fiscal month where April = 1 and March = 12 |

### `gold.dim_currency`

Grain: one purchase-order currency.

Column: `currency_code`.

### `gold.dim_supplier`

Grain: one supplier.

Column: `supplier_id`.

### `gold.dim_product`

Grain: one product/SKU.

Column: `product_id`.

## Gold facts and analytical views

### `gold.v_fx_rates`

Historical FX time series used for Power BI trend analysis.

| Column | Description |
|---|---|
| `rate_date` | Observation date |
| `currency_code` | Foreign currency |
| `zar_per_unit` | ZAR per one unit of foreign currency |
| `previous_rate` | Previous available observation for the same currency |
| `rate_change` | Absolute change vs previous observation |
| `rate_change_pct` | Percentage change vs previous observation |
| `provider_count` | Number of contributing source providers |
| `extracted_at_utc` | Extraction timestamp |

### `gold.v_latest_fx_rates`

Grain: one row per currency containing the latest available FX observation.

Columns: `currency_code, rate_date, zar_per_unit, provider_count, extracted_at_utc`.

### `gold.v_macro_indicators`

Reporting view over the annual macroeconomic indicators.

Columns: `country_code, country_name, indicator_code, indicator_name, year, value, unit, obs_status`.

### `gold.fact_purchase_order_exposure`

Grain: one purchase order.

| Column | Description |
|---|---|
| `po_id` | Purchase-order identifier |
| `supplier_id` | Supplier identifier |
| `product_id` | Product/SKU identifier |
| `order_date` | PO date |
| `expected_arrival_date` | Expected goods arrival date |
| `settlement_date` | Actual/synthetic settlement date for received POs |
| `currency_code` | Foreign currency |
| `status` | Open or Received |
| `foreign_value` | PO value in foreign currency |
| `budget_fx_rate` | Budgeted ZAR-per-unit rate |
| `settlement_fx_rate` | Settled ZAR-per-unit rate for received POs |
| `budget_zar_value` | `foreign_value × budget_fx_rate` |
| `current_fx_rate_date` | Date of latest FX rate applied |
| `current_fx_rate` | Latest ZAR-per-unit FX rate |
| `current_zar_value` | Current ZAR revaluation for open POs |
| `settled_zar_value` | Settled ZAR value for received POs |
| `unrealized_fx_variance_zar` | Current less budget ZAR value for open POs |
| `unrealized_fx_variance_pct` | Current-rate variance vs budget for open POs |
| `realized_fx_variance_zar` | Settled less budget ZAR value for received POs |
| `realized_fx_variance_pct` | Settlement-rate variance vs budget for received POs |
| `fx_variance_zar` | Backward-compatible unrealized variance for open POs |
| `fx_variance_pct` | `current_fx_rate / budget_fx_rate - 1` for open POs |
| `open_exposure_zar` | Current ZAR value for open POs; zero for received POs |
| `days_to_arrival` | Expected arrival date minus current date |

### Variance interpretation

For this importer scenario:

- **Negative FX variance = favourable** because current expected ZAR cost is below budget.
- **Positive FX variance = unfavourable** because current expected ZAR cost is above budget.

Received POs are valued using their settlement FX rate and therefore report realized variance independently of current market rates.

### `gold.v_data_quality_failures`

Operational control view. A healthy pipeline returns zero rows.

Implemented tests:

| Test | Failure condition |
|---|---|
| `fx_non_positive_rate` | FX rate is zero or negative |
| `fx_duplicate_business_key` | Duplicate FX date/base/currency key |
| `macro_duplicate_business_key` | Duplicate country/indicator/year key |
| `purchase_order_duplicate_id` | Duplicate PO ID |
| `open_po_missing_fx_rate` | Open PO has no current FX rate |

The pipeline raises an error if any quality failure is returned.
