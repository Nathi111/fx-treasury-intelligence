CREATE TABLE IF NOT EXISTS ops.etl_run (
    run_id BIGSERIAL PRIMARY KEY,
    started_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at_utc TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    fx_rows_processed INTEGER NOT NULL DEFAULT 0
        CHECK (fx_rows_processed >= 0),
    macro_rows_processed INTEGER NOT NULL DEFAULT 0
        CHECK (macro_rows_processed >= 0),
    po_rows_processed INTEGER NOT NULL DEFAULT 0
        CHECK (po_rows_processed >= 0),
    error_message TEXT,
    CHECK (
        (status = 'RUNNING' AND completed_at_utc IS NULL)
        OR
        (status IN ('SUCCESS', 'FAILED') AND completed_at_utc IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_etl_run_started_at_utc
    ON ops.etl_run (started_at_utc DESC);
