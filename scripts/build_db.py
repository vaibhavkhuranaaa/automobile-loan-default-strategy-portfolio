"""Load the authorized vehicle-loan CSV into a git-ignored SQLite star schema.

Builds data/quarantine/loans.db (never committed; see .gitignore) from
data/quarantine/train.csv, applying the star schema in sql/schema.sql:
fact_loan plus dim_state, dim_employment, dim_manufacturer, and dim_date.

The fact table's risk_score column reuses the exact calibrated-challenger
scores from scripts/run_evaluation.py (via its shared load_and_prepare /
fit_and_select functions), so the SQL policy-band queries in
sql/policy_bands.sql operate on the same evidence already verified in
artifacts/strategy_summary.json rather than a second, drifting model.

All three vintages carry a score. October is the clean holdout and is the
only one any policy or performance claim may rest on; August is the fitting
sample and September fitted the isotonic calibrator, so their scores are
in-sample and optimistic. They exist so the portfolio views can show how the
score distribution moves month to month. dim_date.split is the provenance
key, and sql/policy_bands.sql still restricts itself to October.

SAS PROC SQL equivalent: this script is the transferable equivalent of a
SAS DATA step + PROC SQL INSERT/APPEND that populates a permanent library
mart from a raw extract. No SAS is used or claimed; the comment documents
transferability only.
"""

from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from run_evaluation import fit_and_select, load_and_prepare

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "quarantine" / "loans.db"
SCHEMA_SQL = ROOT / "sql" / "schema.sql"

MONTH_SPLIT = {8: "train", 9: "calibration", 10: "test"}


def month_split(month: int) -> str:
    return MONTH_SPLIT.get(int(month), "unknown")


def record_refs(size: int) -> list[str]:
    """Generate opaque references stored only in the private SQLite release asset."""
    refs: list[str] = []
    seen: set[str] = set()
    while len(refs) < size:
        ref = secrets.token_hex(6).upper()
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


def main() -> None:
    data, features, train, calibrate, test = load_and_prepare()
    selected_name, selected_p, _baseline_test, _challenger_test, selected_model = fit_and_select(features, train, calibrate, test)
    print(f"Reused evaluated model for risk_score: {selected_name}")

    frame = data.copy()
    frame["EMPLOYMENT_TYPE"] = frame["EMPLOYMENT_TYPE"].fillna("Missing")
    frame["RISK_SCORE"] = np.nan
    frame.loc[test.index, "RISK_SCORE"] = selected_p
    # August and September are scored by the same fitted estimator so the
    # portfolio views can show a score distribution per vintage. Only October is
    # a clean holdout: August is the fitting sample and September fitted the
    # isotonic calibrator, so both are optimistic by construction. dim_date.split
    # carries that provenance and every surface that reads these rows states it.
    for split_frame in (train, calibrate):
        frame.loc[split_frame.index, "RISK_SCORE"] = selected_model.predict_proba(split_frame[features])[:, 1]

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))

        dim_date = (
            frame[["DISBURSAL_DATE"]]
            .drop_duplicates()
            .assign(
                date_id=lambda d: d["DISBURSAL_DATE"].dt.strftime("%Y-%m-%d"),
                year=lambda d: d["DISBURSAL_DATE"].dt.year,
                month=lambda d: d["DISBURSAL_DATE"].dt.month,
                month_name=lambda d: d["DISBURSAL_DATE"].dt.strftime("%B"),
                split=lambda d: d["DISBURSAL_DATE"].dt.month.map(month_split),
            )[["date_id", "year", "month", "month_name", "split"]]
        )
        dim_date.to_sql("dim_date", conn, if_exists="append", index=False)

        dim_state = pd.DataFrame({"state_id": sorted(frame["STATE_ID"].dropna().unique().astype(int))})
        dim_state.to_sql("dim_state", conn, if_exists="append", index=False)

        dim_employment = pd.DataFrame({"employment_type": sorted(frame["EMPLOYMENT_TYPE"].unique())})
        dim_employment.insert(0, "employment_type_id", range(1, len(dim_employment) + 1))
        dim_employment.to_sql("dim_employment", conn, if_exists="append", index=False)
        employment_lookup = dict(zip(dim_employment["employment_type"], dim_employment["employment_type_id"]))

        dim_manufacturer = pd.DataFrame({"manufacturer_id": sorted(frame["MANUFACTURER_ID"].dropna().unique().astype(int))})
        dim_manufacturer.to_sql("dim_manufacturer", conn, if_exists="append", index=False)

        fact = pd.DataFrame({
            "loan_id": frame["UNIQUEID"].astype(int),
            "public_ref": record_refs(len(frame)),
            "disbursal_date_id": frame["DISBURSAL_DATE"].dt.strftime("%Y-%m-%d"),
            "state_id": frame["STATE_ID"].astype("Int64"),
            "branch_id": frame["BRANCH_ID"].astype("Int64") if "BRANCH_ID" in frame.columns else None,
            "manufacturer_id": frame["MANUFACTURER_ID"].astype("Int64"),
            "employment_type_id": frame["EMPLOYMENT_TYPE"].map(employment_lookup),
            "disbursed_amount": frame["DISBURSED_AMOUNT"].astype(float),
            "asset_cost": frame["ASSET_COST"].astype(float),
            "ltv": frame["LTV"].astype(float),
            "perform_cns_score": frame["PERFORM_CNS_SCORE"].astype(float),
            "loan_default": frame["LOAN_DEFAULT"].astype(int),
            "risk_score": frame["RISK_SCORE"].astype(float),
        })
        fact.to_sql("fact_loan", conn, if_exists="append", index=False)

        conn.commit()
        counts = {
            name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in ("fact_loan", "dim_state", "dim_employment", "dim_manufacturer", "dim_date")
        }
        scored = dict(conn.execute(
            "SELECT d.split, COUNT(*) FROM fact_loan f JOIN dim_date d ON d.date_id = f.disbursal_date_id"
            " WHERE f.risk_score IS NOT NULL GROUP BY d.split"
        ).fetchall())
    finally:
        conn.close()
    print(f"Wrote {DB_PATH.relative_to(ROOT)}: {counts}; scored rows by split: {scored}")


if __name__ == "__main__":
    main()
