-- Policy-band aggregation over the scored October 2018 test cohort:
-- approval rate, manual-review rate, observed first-EMI default rate, and
-- the approved/defaulted disbursed amount a policy owner needs to compute
-- estimated net contribution (contribution-rate and loss-severity
-- assumptions are applied in Python/Excel, not in this query, so the
-- assumptions stay visibly editable rather than baked into SQL).
--
-- This is the SQL-expressed equivalent of the policy() function in
-- scripts/run_evaluation.py: approved = risk_score < threshold; review =
-- within +/- review_band of threshold.
--
-- Eligibility is the October holdout, selected explicitly through
-- dim_date.split. Every vintage now carries a risk_score, so a bare
-- "risk_score IS NOT NULL" would silently widen this query to all 233,154
-- rows and mix in-sample August and September scores into a published
-- policy figure. The split predicate is the guard.
--
-- SAS PROC SQL equivalent:
--   PROC SQL;
--     SELECT COUNT(*) AS approved_count,
--            MEAN(CASE WHEN loan_default THEN 1 ELSE 0 END) AS observed_default_rate,
--            SUM(disbursed_amount) AS approved_amount_inr
--     FROM fact_loan f INNER JOIN dim_date d ON d.date_id = f.disbursal_date_id
--     WHERE d.split = 'test' AND f.risk_score < &threshold;
--   QUIT;
-- (approval/review rates and the review-band count are computed the same
-- way, filtered against &threshold and &review_band macro variables.)

SELECT
    :band_name AS band,
    :threshold AS risk_threshold,
    COUNT(*) AS scored_count,
    COUNT(*) FILTER (WHERE risk_score < :threshold) AS approved_count,
    COUNT(*) FILTER (
        WHERE risk_score >= (:threshold - :review_band)
          AND risk_score <  (:threshold + :review_band)
    ) AS review_count,
    AVG(loan_default) FILTER (WHERE risk_score < :threshold) AS observed_default_rate,
    SUM(disbursed_amount) FILTER (WHERE risk_score < :threshold) AS approved_amount_inr,
    SUM(disbursed_amount * loan_default) FILTER (WHERE risk_score < :threshold) AS defaulted_amount_inr,
    CAST(COUNT(*) FILTER (WHERE risk_score < :threshold) AS REAL) / COUNT(*) AS approval_rate,
    CAST(
        COUNT(*) FILTER (
            WHERE risk_score >= (:threshold - :review_band)
              AND risk_score <  (:threshold + :review_band)
        ) AS REAL
    ) / COUNT(*) AS manual_review_rate
FROM fact_loan
JOIN dim_date ON dim_date.date_id = fact_loan.disbursal_date_id
WHERE dim_date.split = 'test'
  AND risk_score IS NOT NULL;
