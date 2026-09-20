CREATE TABLE IF NOT EXISTS silver.fx_rate (
    rate_date DATE NOT NULL,
    base_currency CHAR(3) NOT NULL,
    foreign_currency CHAR(3) NOT NULL,
    foreign_per_zar NUMERIC(18,8) NOT NULL CHECK (foreign_per_zar > 0),
    zar_per_unit NUMERIC(18,8) NOT NULL CHECK (zar_per_unit > 0),
    provider_count INTEGER NOT NULL DEFAULT 0 CHECK (provider_count >= 0),
    payload_hash CHAR(64) NOT NULL,
    extracted_at_utc TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (rate_date, base_currency, foreign_currency)
);

CREATE TABLE IF NOT EXISTS silver.macro_indicator (
    country_code CHAR(3) NOT NULL,
    country_name TEXT,
    indicator_code TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    year INTEGER NOT NULL CHECK (year BETWEEN 1900 AND 2200),
    value NUMERIC(24,8) NOT NULL,
    unit TEXT,
    obs_status TEXT,
    extracted_at_utc TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (country_code, indicator_code, year)
);

CREATE TABLE IF NOT EXISTS silver.purchase_order (
    po_id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    order_date DATE NOT NULL,
    expected_arrival_date DATE NOT NULL,
    currency CHAR(3) NOT NULL CHECK (currency IN ('USD','GBP','EUR')),
    foreign_value NUMERIC(18,2) NOT NULL CHECK (foreign_value > 0),
    budget_fx_rate NUMERIC(18,6) NOT NULL CHECK (budget_fx_rate > 0),
    status TEXT NOT NULL CHECK (status IN ('Open','Received')),
    loaded_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (expected_arrival_date >= order_date)
)
