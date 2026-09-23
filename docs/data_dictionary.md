# Data Dictionary

This dictionary documents the implemented Bronze, Silver and Gold objects used by the FX Treasury Intelligence project.

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
| `currency_code` | Foreign currency |
| `status` | Open or Received |
| `foreign_value` | PO value in foreign currency |
| `budget_fx_rate` | Budgeted ZAR-per-unit rate |
| `budget_zar_value` | `foreign_value × budget_fx_rate` |
| `current_fx_rate_date` | Date of latest FX rate applied |
| `current_fx_rate` | Latest ZAR-per-unit FX rate |
| `current_zar_value` | Current ZAR revaluation for open POs |
| `fx_variance_zar` | `current_zar_value - budget_zar_value` for open POs |
| `fx_variance_pct` | `current_fx_rate / budget_fx_rate - 1` for open POs |
| `open_exposure_zar` | Current ZAR value for open POs; zero for received POs |
| `days_to_arrival` | Expected arrival date minus current date |

### Variance interpretation

For this importer scenario:

- **Negative FX variance = favourable** because current expected ZAR cost is below budget.
- **Positive FX variance = unfavourable** because current expected ZAR cost is above budget.

Received POs are not revalued because the model does not yet contain settlement FX rates.

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
