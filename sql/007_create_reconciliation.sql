CREATE TABLE IF NOT EXISTS ops.etl_reconciliation (
    reconciliation_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES ops.etl_run(run_id) ON DELETE CASCADE,
    dataset_name TEXT NOT NULL,
    extracted_record_count INTEGER NOT NULL CHECK (extracted_record_count >= 0),
    bronze_payload_count INTEGER NOT NULL CHECK (bronze_payload_count >= 0),
    transformed_record_count INTEGER NOT NULL CHECK (transformed_record_count >= 0),
    filtered_record_count INTEGER NOT NULL CHECK (filtered_record_count >= 0),
    deduplicated_record_count INTEGER NOT NULL CHECK (deduplicated_record_count >= 0),
    loaded_record_count INTEGER NOT NULL CHECK (loaded_record_count >= 0),
    unexplained_variance_count INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'FAIL')),
    details TEXT,
    checked_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_etl_reconciliation_run_id
    ON ops.etl_reconciliation (run_id);

CREATE INDEX IF NOT EXISTS idx_etl_reconciliation_status
    ON ops.etl_reconciliation (status, checked_at_utc DESC);
