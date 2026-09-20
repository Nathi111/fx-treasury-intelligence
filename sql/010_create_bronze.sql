CREATE TABLE IF NOT EXISTS bronze.api_payload (
    payload_id BIGSERIAL PRIMARY KEY,
    source_name TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    payload JSONB NOT NULL,
    extracted_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
