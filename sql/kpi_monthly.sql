-- Monthly origination volume and observed first-EMI default rate, one row
-- per calendar month in the retrospective Aug-Oct 2018 window. Backs the
-- "trend" panel of scripts/build_kpi_pack.py and bi/dashboard.py. This is
-- the raw monthly rollup (no model score required, so it covers all three
-- months); sql/policy_bands.sql is the scored, threshold-based rollup that
-- is only available for the October (test) cohort.
--
-- SAS PROC SQL equivalent:
--   PROC SQL;
--     SELECT d.year, d.month, d.month_name, d.split,
--            COUNT(*) AS loan_count,
--            MEAN(loan_default) AS observed_default_rate,
--            SUM(disbursed_amount) AS disbursed_amount_inr
--     FROM fact_loan AS f
--     INNER JOIN dim_date AS d ON d.date_id = f.disbursal_date_id
--     GROUP BY d.year, d.month, d.month_name, d.split
--     ORDER BY d.year, d.month;
--   QUIT;

SELECT
    d.year,
    d.month,
    d.month_name,
    d.split,
    COUNT(*) AS loan_count,
    AVG(f.loan_default) AS observed_default_rate,
    SUM(f.disbursed_amount) AS disbursed_amount_inr
FROM fact_loan f
JOIN dim_date d ON d.date_id = f.disbursal_date_id
GROUP BY d.year, d.month, d.month_name, d.split
ORDER BY d.year, d.month;
