"""Build retrospective, aggregate-only first-EMI strategy evidence."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "quarantine" / "train.csv"
OUT = ROOT / "artifacts" / "strategy_summary.json"
WEB_DATA = ROOT / "web" / "src" / "data.js"
TARGET = "LOAN_DEFAULT"
PROHIBITED = {
    "UNIQUEID", "DISBURSAL_DATE", "CURRENT_PINCODE_ID", "DATE_OF_BIRTH",
    "EMPLOYEE_CODE_ID", "MOBILENO_AVL_FLAG", "AADHAR_FLAG", "PAN_FLAG",
    "VOTERID_FLAG", "DRIVING_FLAG", "PASSPORT_FLAG",
}
CATEGORICAL = {"EMPLOYMENT_TYPE", "PERFORM_CNS_SCORE_DESCRIPTION"}
# Nominal codes, not quantities. See the encoding note in fit_and_select.
IDENTIFIERS = ["BRANCH_ID", "SUPPLIER_ID", "MANUFACTURER_ID", "STATE_ID"]


def calibration_summary(y: pd.Series, p: np.ndarray) -> dict[str, float]:
    frame = pd.DataFrame({"y": y.to_numpy(), "p": p})
    frame["bin"] = pd.qcut(frame["p"], q=10, duplicates="drop")
    grouped = frame.groupby("bin", observed=True).agg(actual=("y", "mean"), predicted=("p", "mean"))
    ece = float((grouped["actual"] - grouped["predicted"]).abs().mean())
    return {"brier_score": round(float(brier_score_loss(y, p)), 5), "ece_decile": round(ece, 5)}


def metrics(y: pd.Series, p: np.ndarray) -> dict[str, float]:
    return {
        "auroc": round(float(roc_auc_score(y, p)), 5),
        "pr_auc": round(float(average_precision_score(y, p)), 5),
        **calibration_summary(y, p),
    }


# Assumption-led economics. These three numbers, not the model, decide which band
# wins: the recommendation flips on a ~3% move in either credit parameter, which is
# why every band also reports its break-even values and why the summary carries a
# sensitivity grid. None is sourced from the lender; all are analyst inputs.
CONTRIBUTION_RATE = 0.12   # contribution margin on disbursed principal
LOSS_SEVERITY = 0.65       # loss given first-EMI default
REVIEW_COST_INR = 1500.0   # fully-loaded underwriter cost per manual review

# The points the published sensitivity analysis is evaluated at. Shared with the
# web bundle so the workbench renders the same grid the artifact reports rather
# than a second set of axes that could drift away from it.
SENSITIVITY_AXES = {
    "contribution_rate": (0.10, 0.12, 0.14),
    "loss_severity": (0.55, 0.65, 0.75),
    "review_cost_inr": (0.0, 1500.0, 3000.0),
}


def policy(
    name: str,
    amount: pd.Series,
    y: pd.Series,
    p: np.ndarray,
    threshold: float,
    contribution_rate: float = CONTRIBUTION_RATE,
    loss_severity: float = LOSS_SEVERITY,
    review_cost: float = REVIEW_COST_INR,
) -> dict[str, float | str]:
    review_band = 0.025
    approved = p < threshold
    review = (p >= threshold - review_band) & (p < threshold + review_band)
    approved_amount = amount[approved]
    observed_default = y[approved]
    defaulted_amount = approved_amount * observed_default

    gross = float((approved_amount * contribution_rate).sum())
    credit_loss = float((defaulted_amount * loss_severity).sum())
    review_spend = float(int(review.sum()) * review_cost)
    contribution = gross - credit_loss - review_spend

    # The assumption values at which this band exactly breaks even, holding the
    # other two fixed. These are what a reviewer asks for first.
    defaulted_total = float(defaulted_amount.sum())
    approved_total = float(approved_amount.sum())
    breakeven_severity = (gross - review_spend) / defaulted_total if defaulted_total else float("nan")
    breakeven_contribution_rate = (credit_loss + review_spend) / approved_total if approved_total else float("nan")
    breakeven_review_cost = (gross - credit_loss) / int(review.sum()) if int(review.sum()) else float("nan")

    return {
        "name": name,
        "risk_threshold": threshold,
        "approved_count": int(approved.sum()),
        "review_count": int(review.sum()),
        "approved_amount_inr": round(approved_total, 2),
        "defaulted_amount_inr": round(defaulted_total, 2),
        "approval_rate": round(float(approved.mean()), 5),
        "manual_review_rate": round(float(review.mean()), 5),
        "observed_default_rate": round(float(observed_default.mean()) if len(observed_default) else 0.0, 5),
        "gross_contribution_inr": round(gross, 2),
        "credit_loss_inr": round(credit_loss, 2),
        "review_cost_inr": round(review_spend, 2),
        "assumption_led_contribution": round(contribution, 2),
        "breakeven_loss_severity": round(breakeven_severity, 5),
        "breakeven_contribution_rate": round(breakeven_contribution_rate, 5),
        "breakeven_review_cost_inr": round(breakeven_review_cost, 2),
        "assumptions": (
            f"{contribution_rate:.0%} contribution rate; {loss_severity:.0%} loss severity; "
            f"INR {review_cost:,.0f} per manual review; retrospective observed first-EMI default"
        ),
    }


def prior_shift(p: np.ndarray, target: float) -> tuple[np.ndarray, float]:
    """Rescale predicted odds by a single factor so their mean matches `target`.

    One parameter, applied uniformly. It cannot change the ranking and it cannot
    change the shape of the calibration curve; all it can do is move the level.
    That is exactly what makes it a useful probe: whatever error it removes was
    a base-rate problem, and whatever survives is the model genuinely
    mis-shaping risk.

    Solved by bisection rather than scipy.optimize, because the mean is monotone
    in the factor and this keeps the offline pipeline one dependency lighter.
    """
    clipped = np.clip(p, 1e-6, 1 - 1e-6)
    odds = clipped / (1 - clipped)
    shifted = lambda k: (k * odds) / (1 + k * odds)
    low, high = 1e-6, 1e6
    for _ in range(200):
        mid = (low + high) / 2
        if shifted(mid).mean() < target:
            low = mid
        else:
            high = mid
    factor = (low + high) / 2
    return shifted(factor), factor


def calibration_drift(
    y_test: pd.Series, p_test: np.ndarray, y_calibration: pd.Series
) -> dict[str, object]:
    """Split the calibration error into base-rate drift and everything else.

    The isotonic calibrator is fitted on September and applied to October, and
    the two months did not default at the same rate. This asks how much of the
    resulting error is simply that inherited prior.

    The correction uses the TEST month's own base rate, which nobody knows in
    advance. That makes this a diagnostic, not a deployable adjustment: it
    measures how much of the gap a correctly-timed recalibration could remove,
    and it would be leakage to present its output as a performance figure. In
    production the same one-parameter shift is fitted on the most recent closed
    month, which is knowable, and this number is the upper bound on what that
    would buy.
    """
    observed = float(y_test.mean())
    calibrated_on = float(y_calibration.mean())
    corrected, factor = prior_shift(p_test, observed)
    before = calibration_summary(y_test, p_test)
    after = calibration_summary(y_test, corrected)
    return {
        "calibration_month_default_rate": round(calibrated_on, 5),
        "test_month_default_rate": round(observed, 5),
        "base_rate_shift": round(observed - calibrated_on, 5),
        "mean_predicted": round(float(p_test.mean()), 5),
        "mean_gap": round(observed - float(p_test.mean()), 5),
        "ece_published": before["ece_decile"],
        "ece_after_prior_shift": after["ece_decile"],
        "share_of_error_from_base_rate": round(
            1 - after["ece_decile"] / before["ece_decile"], 4
        ) if before["ece_decile"] else 0.0,
        "odds_factor": round(float(factor), 4),
        "note": (
            "The correction uses the test month's own base rate, which is not knowable in advance, "
            "so this is a diagnostic and not a deployable adjustment. It bounds what a correctly-timed "
            "recalibration could recover. Refitting the calibrator on the month being scored would not "
            "be time-safe and is not done here."
        ),
    }


BOOTSTRAP_DRAWS = 400
BOOTSTRAP_SEED = 42


def bootstrap_bands(
    amount: pd.Series,
    y: pd.Series,
    p: np.ndarray,
    bands: dict[str, float],
    contribution_rate: float = CONTRIBUTION_RATE,
    loss_severity: float = LOSS_SEVERITY,
    review_cost: float = REVIEW_COST_INR,
    draws: int = BOOTSTRAP_DRAWS,
) -> dict[str, dict[str, list[float]]]:
    """Resample the holdout to put an interval around every headline band figure.

    The published net contribution is a small difference between two large
    numbers, so the question a reviewer asks first is whether two bands are
    distinguishable at all. Without an interval, +1.52 cr against -3.38 cr reads
    as a ranking; with one it may read as a coin toss.

    The cut-offs are held fixed and the loans are resampled with replacement,
    which answers "how far would this figure move on another sample of the same
    size drawn from the same population". It does not, and cannot, capture the
    far larger uncertainty in the three economic assumptions themselves; the
    sensitivity grid is what covers that.
    """
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    amount_values = amount.to_numpy(dtype=float)
    y_values = y.to_numpy(dtype=float)
    n = len(p)
    review_band = 0.025

    draws_by_band: dict[str, dict[str, list[float]]] = {
        name: {"approval_rate": [], "observed_default_rate": [], "contribution_inr": []}
        for name in bands
    }
    for _ in range(draws):
        idx = rng.integers(0, n, n)
        p_s, a_s, y_s = p[idx], amount_values[idx], y_values[idx]
        for name, threshold in bands.items():
            approved = p_s < threshold
            review = (p_s >= threshold - review_band) & (p_s < threshold + review_band)
            approved_amount = a_s[approved]
            defaulted_amount = approved_amount * y_s[approved]
            contribution = (
                approved_amount.sum() * contribution_rate
                - defaulted_amount.sum() * loss_severity
                - int(review.sum()) * review_cost
            )
            record = draws_by_band[name]
            record["approval_rate"].append(float(approved.mean()))
            record["observed_default_rate"].append(
                float(y_s[approved].mean()) if approved.any() else 0.0
            )
            record["contribution_inr"].append(float(contribution))

    summary: dict[str, dict[str, list[float]]] = {}
    for name, record in draws_by_band.items():
        entry: dict[str, list[float]] = {}
        for metric, values in record.items():
            low, high = np.percentile(values, [2.5, 97.5])
            entry[metric] = [round(float(low), 5 if "rate" in metric else 2),
                             round(float(high), 5 if "rate" in metric else 2)]
        entry["contribution_positive_share"] = round(
            float(np.mean(np.array(record["contribution_inr"]) > 0)), 4
        )
        summary[name] = entry
    return summary


def band_separation(bootstrap: dict[str, dict[str, list[float]]], bands: list[str]) -> dict[str, object]:
    """Whether the top two bands' contribution intervals actually separate."""
    ordered = sorted(bands, key=lambda name: bootstrap[name]["contribution_inr"][0], reverse=True)
    best, runner_up = ordered[0], ordered[1]
    best_low = bootstrap[best]["contribution_inr"][0]
    runner_high = bootstrap[runner_up]["contribution_inr"][1]
    return {
        "best_band": best,
        "runner_up": runner_up,
        "intervals_overlap": bool(best_low <= runner_high),
        "note": (
            "95% intervals from resampling the October holdout with the cut-offs held fixed. "
            "They cover sampling variation only, not the economic assumptions."
        ),
    }


def impact_by_group(
    test: pd.DataFrame,
    y: pd.Series,
    p: np.ndarray,
    bands: dict[str, float],
    attributes: dict[str, str],
    min_group: int = 500,
) -> list[dict[str, object]]:
    """Approval and observed default per band, split by attribute.

    Moving approval from 86% to 45% does not land evenly, and this is the report
    that says where it lands. STATE_ID is target-encoded into the score and
    EMPLOYMENT_TYPE is a feature, so both are candidates for a proxy effect that
    an aggregate approval rate hides completely.

    Reported alongside each group's approval rate is its ratio to the most-
    approved group in the same band. That ratio is a screen, not a verdict: a
    low value says look here, and nothing about whether the difference is
    justified by risk. Groups below `min_group` loans are excluded because a
    ratio computed on a handful of applications is noise wearing a decimal
    point. This is disparate-impact *reporting*, not a fair-lending opinion, and
    the source carries no protected attribute to test one with.
    """
    rows: list[dict[str, object]] = []
    for attribute, column in attributes.items():
        values = test[column].fillna("Not recorded") if test[column].dtype == object else test[column]
        for band_name, threshold in bands.items():
            approved = p < threshold
            frame = pd.DataFrame({"group": values.to_numpy(), "approved": approved, "y": y.to_numpy()})
            grouped = frame.groupby("group", observed=True).agg(
                loans=("approved", "size"),
                approval_rate=("approved", "mean"),
                observed_default_rate=("y", "mean"),
            )
            grouped = grouped[grouped["loans"] >= min_group]
            if grouped.empty:
                continue
            best = float(grouped["approval_rate"].max())
            for group, record in grouped.iterrows():
                rows.append({
                    "attribute": attribute,
                    "band": band_name,
                    "group": str(group),
                    "loans": int(record["loans"]),
                    "approval_rate": round(float(record["approval_rate"]), 5),
                    "observed_default_rate": round(float(record["observed_default_rate"]), 5),
                    "approval_ratio_to_best": round(float(record["approval_rate"] / best), 4) if best else 0.0,
                })
    return rows


def sensitivity_grid(
    amount: pd.Series, y: pd.Series, p: np.ndarray, bands: dict[str, float]
) -> list[dict[str, float | str]]:
    """Which band wins under each assumption combination, not just the default one.

    The headline recommendation is fragile: it flips on a few percent of movement in
    either credit parameter. Publishing the grid makes that visible instead of
    letting a reader mistake one point estimate for a robust conclusion.
    """
    grid = []
    for rate in SENSITIVITY_AXES["contribution_rate"]:
        for severity in SENSITIVITY_AXES["loss_severity"]:
            for cost in SENSITIVITY_AXES["review_cost_inr"]:
                scored = {
                    n: float(policy(n, amount, y, p, t, rate, severity, cost)["assumption_led_contribution"])
                    for n, t in bands.items()
                }
                best = max(scored, key=scored.__getitem__)
                grid.append({
                    "contribution_rate": rate,
                    "loss_severity": severity,
                    "review_cost_inr": cost,
                    "best_band": best,
                    "best_contribution_inr": round(scored[best], 2),
                    "any_band_positive": bool(scored[best] > 0),
                })
    return grid


def percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def write_web_evidence(summary: dict[str, object]) -> None:
    policies = summary["policies"]
    assert isinstance(policies, list)
    # Derived, never asserted. These lines were hard-coded per band, which
    # survived a correction that turned the recommended band negative and left
    # the bundle recommending a band that loses money.
    def decision_for(item: dict, interval: dict) -> str:
        net = float(item["assumption_led_contribution"])
        positive_share = float(interval["contribution_positive_share"])
        if net <= 0:
            return "Not recommended at the published assumptions"
        if positive_share < 0.95:
            return "Not distinguishable from zero"
        return "Candidate for governance review"
    display_policies = []
    for item in policies:
        assert isinstance(item, dict)
        name = str(item["name"])
        display_policies.append({
            "key": name,
            "label": name.title(),
            "threshold": percentage(float(item["risk_threshold"])),
            "approval": percentage(float(item["approval_rate"])),
            "review": percentage(float(item["manual_review_rate"])),
            "defaultRate": percentage(float(item["observed_default_rate"])),
            "approvedCount": int(item["approved_count"]),
            "reviewCount": int(item["review_count"]),
            "approvedAmountInr": float(item["approved_amount_inr"]),
            "defaultedAmountInr": float(item["defaulted_amount_inr"]),
            # The published result at the default assumptions. The workbench
            # recomputes contribution live as the analyst moves the sliders;
            # this is the figure it compares that live result against, so a
            # visitor can always see how far they have moved from the record.
            "netContributionInr": float(item["assumption_led_contribution"]),
            "decision": decision_for(item, summary["bootstrap"][name]),
        })
    bootstrap = summary["bootstrap"]
    for item in display_policies:
        interval = bootstrap[item["key"]]
        item["netContributionRangeInr"] = interval["contribution_inr"]
        item["approvalRateRange"] = interval["approval_rate"]
        item["defaultRateRange"] = interval["observed_default_rate"]
        item["positiveShare"] = interval["contribution_positive_share"]
    models = summary["models"]
    splits = summary["splits"]
    assert isinstance(models, dict) and isinstance(splits, dict)
    evidence = {
        "period": "1 Aug - 31 Oct 2018",
        "splits": f"{splits['train']:,} train | {splits['calibration']:,} calibration | {splits['test']:,} test",
        "selectedModel": "Calibrated challenger",
        "testApplicants": int(splits["test"]),
        "metrics": {
            "auroc": f"{models['calibrated_challenger']['auroc']:.3f}",
            "prAuc": f"{models['calibrated_challenger']['pr_auc']:.3f}",
            "brier": f"{models['calibrated_challenger']['brier_score']:.3f}",
            "ece": f"{models['calibrated_challenger']['ece_decile']:.3f}",
        },
        "policies": display_policies,
        "assumptions": {
            "contributionRate": CONTRIBUTION_RATE,
            "lossSeverity": LOSS_SEVERITY,
            "reviewCostInr": REVIEW_COST_INR,
        },
        "bandSeparation": summary["band_separation"],
        "impactByGroup": summary["impact_by_group"],
        "labelCaveats": summary["label_caveats"],
        "calibrationDrift": summary["calibration_drift"],
        "sensitivityAxes": {
            "contributionRate": list(SENSITIVITY_AXES["contribution_rate"]),
            "lossSeverity": list(SENSITIVITY_AXES["loss_severity"]),
            "reviewCostInr": list(SENSITIVITY_AXES["review_cost_inr"]),
        },
    }
    WEB_DATA.write_text(
        "// Generated by scripts/run_evaluation.py from aggregate-only evidence.\n"
        f"export const evidence = {json.dumps(evidence, indent=2)};\n",
        encoding="utf-8",
    )


def load_and_prepare() -> tuple[pd.DataFrame, list[str], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the authorized source, engineer features, and apply the temporal split.

    Shared by this script and scripts/build_db.py so the SQLite store's
    risk_score column is scored by the exact same feature set and split as
    the approved evaluation evidence, not a second, drifting definition.
    """
    if not RAW.is_file():
        raise FileNotFoundError(f"Missing private data file: {RAW}")
    data = pd.read_csv(RAW)
    data["DISBURSAL_DATE"] = pd.to_datetime(data["DISBURSAL_DATE"], dayfirst=True, errors="raise")
    for column in ("AVERAGE_ACCT_AGE", "CREDIT_HISTORY_LENGTH"):
        parts = data[column].str.extract(r"(?P<years>\d+)yrs\s+(?P<months>\d+)mon").astype(float)
        data[column] = parts["years"] * 12 + parts["months"]
    # The bureau score column encodes "no usable score" as a number, in two
    # different ways, and both have to be removed before the value is treated as
    # a quantity.
    #
    # A score of 0 means "no bureau history". Left as 0 it sits below every real
    # score and the model reads thin-file applicants as maximally risky rather
    # than as unknown.
    #
    # Values 11 to 18 are the same problem wearing a different disguise, and they
    # are the reason PERFORM_CNS_SCORE_DESCRIPTION has to be consulted rather
    # than trusted to the number alone. For 12,835 loans the description reads
    # "Not Scored: Sufficient History Not Available", "Not Scored: Not Enough
    # Info available on the customer", "Not Scored: No Activity seen on the
    # customer (Inactive)", "Not Scored: No Updates available in last 36 months",
    # or "Not Scored: Only a Guarantor". The bureau is saying *unknown*. Passed
    # through as 15, on a scale whose real floor is 300, the model is told
    # *catastrophic* instead.
    not_scored = data["PERFORM_CNS_SCORE_DESCRIPTION"].str.startswith("Not Scored", na=False)
    data.loc[not_scored, "PERFORM_CNS_SCORE"] = np.nan
    data["PERFORM_CNS_SCORE"] = data["PERFORM_CNS_SCORE"].replace(0, np.nan)
    # Derived after both recodes, not before. Deriving it from the raw column
    # marked every one of those 12,835 loans as having a bureau file when the
    # source explicitly says it has none, which inverted the thin-file indicator
    # on 5.5% of a book that is half thin-file.
    data["HAS_BUREAU"] = data["PERFORM_CNS_SCORE"].notna().astype(int)
    # Ratios the raw columns only imply. Division guards against zero denominators,
    # which HistGradientBoostingClassifier handles natively as missing.
    ratio = lambda a, b: a / b.replace(0, np.nan)
    data["PRI_UTILISATION"] = ratio(data["PRI_CURRENT_BALANCE"], data["PRI_SANCTIONED_AMOUNT"])
    data["PRI_OVERDUE_RATIO"] = ratio(data["PRI_OVERDUE_ACCTS"], data["PRI_NO_OF_ACCTS"])
    data["TOTAL_ACCTS"] = data["PRI_NO_OF_ACCTS"] + data["SEC_NO_OF_ACCTS"]
    data["INSTAL_BURDEN"] = ratio(
        data["PRIMARY_INSTAL_AMT"] + data["SEC_INSTAL_AMT"], data["DISBURSED_AMOUNT"]
    )
    if data[TARGET].isna().any() or data["UNIQUEID"].duplicated().any():
        raise ValueError("Target or unique-ID quality gate failed")
    features = [c for c in data.columns if c not in PROHIBITED | {TARGET}]
    if PROHIBITED.intersection(features):
        raise ValueError("Prohibited field reached feature matrix")
    train = data[data["DISBURSAL_DATE"].dt.month == 8].copy()
    calibrate = data[data["DISBURSAL_DATE"].dt.month == 9].copy()
    test = data[data["DISBURSAL_DATE"].dt.month == 10].copy()
    if min(len(train), len(calibrate), len(test)) == 0:
        raise ValueError("Temporal split quality gate failed")
    return data, features, train, calibrate, test


def fit_and_select(
    features: list[str], train: pd.DataFrame, calibrate: pd.DataFrame, test: pd.DataFrame
) -> tuple[str, np.ndarray, np.ndarray, np.ndarray, Pipeline | CalibratedClassifierCV]:
    """Fit the logistic baseline and calibrated challenger, then select by Brier score.

    Returns (selected_model_name, selected_test_scores, baseline_test_scores,
    challenger_test_scores, selected_fitted_estimator). The fitted estimator is
    returned so scripts/build_db.py can score the August and September vintages
    with the same object that produced the October evidence, rather than fitting
    a second model that would drift from it.
    """
    numeric = [c for c in features if c not in CATEGORICAL]
    linear_prep = ColumnTransformer([
        ("numeric", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore"))]), sorted(CATEGORICAL)),
    ])
    baseline = Pipeline([("prep", linear_prep), ("model", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    baseline.fit(train[features], train[TARGET])
    baseline_test = baseline.predict_proba(test[features])[:, 1]

    # BRANCH_ID, SUPPLIER_ID, MANUFACTURER_ID and STATE_ID are nominal codes. Fed
    # through as plain numbers the model can split on "branch 47 < branch 92", which
    # is meaningless. TargetEncoder is cross-fitted internally so it does not leak,
    # and unlike HistGradientBoostingClassifier's native categorical support it has
    # no 255-level cap  -  SUPPLIER_ID alone has 2,420 levels.
    identifiers = [c for c in IDENTIFIERS if c in features]
    challenger_numeric = [c for c in numeric if c not in set(identifiers)]
    challenger_prep = ColumnTransformer([
        ("identifiers", TargetEncoder(random_state=42), identifiers),
        ("numeric", "passthrough", challenger_numeric),
        ("categorical", Pipeline([("impute", SimpleImputer(strategy="most_frequent")), ("encode", OneHotEncoder(handle_unknown="ignore", sparse_output=False))]), sorted(CATEGORICAL)),
    ])
    challenger = Pipeline([("prep", challenger_prep), ("model", HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=31, random_state=42))])
    challenger.fit(train[features], train[TARGET])
    calibrated = CalibratedClassifierCV(FrozenEstimator(challenger), method="isotonic")
    calibrated.fit(calibrate[features], calibrate[TARGET])
    challenger_test = calibrated.predict_proba(test[features])[:, 1]
    selected_name, selected_p, selected_model = (
        ("calibrated_challenger", challenger_test, calibrated)
        if metrics(test[TARGET], challenger_test)["brier_score"] < metrics(test[TARGET], baseline_test)["brier_score"]
        else ("logistic_baseline", baseline_test, baseline)
    )
    return selected_name, selected_p, baseline_test, challenger_test, selected_model


def main() -> None:
    _data, features, train, calibrate, test = load_and_prepare()
    selected_name, selected_p, baseline_test, challenger_test, _model = fit_and_select(features, train, calibrate, test)
    amount = test["DISBURSED_AMOUNT"]
    bands = {"conservative": 0.16, "reference": 0.22, "expansion": 0.28}
    bootstrap = bootstrap_bands(amount, test[TARGET], selected_p, bands)
    summary = {
        "scope": "retrospective first-EMI default strategy evidence; not underwriting, fraud, pricing, or automated decisions",
        "data_period": "2018-08-01 through 2018-10-31",
        "splits": {"train": len(train), "calibration": len(calibrate), "test": len(test)},
        "feature_count": len(features),
        "prohibited_fields": sorted(PROHIBITED),
        "models": {"logistic_baseline": metrics(test[TARGET], baseline_test), "calibrated_challenger": metrics(test[TARGET], challenger_test)},
        "selected_model": selected_name,
        "economic_assumptions": {
            "contribution_rate": CONTRIBUTION_RATE,
            "loss_severity": LOSS_SEVERITY,
            "review_cost_inr": REVIEW_COST_INR,
            "note": (
                "Analyst inputs, not lender-sourced. The band ranking is sensitive to all "
                "three; see per-band break-even values and the sensitivity grid."
            ),
        },
        "policies": [policy(name, amount, test[TARGET], selected_p, t) for name, t in bands.items()],
        "sensitivity": sensitivity_grid(amount, test[TARGET], selected_p, bands),
        "bootstrap": bootstrap,
        "calibration_drift": calibration_drift(test[TARGET], selected_p, calibrate[TARGET]),
        "band_separation": band_separation(bootstrap, list(bands)),
        "impact_by_group": impact_by_group(
            test, test[TARGET], selected_p, bands,
            {"State": "STATE_ID", "Employment": "EMPLOYMENT_TYPE"},
        ),
        "label_caveats": {
            "outcome": "Verified default on the first EMI on its due date.",
            "operational_contamination": (
                "The book runs at a 21.7% first-EMI default rate. First-payment default in a "
                "performing vehicle book is normally low single digits, so this label almost "
                "certainly mixes mandate and payment-plumbing failures, such as NACH "
                "registration not completing, with genuine inability to pay. The source "
                "carries no field that separates them. Where the operational share is large "
                "the correct response is to repair onboarding, not to decline the applicant."
            ),
            "loss_severity_mismatch": (
                "Loss severity is applied to disbursal on loans that missed the first EMI. A "
                "first-EMI miss is a delinquency flag, not a loss event, and a large share of "
                "first-payment defaulters cure. The 65% figure is an ultimate-loss assumption "
                "charged against an early-delinquency population, which overstates credit "
                "loss by an amount this dataset cannot quantify: it carries no recovery, "
                "roll-rate, or ultimate-default data."
            ),
            "seasonality": (
                "August trains, September calibrates, October tests: three consecutive months "
                "of one quarter, with no out-of-time validation beyond a single month and no "
                "economic cycle. October 2018 also falls in the Indian festival period, the "
                "peak of the vehicle-sales year, which draws a different applicant mix. Some "
                "of the October deterioration may be seasonal rather than a model or "
                "population problem, and nothing here separates the two."
            ),
            "calibration_currency": (
                "The isotonic calibrator was fitted on September and applied to October, and "
                "the months ran at different default rates, so predicted probabilities sit "
                "below observed across every decile. The scores rank; they do not price. "
                "Fit any replacement calibrator on the most recent closed month, then apply "
                "it to the next scoring period."
            ),
        },
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_web_evidence(summary)
    print(f"Wrote aggregate evidence: {OUT.relative_to(ROOT)} and {WEB_DATA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
