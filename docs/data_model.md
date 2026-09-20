# Data model

## Silver layer

### `silver.fx_rate`
Grain: one observation per rate date, ZAR base, and foreign currency.

### `silver.macro_indicator`
Grain: one South Africa / indicator / year observation.

### `silver.purchase_order`
Grain: one synthetic purchase order.

The purchase orders are synthetic by design; real market/macro observations come from public APIs.

## Gold star-schema layer

### Dimensions
- `gold.dim_date` — daily calendar plus April-to-March fiscal month, fiscal-year-start, and fiscal-year-end attributes.
- `gold.dim_currency`
- `gold.dim_supplier`
- `gold.dim_product`

### Facts / analytical views
- `gold.v_fx_rates` — FX time series with prior rate and rate change.
- `gold.fact_purchase_order_exposure` — PO-level treasury exposure and FX variance.
- `gold.v_macro_indicators` — macroeconomic context.

### `gold.fact_purchase_order_exposure` business logic

For each PO:

- `budget_zar_value = foreign_value × budget_fx_rate`
- for open POs, `current_zar_value = foreign_value × latest_fx_rate`
- for open POs, `fx_variance_zar = current_zar_value − budget_zar_value`
- for open POs, `fx_variance_pct = current_fx_rate ÷ budget_fx_rate − 1`
- `open_exposure_zar` is current ZAR value only for open POs; received POs are not revalued without a settlement rate.

This supports Power BI analysis by currency, supplier, product, order month, arrival month, and status.
