CREATE OR REPLACE VIEW gold.v_data_quality_failures AS
SELECT 'fx_non_positive_rate' AS test_name, COUNT(*)::BIGINT AS failure_count
FROM silver.fx_rate
WHERE zar_per_unit <= 0 OR foreign_per_zar <= 0
HAVING COUNT(*) > 0

UNION ALL

SELECT 'fx_duplicate_business_key', COUNT(*)::BIGINT
FROM (
    SELECT rate_date, base_currency, foreign_currency
    FROM silver.fx_rate
    GROUP BY 1,2,3
    HAVING COUNT(*) > 1
) d
HAVING COUNT(*) > 0

UNION ALL

SELECT 'macro_duplicate_business_key', COUNT(*)::BIGINT
FROM (
    SELECT country_code, indicator_code, year
    FROM silver.macro_indicator
    GROUP BY 1,2,3
    HAVING COUNT(*) > 1
) d
HAVING COUNT(*) > 0

UNION ALL

SELECT 'purchase_order_duplicate_id', COUNT(*)::BIGINT
FROM (
    SELECT po_id
    FROM silver.purchase_order
    GROUP BY po_id
    HAVING COUNT(*) > 1
) d
HAVING COUNT(*) > 0

UNION ALL

SELECT 'open_po_missing_fx_rate', COUNT(*)::BIGINT
FROM gold.fact_purchase_order_exposure
WHERE status = 'Open' AND current_fx_rate IS NULL
HAVING COUNT(*) > 0

UNION ALL

SELECT 'received_po_missing_settlement', COUNT(*)::BIGINT
FROM silver.purchase_order
WHERE status = 'Received'
  AND (settlement_date IS NULL OR settlement_fx_rate IS NULL)
HAVING COUNT(*) > 0

UNION ALL

SELECT 'open_po_has_settlement_data', COUNT(*)::BIGINT
FROM silver.purchase_order
WHERE status = 'Open'
  AND (settlement_date IS NOT NULL OR settlement_fx_rate IS NOT NULL)
HAVING COUNT(*) > 0

UNION ALL

SELECT 'received_po_invalid_settlement_date', COUNT(*)::BIGINT
FROM silver.purchase_order
WHERE status = 'Received'
  AND settlement_date < order_date
HAVING COUNT(*) > 0

UNION ALL

SELECT 'received_po_non_positive_settlement_rate', COUNT(*)::BIGINT
FROM silver.purchase_order
WHERE status = 'Received'
  AND settlement_fx_rate <= 0
HAVING COUNT(*) > 0
