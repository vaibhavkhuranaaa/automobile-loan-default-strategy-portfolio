import { useApi } from "../api.js";
import { ColumnChart, DataTable, Figure, LineChart, PALETTE } from "../charts.jsx";
import { count, crore, index, points, pointsDelta, rate } from "../format.js";
import { Async, Empty, Stat, StatRow, TechStack } from "../ui.jsx";
import { STACK, STACK_NOTE } from "../stack.js";

export default function Portfolio({ onNavigate }) {
  const state = useApi("/api/analytics/overview", []);

  return (
    <Async state={state} label="Loading the portfolio summary">
      {(data) => {
        const { portfolio, vintages, model } = data;
        if (!portfolio || !model || !vintages?.length) {
          return <Empty title="No portfolio summary is available."><p>Try again after the analytical store has been rebuilt.</p></Empty>;
        }
        const worst = vintages.reduce((a, b) => (b.observedDefaultRate > a.observedDefaultRate ? b : a));
        const best = vintages.reduce((a, b) => (b.observedDefaultRate < a.observedDefaultRate ? b : a));
        const swing = worst.observedDefaultRate - best.observedDefaultRate;

        return (
          <>
            <StatRow>
              <Stat label="Loans in the book" value={count(portfolio.loans)} sub="August to October 2018" />
              <Stat label="Disbursed" value={crore(portfolio.exposureInr)} sub={`${crore(portfolio.defaultedExposureInr)} of it to loans that missed the first EMI`} />
              <Stat label="First-EMI default" value={rate(portfolio.observedDefaultRate)} sub="Observed outcome, not a prediction" />
              <Stat label="No bureau history" value={rate(portfolio.thinFileShare)} sub="The largest single segment in the book" />
            </StatRow>

            <section className="panel">
              <div className="panel-head">
                <h2>Vintage outcome exception</h2>
                <p>
                  Volume and mix barely move across the three months, but the first-EMI default rate swings{" "}
                  {pointsDelta(swing)} between {best.month} and {worst.month}. A policy calibrated on the
                  quiet month meets a different book in the loud one, which is what the{" "}
                  <button type="button" className="link" onClick={() => onNavigate("monitoring")}>monitoring view</button>{" "}
                  exists to catch.
                </p>
              </div>

              <div className="figure-pair">
                <Figure
                  question="Monthly originations"
                  units="Loans originated"
                  source="fact_loan, all 233,154 records"
                >
                  <ColumnChart
                    data={vintages.map((v) => ({
                      label: v.month,
                      value: v.loans,
                      sublabel: v.clean ? "held out" : "model fitted",
                      tip: `${count(v.loans)} loans, ${crore(v.exposureInr)} disbursed`,
                    }))}
                    format={(value) => (value >= 1000 ? `${Math.round(value / 1000)}k` : count(value))}
                    ariaLabel="Loans originated per month"
                  />
                </Figure>

                <Figure
                  question="Monthly first-EMI default"
                  units="Share of that month's loans, percent"
                  source="fact_loan.loan_default, the verified outcome"
                  note="Measured outcome for every month. No model is involved in this chart."
                >
                  <LineChart
                    series={[{
                      label: "Observed first-EMI default",
                      color: PALETTE.primary,
                      points: vintages.map((v, i) => ({ x: i, y: v.observedDefaultRate * 100, tick: v.month, label: v.month })),
                    }]}
                    xDomain={[0, vintages.length - 1]}
                    xFormat={(x) => vintages[Math.round(x)]?.month ?? ""}
                    yFormat={(y) => `${y.toFixed(0)}%`}
                    ariaLabel="Observed first-EMI default rate by month"
                  />
                </Figure>
              </div>

              <DataTable
                caption="Every month, measured directly from the loan store"
                columns={[
                  { key: "month", label: "Month" },
                  { key: "role", label: "Role", render: (r) => (r.clean ? "Held-out test" : r.split === "train" ? "Model fitted here" : "Calibrator fitted here") },
                  { key: "loans", label: "Loans", render: (r) => count(r.loans) },
                  { key: "exposure", label: "Disbursed", render: (r) => crore(r.exposureInr) },
                  { key: "observed", label: "First-EMI default", render: (r) => rate(r.observedDefaultRate) },
                  { key: "ltv", label: "Average LTV", render: (r) => points(r.averageLtv) },
                  { key: "thin", label: "No bureau history", render: (r) => rate(r.thinFileShare) },
                ]}
                rows={vintages.map((v) => ({ ...v, key: v.month }))}
              />
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>Model standing</h2>
                <p>
                  These are the published evaluation figures, measured once on the held-out October month and
                  quoted here rather than recomputed. The model ranks risk usefully and prices it imperfectly;
                  both halves of that matter to a policy decision.
                </p>
              </div>
              <StatRow>
                <Stat label="AUROC" value={model.auroc.toFixed(3)} sub={`Logistic baseline reaches ${model.baselineAuroc.toFixed(3)}. Published work on this dataset tops out near 0.68.`} />
                <Stat label="Brier score" value={model.brier.toFixed(3)} sub={`Against ${model.baselineBrier.toFixed(3)} at baseline. Lower is better.`} />
                <Stat label="Calibration error" value={model.ece.toFixed(3)} sub="Average gap between predicted and observed default across score deciles." />
                <Stat label="Features" value={index(model.featureCount)} sub="Protected attributes, identifiers and post-origination fields excluded." />
              </StatRow>
              <p className="aside">
                The calibration error is not a rounding detail. Predicted risk sits below observed risk in
                every decile of the holdout, so a forward projection built on the predicted rate reads
                too kind.{" "}
                <button type="button" className="link" onClick={() => onNavigate("monitoring")}>See where it breaks.</button>
              </p>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>Implementation record</h2>
                <p>Supporting delivery stack. This section is secondary to the portfolio evidence and policy decision.</p>
              </div>
              <TechStack stack={STACK} note={STACK_NOTE} />
            </section>
          </>
        );
      }}
    </Async>
  );
}
