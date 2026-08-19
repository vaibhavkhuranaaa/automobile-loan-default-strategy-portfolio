# Automobile-Loan First-EMI Default Strategy Portfolio

## Portfolio contract

- **Category / industry:** data science analytics / automobile credit risk.
- **Industry question:** Which bounded Indian vehicle-loan policy band best balances first-EMI default risk, assumption-led contribution, and manual-review capacity?
- **Decision owner:** A credit-policy analyst preparing an aggregate scenario for human governance review.
- **Use boundary:** Retrospective decision support only. The project does not make approval, decline, pricing, underwriting, or adverse-action decisions.
- **Data boundary:** The authorized source CSV and derived SQLite store remain private and untracked. Public evidence is aggregate. Direct identifiers and identity-document fields are excluded from models, views, and API responses.
- **Release status:** Public source and a live Azure Container Apps demo exist. The current branch is a local release candidate. Portfolio admission remains pending until an approved push and redeploy make live `/health` `source_sha` equal the GitHub default-branch commit.
- **Cost boundary:** The existing demo scales to zero. No paid infrastructure or new public resource is requested.

## Success criteria

1. A reviewer can follow the data-quality, feature-eligibility, leakage, and temporal-validation choices without access to private delivery state.
2. The project reports discrimination, calibration, uncertainty, approval/default/contribution trade-offs, capacity limits, and explicit economic assumptions for each evaluated band.
3. The five-view workbench supports the complete review path at 1440px and 390px with accessible loading, empty, error, retry, and keyboard states.
4. Public source, CI, release manifests, container metadata, `/health`, and the portfolio registry agree on the exact deployed commit before publication.

## Delivery constraints

- The dataset's published licence is unknown. Code and documentation are MIT licensed; the source data and derived database are not distributed.
- Results are bounded to the August to October 2018 cohort and one held-out month. They do not establish forward or long-horizon performance.
- First-EMI default mixes credit and possible payment-mandate failures that the source cannot distinguish.
- Economic outputs are sensitivity estimates built from analyst inputs, not observed lender profit and loss.
- No push, deployment, GitHub metadata change, portfolio synchronization, paid provisioning, visibility change, or history rewrite occurs without the recorded human release approval.

## First review workflow

1. Read the portfolio and vintage outcome.
2. Check ranking, segment risk, exposure concentration, and approval impact.
3. Compare the three evaluated cut-offs under editable economics and review capacity.
4. Inspect anonymized cohort records behind an aggregate.
5. Review calibration and population stability before preparing a recommendation or refusal for governance.

## Transferability boundary

The source has no fraud label or declared origination channel. The policy-band,
manual-review, challenger-validation, and monitoring patterns can transfer to a
fraud-strategy workflow, but this repository makes no fraud-detection, identity-
linking, channel, Power BI, Tableau, or SAS implementation claim.
