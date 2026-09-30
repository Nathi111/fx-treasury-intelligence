CREATE OR REPLACE VIEW gold.v_fx_rates AS
SELECT
    rate_date,
    foreign_currency AS currency_code,
    zar_per_unit,
    LAG(zar_per_unit) OVER (
        PARTITION BY foreign_currency ORDER BY rate_date
    ) AS previous_rate,
    zar_per_unit - LAG(zar_per_unit) OVER (
        PARTITION BY foreign_currency ORDER BY rate_date
    ) AS rate_change,
    CASE
        WHEN LAG(zar_per_unit) OVER (PARTITION BY foreign_currency ORDER BY rate_date) IS NULL THEN NULL
        ELSE (zar_per_unit / LAG(zar_per_unit) OVER (PARTITION BY foreign_currency ORDER BY rate_date)) - 1
    END AS rate_change_pct,
    provider_count,
    extracted_at_utc
FROM silver.fx_rate;

CREATE OR REPLACE VIEW gold.v_latest_fx_rates AS
SELECT DISTINCT ON (foreign_currency)
    foreign_currency AS currency_code,
    rate_date,
    zar_per_unit,
    provider_count,
    extracted_at_utc
FROM silver.fx_rate
ORDER BY foreign_currency, rate_date DESC;

CREATE OR REPLACE VIEW gold.v_macro_indicators AS
SELECT
    country_code,
    country_name,
    indicator_code,
    indicator_name,
    year,
    value,
    unit,
    obs_status
FROM silver.macro_indicator;

CREATE OR REPLACE VIEW gold.dim_currency AS
SELECT DISTINCT
    currency AS currency_code
FROM silver.purchase_order;

CREATE OR REPLACE VIEW gold.dim_supplier AS
SELECT
    supplier_id,
    supplier_name,
    country_code,
    country_name,
    region,
    supplier_tier,
    payment_terms_days,
    is_synthetic
FROM silver.supplier;

CREATE OR REPLACE VIEW gold.dim_product AS
SELECT
    product_id,
    product_name,
    brand_name,
    category,
    subcategory,
    unit_of_measure,
    is_synthetic
FROM silver.product;

CREATE OR REPLACE VIEW gold.dim_date AS
SELECT
    d::DATE AS date,
    EXTRACT(YEAR FROM d)::INTEGER AS calendar_year,
    EXTRACT(MONTH FROM d)::INTEGER AS month_number,
    TO_CHAR(d, 'Mon') AS month_short,
    TO_CHAR(d, 'YYYY-MM') AS year_month,
    CASE WHEN EXTRACT(MONTH FROM d) >= 4
        THEN EXTRACT(YEAR FROM d)::INTEGER
        ELSE EXTRACT(YEAR FROM d)::INTEGER - 1
    END AS fiscal_year_start,
    CASE WHEN EXTRACT(MONTH FROM d) >= 4
        THEN EXTRACT(YEAR FROM d)::INTEGER + 1
        ELSE EXTRACT(YEAR FROM d)::INTEGER
    END AS fiscal_year_end,
    ((EXTRACT(MONTH FROM d)::INTEGER + 8) % 12) + 1 AS fiscal_month_number
FROM generate_series(
    LEAST(
        COALESCE((SELECT MIN(order_date) FROM silver.purchase_order), CURRENT_DATE),
        COALESCE((SELECT MIN(rate_date) FROM silver.fx_rate), CURRENT_DATE)
    )::TIMESTAMP,
    GREATEST(
        COALESCE((SELECT MAX(expected_arrival_date) FROM silver.purchase_order), CURRENT_DATE),
        COALESCE((SELECT MAX(settlement_date) FROM silver.purchase_order), CURRENT_DATE),
        CURRENT_DATE
    )::TIMESTAMP,
    INTERVAL '1 day'
) d;

CREATE OR REPLACE VIEW gold.fact_purchase_order_exposure AS
SELECT
    po.po_id,
    po.supplier_id,
    po.product_id,
    po.order_date,
    po.expected_arrival_date,
    po.currency AS currency_code,
    po.status,
    po.foreign_value,
    po.budget_fx_rate,
    po.foreign_value * po.budget_fx_rate AS budget_zar_value,
    CASE WHEN po.status = 'Open' THEN fx.rate_date END AS current_fx_rate_date,
    (CASE WHEN po.status = 'Open' THEN fx.zar_per_unit END)::NUMERIC(18,8) AS current_fx_rate,
    CASE WHEN po.status = 'Open'
        THEN po.foreign_value * fx.zar_per_unit
    END AS current_zar_value,
    CASE WHEN po.status = 'Open'
        THEN (po.foreign_value * fx.zar_per_unit) - (po.foreign_value * po.budget_fx_rate)
    END AS fx_variance_zar,
    CASE
        WHEN po.status <> 'Open' OR po.budget_fx_rate = 0 THEN NULL
        ELSE (fx.zar_per_unit / po.budget_fx_rate) - 1
    END AS fx_variance_pct,
    CASE WHEN po.status = 'Open' THEN po.foreign_value * fx.zar_per_unit ELSE 0 END AS open_exposure_zar,
    po.expected_arrival_date - CURRENT_DATE AS days_to_arrival,
    po.settlement_date,
    po.settlement_fx_rate,
    CASE WHEN po.status = 'Received'
        THEN po.foreign_value * po.settlement_fx_rate
    END AS settled_zar_value,
    CASE WHEN po.status = 'Open'
        THEN (po.foreign_value * fx.zar_per_unit) - (po.foreign_value * po.budget_fx_rate)
    END AS unrealized_fx_variance_zar,
    CASE
        WHEN po.status <> 'Open' OR po.budget_fx_rate = 0 THEN NULL
        ELSE (fx.zar_per_unit / po.budget_fx_rate) - 1
    END AS unrealized_fx_variance_pct,
    CASE WHEN po.status = 'Received'
        THEN (po.foreign_value * po.settlement_fx_rate) - (po.foreign_value * po.budget_fx_rate)
    END AS realized_fx_variance_zar,
    CASE
        WHEN po.status <> 'Received' OR po.budget_fx_rate = 0 THEN NULL
        ELSE (po.settlement_fx_rate / po.budget_fx_rate) - 1
    END AS realized_fx_variance_pct
FROM silver.purchase_order po
LEFT JOIN gold.v_latest_fx_rates fx
    ON fx.currency_code = po.currency
