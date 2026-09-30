CREATE TABLE IF NOT EXISTS ops.data_freshness_check (
    check_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES ops.etl_run(run_id) ON DELETE CASCADE,
    dataset_name TEXT NOT NULL,
    latest_available_date DATE,
    latest_available_year INTEGER,
    lag_value INTEGER,
    tolerance_value INTEGER NOT NULL CHECK (tolerance_value >= 0),
    lag_unit TEXT NOT NULL CHECK (lag_unit IN ('business_days', 'years')),
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    details TEXT,
    checked_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_freshness_check_run_id
    ON ops.data_freshness_check (run_id);

CREATE INDEX IF NOT EXISTS idx_data_freshness_check_status
    ON ops.data_freshness_check (status, checked_at_utc DESC);
