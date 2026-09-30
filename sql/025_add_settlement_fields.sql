ALTER TABLE silver.purchase_order
    ADD COLUMN IF NOT EXISTS settlement_date DATE;

ALTER TABLE silver.purchase_order
    ADD COLUMN IF NOT EXISTS settlement_fx_rate NUMERIC(18,6);

ALTER TABLE silver.purchase_order
    DROP CONSTRAINT IF EXISTS purchase_order_settlement_consistency;

ALTER TABLE silver.purchase_order
    ADD CONSTRAINT purchase_order_settlement_consistency CHECK (
        (status = 'Open' AND settlement_date IS NULL AND settlement_fx_rate IS NULL)
        OR
        (
            status = 'Received'
            AND settlement_date IS NOT NULL
            AND settlement_fx_rate IS NOT NULL
            AND settlement_fx_rate > 0
            AND settlement_date >= order_date
        )
    ) NOT VALID;
