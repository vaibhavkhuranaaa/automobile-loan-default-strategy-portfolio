import { useApi } from "../api.js";
import { DataTable, Figure, Legend, LineChart, MiniLine, PALETTE } from "../charts.jsx";
import { count, psi, psiVerdict, rate, signedPoints } from "../format.js";
import { Async, Empty, Stat, StatRow } from "../ui.jsx";
import { evidence } from "../data.js";

export default function Monitoring() {
  const state = useApi("/api/analytics/stability", []);

  return (
    <Async state={state} label="Loading monitoring">
      {(data) => {
        if (!data.mix?.length || !data.calibration?.points?.length || !data.bandChecks?.bands?.length) {
          return <Empty title="No monitoring evidence is available."><p>Retry after the stability and calibration tables have been rebuilt.</p></Empty>;
        }
        const worstPsi = Math.max(...data.mix.flatMap((d) => d.months.map((m) => m.psi)));
        const verdict = psiVerdict(worstPsi);
        const gaps = data.calibration.points.map((p) => p.gap);
        const meanGap = gaps.reduce((a, b) => a + b, 0) / gaps.length;
        const allUnder = gaps.every((gap) => gap > 0);
        const conservative = data.bandChecks.bands[0];
        const drift = evidence.calibrationDrift;

        return (
          <>
            <div className="panel-head">
              <h2>Control scope</h2>
              <p>
                Review population stability and the gap between predicted and observed risk. The October
                holdout is the only period with a valid calibration comparison.
              </p>
            </div>

            <StatRow>
              <Stat label="Population stability" value={psi(worstPsi)} tone={verdict.tone} sub={`${verdict.label}. Largest shift across every characteristic and month.`} />
              <Stat label="Calibration gap" value={signedPoints(meanGap)} tone="alert" sub={`Mean gap across the ten deciles. ${rate(evidence.calibrationDrift.share_of_error_from_base_rate)} of it is base-rate drift, not model error.`} />
              <Stat label="Deciles under-predicted" value={`${gaps.filter((g) => g > 0).length} of ${gaps.length}`} tone={allUnder ? "alert" : undefined} sub="Where observed default came in above what the model predicted." />
              <Stat label="Conservative band" value={signedPoints(conservative.gap)} tone="alert" sub={`Predicted ${rate(conservative.predictedDefaultRate)}, observed ${rate(conservative.observedDefaultRate)} on the admitted book.`} />
            </StatRow>

            <section className="panel finding">
              <h3>The model under-predicts risk in every decile of the holdout</h3>
              <p>
                Observed default lands above predicted default in all ten deciles, by {signedPoints(Math.min(...gaps))} to{" "}
                {signedPoints(Math.max(...gaps))}. This is not noise in one bucket; it is a level shift across
                the whole score range, and it is the published calibration error of {evidence.metrics.ece} seen
                from the side.
              </p>
              <p>
                The cause is visible in the vintages, and it is measurable. The isotonic calibrator was
                fitted on September, which defaulted at {rate(drift.calibration_month_default_rate)}, and
                applied to October, which defaulted at {rate(drift.test_month_default_rate)}. Mean predicted
                risk on October is {rate(drift.mean_predicted)}, which is September's rate almost exactly:
                the calibrator carried the wrong month's prior.
              </p>
              <p>
                Rescaling the predicted odds by a single factor of {drift.odds_factor} so their mean matches
                October drops decile calibration error from {drift.ece_published} to{" "}
                <strong>{drift.ece_after_prior_shift}</strong>. One parameter, applied uniformly, cannot
                change the ranking or the shape of the curve, so{" "}
                <strong>{rate(drift.share_of_error_from_base_rate)} of the calibration error is base-rate
                drift</strong> rather than the model mis-shaping risk. That is a recalibration problem, not
                a retraining one.
              </p>
              <p className="aside">
                This correction uses October's own base rate, which nobody knows in advance, so it is a
                diagnostic rather than a deployable adjustment. Refitting the calibrator on the month being
                scored would not be time-safe and is not done here. In production the same one-parameter
                shift is fitted on the most recent closed month, and this figure is the ceiling on what that
                would recover.
              </p>
            </section>

            <div className="figure-pair">
              <Figure
                question="Calibration by score decile"
                units="First-EMI default rate, percent"
                source="98,364 October loans in ten score deciles"
                note="Perfect calibration would put the two lines on top of each other. The observed line sitting above the predicted line everywhere is a level bias, not scatter."
              >
                <LineChart
                  series={[
                    { label: "Observed", color: PALETTE.primary, points: data.calibration.points.map((p) => ({ x: p.decile, y: p.observedDefaultRate * 100, tick: String(p.decile), label: `Decile ${p.decile}` })) },
                    { label: "Predicted", color: PALETTE.secondary, points: data.calibration.points.map((p) => ({ x: p.decile, y: p.meanPredicted * 100, tick: String(p.decile), label: `Decile ${p.decile}` })) },
                  ]}
                  xDomain={[1, 10]}
                  xFormat={(x) => String(Math.round(x))}
                  yFormat={(y) => `${y.toFixed(0)}%`}
                  xLabel="Score decile, safest to riskiest"
                  ariaLabel="Predicted against observed default rate by decile"
                />
                <Legend items={[
                  { label: "Observed", color: PALETTE.primary },
                  { label: "Predicted", color: PALETTE.secondary },
                ]} />
              </Figure>

              <Figure
                question="Population stability by characteristic"
                units="Population Stability Index against the August baseline"
                source="All 233,154 loans, by characteristic and month"
                note="Below 0.10 is stable, 0.10 to 0.25 a moderate shift, above 0.25 material. No model is involved: this compares the book's composition with itself."
              >
                <div className="mini-grid">
                  {data.mix.map((dimension) => {
                    const latest = dimension.months[dimension.months.length - 1];
                    const dimensionVerdict = psiVerdict(latest.psi);
                    return (
                      <div className="mini-panel" key={dimension.key}>
                        <p className="mini-title">{dimension.label}</p>
                        <MiniLine
                          points={dimension.months.map((m) => ({ label: m.month.slice(0, 3), y: m.psi }))}
                          format={psi}
                          threshold={0.1}
                          ariaLabel={`Population stability index for ${dimension.label}`}
                        />
                        <p className={`mini-verdict ${dimensionVerdict.tone}`}>{dimensionVerdict.label}</p>
                      </div>
                    );
                  })}
                </div>
              </Figure>
            </div>

            <section className="panel">
              <div className="panel-head">
                <h3>Band calibration exception</h3>
                <p>
                  For the loans each cut-off admits: the default rate the model predicted for them, and the
                  rate they actually ran at. The gap is what a business case built on predictions would have
                  missed.
                </p>
              </div>
              <DataTable
                open
                caption="Predicted against observed default on the admitted book, October holdout"
                columns={[
                  { key: "label", label: "Band" },
                  { key: "threshold", label: "Cut-off", render: (r) => rate(r.threshold, true) },
                  { key: "loans", label: "Admitted", render: (r) => count(r.loans) },
                  { key: "pred", label: "Predicted default", render: (r) => rate(r.predictedDefaultRate) },
                  { key: "obs", label: "Observed default", render: (r) => rate(r.observedDefaultRate) },
                  { key: "gap", label: "Gap", render: (r) => <span className="alert">{signedPoints(r.gap)}</span> },
                ]}
                rows={data.bandChecks.bands.map((b) => ({ ...b, key: b.key }))}
              />
              <p className="aside">
                The published net-contribution figures are computed from observed defaults, not predicted
                ones, so this gap does not move them. It moves anything you would project onto a future book.
              </p>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h3>Evidence limitations</h3>
                <p>
                  Four properties of the label and the window that bear on every number in this product.
                  They are limits of the source, not defects in the analysis, and none of them can be
                  fixed with more modelling.
                </p>
              </div>
              <dl className="caveats">
                <div>
                  <dt>The label is not purely credit risk</dt>
                  <dd>{evidence.labelCaveats.operational_contamination}</dd>
                </div>
                <div>
                  <dt>Loss severity is charged against the wrong event</dt>
                  <dd>{evidence.labelCaveats.loss_severity_mismatch}</dd>
                </div>
                <div>
                  <dt>Three months of one quarter, in festival season</dt>
                  <dd>{evidence.labelCaveats.seasonality}</dd>
                </div>
                <div>
                  <dt>The scores rank, they do not price</dt>
                  <dd>{evidence.labelCaveats.calibration_currency}</dd>
                </div>
              </dl>
            </section>

            <DataTable
              caption={`Population stability by characteristic, against ${data.referenceMonth}`}
              columns={[
                { key: "dimension", label: "Characteristic" },
                { key: "month", label: "Month" },
                { key: "psi", label: "PSI", render: (r) => (r.isReference ? "baseline" : psi(r.psi)) },
                { key: "verdict", label: "Reading", render: (r) => (r.isReference ? "Reference month" : psiVerdict(r.psi).label) },
              ]}
              rows={data.mix.flatMap((dimension) => dimension.months.map((m) => ({
                key: `${dimension.key}-${m.month}`,
                dimension: dimension.label,
                month: m.month,
                psi: m.psi,
                isReference: m.isReference,
              })))}
            />
          </>
        );
      }}
    </Async>
  );
}
