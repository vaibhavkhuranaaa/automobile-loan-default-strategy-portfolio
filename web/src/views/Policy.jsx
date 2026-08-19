import { useMemo, useState } from "react";
import { evidence } from "../data.js";
import { DataTable, Figure } from "../charts.jsx";
import { count, crore, points, rate, rupees } from "../format.js";
import { Field, Stat, StatRow } from "../ui.jsx";

const PUBLISHED = {
  contributionRate: evidence.assumptions.contributionRate * 100,
  lossSeverity: evidence.assumptions.lossSeverity * 100,
  reviewCost: evidence.assumptions.reviewCostInr,
};

const INPUTS = [
  { key: "contributionRate", label: "Contribution rate", unit: "per ₹ disbursed", min: 0, max: 25, step: 0.5, format: (v) => `${v.toFixed(1)}%`, hint: "Analyst input. No lender published this." },
  { key: "lossSeverity", label: "Loss severity", unit: "on defaulted ₹", min: 0, max: 100, step: 1, format: (v) => `${v.toFixed(0)}%`, hint: "Analyst input. No lender published this." },
  { key: "reviewCost", label: "Manual review cost", unit: "per referral", min: 0, max: 5000, step: 100, format: rupees, hint: "Placeholder. This one has no source at all." },
];

// Contribution is exactly linear in the three assumptions, because the risk
// cut-off does not move when the economics do. So the workbench reproduces the
// published arithmetic from three per-band totals rather than re-scoring 98,364
// loans in the browser.
const evaluate = (policy, { contributionRate, lossSeverity, reviewCost }) => {
  const gross = policy.approvedAmountInr * (contributionRate / 100);
  const creditLoss = policy.defaultedAmountInr * (lossSeverity / 100);
  const reviewSpend = policy.reviewCount * reviewCost;
  return { gross, creditLoss, reviewSpend, net: gross - creditLoss - reviewSpend };
};

const leaderOf = (scored) => scored.reduce((best, candidate) => (candidate.net > best.net ? candidate : best));
const near = (a, b) => Math.abs(a - b) < 1e-9;

const SENSITIVITY = evidence.sensitivityAxes.reviewCostInr.map((reviewCost) => ({
  reviewCost,
  rows: evidence.sensitivityAxes.contributionRate.map((contributionRate) => ({
    contributionRate,
    cells: evidence.sensitivityAxes.lossSeverity.map((lossSeverity) => {
      const at = { contributionRate: contributionRate * 100, lossSeverity: lossSeverity * 100, reviewCost };
      const best = leaderOf(evidence.policies.map((p) => ({ key: p.key, label: p.label, net: evaluate(p, at).net })));
      return { lossSeverity, best, anyPositive: best.net > 0 };
    }),
  })),
}));
const CELLS = SENSITIVITY.flatMap((b) => b.rows.flatMap((r) => r.cells));
const WINS = CELLS.filter((c) => c.best.key === "conservative").length;
const NONE_POSITIVE = CELLS.filter((c) => !c.anyPositive).length;

const breakevenText = (value, format, max) =>
  Number.isFinite(value) && value >= 0 && value <= max ? format(value) : "Not reachable";

function memo(band, assumptions, capacity, result) {
  const interval = band.netContributionRangeInr;
  return [
    `POLICY ASSESSMENT FOR GOVERNANCE REVIEW`,
    ``,
    `Band:                 ${band.label} (risk cut-off ${band.threshold})`,
    `Admitted share:       ${band.approval} of the October 2018 holdout`,
    `Loans admitted:       ${count(band.approvedCount)} of ${count(evidence.testApplicants)}`,
    `Observed default:     ${band.defaultRate} among admitted loans`,
    `Manual review:        ${band.review} (${count(band.reviewCount)} referrals), capacity assumed ${capacity}%`,
    `Net contribution:     ${crore(result.net)} (estimated)`,
    `95% interval:         ${crore(interval[0])} to ${crore(interval[1])} at the published assumptions`,
    `Above zero in:        ${Math.round(band.positiveShare * 100)}% of holdout resamples`,
    `Standing:             ${band.decision}`,
    ``,
    `ASSUMPTIONS USED (all analyst inputs, none lender-sourced)`,
    `  Contribution rate:  ${assumptions.contributionRate.toFixed(1)}% per rupee disbursed`,
    `  Loss severity:      ${assumptions.lossSeverity.toFixed(0)}% of defaulted disbursal`,
    `  Manual review cost: ${rupees(assumptions.reviewCost)} per referral (placeholder, no source)`,
    ``,
    `OPERATIONAL SHARE TO BREAK EVEN`,
    `  Under a zero-loss cure scenario, ${band.label} clears zero if at least ${(() => { const v = result.operationalShare; return v <= 0 ? "none" : v < 1 ? `${(v * 100).toFixed(2)}%` : "an unreachable share"; })()} of its`,
    `  first-EMI misses are operational rather than credit events. Compare this scenario with`,
    `  the lender's observed cure and loss experience; the source cannot measure either.`,
    ``,
    `ROBUSTNESS`,
    `  Across the ${CELLS.length} published assumption combinations, conservative ranks first in ${WINS}.`,
    `  In ${NONE_POSITIVE} of ${CELLS.length}, no band clears zero at all.`,
    `  The interval above covers sampling variation only, not the three assumptions.`,
    ``,
    `LIMITATIONS THAT BEAR ON THIS RECOMMENDATION`,
    `  Label contamination. ${evidence.labelCaveats.operational_contamination}`,
    ``,
    `  Loss severity. ${evidence.labelCaveats.loss_severity_mismatch}`,
    ``,
    `  Seasonality and window. ${evidence.labelCaveats.seasonality}`,
    ``,
    `  Calibration. ${evidence.labelCaveats.calibration_currency}`,
    ``,
    `  Distributional effect. Approval rates differ sharply by state code under every band;`,
    `  see the fairness view. No protected attribute exists in the source, so this is`,
    `  impact reporting and not a fair-lending opinion.`,
    ``,
    `  This is an aggregate portfolio assessment. It is not an approval, decline, or price.`,
    ``,
    `Generated from the policy workbench. Figures reproduce artifacts/strategy_summary.json.`,
  ].join("\n");
}

export default function Policy() {
  const [selectedKey, setSelectedKey] = useState("conservative");
  const [assumptions, setAssumptions] = useState(PUBLISHED);
  const [capacity, setCapacity] = useState(20);
  const [scenarios, setScenarios] = useState([]);
  const [name, setName] = useState("");

  const atPublished = INPUTS.every(({ key }) => near(assumptions[key], PUBLISHED[key]));

  const computed = useMemo(() => evidence.policies.map((policy) => {
    const { gross, creditLoss, reviewSpend, net } = evaluate(policy, assumptions);
    const reviewRate = Number.parseFloat(policy.review);
    return {
      ...policy,
      net,
      reviewRate,
      capacityBreach: reviewRate > capacity,
      breakeven: {
        contributionRate: ((creditLoss + reviewSpend) / policy.approvedAmountInr) * 100,
        lossSeverity: ((gross - reviewSpend) / policy.defaultedAmountInr) * 100,
        reviewCost: (gross - creditLoss) / policy.reviewCount,
      },
      // The share of first-EMI misses that would have to be operational rather
      // than credit for this band to break even. If a mandate failed, the
      // borrower could and would have paid, so that loan carries no credit
      // loss and cures once the mandate is repaired. Setting
      //   net = gross − defaulted × (1 − share) × severity − review = 0
      // reduces to 1 − breakevenSeverity / severity, which is why this needs no
      // new evidence: it is the break-even severity read on a different axis.
      operationalShare: 1 - ((gross - reviewSpend) / policy.defaultedAmountInr) / (assumptions.lossSeverity / 100),
      defaultedLoans: Math.round(policy.approvedCount * (Number.parseFloat(policy.defaultRate) / 100)),
    };
  }), [assumptions, capacity]);

  const selected = computed.find((policy) => policy.key === selectedKey);
  const leader = leaderOf(computed);
  const noneClearZero = leader.net <= 0;

  const saveScenario = () => {
    const label = name.trim() || `Scenario ${scenarios.length + 1}`;
    setScenarios([...scenarios, {
      id: `${label}-${scenarios.length}`,
      label,
      band: selected.label,
      bandKey: selected.key,
      assumptions: { ...assumptions },
      capacity,
      net: selected.net,
      breach: selected.capacityBreach,
    }]);
    setName("");
  };

  const downloadMemo = () => {
    const blob = new Blob([memo(selected, assumptions, capacity, { net: selected.net, operationalShare: selected.operationalShare })], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `policy-memo-${selected.key}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="panel-head">
        <h2>Decision scope</h2>
        <p>
          Three risk cut-offs were evaluated on the October holdout. Select a band, set the economic and
          capacity assumptions, and record a governed recommendation or refusal. Aggregate portfolio use only.
        </p>
      </div>

      <section className="panel finding">
        <h3>No band clears zero at the published assumptions</h3>
        <p>
          The best of the three, {leader.label.toLowerCase()}, lands at {crore(leader.net)}, and resampling
          the holdout puts it above zero in only{" "}
          {Math.round((evidence.policies.find((item) => item.key === leader.key)?.positiveShare ?? 0) * 100)}% of
          draws. Across the {CELLS.length} published assumption combinations, no band clears zero in{" "}
          <strong>{NONE_POSITIVE}</strong> of them, and the winner changes in the rest.
        </p>
        <p>
          Treat the ranking as the finding and the rupee figure as an illustration. The three economic
          inputs are analyst estimates, one of them an unsourced placeholder, and the net result is a small
          difference between two much larger numbers built from them.
        </p>
      </section>

      <div className="band-picker" role="radiogroup" aria-label="Evaluated risk bands">
        {computed.map((policy) => (
          <button
            key={policy.key}
            type="button"
            role="radio"
            aria-checked={selectedKey === policy.key}
            tabIndex={selectedKey === policy.key ? 0 : -1}
            className={selectedKey === policy.key ? "band on" : "band"}
            onClick={() => setSelectedKey(policy.key)}
            onKeyDown={(event) => {
              const current = computed.findIndex((item) => item.key === selectedKey);
              const offset = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : ["ArrowLeft", "ArrowUp"].includes(event.key) ? -1 : 0;
              const next = event.key === "Home" ? 0 : event.key === "End" ? computed.length - 1 : (current + offset + computed.length) % computed.length;
              if (!offset && !["Home", "End"].includes(event.key)) return;
              event.preventDefault();
              setSelectedKey(computed[next].key);
              event.currentTarget.parentElement.children[next].focus();
            }}
          >
            <span className="band-name">{policy.label}</span>
            <strong>{policy.threshold}</strong>
            <span className="band-sub">highest risk admitted</span>
            <span className={policy.net < 0 ? "band-net negative" : "band-net positive"}>{crore(policy.net)}</span>
          </button>
        ))}
      </div>

      <section className="panel">
        <div className="panel-head row">
          <div>
            <h3>Economic assumptions</h3>
            <p>Move any one and every rupee figure recalculates. The ranking is not robust to them, which is the point of moving them.</p>
          </div>
          <button type="button" className="ghost" disabled={atPublished} onClick={() => setAssumptions(PUBLISHED)}>
            Reset to published
          </button>
        </div>
        <div className="sliders">
          {INPUTS.map((input) => (
            <label className="slider" key={input.key}>
              <span className="slider-head">
                <span className="slider-name">{input.label} <em>{input.unit}</em></span>
                <output>{input.format(assumptions[input.key])}</output>
              </span>
              <input
                type="range" min={input.min} max={input.max} step={input.step}
                value={assumptions[input.key]}
                onChange={(event) => setAssumptions({ ...assumptions, [input.key]: Number(event.target.value) })}
              />
              <span className="slider-hint">{input.hint} Published {input.format(PUBLISHED[input.key])}.</span>
            </label>
          ))}
          <label className="slider">
            <span className="slider-head">
              <span className="slider-name">Review capacity <em>share of applications</em></span>
              <output>{capacity}%</output>
            </span>
            <input type="range" min="0" max="100" step="1" value={capacity} onChange={(event) => setCapacity(Number(event.target.value))} />
            <span className="slider-hint">Operating limit, not an economic input. It flags a band, it does not change the money.</span>
          </label>
        </div>
      </section>

      <section className={noneClearZero ? "panel result refusal" : "panel result"} aria-live="polite">
        <div className="panel-head">
          <h3>
            {selected.capacityBreach ? "Capacity breach: revise before governance review"
              : noneClearZero ? "No band clears zero under these assumptions"
                : selected.net > 0 ? "Candidate for governance review"
                  : "Not recommended under these assumptions"}
          </h3>
          <p>
            {selected.capacityBreach
              ? `${selected.label} refers ${points(selected.reviewRate)} of applications for manual review, above the ${capacity}% your team can absorb.`
              : noneClearZero
                ? `The best of the three is ${leader.label.toLowerCase()} at ${crore(leader.net)}, so the honest recommendation is to advance none of them until an assumption is sourced.`
                : `Best under these assumptions is ${leader.label.toLowerCase()} at ${crore(leader.net)}.${selectedKey !== leader.key ? ` You have ${selected.label.toLowerCase()} selected.` : ""}`}
          </p>
          {!atPublished && (
            <p className="moved">
              These are your assumptions, not the published record. Published for {selected.label.toLowerCase()} is {crore(selected.netContributionInr)}.
            </p>
          )}
        </div>

        <StatRow>
          <Stat
            label="Estimated net contribution"
            value={crore(selected.net)}
            tone={selected.net < 0 ? "alert" : selected.positiveShare >= 0.95 ? "good" : "watch"}
            sub={atPublished
              ? `95% interval ${crore(selected.netContributionRangeInr[0])} to ${crore(selected.netContributionRangeInr[1])}, above zero in ${Math.round(selected.positiveShare * 100)}% of resamples.`
              : `Admitted ₹ × contribution − defaulted ₹ × severity − ${count(selected.reviewCount)} referrals × review cost.`}
          />
          <Stat label="Loans admitted" value={count(selected.approvedCount)} sub={`${selected.approval} of the October holdout.`} />
          <Stat label="Observed first-EMI default" value={selected.defaultRate} sub="Actual outcome among admitted loans." />
          <Stat label="Manual-review demand" value={selected.review} tone={selected.capacityBreach ? "alert" : undefined} sub={`${count(selected.reviewCount)} referrals, ${selected.capacityBreach ? "above" : "within"} the ${capacity}% assumption.`} />
        </StatRow>

        <div className="breakeven">
          <p className="breakeven-title">Where {selected.label.toLowerCase()} flips to zero</p>
          <dl>
            <div>
              <dt>Contribution rate</dt>
              <dd>{breakevenText(selected.breakeven.contributionRate, (v) => `${v.toFixed(1)}%`, 25)}</dd>
              <dd className="now">now {assumptions.contributionRate.toFixed(1)}%</dd>
            </div>
            <div>
              <dt>Loss severity</dt>
              <dd>{breakevenText(selected.breakeven.lossSeverity, (v) => `${v.toFixed(1)}%`, 100)}</dd>
              <dd className="now">now {assumptions.lossSeverity.toFixed(0)}%</dd>
            </div>
            <div>
              <dt>Review cost</dt>
              <dd>{breakevenText(selected.breakeven.reviewCost, rupees, 5000)}</dd>
              <dd className="now">now {rupees(assumptions.reviewCost)}</dd>
            </div>
          </dl>
          <p className="aside">Each figure moves one control and holds the other two. "Not reachable" means no setting of that slider alone flips the band.</p>
        </div>

        <div className="result-actions">
          <Field label="Name this scenario">
            <input type="text" value={name} placeholder={`${selected.label} at ${assumptions.contributionRate.toFixed(1)}%`} onChange={(event) => setName(event.target.value)} />
          </Field>
          <button type="button" onClick={saveScenario}>Save to compare</button>
          <button type="button" className="ghost" onClick={downloadMemo}>Download policy memo</button>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <h3>Operational-miss break-even requirement</h3>
          <p>
            This scenario asks how much of the first-EMI label would need to be operational rather than
            credit-related for each band to break even. It assumes an operational miss cures with zero
            credit loss. The source cannot identify operational misses, later cure, or realized loss, so
            this is an explicit break-even assumption to test with lender evidence, not an observed result.
          </p>
        </div>
        <p className="table-scroll-hint">Scroll horizontally to see all columns.</p>
        <div className="table-scroll" tabIndex="0" role="region" aria-label="Operational break-even requirements table">
          <table className="operational">
            <caption className="visually-hidden">Operational share required for each band to break even</caption>
            <thead>
              <tr>
                <th scope="col">Band</th>
                <th scope="col">Operational share needed</th>
                <th scope="col">Roughly</th>
                <th scope="col">Reading</th>
              </tr>
            </thead>
            <tbody>
              {computed.map((policy) => {
                const share = policy.operationalShare;
                const reachable = share < 1;
                const already = share <= 0;
                return (
                  <tr key={policy.key} className={policy.key === selectedKey ? "selected" : undefined}>
                    <td><strong>{policy.label}</strong></td>
                    <td className="numeric">
                      {already ? "none" : reachable ? rate(share) : "not reachable"}
                    </td>
                    <td className="numeric">
                      {already || !reachable ? "not applicable" : `${count(Math.round(policy.defaultedLoans * share))} of ${count(policy.defaultedLoans)} loans`}
                    </td>
                    <td>
                      {already
                        ? "Already clears zero at these assumptions."
                        : reachable
                          ? "Under the zero-loss cure assumption, clears zero at this operational share."
                          : "Loses money even if every first-EMI miss were operational."}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="aside">
          Read against the lender's observed first-presentation failure, cure, and loss experience. Nothing
          in this dataset separates an operational miss from a credit event or observes later cure, so the
          scenario frames the evidence needed to revisit the refusal rather than resolving it here.
        </p>
      </section>

      {scenarios.length > 0 && (
        <section className="panel">
          <div className="panel-head row">
            <div>
              <h3>Saved scenarios</h3>
              <p>Every combination you kept, side by side. Cleared when you leave the page.</p>
            </div>
            <button type="button" className="ghost" onClick={() => setScenarios([])}>Clear all</button>
          </div>
          <p className="table-scroll-hint">Scroll horizontally to see all columns.</p>
          <div className="table-scroll" tabIndex="0" role="region" aria-label="Saved policy scenarios table">
            <table className="compare">
              <caption className="visually-hidden">Saved policy scenarios</caption>
              <thead>
                <tr>
                  <th scope="col">Scenario</th><th scope="col">Band</th><th scope="col">Contribution</th>
                  <th scope="col">Severity</th><th scope="col">Review cost</th><th scope="col">Capacity</th>
                  <th scope="col">Net contribution</th>
                </tr>
              </thead>
              <tbody>
                {scenarios.map((scenario) => (
                  <tr key={scenario.id}>
                    <td>{scenario.label}</td>
                    <td>{scenario.band}{scenario.breach && <em className="alert"> capacity breach</em>}</td>
                    <td className="numeric">{scenario.assumptions.contributionRate.toFixed(1)}%</td>
                    <td className="numeric">{scenario.assumptions.lossSeverity.toFixed(0)}%</td>
                    <td className="numeric">{rupees(scenario.assumptions.reviewCost)}</td>
                    <td className="numeric">{scenario.capacity}%</td>
                    <td className={scenario.net < 0 ? "numeric alert" : "numeric good"}>{crore(scenario.net)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="panel">
        <div className="panel-head">
          <h3>Published band and sensitivity register</h3>
          <p>
            Net contribution moves with the sliders. Admitted share, observed default and review demand are
            measured on the holdout and never move. Conservative ranks first in {WINS} of the {CELLS.length}
            {" "}published combinations, and in {NONE_POSITIVE} of them no band clears zero at all. The second
            number is what makes the first one worth anything.
          </p>
        </div>

        <DataTable
          open
          caption="The three evaluated bands under the current assumptions"
          columns={[
            { key: "label", label: "Band" },
            { key: "threshold", label: "Cut-off" },
            { key: "approval", label: "Admitted" },
            { key: "defaultRate", label: "First-EMI default" },
            { key: "review", label: "Review demand", render: (r) => <>{r.review}{r.capacityBreach && <em className="alert"> breach</em>}</> },
            { key: "net", label: "Net contribution", render: (r) => <span className={r.net < 0 ? "alert" : "good"}>{crore(r.net)}{r.key === leader.key && !noneClearZero && <em> ranks first</em>}</span> },
            { key: "interval", label: "95% interval", render: (r) => (atPublished
              ? <span className="interval">{crore(r.netContributionRangeInr[0])} to {crore(r.netContributionRangeInr[1])}</span>
              : <span className="interval muted">published only</span>) },
          ]}
          rows={computed}
        />

        <Figure
          question="Winning band across the assumption grid"
          units={`Band with the highest net contribution at each of the ${CELLS.length} published combinations`}
          source="artifacts/strategy_summary.json"
          note="Cells marked as all-negative name the least bad band, not a recommendation."
        >
          <p className="table-scroll-hint">Scroll horizontally to see all columns.</p>
          <div className="table-scroll" tabIndex="0" role="region" aria-label="Published assumption sensitivity table">
            <table className="grid">
              <caption className="visually-hidden">Sensitivity grid across the published assumption combinations</caption>
              <thead>
                <tr>
                  <th scope="col">Review cost</th>
                  <th scope="col">Contribution</th>
                  {evidence.sensitivityAxes.lossSeverity.map((severity) => (
                    <th scope="col" key={severity}>{Math.round(severity * 100)}% severity</th>
                  ))}
                </tr>
              </thead>
              {SENSITIVITY.map((block) => (
                <tbody key={block.reviewCost}>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={row.contributionRate}>
                      {rowIndex === 0 && <th scope="rowgroup" rowSpan={block.rows.length}>{rupees(block.reviewCost)}</th>}
                      <th scope="row">{Math.round(row.contributionRate * 100)}%</th>
                      {row.cells.map((cell) => {
                        const here = near(block.reviewCost, assumptions.reviewCost)
                          && near(row.contributionRate * 100, assumptions.contributionRate)
                          && near(cell.lossSeverity * 100, assumptions.lossSeverity);
                        return (
                          <td key={cell.lossSeverity} className={`${cell.anyPositive ? "positive-cell" : "negative-cell"}${here ? " here" : ""}`}>
                            <span>{cell.best.label}</span>
                            {!cell.anyPositive && <em>all three negative</em>}
                            {here && <em className="marker">your setting</em>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
          </div>
        </Figure>
      </section>
    </>
  );
}
