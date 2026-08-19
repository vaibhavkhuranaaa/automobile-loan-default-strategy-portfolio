"""Risk-analytics endpoints behind the portfolio, risk, monitoring and loan views.

Everything here reads data/quarantine/loans.db through parameterized SQL. The
heavier analytical queries live in sql/ alongside the policy-band query so the
SQL layer stays inspectable; the running totals derived from them (cumulative
capture, lift, KS, PSI) are computed here because they are arithmetic over ten
or twenty rows and gain nothing from being expressed as correlated subqueries.

Two rules govern every response:

Published figures are never recomputed. AUROC, PR-AUC, Brier and ECE come from
artifacts/strategy_summary.json, which scripts/run_evaluation.py wrote from the
fitted model with the same rounding the case study and portfolio manifest
quote. Recomputing them here from stored scores would eventually disagree with
the record, and the disagreement would be silent.

Vintage provenance travels with the data. Only October is a clean holdout.
August fitted the model and September fitted the isotonic calibrator, so any
score-based figure on those months is optimistic. Endpoints that accept a split
return the provenance alongside the numbers rather than leaving the caller to
remember it.
"""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "quarantine" / "loans.db"
SUMMARY_PATH = ROOT / "artifacts" / "strategy_summary.json"

DECILE_SQL = (ROOT / "sql" / "score_deciles.sql").read_text(encoding="utf-8")
SEGMENT_SQL = (ROOT / "sql" / "segment_risk.sql").read_text(encoding="utf-8")

# The straddle half-width that defines a manual-review referral, identical to
# the review_band in scripts/run_evaluation.py's policy(). Changing it here
# without changing it there would put the inspector's per-loan verdict out of
# step with the published band totals.
REVIEW_BAND = 0.025

SPLIT_PROVENANCE = {
    "test": {
        "month": "October 2018",
        "clean": True,
        "note": "Held-out month. The model never saw it, so its figures carry the evaluation.",
    },
    "calibration": {
        "month": "September 2018",
        "clean": False,
        "note": "Fitted the isotonic calibrator, so its scores are in-sample and read better than they would on unseen loans.",
    },
    "train": {
        "month": "August 2018",
        "clean": False,
        "note": "Fitted the model, so its scores are in-sample and read better than they would on unseen loans.",
    },
    "all": {
        "month": "August to October 2018",
        "clean": False,
        "note": "Mixes the held-out month with the two the model was fitted on.",
    },
}

DIMENSION_LABELS = {
    "ltv": "Loan to value",
    "bureau": "Bureau score",
    "employment": "Employment",
    "ticket": "Ticket size",
}

CONCENTRATION_DIMENSIONS = {
    "branch": ("branch_id", "Branch"),
    "state": ("state_id", "State"),
    "manufacturer": ("manufacturer_id", "Manufacturer"),
}

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def connection() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail="The loan store is not built. Run `uv run python scripts/build_db.py`.",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _summary() -> dict:
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def bands() -> list[dict[str, object]]:
    """The three evaluated cut-offs, read from the published evidence."""
    return [
        {
            "key": str(policy["name"]),
            "label": str(policy["name"]).title(),
            "threshold": float(policy["risk_threshold"]),
        }
        for policy in _summary()["policies"]
    ]


def provenance(split: str) -> dict[str, object]:
    return {"split": split, **SPLIT_PROVENANCE[split]}


def _rate(numerator: float, denominator: float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


@router.get("/overview")
def overview() -> dict[str, object]:
    """Portfolio headline plus one row per vintage.

    Volume, exposure, outcome and book mix are measured directly and involve no
    model, so they are reported for all three months without qualification. The
    mean predicted risk column is the one figure that carries provenance.
    """
    summary = _summary()
    conn = connection()
    try:
        total = dict(conn.execute(
            """
            SELECT COUNT(*) AS loans,
                   SUM(disbursed_amount) AS exposure_inr,
                   AVG(loan_default) AS observed_default_rate,
                   AVG(ltv) AS average_ltv,
                   AVG(perform_cns_score IS NULL) AS thin_file_share,
                   SUM(disbursed_amount * loan_default) AS defaulted_exposure_inr
            FROM fact_loan
            """
        ).fetchone())
        vintages = [dict(row) for row in conn.execute(
            """
            SELECT d.split,
                   d.month_name AS month,
                   COUNT(*) AS loans,
                   SUM(f.disbursed_amount) AS exposure_inr,
                   AVG(f.loan_default) AS observed_default_rate,
                   AVG(f.ltv) AS average_ltv,
                   AVG(f.perform_cns_score IS NULL) AS thin_file_share,
                   AVG(f.risk_score) AS mean_predicted
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            GROUP BY d.split, d.month_name
            ORDER BY MIN(d.month)
            """
        )]
    finally:
        conn.close()

    model = summary["models"][summary["selected_model"]]
    return {
        "portfolio": {
            "loans": int(total["loans"]),
            "exposureInr": float(total["exposure_inr"]),
            "defaultedExposureInr": float(total["defaulted_exposure_inr"]),
            "observedDefaultRate": float(total["observed_default_rate"]),
            "averageLtv": float(total["average_ltv"]),
            "thinFileShare": float(total["thin_file_share"]),
        },
        "vintages": [
            {
                "split": row["split"],
                "month": row["month"],
                "loans": int(row["loans"]),
                "exposureInr": float(row["exposure_inr"]),
                "observedDefaultRate": float(row["observed_default_rate"]),
                "averageLtv": float(row["average_ltv"]),
                "thinFileShare": float(row["thin_file_share"]),
                "meanPredicted": float(row["mean_predicted"]),
                "clean": bool(SPLIT_PROVENANCE[row["split"]]["clean"]),
            }
            for row in vintages
        ],
        # Quoted from the published artifact, never recomputed here.
        "model": {
            "name": "Calibrated challenger",
            "auroc": float(model["auroc"]),
            "prAuc": float(model["pr_auc"]),
            "brier": float(model["brier_score"]),
            "ece": float(model["ece_decile"]),
            "baselineAuroc": float(summary["models"]["logistic_baseline"]["auroc"]),
            "baselineBrier": float(summary["models"]["logistic_baseline"]["brier_score"]),
            "featureCount": int(summary["feature_count"]),
        },
        "evaluatedOn": provenance("test"),
    }


@router.get("/deciles")
def deciles(split: str = Query(default="test", pattern="^(test|calibration|train)$")) -> dict[str, object]:
    """Score deciles with the running totals a lift table, gains curve and KS need.

    Decile 1 is the safest tenth of the book by predicted risk, decile 10 the
    riskiest. Capture is read from the risky end down, which is the direction a
    strategy actually works in: how much of the book's default you remove by
    declining the worst N%.
    """
    conn = connection()
    try:
        rows = [dict(row) for row in conn.execute(DECILE_SQL, {"split": split})]
    finally:
        conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No scored loans in split '{split}'.")

    total_loans = sum(int(r["loans"]) for r in rows)
    total_defaults = sum(int(r["defaults"]) for r in rows)
    total_goods = total_loans - total_defaults
    base_rate = _rate(total_defaults, total_loans)

    # Walk from the riskiest decile down so cumulative capture answers "decline
    # the worst N% of the book and this much of its default goes with them".
    cumulative: list[dict[str, object]] = []
    seen_loans = seen_defaults = 0
    for row in reversed(rows):
        seen_loans += int(row["loans"])
        seen_defaults += int(row["defaults"])
        cumulative.append({
            "decile": int(row["decile"]),
            "cumulativeLoanShare": _rate(seen_loans, total_loans),
            "cumulativeDefaultCapture": _rate(seen_defaults, total_defaults),
        })
    capture_by_decile = {int(item["decile"]): item for item in cumulative}

    # KS compares the two cumulative distributions read from the safe end up,
    # which is the conventional orientation for the statistic.
    ks_loans = ks_defaults = ks_goods = 0
    ks_value = 0.0
    ks_decile = 1
    table = []
    for row in rows:
        decile = int(row["decile"])
        loans = int(row["loans"])
        defaults = int(row["defaults"])
        ks_loans += loans
        ks_defaults += defaults
        ks_goods += loans - defaults
        separation = abs(_rate(ks_defaults, total_defaults) - _rate(ks_goods, total_goods))
        if separation > ks_value:
            ks_value, ks_decile = separation, decile
        observed = float(row["observed_default_rate"])
        table.append({
            "decile": decile,
            "loans": loans,
            "defaults": defaults,
            "meanPredicted": float(row["mean_predicted"]),
            "minPredicted": float(row["min_predicted"]),
            "maxPredicted": float(row["max_predicted"]),
            "observedDefaultRate": observed,
            "exposureInr": float(row["exposure_inr"]),
            # Lift above 1 means this decile defaults more than the book average.
            "lift": _rate(observed, base_rate),
            "cumulativeLoanShare": float(capture_by_decile[decile]["cumulativeLoanShare"]),
            "cumulativeDefaultCapture": float(capture_by_decile[decile]["cumulativeDefaultCapture"]),
        })

    return {
        "provenance": provenance(split),
        "loans": total_loans,
        "defaults": total_defaults,
        "baseDefaultRate": base_rate,
        "ks": {"value": ks_value, "decile": ks_decile},
        "deciles": table,
    }


@router.get("/segments")
def segments(split: str = Query(default="test", pattern="^(test|calibration|train|all)$")) -> dict[str, object]:
    """Observed default by business segment, indexed against the book average.

    An index of 100 is the portfolio rate. 130 means that segment defaults 30%
    more often than the book, which is the form a policy reader can act on
    without converting percentages in their head.
    """
    conn = connection()
    try:
        rows = [dict(row) for row in conn.execute(SEGMENT_SQL, {"split": split})]
        overall = conn.execute(
            """
            SELECT AVG(f.loan_default) AS rate
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            WHERE (:split = 'all' OR d.split = :split)
            """,
            {"split": split},
        ).fetchone()["rate"]
    finally:
        conn.close()

    base_rate = float(overall or 0.0)
    grouped: dict[str, list[dict[str, object]]] = {}
    totals: dict[str, dict[str, float]] = {}
    for row in rows:
        dimension = str(row["dimension"])
        bucket = totals.setdefault(dimension, {"loans": 0.0, "exposure": 0.0})
        bucket["loans"] += int(row["loans"])
        bucket["exposure"] += float(row["exposure_inr"])
    for row in rows:
        dimension = str(row["dimension"])
        observed = float(row["observed_default_rate"])
        grouped.setdefault(dimension, []).append({
            "segment": str(row["segment"]),
            "loans": int(row["loans"]),
            "defaults": int(row["defaults"]),
            "observedDefaultRate": observed,
            "exposureInr": float(row["exposure_inr"]),
            "loanShare": _rate(int(row["loans"]), totals[dimension]["loans"]),
            "exposureShare": _rate(float(row["exposure_inr"]), totals[dimension]["exposure"]),
            "riskIndex": _rate(observed, base_rate) * 100,
        })

    return {
        "provenance": provenance(split),
        "baseDefaultRate": base_rate,
        "dimensions": [
            {"key": key, "label": DIMENSION_LABELS[key], "segments": grouped[key]}
            for key in DIMENSION_LABELS
            if key in grouped
        ],
    }


@router.get("/concentration")
def concentration(
    dimension: str = Query(default="branch", pattern="^(branch|state|manufacturer)$"),
    split: str = Query(default="all", pattern="^(test|calibration|train|all)$"),
    limit: int = Query(default=12, ge=3, le=30),
) -> dict[str, object]:
    """Where exposure piles up, ranked, with each unit's default rate beside it.

    The source publishes no lookup for these identifiers, so a chart with them
    along the axis would be a row of meaningless integers. Ranked by exposure
    they answer a question that does not need the real name: how concentrated is
    the book, and do the largest units carry more default than the average.
    """
    column, noun = CONCENTRATION_DIMENSIONS[dimension]
    conn = connection()
    try:
        rows = [dict(row) for row in conn.execute(
            f"""
            SELECT f.{column} AS unit,
                   COUNT(*) AS loans,
                   SUM(f.disbursed_amount) AS exposure_inr,
                   AVG(f.loan_default) AS observed_default_rate
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            WHERE (:split = 'all' OR d.split = :split) AND f.{column} IS NOT NULL
            GROUP BY f.{column}
            ORDER BY exposure_inr DESC
            """,
            {"split": split},
        )]
        base_rate = float(conn.execute(
            """
            SELECT AVG(f.loan_default)
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            WHERE (:split = 'all' OR d.split = :split)
            """,
            {"split": split},
        ).fetchone()[0] or 0.0)
    finally:
        conn.close()

    total_exposure = sum(float(r["exposure_inr"]) for r in rows)
    total_loans = sum(int(r["loans"]) for r in rows)
    ranked = []
    running = 0.0
    for position, row in enumerate(rows, start=1):
        exposure = float(row["exposure_inr"])
        running += exposure
        observed = float(row["observed_default_rate"])
        ranked.append({
            "rank": position,
            "unit": int(row["unit"]),
            "label": f"{noun} {int(row['unit'])}",
            "loans": int(row["loans"]),
            "exposureInr": exposure,
            "exposureShare": _rate(exposure, total_exposure),
            "cumulativeExposureShare": _rate(running, total_exposure),
            "observedDefaultRate": observed,
            "riskIndex": _rate(observed, base_rate) * 100,
        })

    top = ranked[:limit]
    return {
        "provenance": provenance(split),
        "dimension": dimension,
        "noun": noun,
        "units": len(ranked),
        "loans": total_loans,
        "exposureInr": total_exposure,
        "baseDefaultRate": base_rate,
        # The headline concentration facts, computed over every unit rather than
        # the truncated list, so the ranking below can be cut without changing them.
        "topFiveExposureShare": sum(item["exposureShare"] for item in ranked[:5]),
        "topDecileExposureShare": sum(
            item["exposureShare"] for item in ranked[: max(1, len(ranked) // 10)]
        ),
        "shown": len(top),
        "ranking": top,
    }


def _psi(expected: list[float], actual: list[float]) -> float:
    """Population Stability Index across matched buckets.

    Zero-share buckets are floored rather than dropped: dropping one silently
    understates the shift, and a bucket that emptied is exactly the shift worth
    seeing. The floor is half of the smallest share a single loan could produce.
    """
    total = 0.0
    floor = 1e-6
    for e, a in zip(expected, actual):
        e = max(e, floor)
        a = max(a, floor)
        total += (a - e) * math.log(a / e)
    return total


@router.get("/stability")
def stability() -> dict[str, object]:
    """Two monitoring questions, both answered without trusting an in-sample score.

    Population stability compares the book's composition month to month. It uses
    no model at all, so it is clean for every vintage: if the mix of what is
    being written moves, a policy calibrated on August is aimed at a book that
    no longer exists.

    Calibration compares predicted against observed default per decile on the
    October holdout only, which is where that comparison means something.
    """
    conn = connection()
    try:
        mix = [dict(row) for row in conn.execute(
            """
            WITH scoped AS (
                SELECT d.split, d.month AS month_number, d.month_name,
                       f.ltv, f.perform_cns_score, e.employment_type
                FROM fact_loan f
                JOIN dim_date d ON d.date_id = f.disbursal_date_id
                JOIN dim_employment e ON e.employment_type_id = f.employment_type_id
            ),
            labelled AS (
                SELECT split, month_number, month_name, 'ltv' AS dimension,
                       CASE WHEN ltv < 60 THEN 'Under 60%' WHEN ltv < 70 THEN '60 to 70%'
                            WHEN ltv < 80 THEN '70 to 80%' WHEN ltv < 85 THEN '80 to 85%'
                            ELSE '85% and above' END AS segment
                FROM scoped
                UNION ALL
                SELECT split, month_number, month_name, 'bureau',
                       CASE WHEN perform_cns_score IS NULL THEN 'No bureau history'
                            WHEN perform_cns_score < 500 THEN 'Under 500'
                            WHEN perform_cns_score < 650 THEN '500 to 650'
                            WHEN perform_cns_score < 725 THEN '650 to 725'
                            ELSE '725 and above' END
                FROM scoped
                UNION ALL
                SELECT split, month_number, month_name, 'employment',
                       CASE employment_type WHEN 'Missing' THEN 'Not recorded' ELSE employment_type END
                FROM scoped
            )
            SELECT dimension, segment, split, month_name, month_number, COUNT(*) AS loans
            FROM labelled
            GROUP BY dimension, segment, split, month_name, month_number
            ORDER BY dimension, segment, month_number
            """
        )]
        calibration = [dict(row) for row in conn.execute(DECILE_SQL, {"split": "test"})]
        band_rows = [dict(row) for row in conn.execute(
            """
            SELECT f.risk_score, f.loan_default
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            WHERE d.split = 'test' AND f.risk_score IS NOT NULL
            """
        )]
    finally:
        conn.close()

    months: list[tuple[int, str, str]] = sorted(
        {(int(r["month_number"]), str(r["month_name"]), str(r["split"])) for r in mix}
    )
    reference_month = months[0][1]
    dimensions = []
    for key, label in (("ltv", "Loan to value"), ("bureau", "Bureau score"), ("employment", "Employment")):
        rows = [r for r in mix if r["dimension"] == key]
        segment_names = sorted({str(r["segment"]) for r in rows})
        by_month: dict[str, dict[str, float]] = {}
        for _, month_name, _split in months:
            month_rows = [r for r in rows if r["month_name"] == month_name]
            month_total = sum(int(r["loans"]) for r in month_rows)
            by_month[month_name] = {
                name: _rate(
                    sum(int(r["loans"]) for r in month_rows if str(r["segment"]) == name),
                    month_total,
                )
                for name in segment_names
            }
        expected = [by_month[reference_month][name] for name in segment_names]
        dimensions.append({
            "key": key,
            "label": label,
            "segments": segment_names,
            "months": [
                {
                    "month": month_name,
                    "shares": [by_month[month_name][name] for name in segment_names],
                    "psi": _psi(expected, [by_month[month_name][name] for name in segment_names]),
                    "isReference": month_name == reference_month,
                }
                for _, month_name, _split in months
            ],
        })

    calibration_points = [
        {
            "decile": int(row["decile"]),
            "meanPredicted": float(row["mean_predicted"]),
            "observedDefaultRate": float(row["observed_default_rate"]),
            "loans": int(row["loans"]),
            "gap": float(row["observed_default_rate"]) - float(row["mean_predicted"]),
        }
        for row in calibration
    ]

    band_checks = []
    for band in bands():
        threshold = float(band["threshold"])
        admitted = [r for r in band_rows if float(r["risk_score"]) < threshold]
        if not admitted:
            continue
        predicted = sum(float(r["risk_score"]) for r in admitted) / len(admitted)
        observed = sum(int(r["loan_default"]) for r in admitted) / len(admitted)
        band_checks.append({
            "key": band["key"],
            "label": band["label"],
            "threshold": threshold,
            "loans": len(admitted),
            "predictedDefaultRate": predicted,
            "observedDefaultRate": observed,
            "gap": observed - predicted,
        })

    return {
        "referenceMonth": reference_month,
        "referenceNote": (
            f"{reference_month} is the month the model was fitted on, so it is the baseline "
            "the later vintages are measured against."
        ),
        "psiBands": [
            {"upTo": 0.10, "label": "Stable"},
            {"upTo": 0.25, "label": "Moderate shift"},
            {"upTo": None, "label": "Material shift"},
        ],
        "mix": dimensions,
        "calibration": {"provenance": provenance("test"), "points": calibration_points},
        "bandChecks": {"provenance": provenance("test"), "bands": band_checks},
    }


def _loan_row_sql(where: str) -> str:
    return f"""
        SELECT f.loan_id, f.public_ref,
               f.disbursed_amount, f.asset_cost, f.ltv, f.perform_cns_score,
               f.loan_default, f.risk_score,
               e.employment_type, d.month_name, d.split, d.date_id
        FROM fact_loan f
        JOIN dim_employment e ON e.employment_type_id = f.employment_type_id
        JOIN dim_date d ON d.date_id = f.disbursal_date_id
        {where}
    """


def _loan_id(record_ref: str) -> int:
    normalized = record_ref.strip().upper()
    if len(normalized) != 15 or not normalized.startswith("VL-"):
        raise HTTPException(status_code=404, detail="Record not found.")
    public_ref = normalized[3:]
    if any(character not in "0123456789ABCDEF" for character in public_ref):
        raise HTTPException(status_code=404, detail="Record not found.")
    conn = connection()
    try:
        row = conn.execute("SELECT loan_id FROM fact_loan WHERE public_ref = :public_ref", {"public_ref": public_ref}).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return int(row[0])


def _present(row: dict) -> dict[str, object]:
    score = row["risk_score"]
    return {
        "recordRef": f"VL-{row['public_ref']}",
        "month": str(row["month_name"]),
        "split": str(row["split"]),
        "employmentType": "Not recorded" if row["employment_type"] == "Missing" else str(row["employment_type"]),
        "disbursedAmountInr": float(row["disbursed_amount"]),
        "assetCostInr": float(row["asset_cost"]),
        "ltv": float(row["ltv"]),
        "bureauScore": None if row["perform_cns_score"] is None else float(row["perform_cns_score"]),
        "hasBureauHistory": row["perform_cns_score"] is not None,
        "defaulted": bool(row["loan_default"]),
        "riskScore": None if score is None else float(score),
    }


@router.get("/loans")
def search_loans(
    preset: str = Query(default="riskiest", pattern="^(riskiest|surprises|thin|borderline)$"),
) -> dict[str, object]:
    """Return one of four fixed analyst shortlists from the held-out month.

    The public record inspector is deliberately not a row-export API. It offers
    four decision-relevant samples with no arbitrary filters, offsets, or ID
    ordering, while the aggregate endpoints still analyze the complete store.
    """
    where, order = {
        "riskiest": ("WHERE d.split = 'test' AND f.risk_score IS NOT NULL", "f.risk_score DESC"),
        "surprises": ("WHERE d.split = 'test' AND f.risk_score IS NOT NULL AND f.loan_default = 1", "f.risk_score ASC"),
        "thin": ("WHERE d.split = 'test' AND f.risk_score IS NOT NULL AND f.perform_cns_score IS NULL", "f.risk_score DESC"),
        "borderline": ("WHERE d.split = 'test' AND f.risk_score BETWEEN 0.135 AND 0.185", "f.risk_score DESC"),
    }[preset]

    conn = connection()
    try:
        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM fact_loan f
            JOIN dim_employment e ON e.employment_type_id = f.employment_type_id
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            {where}
            """,
        ).fetchone()[0]
        rows = [dict(row) for row in conn.execute(
            f"{_loan_row_sql(where)} ORDER BY {order}, f.loan_id LIMIT 20",
        )]
    finally:
        conn.close()
    return {
        "total": int(total),
        "provenance": provenance("test"),
        "rows": [_present(row) for row in rows],
    }


@router.get("/loans/{record_ref}")
def loan_detail(record_ref: str) -> dict[str, object]:
    """One loan, its score, what each band would have done with it, and its peers.

    The peer comparison is empirical: the observed default rate among loans in
    the same vintage sharing this loan's LTV band and bureau band. It is not a
    second model, and it is not this loan's probability. It answers "how did
    loans that looked like this one actually perform", which is the question a
    reviewer opening a file is really asking.
    """
    loan_id = _loan_id(record_ref)
    conn = connection()
    try:
        row = conn.execute(_loan_row_sql("WHERE f.loan_id = :loan_id"), {"loan_id": loan_id}).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Record not found.")
        loan = dict(row)
        split = str(loan["split"])
        score = loan["risk_score"]

        percentile = None
        if score is not None:
            below, cohort_size = conn.execute(
                """
                SELECT SUM(f.risk_score < :score), COUNT(*)
                FROM fact_loan f
                JOIN dim_date d ON d.date_id = f.disbursal_date_id
                WHERE d.split = :split AND f.risk_score IS NOT NULL
                """,
                {"score": float(score), "split": split},
            ).fetchone()
            percentile = _rate(int(below or 0), int(cohort_size or 0))

        peer = conn.execute(
            """
            SELECT COUNT(*) AS loans, AVG(f.loan_default) AS observed_default_rate
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            WHERE d.split = :split
              AND (f.perform_cns_score IS NULL) = :thin
              AND CASE WHEN f.ltv < 60 THEN 1 WHEN f.ltv < 70 THEN 2
                       WHEN f.ltv < 80 THEN 3 WHEN f.ltv < 85 THEN 4 ELSE 5 END = :ltv_band
            """,
            {
                "split": split,
                "thin": 1 if loan["perform_cns_score"] is None else 0,
                "ltv_band": 1 if loan["ltv"] < 60 else 2 if loan["ltv"] < 70 else 3 if loan["ltv"] < 80 else 4 if loan["ltv"] < 85 else 5,
            },
        ).fetchone()
        vintage_rate = conn.execute(
            """
            SELECT AVG(f.loan_default)
            FROM fact_loan f
            JOIN dim_date d ON d.date_id = f.disbursal_date_id
            WHERE d.split = :split
            """,
            {"split": split},
        ).fetchone()[0]
    finally:
        conn.close()

    verdicts = []
    if score is not None:
        for band in bands():
            threshold = float(band["threshold"])
            value = float(score)
            # Referral wins over admission: a loan inside the straddle is the one
            # an underwriter looks at, whichever side of the cut-off it sits on.
            if threshold - REVIEW_BAND <= value < threshold + REVIEW_BAND:
                verdict, explanation = "Refer", "Inside the manual-review straddle around the cut-off."
            elif value < threshold:
                verdict, explanation = "Admit", "Predicted risk sits below the cut-off."
            else:
                verdict, explanation = "Decline", "Predicted risk sits above the cut-off and outside the review straddle."
            verdicts.append({
                "key": band["key"],
                "label": band["label"],
                "threshold": threshold,
                "verdict": verdict,
                "explanation": explanation,
            })

    return {
        "loan": _present(loan),
        "provenance": provenance(split),
        "riskPercentile": percentile,
        "bandVerdicts": verdicts,
        "peers": {
            "loans": int(peer["loans"] or 0),
            "observedDefaultRate": float(peer["observed_default_rate"] or 0.0),
            "vintageDefaultRate": float(vintage_rate or 0.0),
            "basis": "Same vintage, same loan-to-value band, same bureau-coverage state.",
        },
    }
