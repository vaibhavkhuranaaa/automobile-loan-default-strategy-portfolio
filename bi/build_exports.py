"""Generate the grouped CSV rollups the BI dashboards chart from.

Every export is grouped in SQL before it reaches a file. That is a
performance and portability choice  -  a chart wants 195 rows, not 233,154,
and the Power BI replica needs flat files it can read without a database
driver. It is NOT a data-rights boundary: the dataset is fully authorised
for this use (.project/evidence.yml,
EV-M1-FULL-DATA-DEPLOYMENT-AUTHORITY-20260805), and bi/dashboard.py reads
per-loan detail straight from SQLite for its drill-down.

Consumed by scripts/build_kpi_pack.py, which renders the monthly KPI one-pager
from these rollups. The application does not read them: its reporting views
query SQLite through the API, so a rollup can never drift from what the product
shows.

Run after scripts/build_db.py:
    uv run python scripts/build_db.py
    uv run python bi/build_exports.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "quarantine" / "loans.db"
SUMMARY_PATH = ROOT / "artifacts" / "strategy_summary.json"
EXPORT_DIR = ROOT / "bi" / "exports"

FACT_AGG_SQL = """
-- Aggregate fact export: one row per (month, state, employment type).
-- GROUP BY keeps the export small enough to chart directly; per-loan
-- detail is read from SQLite by the dashboard, not from this file.
-- SAS PROC SQL equivalent:
--   PROC SQL;
--     SELECT d.year, d.month, d.month_name, d.split, f.state_id, e.employment_type,
--            COUNT(*), MEAN(loan_default), SUM(disbursed_amount), MEAN(ltv)
--     FROM fact_loan AS f
--     INNER JOIN dim_date AS d ON d.date_id = f.disbursal_date_id
--     INNER JOIN dim_employment AS e ON e.employment_type_id = f.employment_type_id
--     GROUP BY d.year, d.month, d.month_name, d.split, f.state_id, e.employment_type;
--   QUIT;
SELECT
    d.year,
    d.month,
    d.month_name,
    d.split,
    f.state_id,
    e.employment_type,
    COUNT(*) AS loan_count,
    AVG(f.loan_default) AS observed_default_rate,
    SUM(f.disbursed_amount) AS disbursed_amount_inr,
    AVG(f.ltv) AS average_ltv
FROM fact_loan f
JOIN dim_date d ON d.date_id = f.disbursal_date_id
JOIN dim_employment e ON e.employment_type_id = f.employment_type_id
GROUP BY d.year, d.month, d.month_name, d.split, f.state_id, e.employment_type
ORDER BY d.month, f.state_id, e.employment_type;
"""


def export_dimension_tables(conn: sqlite3.Connection) -> None:
    pd.read_sql_query("SELECT * FROM dim_state ORDER BY state_id", conn).to_csv(EXPORT_DIR / "dim_state.csv", index=False)
    pd.read_sql_query("SELECT * FROM dim_employment ORDER BY employment_type_id", conn).to_csv(EXPORT_DIR / "dim_employment.csv", index=False)
    pd.read_sql_query("SELECT * FROM dim_manufacturer ORDER BY manufacturer_id", conn).to_csv(EXPORT_DIR / "dim_manufacturer.csv", index=False)
    pd.read_sql_query("SELECT * FROM dim_date ORDER BY date_id", conn).to_csv(EXPORT_DIR / "dim_date.csv", index=False)


def export_fact_agg(conn: sqlite3.Connection) -> None:
    frame = pd.read_sql_query(FACT_AGG_SQL, conn)
    frame.to_csv(EXPORT_DIR / "fact_loan_agg.csv", index=False)


def export_policy_bands() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    rows = []
    for policy in summary["policies"]:
        rows.append({
            "band": policy["name"],
            "risk_threshold": policy["risk_threshold"],
            "approval_rate": policy["approval_rate"],
            "manual_review_rate": policy["manual_review_rate"],
            "observed_default_rate": policy["observed_default_rate"],
            "approved_count": policy["approved_count"],
            "review_count": policy["review_count"],
            "approved_amount_inr": policy["approved_amount_inr"],
            "estimated_net_contribution_inr": policy["assumption_led_contribution"],
        })
    pd.DataFrame(rows).to_csv(EXPORT_DIR / "policy_bands.csv", index=False)


def main() -> None:
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Missing SQLite store: {DB_PATH}. Run `uv run python scripts/build_db.py` first.")
    if not SUMMARY_PATH.is_file():
        raise FileNotFoundError(f"Missing aggregate evidence: {SUMMARY_PATH}. Run `uv run python scripts/run_evaluation.py` first.")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        export_dimension_tables(conn)
        export_fact_agg(conn)
    finally:
        conn.close()
    export_policy_bands()
    for path in sorted(EXPORT_DIR.glob("*.csv")):
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
