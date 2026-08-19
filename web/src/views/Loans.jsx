import { useEffect, useState } from "react";
import { get, useApi } from "../api.js";
import { count, lakh, ordinal, points, rate, rupees, score } from "../format.js";
import { Async, Empty, ErrorState, Field, Loading, Provenance, Segmented, Stat, StatRow } from "../ui.jsx";

const PRESETS = [
  { key: "riskiest", label: "Riskiest scored", blurb: "Where the model is most confident of trouble." },
  { key: "surprises", label: "Low score, still defaulted", blurb: "The loans the model got most wrong. Worth reading before trusting a cut-off." },
  { key: "thin", label: "No bureau history", blurb: "Half the book. No credit file to lean on." },
  { key: "borderline", label: "Around the conservative cut-off", blurb: "The manual-review straddle, where an underwriter's time actually goes." },
];

const VERDICT_TONE = { Admit: "good", Refer: "watch", Decline: "alert" };

function buildQuery(preset) {
  return `/api/analytics/loans?preset=${encodeURIComponent(preset.key)}`;
}

function LoanDetail({ recordRef, onClose }) {
  const [state, setState] = useState({ data: null, error: null });

  useEffect(() => {
    let live = true;
    setState({ data: null, error: null });
    get(`/api/analytics/loans/${recordRef}`)
      .then((data) => live && setState({ data, error: null }))
      .catch((error) => live && setState({ data: null, error: error.message }));
    return () => { live = false; };
  }, [recordRef]);

  if (state.error) return <ErrorState message={state.error} />;
  if (!state.data) return <Loading label={`Loading record ${recordRef}`} />;

  const { loan, riskPercentile, bandVerdicts, peers } = state.data;
  const peerDelta = peers.observedDefaultRate - peers.vintageDefaultRate;

  return (
    <section className="detail" aria-labelledby="detail-title">
      <header className="detail-head">
        <div>
          <p className="detail-eyebrow">Record {loan.recordRef}</p>
          <h3 id="detail-title">{lakh(loan.disbursedAmountInr)} at {points(loan.ltv)} LTV</h3>
          <p>
            {loan.month} 2018 vintage. {loan.employmentType}.{" "}
            {loan.hasBureauHistory ? `Bureau score ${Math.round(loan.bureauScore)}.` : "No bureau history."}
          </p>
        </div>
        <button type="button" className="ghost" onClick={onClose}>Close</button>
      </header>

      <StatRow>
        <Stat label="Predicted risk" value={score(loan.riskScore)} sub={riskPercentile == null ? "Not scored" : `${ordinal(riskPercentile)} percentile of its month, riskiest last.`} />
        <Stat
          label="What happened"
          value={loan.defaulted ? "Missed the first EMI" : "Paid the first EMI"}
          tone={loan.defaulted ? "alert" : "good"}
          sub="The verified outcome in the source."
        />
        <Stat label="Asset cost" value={rupees(loan.assetCostInr)} sub={`Financed ${points((loan.disbursedAmountInr / loan.assetCostInr) * 100)} of it.`} />
        <Stat label="Loans like this one" value={rate(peers.observedDefaultRate)} sub={`Against ${rate(peers.vintageDefaultRate)} for the month overall.`} />
      </StatRow>

      <div className="detail-grid">
        <div>
          <h4>What each evaluated band would have done</h4>
          <ul className="verdicts">
            {bandVerdicts.map((verdict) => (
              <li key={verdict.key}>
                <span className={`verdict ${VERDICT_TONE[verdict.verdict]}`}>{verdict.verdict}</span>
                <div>
                  <strong>{verdict.label}</strong>
                  <span>Cut-off {rate(verdict.threshold, true)}. {verdict.explanation}</span>
                </div>
              </li>
            ))}
          </ul>
          <p className="aside">
            A referral outranks an admission: a loan inside the review straddle is one an underwriter opens,
            whichever side of the cut-off it sits on.
          </p>
        </div>
        <div>
          <h4>How its peers performed</h4>
          <p>
            {count(peers.loans)} loans in the same month share this loan's loan-to-value band and bureau
            coverage. They defaulted at {rate(peers.observedDefaultRate)}, which is{" "}
            {Math.abs(peerDelta * 100).toFixed(1)} points {peerDelta >= 0 ? "above" : "below"} the month.
          </p>
          <p className="aside">{peers.basis} This is the observed rate for a comparable group, not a second
            prediction for this loan.</p>
          <h4>Record boundary</h4>
          <p className="aside">The public reference is random and release-specific. Source identifiers, precise location, and operational codes are not returned.</p>
        </div>
      </div>
    </section>
  );
}

export default function Loans() {
  const [presetKey, setPresetKey] = useState("riskiest");
  const [lookup, setLookup] = useState("");
  const [selected, setSelected] = useState(null);
  const preset = PRESETS.find((p) => p.key === presetKey);
  const state = useApi(buildQuery(preset), [presetKey]);

  const submitLookup = (event) => {
    event.preventDefault();
    const recordRef = lookup.trim().toUpperCase();
    if (/^VL-[0-9A-F]{12}$/.test(recordRef)) setSelected(recordRef);
  };

  return (
    <>
      <div className="panel-head">
        <h2>Review scope</h2>
        <p>
          Open one retrospective record, inspect its score and band treatment, then compare the observed
          outcome with similar loans. This schedule does not make an applicant decision.
        </p>
      </div>

      <div className="control-row split">
        <Segmented
          label="Loan shortlist"
          options={PRESETS.map((p) => ({ value: p.key, label: p.label }))}
          value={presetKey}
          onChange={(value) => { setPresetKey(value); setSelected(null); }}
        />
        <form className="lookup" onSubmit={submitLookup}>
          <Field label="Open a record by reference">
            <input
              type="text" value={lookup} placeholder="e.g. VL-3F2A90C81D74"
              onChange={(event) => setLookup(event.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ""))}
            />
          </Field>
          <button type="submit" disabled={!/^VL-[0-9A-F]{12}$/.test(lookup.trim().toUpperCase())}>Open</button>
        </form>
      </div>
      <p className="lede">{preset.blurb}</p>

      {selected != null && <LoanDetail recordRef={selected} onClose={() => setSelected(null)} />}

      <Async state={state} label="Loading loans">
        {(data) => (
          data.rows.length === 0 ? (
            <Empty title="No loans match that shortlist.">
              <p>Pick another shortlist above, or open a record by its displayed reference.</p>
            </Empty>
          ) : (
            <>
              <Provenance provenance={data.provenance} />
              <p className="result-note">
                {count(data.total)} loans match. Showing the first {data.rows.length}, ordered by the
                shortlist. Select a row to open it.
              </p>
              <p className="table-scroll-hint">Scroll horizontally to see all columns.</p>
              <div className="table-scroll" tabIndex="0" role="region" aria-label="Loans matching the selected shortlist table">
                <table className="loan-table">
                  <caption className="visually-hidden">Loans matching the selected shortlist</caption>
                  <thead>
                    <tr>
                      <th scope="col">Record</th>
                      <th scope="col" className="numeric">Predicted risk</th>
                      <th scope="col" className="numeric">Disbursed</th>
                      <th scope="col" className="numeric">LTV</th>
                      <th scope="col" className="numeric">Bureau</th>
                      <th scope="col">Employment</th>
                      <th scope="col">Outcome</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rows.map((row) => (
                      <tr key={row.recordRef} className={selected === row.recordRef ? "selected" : undefined}>
                        <td>
                          <button type="button" className="link" onClick={() => setSelected(row.recordRef)}>
                            {row.recordRef}
                          </button>
                        </td>
                        <td className="numeric">{score(row.riskScore)}</td>
                        <td className="numeric">{lakh(row.disbursedAmountInr)}</td>
                        <td className="numeric">{points(row.ltv)}</td>
                        <td className="numeric">{row.hasBureauHistory ? Math.round(row.bureauScore) : "None"}</td>
                        <td>{row.employmentType}</td>
                        <td>
                          <span className={row.defaulted ? "outcome alert" : "outcome good"}>
                            {row.defaulted ? "Defaulted" : "Paid"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )
        )}
      </Async>
    </>
  );
}
