-- Observed first-EMI default by business segment, for every dimension the risk
-- views offer, in one pass.
--
-- This query exists because the opaque source identifiers are not analysis
-- dimensions. state_id, branch_id and manufacturer_id are anonymised integers
-- with no published lookup, so ranking a chart by them tells a reader nothing.
-- The dimensions below are derived from fields that do carry business meaning:
-- loan-to-value, bureau coverage and score, employment, and ticket size. The
-- identifiers remain available as drill keys and as concentration rankings,
-- which is what they can honestly support.
--
-- Bands follow the observed distribution across all 233,154 loans rather than
-- round numbers: LTV runs p25=69 / p50=77 / p75=84, ticket size p25=47k /
-- p50=54k / p75=60k, and bureau score p25=479 / p50=679 / p75=738. Exactly
-- 50.2% of loans carry no bureau history at all, which is the single largest
-- segment in the book and the reason "no bureau history" is its own band
-- rather than a zero folded into the bottom of the score range.
--
-- :split selects the vintage. Passing 'all' covers the full book.
--
-- SAS PROC SQL equivalent:
--   PROC SQL;
--     SELECT CASE WHEN ltv < 60 THEN '<60' ... END AS segment,
--            COUNT(*) AS loans, MEAN(loan_default) AS observed_default_rate,
--            SUM(disbursed_amount) AS exposure_inr
--     FROM fact_loan GROUP BY segment;
--   QUIT;

WITH scoped AS (
    SELECT f.*, e.employment_type
    FROM fact_loan f
    JOIN dim_date d ON d.date_id = f.disbursal_date_id
    JOIN dim_employment e ON e.employment_type_id = f.employment_type_id
    WHERE (:split = 'all' OR d.split = :split)
),
labelled AS (
    SELECT 'ltv' AS dimension,
           CASE
               WHEN ltv < 60 THEN 1 WHEN ltv < 70 THEN 2 WHEN ltv < 80 THEN 3
               WHEN ltv < 85 THEN 4 ELSE 5
           END AS sort_order,
           CASE
               WHEN ltv < 60 THEN 'Under 60%'      WHEN ltv < 70 THEN '60 to 70%'
               WHEN ltv < 80 THEN '70 to 80%'      WHEN ltv < 85 THEN '80 to 85%'
               ELSE '85% and above'
           END AS segment,
           loan_default, disbursed_amount
    FROM scoped
    UNION ALL
    SELECT 'bureau',
           CASE
               WHEN perform_cns_score IS NULL THEN 1 WHEN perform_cns_score < 500 THEN 2
               WHEN perform_cns_score < 650 THEN 3  WHEN perform_cns_score < 725 THEN 4
               ELSE 5
           END,
           CASE
               WHEN perform_cns_score IS NULL THEN 'No bureau history'
               WHEN perform_cns_score < 500 THEN 'Under 500'
               WHEN perform_cns_score < 650 THEN '500 to 650'
               WHEN perform_cns_score < 725 THEN '650 to 725'
               ELSE '725 and above'
           END,
           loan_default, disbursed_amount
    FROM scoped
    UNION ALL
    SELECT 'employment',
           CASE employment_type WHEN 'Salaried' THEN 1 WHEN 'Self employed' THEN 2 ELSE 3 END,
           CASE employment_type WHEN 'Missing' THEN 'Not recorded' ELSE employment_type END,
           loan_default, disbursed_amount
    FROM scoped
    UNION ALL
    SELECT 'ticket',
           CASE
               WHEN disbursed_amount < 40000 THEN 1 WHEN disbursed_amount < 50000 THEN 2
               WHEN disbursed_amount < 60000 THEN 3 WHEN disbursed_amount < 75000 THEN 4
               ELSE 5
           END,
           CASE
               WHEN disbursed_amount < 40000 THEN 'Under 40k'   WHEN disbursed_amount < 50000 THEN '40k to 50k'
               WHEN disbursed_amount < 60000 THEN '50k to 60k'  WHEN disbursed_amount < 75000 THEN '60k to 75k'
               ELSE '75k and above'
           END,
           loan_default, disbursed_amount
    FROM scoped
)
SELECT
    dimension,
    segment,
    sort_order,
    COUNT(*)              AS loans,
    SUM(loan_default)     AS defaults,
    AVG(loan_default)     AS observed_default_rate,
    SUM(disbursed_amount) AS exposure_inr
FROM labelled
GROUP BY dimension, segment, sort_order
ORDER BY dimension, sort_order;
