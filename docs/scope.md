# Scope

## Decision

Support a credit-policy analyst deciding whether one of three evaluated first-EMI risk bands is credible enough for human governance review.

## Included

- Retrospective portfolio, vintage, score-ranking, segment, concentration, policy, loan-detail, and monitoring views.
- Full-data API queries over all 233,154 records, with bounded pseudonymous record inspection.
- Editable contribution-rate, loss-severity, review-cost, and capacity assumptions.
- Aggregate evaluation evidence and a printable monthly KPI pack.
- Source-identity verification between GitHub, the deployed container, and the portfolio registry.

## Excluded

- Live underwriting, pricing, approvals, declines, or adverse action.
- Fraud detection or fraud-data claims.
- A protected-attribute fairness conclusion.
- Long-horizon default, recovery, roll-rate, or observed profit and loss claims.
- Redistribution of the source dataset or derived database.
- Exposure of the source application identifier, precise location, birth date, workforce identifier, contact flag, or identity-document fields.
