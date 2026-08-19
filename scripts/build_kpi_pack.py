"""Build a one-page monthly KPI report pack from aggregate evidence only.

Reads two already-aggregate sources  -  never raw rows:
  1. artifacts/strategy_summary.json (policy-band approval/default/review/
     contribution evidence, already verified by scripts/run_evaluation.py).
  2. sql/kpi_monthly.sql executed against data/quarantine/loans.db (a
     GROUP BY rollup  -  one row per calendar month, no per-loan data).

Writes to artifacts/kpi_pack/ (a summary rollup by design; the KPI
dashboard carries the per-loan drill-down):
  - kpi_pack.csv   flat policy-band KPI table
  - kpi_pack.xlsx  workbook: Policy KPIs + Monthly Volume sheets
  - kpi_pack.png   rendered one-page leadership KPI rollup

This is the transferable analog of the "fraud reporting to senior
leadership" / monthly fraud-KPI cadence named in the OneMain posting
The source dataset has no fraud label;
these are first-EMI default-strategy KPIs, not fraud KPIs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "artifacts" / "strategy_summary.json"
DB_PATH = ROOT / "data" / "quarantine" / "loans.db"
KPI_SQL = ROOT / "sql" / "kpi_monthly.sql"
OUT_DIR = ROOT / "artifacts" / "kpi_pack"

# DESIGN.md semantic roles. The three series colours were validated as a
# categorical set (lightness band, chroma floor, colour-vision separation,
# normal-vision separation, and >=3:1 contrast against both the paper and the
# card surface) before use. Each series is also directly value-labelled, so no
# meaning is carried by colour alone.
INK = "#17212b"          # graphite, primary text
INK_MUTED = "#536575"    # graphite, secondary text
RULE = "#c8d1da"         # recessive hairline grid/axis
COBALT = "#0b67ad"       # action / volume
REFUSAL = "#a43838"       # risk / default outcome
CAUTION = "#c78100"      # capacity / manual-review demand
PAPER = "#ffffff"


def load_policy_kpis() -> pd.DataFrame:
    if not SUMMARY_PATH.is_file():
        raise FileNotFoundError(
            f"Missing aggregate evidence: {SUMMARY_PATH}. Run `uv run python scripts/run_evaluation.py` first."
        )
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
            "estimated_net_contribution_inr_cr": round(policy["assumption_led_contribution"] / 1e7, 2),
        })
    return pd.DataFrame(rows)


def load_monthly_volume() -> pd.DataFrame:
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"Missing SQLite store: {DB_PATH}. Run `uv run python scripts/build_db.py` first."
        )
    conn = sqlite3.connect(DB_PATH)
    try:
        frame = pd.read_sql_query(KPI_SQL.read_text(encoding="utf-8"), conn)
    finally:
        conn.close()
    frame["disbursed_amount_inr_cr"] = (frame["disbursed_amount_inr"] / 1e7).round(2)
    return frame


def write_csv(policy_kpis: pd.DataFrame) -> Path:
    path = OUT_DIR / "kpi_pack.csv"
    policy_kpis.to_csv(path, index=False)
    return path


def write_excel(policy_kpis: pd.DataFrame, monthly_volume: pd.DataFrame) -> Path:
    path = OUT_DIR / "kpi_pack.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        policy_kpis.to_excel(writer, sheet_name="Policy KPIs", index=False)
        monthly_volume.to_excel(writer, sheet_name="Monthly Volume", index=False)
    return path


def _style_axes(ax: plt.Axes, ylabel: str | None = None) -> None:
    """Recessive chrome: hairline horizontal grid, no boxed frame, graphite ink."""
    ax.set_axisbelow(True)
    ax.yaxis.grid(True, color=RULE, linewidth=0.6)
    ax.xaxis.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(RULE)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(colors=INK_MUTED, labelsize=8, length=0)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8, color=INK_MUTED)


def write_one_pager(policy_kpis: pd.DataFrame, monthly_volume: pd.DataFrame) -> Path:
    path = OUT_DIR / "kpi_pack.png"
    fig = plt.figure(figsize=(11, 8.5), dpi=150, facecolor=PAPER)
    fig.text(
        0.06, 0.955,
        "Vehicle-Loan First-EMI Default Strategy  -  Monthly KPI Pack",
        fontsize=15, fontweight="bold", color=INK,
    )
    fig.text(
        0.06, 0.928,
        "Retrospective evidence, August–October 2018 (233,154 loans; October holdout = 98,364). "
        "This dataset measures first-EMI default, not fraud.",
        fontsize=8.5, color=INK_MUTED,
    )
    fig.text(
        0.06, 0.909,
        "No view on this page makes a live approval, decline, or pricing decision. Contribution figures are assumption-led, not observed P&L.",
        fontsize=8.5, color=REFUSAL,
    )

    # --- Chart 1: policy-band trade-off. Question: what does each band cost? ---
    ax_bars = fig.add_axes((0.06, 0.575, 0.88, 0.275))
    bands = policy_kpis["band"].str.title().tolist()
    x = range(len(bands))
    width = 0.26
    series = (
        ("Approval rate %", policy_kpis["approval_rate"] * 100, COBALT, -width),
        ("Observed default rate %", policy_kpis["observed_default_rate"] * 100, REFUSAL, 0.0),
        ("Manual-review rate %", policy_kpis["manual_review_rate"] * 100, CAUTION, width),
    )
    for label, values, colour, offset in series:
        # 2px-equivalent surface gap between adjacent fills, not a drawn border.
        positions = [i + offset for i in x]
        ax_bars.bar(positions, values, width * 0.92, label=label, color=colour, linewidth=0)
        # Direct value labels: identity and value are never colour-alone.
        for pos, value in zip(positions, values):
            ax_bars.text(pos, value + 1.4, f"{value:.1f}", ha="center", va="bottom",
                         fontsize=7.5, color=INK, fontweight="bold")
    ax_bars.set_xticks(list(x))
    ax_bars.set_xticklabels(bands, fontsize=9.5, color=INK)
    ax_bars.set_ylim(0, 95)
    _style_axes(ax_bars, "Percent of October test cohort")
    ax_bars.set_title(
        "Which band buys volume, and what does it cost in default risk and review capacity?",
        fontsize=10.5, fontweight="bold", color=INK, loc="left", pad=10,
    )
    legend = ax_bars.legend(fontsize=8, loc="upper left", frameon=False, ncol=3,
                            bbox_to_anchor=(0.0, 1.0))
    for text in legend.get_texts():
        text.set_color(INK_MUTED)

    # --- Charts 2 and 3: one measure per axis. Volume and rate are never
    # plotted against two y-scales on a shared plot: the alignment of the two
    # scales would be arbitrary and would imply a correlation the data does
    # not contain. Two charts share one x category order instead. ---
    months = monthly_volume["month_name"].tolist()
    splits = {"August": "train", "September": "calibration", "October": "test"}
    month_labels = [f"{m}\n{splits.get(m, '')}" for m in months]

    ax_vol = fig.add_axes((0.06, 0.315, 0.40, 0.175))
    counts = monthly_volume["loan_count"]
    ax_vol.bar(months, counts, 0.55, color=COBALT, linewidth=0)
    for month, value in zip(months, counts):
        ax_vol.text(month, value + max(counts) * 0.03, f"{value:,.0f}", ha="center",
                    va="bottom", fontsize=7.5, color=INK, fontweight="bold")
    ax_vol.set_ylim(0, max(counts) * 1.25)
    ax_vol.set_xticks(range(len(months)))
    ax_vol.set_xticklabels(month_labels, fontsize=8, color=INK)
    _style_axes(ax_vol, "Loans originated")
    ax_vol.set_title("Monthly origination volume", fontsize=10, fontweight="bold",
                     color=INK, loc="left", pad=8)

    ax_rate = fig.add_axes((0.555, 0.315, 0.385, 0.175))
    rates = monthly_volume["observed_default_rate"] * 100
    ax_rate.plot(months, rates, marker="o", markersize=6, linewidth=2,
                 color=REFUSAL, markerfacecolor=REFUSAL, markeredgecolor=PAPER,
                 markeredgewidth=1.5)
    for month, value in zip(months, rates):
        ax_rate.text(month, value + 0.55, f"{value:.1f}%", ha="center", va="bottom",
                     fontsize=7.5, color=INK, fontweight="bold")
    ax_rate.set_ylim(0, max(rates) * 1.35)
    ax_rate.set_xticks(range(len(months)))
    ax_rate.set_xticklabels(month_labels, fontsize=8, color=INK)
    _style_axes(ax_rate, "Observed first-EMI default %")
    ax_rate.set_title("Monthly observed first-EMI default rate", fontsize=10,
                      fontweight="bold", color=INK, loc="left", pad=8)

    # --- Table view: the WCAG-clean twin of every figure above. ---
    fig.text(0.06, 0.245, "Policy-band table view  -  every plotted value, exactly as evaluated",
             fontsize=10, fontweight="bold", color=INK)
    ax_table = fig.add_axes((0.06, 0.075, 0.88, 0.155))
    ax_table.axis("off")
    table_data = policy_kpis[[
        "band", "risk_threshold", "approval_rate", "observed_default_rate",
        "manual_review_rate", "estimated_net_contribution_inr_cr",
    ]].copy()
    table_data["band"] = table_data["band"].str.title()
    table_data["risk_threshold"] = (table_data["risk_threshold"] * 100).map("{:.1f}%".format)
    table_data["approval_rate"] = (table_data["approval_rate"] * 100).map("{:.2f}%".format)
    table_data["observed_default_rate"] = (table_data["observed_default_rate"] * 100).map("{:.2f}%".format)
    table_data["manual_review_rate"] = (table_data["manual_review_rate"] * 100).map("{:.2f}%".format)
    # Match the workbench currency format exactly: the minus sign precedes the
    # currency symbol, and `cr` (crore) is always written out, never `m`.
    table_data["estimated_net_contribution_inr_cr"] = table_data["estimated_net_contribution_inr_cr"].map(
        lambda value: f"{'−' if value < 0 else ''}₹{abs(value):.2f} cr"
    )
    table_data.columns = [
        "Band", "Risk threshold", "Approval rate", "Observed default rate",
        "Manual-review rate", "Est. net contribution",
    ]
    table = ax_table.table(cellText=table_data.values, colLabels=table_data.columns,
                           loc="upper center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.55)
    for (row, _col), cell in table.get_celld().items():
        cell.set_edgecolor(RULE)
        cell.set_linewidth(0.6)
        if row == 0:
            cell.set_text_props(fontweight="bold", color=INK)
            cell.set_facecolor("#eef1f5")
        else:
            cell.set_text_props(color=INK)
            cell.set_facecolor(PAPER)

    fig.text(
        0.06, 0.032,
        "Assumptions behind estimated net contribution: 12% contribution rate on approved ₹ disbursed, 65% loss severity on defaulted ₹. "
        "These are editable sensitivity inputs, not observed results.",
        fontsize=7, color=INK_MUTED,
    )
    fig.text(
        0.06, 0.014,
        "Source: artifacts/strategy_summary.json + sql/kpi_monthly.sql over data/quarantine/loans.db (SQLite). "
        "A one-page rollup; per-loan detail lives in the KPI dashboard. Metric definitions: docs/metric-glossary.md.",
        fontsize=7, color=INK_MUTED,
    )
    fig.savefig(path, facecolor=PAPER)
    plt.close(fig)
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    policy_kpis = load_policy_kpis()
    monthly_volume = load_monthly_volume()
    csv_path = write_csv(policy_kpis)
    xlsx_path = write_excel(policy_kpis, monthly_volume)
    png_path = write_one_pager(policy_kpis, monthly_volume)
    for path in (csv_path, xlsx_path, png_path):
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
