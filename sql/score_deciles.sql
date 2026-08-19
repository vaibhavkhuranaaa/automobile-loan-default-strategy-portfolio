-- Score-decile distribution for the risk-analytics views: the standard
-- credit-risk artifact behind a gains curve, a lift table, a KS statistic, and
-- a calibration plot. One row per decile of predicted first-EMI risk, ordered
-- from the safest decile to the riskiest.
--
-- The caller supplies :split. Only 'test' (October) is a clean holdout; August
-- fitted the model and September fitted the isotonic calibrator, so their
-- scores are in-sample. Every surface that requests a non-test split says so.
--
-- Cumulative capture, lift and KS are derived from these rows in Python rather
-- than in SQL: they are running totals over ten rows, and expressing them as
-- correlated subqueries here would obscure a simple calculation.
--
-- SAS PROC SQL equivalent:
--   PROC RANK DATA=fact_loan GROUPS=10 OUT=ranked;
--     VAR risk_score; RANKS decile;
--   RUN;
--   PROC SQL;
--     SELECT decile, COUNT(*) AS loans, MEAN(risk_score) AS mean_predicted,
--            MEAN(loan_default) AS observed_default_rate
--     FROM ranked GROUP BY decile;
--   QUIT;

WITH scored AS (
    SELECT
        f.risk_score,
        f.loan_default,
        f.disbursed_amount,
        NTILE(10) OVER (ORDER BY f.risk_score) AS decile
    FROM fact_loan f
    JOIN dim_date d ON d.date_id = f.disbursal_date_id
    WHERE d.split = :split
      AND f.risk_score IS NOT NULL
)
SELECT
    decile,
    COUNT(*)                        AS loans,
    AVG(risk_score)                 AS mean_predicted,
    MIN(risk_score)                 AS min_predicted,
    MAX(risk_score)                 AS max_predicted,
    SUM(loan_default)               AS defaults,
    AVG(loan_default)               AS observed_default_rate,
    SUM(disbursed_amount)           AS exposure_inr
FROM scored
GROUP BY decile
ORDER BY decile;
