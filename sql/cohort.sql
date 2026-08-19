-- Cohort summary: count, observed first-EMI default rate, disbursed amount,
-- average LTV, and average bureau score for loans matching an analyst's
-- optional filters (state, employment type, LTV range).
-- Backs GET /api/cohort in api/main.py. Named parameters (:state_id, etc.)
-- are bound conditionally; a NULL-bound parameter disables that filter.
--
-- SAS PROC SQL equivalent:
--   PROC SQL;
--     SELECT COUNT(*), MEAN(loan_default), SUM(disbursed_amount),
--            MEAN(ltv), MEAN(perform_cns_score)
--     FROM fact_loan AS f
--     INNER JOIN dim_employment AS e
--       ON e.employment_type_id = f.employment_type_id
--     WHERE (&state_id IS NULL OR f.state_id = &state_id)
--       AND (&employment_type IS NULL OR e.employment_type = "&employment_type")
--       AND (&min_ltv IS NULL OR f.ltv >= &min_ltv)
--       AND (&max_ltv IS NULL OR f.ltv <= &max_ltv);
--   QUIT;

SELECT
    COUNT(*) AS count,
    AVG(f.loan_default) AS default_rate,
    SUM(f.disbursed_amount) AS disbursed_amount_inr,
    AVG(f.ltv) AS average_ltv,
    AVG(f.perform_cns_score) AS average_bureau_score
FROM fact_loan f
JOIN dim_employment e ON e.employment_type_id = f.employment_type_id
WHERE (:state_id IS NULL OR f.state_id = :state_id)
  AND (:employment_type IS NULL OR e.employment_type = :employment_type)
  AND (:min_ltv IS NULL OR f.ltv >= :min_ltv)
  AND (:max_ltv IS NULL OR f.ltv <= :max_ltv);
