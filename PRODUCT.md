# Product


## Platform

web

## Users

Credit-policy analysts preparing a governed vehicle-loan portfolio recommendation in India. Recruiters and hiring managers can inspect the same aggregate workflow as evidence of analytical judgment.

## Product Purpose

The Portfolio Policy Workbench explores the full authorized vehicle-loan dataset, supports bounded pseudonymous record review, then tests a first-EMI-risk policy band against portfolio economics and manual-review capacity. Its outcome is a recommendation to take to governance, not a decision on an individual applicant.

## Positioning

Unlike a model report, the workbench combines full-data analyst exploration with an analyst-controlled policy scenario: filter and inspect cohorts, choose an evidence-backed risk cut-off, change transparent Indian lending assumptions, and see the resulting admitted volume, observed default rate, review load, and estimated net contribution in Indian rupees.

## Operating Context

An analyst reviews the full authorized dataset and an October 2018 retrospective holdout before a policy meeting. They filter and inspect cohorts, compare three calibrated-model cut-offs, pressure-test contribution rate, loss severity, and manual review cost against review capacity, then document a candidate or a refusal for human governance. The pressure-testing is the point of the product, not a garnish on it: the ranking of the three bands flips inside the plausible range of those assumptions, so an analyst who cannot move them cannot tell a robust recommendation from a fragile one.

## Capabilities and Constraints

- The complete authorized Kaggle vehicle-loan dataset may be deployed and publicly showcased; the product will use it through an API and full-data store rather than bundling a large CSV into the browser.
- Reports Indian rupees in crore (`₹ cr`); all economic output is an assumption-led estimate, not observed P&L.
- Supports scenario selection and economic/capacity sensitivity, not arbitrary threshold optimization beyond the three evaluated policy bands. The three economic assumptions are live controls; the risk cut-offs are not, because only the three were evaluated.
- Distinguishes what the assumptions can and cannot move. Net contribution and break-even values recalculate; admitted share, observed default rate, and manual-review demand are measured on the holdout and never change with an assumption.
- Does not expose direct identifiers or source rows verbatim, score a new applicant, make an approval/decline, set pricing, claim fraud detection, or distinguish branch from digital channels. The loan inspector shows bounded, anonymized fields from the retrospective cohort.

## Evidence on Hand

- Authorized source expected at the private build path `data/quarantine/train.csv`; it is not tracked or included in this checkout.
- Aggregate evaluation: `artifacts/strategy_summary.json`.
- Generated UI evidence: `web/src/data.js`.
- Metric methods and limits: `docs/metric-glossary.md`.
- Data rights, source, and privacy boundary: private delivery records, summarized publicly in `NOTICE` and `docs/scope.md`.

## Product Principles

1. Begin with the analyst's policy decision, not model metrics.
2. Separate observed evidence from adjustable assumptions.
3. Use Indian lending language and units without pretending the source provides unsupported operating facts.
4. Make refusal and capacity breaches as legible as positive outcomes.
5. Keep every conclusion bounded to retrospective governance review.
6. Write for a senior analyst: state the decision, evidence, exception, owner, and next action without promotional or conversational dashboard language.

## Accessibility & Inclusion

Keyboard-operable native controls, visible focus, semantic labels, and plain-language definitions are required. Meaning is never conveyed by colour alone.

## Transferability to fraud-strategy analytics

The workbench measures first-EMI default, not fraud, and never claims fraud detection, fraud data, or branch or digital channel capability. The policy band, manual-review-capacity control, challenger validation, monitoring view, and monthly KPI pack demonstrate transferable analytical patterns while remaining populated only with default-risk evidence. Power BI, Tableau, and SAS are not demonstrated or claimed.
