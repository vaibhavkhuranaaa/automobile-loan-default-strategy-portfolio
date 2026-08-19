import { useState } from "react";
import { evidence } from "../data.js";
import { useApi } from "../api.js";
import { ColumnChart, DataTable, DivergingBars, Figure, Legend, LineChart, PALETTE, RankedBars } from "../charts.jsx";
import { count, crore, index, rate, signedPoints } from "../format.js";
import { Async, Empty, Provenance, Segmented, Stat, StatRow } from "../ui.jsx";

const DIMENSION_OPTIONS = [
  { value: "branch", label: "Branch" },
  { value: "state", label: "State" },
  { value: "manufacturer", label: "Manufacturer" },
];

const PLURAL = { branch: "Branches", state: "States", manufacturer: "Manufacturers" };

function Deciles() {
  const state = useApi("/api/analytics/deciles?split=test", []);
  return (
    <Async state={state} label="Loading score deciles">
      {(data) => {
        if (!data.deciles?.length) {
          return <Empty title="No score deciles are available."><p>Retry after the held-out score table has been rebuilt.</p></Empty>;
        }
        const worst = data.deciles[data.deciles.length - 1];
        const best = data.deciles[0];
        // Read the gains curve from the risky end down: decline the worst N% of
        // the book and this much of its default goes with them.
        const gains = [...data.deciles]
          .sort((a, b) => b.decile - a.decile)
          .map((d) => ({
            x: d.cumulativeLoanShare * 100,
            y: d.cumulativeDefaultCapture * 100,
            label: `Worst ${(d.cumulativeLoanShare * 100).toFixed(0)}% of the book`,
            tick: `${(d.cumulativeLoanShare * 100).toFixed(0)}%`,
          }));

        return (
          <>
            <StatRow>
              <Stat label="KS statistic" value={data.ks.value.toFixed(3)} sub={`Widest separation between defaulters and payers, at decile ${data.ks.decile}.`} />
              <Stat label="Worst decile lift" value={`${worst.lift.toFixed(2)}×`} sub={`Defaults at ${rate(worst.observedDefaultRate)} against a book average of ${rate(data.baseDefaultRate)}.`} />
              <Stat label="Safest decile" value={rate(best.observedDefaultRate)} sub={`${best.lift.toFixed(2)}× the book average.`} />
              <Stat label="Capture in the worst fifth" value={rate(gains[1].y / 100)} sub="Share of all first-EMI defaults sitting in the riskiest 20% of loans." />
            </StatRow>

            <div className="figure-pair">
              <Figure
                question="Observed default by score decile"
                units="Observed first-EMI default, percent of each decile"
                source="98,364 October loans, ranked into ten equal groups"
                note="Decile 1 is the safest tenth, decile 10 the riskiest. The rise is monotonic across all ten, which is the property a policy cut-off depends on."
              >
                <ColumnChart
                  data={data.deciles.map((d) => ({
                    label: String(d.decile),
                    value: d.observedDefaultRate * 100,
                    tip: `${count(d.loans)} loans, ${count(d.defaults)} defaults, lift ${d.lift.toFixed(2)}×`,
                    color: d.observedDefaultRate > data.baseDefaultRate ? PALETTE.high : PALETTE.low,
                  }))}
                  format={(value) => `${value.toFixed(0)}%`}
                  valueLabels={false}
                  ariaLabel="Observed default rate by score decile"
                />
                <Legend items={[
                  { label: "Below the book average", color: PALETTE.low },
                  { label: "Above the book average", color: PALETTE.high },
                ]} />
              </Figure>

              <Figure
                question="Cumulative default capture"
                units="Cumulative share of all defaults captured, percent"
                source="Same 98,364 October loans, read from the riskiest decile down"
                note="The diagonal is what random declining would achieve. Distance above it is the model's contribution."
              >
                <LineChart
                  series={[{ label: "Model ranking", color: PALETTE.primary, points: gains }]}
                  xDomain={[0, 100]}
                  reference={{ from: { x: 0, y: 0 }, to: { x: 100, y: 100 }, label: "Random" }}
                  xFormat={(x) => `${x.toFixed(0)}%`}
                  yFormat={(y) => `${y.toFixed(0)}%`}
                  xLabel="Share of the book declined, worst first"
                  ariaLabel="Cumulative default capture against share of book declined"
                />
              </Figure>
            </div>

            <DataTable
              caption="Lift table for the October holdout"
              columns={[
                { key: "decile", label: "Decile" },
                { key: "loans", label: "Loans", render: (r) => count(r.loans) },
                { key: "range", label: "Predicted risk", render: (r) => `${rate(r.minPredicted)} to ${rate(r.maxPredicted)}` },
                { key: "pred", label: "Mean predicted", render: (r) => rate(r.meanPredicted) },
                { key: "obs", label: "Observed", render: (r) => rate(r.observedDefaultRate) },
                { key: "gap", label: "Gap", render: (r) => signedPoints(r.observedDefaultRate - r.meanPredicted) },
                { key: "lift", label: "Lift", render: (r) => `${r.lift.toFixed(2)}×` },
                { key: "exposure", label: "Disbursed", render: (r) => crore(r.exposureInr) },
              ]}
              rows={data.deciles.map((d) => ({ ...d, key: d.decile }))}
            />
          </>
        );
      }}
    </Async>
  );
}

function Segments() {
  const state = useApi("/api/analytics/segments?split=test", []);
  return (
    <Async state={state} label="Loading segment risk">
      {(data) => data.dimensions?.length ? (
        <>
          <p className="lede">
            An index of 100 is the October book average of {rate(data.baseDefaultRate)}. A segment at 120
            defaults a fifth more often than the book. These are the dimensions that carry business meaning;
            the source's branch, state and manufacturer identifiers are anonymised integers and appear under
            concentration instead, where a rank is all they can honestly support.
          </p>
          <div className="figure-grid">
            {data.dimensions.map((dimension) => (
              <Figure
                key={dimension.key}
                question={`${dimension.label}`}
                units="Risk index, 100 = book average"
                source={`${count(dimension.segments.reduce((sum, s) => sum + s.loans, 0))} October loans`}
              >
                <DivergingBars
                  data={dimension.segments.map((segment) => ({
                    label: segment.segment,
                    value: segment.riskIndex,
                    tip: `${count(segment.loans)} loans (${rate(segment.loanShare)} of the book), defaulting at ${rate(segment.observedDefaultRate)}`,
                  }))}
                  center={100}
                  format={index}
                  ariaLabel={`Risk index by ${dimension.label}`}
                />
                <DataTable
                  caption={`${dimension.label}: observed default and share`}
                  columns={[
                    { key: "segment", label: dimension.label },
                    { key: "loans", label: "Loans", render: (r) => count(r.loans) },
                    { key: "share", label: "Share", render: (r) => rate(r.loanShare) },
                    { key: "obs", label: "Default", render: (r) => rate(r.observedDefaultRate) },
                    { key: "idx", label: "Index", render: (r) => index(r.riskIndex) },
                  ]}
                  rows={dimension.segments.map((s) => ({ ...s, key: s.segment }))}
                />
              </Figure>
            ))}
          </div>
        </>
      ) : <Empty title="No segment results are available."><p>Retry after the segment-risk query has been rebuilt.</p></Empty>}
    </Async>
  );
}

function Concentration() {
  const [dimension, setDimension] = useState("branch");
  const state = useApi(`/api/analytics/concentration?dimension=${dimension}&split=all`, [dimension]);

  return (
    <Async state={state} label="Loading concentration">
      {(data) => data.ranking?.length ? (
        <>
          <div className="control-row">
            <Segmented label="Concentration dimension" options={DIMENSION_OPTIONS} value={dimension} onChange={setDimension} />
          </div>
          <StatRow>
            <Stat label={`${PLURAL[dimension]} in the book`} value={index(data.units)} sub="Units carrying at least one loan." />
            <Stat label="Top five share" value={rate(data.topFiveExposureShare)} sub="Share of all disbursal sitting in the five largest units." />
            <Stat label="Disbursed" value={crore(data.exposureInr)} sub="Across every vintage." />
            <Stat label="Book default rate" value={rate(data.baseDefaultRate)} sub="The line each unit below is measured against." />
          </StatRow>
          <Figure
            question="Disbursal concentration and observed risk"
            units="Share of total disbursal, percent"
            source={`${data.units} ${data.noun.toLowerCase()} units; the ${data.shown} largest shown`}
            note={`The source publishes no lookup for these identifiers, so the code is a key, not a name. Ranked by exposure they still answer the question that matters: concentration, and whether the big units run hot.`}
          >
            <RankedBars
              data={data.ranking.map((unit) => ({
                label: unit.label,
                value: unit.exposureShare * 100,
                color: unit.riskIndex > 110 ? PALETTE.high : PALETTE.primary,
                tip: `${count(unit.loans)} loans, ${crore(unit.exposureInr)}, defaulting at ${rate(unit.observedDefaultRate)} (index ${index(unit.riskIndex)})`,
              }))}
              format={(value) => `${value.toFixed(1)}%`}
              ariaLabel={`Disbursal share by ${data.noun}`}
            />
            <Legend items={[
              { label: "At or near the book default rate", color: PALETTE.primary },
              { label: "Running 10% or more above it", color: PALETTE.high },
            ]} />
          </Figure>
          <DataTable
            open
            caption={`The ${data.shown} largest ${data.noun.toLowerCase()} units by disbursal`}
            columns={[
              { key: "rank", label: "Rank" },
              { key: "label", label: data.noun },
              { key: "loans", label: "Loans", render: (r) => count(r.loans) },
              { key: "exposure", label: "Disbursed", render: (r) => crore(r.exposureInr) },
              { key: "share", label: "Share", render: (r) => rate(r.exposureShare) },
              { key: "cum", label: "Cumulative", render: (r) => rate(r.cumulativeExposureShare) },
              { key: "obs", label: "Default", render: (r) => rate(r.observedDefaultRate) },
              { key: "idx", label: "Index", render: (r) => index(r.riskIndex) },
            ]}
            rows={data.ranking.map((u) => ({ ...u, key: u.rank }))}
          />
        </>
      ) : <Empty title="No concentration results are available."><p>Choose another dimension or retry after the store has been rebuilt.</p></Empty>}
    </Async>
  );
}

const TABS = [
  { value: "deciles", label: "Ranking quality" },
  { value: "segments", label: "Segment risk" },
  { value: "concentration", label: "Concentration" },
  { value: "impact", label: "Who gets declined" },
];

const BAND_OPTIONS = evidence.policies.map((policy) => ({ value: policy.key, label: policy.label }));

/** Approval and observed default per group under one band.
 *
 *  The aggregate approval rate hides everything that matters here. STATE_ID is
 *  target-encoded straight into the score and EMPLOYMENT_TYPE is a feature, so
 *  both can carry a proxy effect that only shows up when the book is split.
 *
 *  The ratio column is a screen, not a verdict. It compares each group with the
 *  most-approved group in the same band; a low value says look here, and says
 *  nothing about whether the gap is justified by risk. The source carries no
 *  protected attribute, so nothing on this page is a fair-lending test. */
function Impact() {
  const [band, setBand] = useState("conservative");
  const rows = evidence.impactByGroup.filter((row) => row.band === band);
  const byAttribute = ["Employment", "State"].map((attribute) => ({
    attribute,
    groups: rows.filter((row) => row.attribute === attribute).sort((a, b) => a.approval_rate - b.approval_rate),
  })).filter((entry) => entry.groups.length > 0);
  const states = byAttribute.find((entry) => entry.attribute === "State")?.groups ?? [];
  const lowest = states[0];
  const highest = states[states.length - 1];

  if (!byAttribute.length) {
    return <Empty title="No approval-impact groups are available."><p>Choose another policy band.</p></Empty>;
  }

  return (
    <>
      <div className="control-row">
        <Segmented label="Policy band" options={BAND_OPTIONS} value={band} onChange={setBand} />
      </div>

      {lowest && highest && (
        <section className="panel finding">
          <h3>The same cut-off admits {rate(highest.approval_rate)} in one state and {rate(lowest.approval_rate)} in another</h3>
          <p>
            Under the {band} band, state code {highest.group} clears {rate(highest.approval_rate)} of its
            applications and state code {lowest.group} clears {rate(lowest.approval_rate)}, a ratio of{" "}
            <strong>{lowest.approval_ratio_to_best.toFixed(2)}</strong>. The conventional four-fifths screen
            flags anything below 0.80.
          </p>
          <p>
            Part of that gap is risk: state {lowest.group} runs at {rate(lowest.observed_default_rate)} observed
            default against {rate(highest.observed_default_rate)} for state {highest.group}. That is an
            explanation, not a justification, and it is the point at which a policy owner has to decide
            whether a geography-driven decline is one the business will defend. The state code is target-encoded
            directly into the score, so the model is not neutral on this.
          </p>
        </section>
      )}

      {byAttribute.map((entry) => (
        <Figure
          key={entry.attribute}
          question={`Approval rate by ${entry.attribute.toLowerCase()} under the ${band} band`}
          units="Share of that group's applications admitted, percent"
          source={`October holdout; groups below 500 loans are excluded as too small to read`}
          note={entry.attribute === "State"
            ? "Codes are the source's own anonymised integers. They are drill keys, not places, and no real state name can be recovered from them."
            : "Recorded employment category in the source."}
        >
          <RankedBars
            data={entry.groups.map((group) => ({
              label: entry.attribute === "State" ? `State ${group.group}` : group.group,
              value: group.approval_rate * 100,
              color: group.approval_ratio_to_best < 0.8 ? PALETTE.high : PALETTE.primary,
              tip: `${count(group.loans)} loans, ${rate(group.approval_rate)} admitted, ${rate(group.observed_default_rate)} observed default, ratio ${group.approval_ratio_to_best.toFixed(2)}`,
            }))}
            format={(value) => `${value.toFixed(0)}%`}
            ariaLabel={`Approval rate by ${entry.attribute}`}
          />
          <Legend items={[
            { label: "At or above four-fifths of the most-approved group", color: PALETTE.primary },
            { label: "Below four-fifths", color: PALETTE.high },
          ]} />
          <DataTable
            open={entry.attribute === "Employment"}
            caption={`${entry.attribute}: approval and observed default under the ${band} band`}
            columns={[
              { key: "group", label: entry.attribute, render: (r) => (entry.attribute === "State" ? `State ${r.group}` : r.group) },
              { key: "loans", label: "Loans", render: (r) => count(r.loans) },
              { key: "approval", label: "Approval rate", render: (r) => rate(r.approval_rate) },
              { key: "ratio", label: "Ratio to best", render: (r) => (
                <span className={r.approval_ratio_to_best < 0.8 ? "alert" : undefined}>{r.approval_ratio_to_best.toFixed(2)}</span>
              ) },
              { key: "default", label: "Observed default", render: (r) => rate(r.observed_default_rate) },
            ]}
            rows={entry.groups.map((g) => ({ ...g, key: `${g.attribute}-${g.group}` }))}
          />
        </Figure>
      ))}
    </>
  );
}

export default function Risk() {
  const [tab, setTab] = useState("deciles");
  return (
    <>
      <div className="panel-head">
        <h2>Review scope</h2>
        <p>
          Whether the score separates risk, where risk actually sits in the book, and how concentrated the
          disbursal is. Everything on this page is measured on the held-out October month.
        </p>
      </div>
      <div className="control-row">
        <Segmented label="Risk view" options={TABS} value={tab} onChange={setTab} />
      </div>
      {tab === "deciles" && <Deciles />}
      {tab === "segments" && <Segments />}
      {tab === "concentration" && <Concentration />}
      {tab === "impact" && <Impact />}
    </>
  );
}
