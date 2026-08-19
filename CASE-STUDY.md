# Case study  -  Automobile-Loan First-EMI Default Strategy Portfolio

Status: release candidate. Source is published at <https://github.com/vaibhavkhuranaaa/automobile-loan-default-strategy-portfolio> and the hosted demo is live. Portfolio admission still requires the live `/health` `source_sha` to equal the repository default branch after the final approved redeploy.

## Executive summary

This project gives a credit-policy analyst an Indian vehicle-loan risk platform over 233,154 loans: portfolio and vintage reporting, score-decile and segment risk analytics, a policy workbench that tests three evaluated risk bands against editable economics, a per-loan inspector, and a monitoring view. It runs as one React application over one JSON API and a SQLite star schema.

**Its headline finding is a refusal, and then a way out of it.** At a 12% contribution rate, 65% loss severity and ₹1,500 per manual review, no evaluated band clears zero. The best of the three, the conservative 16% cut-off, lands at **−₹0.07 cr**, and resampling the October holdout puts it above zero in only **39%** of draws. Across the 27 published assumption combinations, no band clears zero in **13**.

The refusal is not a dead end. The workbench reports how much of the label would have to be operational for each band to break even under an explicit assumption that an operational miss cures with zero credit loss. Conservative needs **0.32%**, about **22 of its 6,722 defaulted loans**; reference needs 8.0% and expansion 19.7%. The source cannot identify operational misses, later cure, or realized loss, so lender evidence must confirm all three before this scenario can change policy.

So the honest conclusion remains a refusal with a bounded evidence request: **under the zero-loss cure scenario, conservative reaches break-even at an operational share of 0.32%.** The project does not observe failure type, cure, or realized loss, so it reports the scenario threshold instead of turning it into a recommendation.

That conclusion is the second correction this project has published against itself, and both are described below. It is not a live lending recommendation and it makes no approval, decline, or pricing decision.

## Business problem

An origination policy can improve headline default metrics while destroying volume or overwhelming review capacity. The workflow makes those trade-offs explicit, and makes the fragility of the answer explicit alongside them, before a policy owner advances a governed change.

## Decision and workflow

- Decision owner: credit-policy analyst.
- Decision supported: recommend, or refuse to recommend, a bounded aggregate policy scenario for human governance review.
- Workflow: read the book and its vintages, check whether the score separates risk and where risk sits, test a cut-off against editable economics and review capacity, inspect individual loans behind the aggregates, and check whether prediction still matches outcome.
- Use boundary: retrospective decision support only. Not an underwriting, pricing, eligibility, or adverse-action system.

## Two corrections this project published against itself

**The first correction: manual review was free.** An earlier version reported **+₹4.17 cr** for the conservative band. It omitted the cost of the manual reviews the strategy itself generates. Costing them at ₹1,500 per referral moved the band to +₹1.52 cr and the figure was withdrawn.

**The second correction: the bureau column encodes "no score" as a number.** The source carries `PERFORM_CNS_SCORE` beside `PERFORM_CNS_SCORE_DESCRIPTION`. For **12,835 loans** the description reads `Not Scored: Sufficient History Not Available`, `Not Scored: Not Enough Info available on the customer`, and four similar variants, while the score column carries values of **11 to 18**. On a scale whose real floor is 300, the bureau was saying *unknown* and the pipeline was reading *catastrophic*. Worse, the thin-file indicator `HAS_BUREAU` was derived as `score > 0`, so every one of those loans was flagged as **having** a bureau file when the source explicitly says it has none, on a book that is half thin-file.

Recoding them to null and deriving the flag afterwards barely moved the model, because the description column was already a categorical feature giving it partial cover: AUROC 0.64452 → **0.64363**, and calibration error actually improved, 0.04603 → **0.04542**.

It moved the economics decisively. More loans landed inside the manual-review straddle, review referrals for the conservative band rose from 18,535 to **27,585**, and the band went from **+₹1.52 cr to −₹0.07 cr**. The recommended band stopped clearing zero. Both superseded figures are retained here because the correction is the more useful artifact.

## Data and limitations

233,154 labeled vehicle-loan records with a verified first-EMI-default outcome. August 2018 trains (68,002), September calibrates (66,788), October tests (98,364). The user authorized local evaluation, full deployment, and public showcasing.

The source CSV and built SQLite store remain private. An authorized local database enters the deployment image at build time so the demo can serve the full cohort. The dataset's published licence is recorded as unknown, so the MIT licence covers the code only; see `NOTICE`. Direct identifiers and identity-document fields are excluded from every view and API response as a product-control choice, not a rights limit.

Four properties of the label and the window bear on every number in this project. They are limits of the source, and no amount of modelling removes them.

- **The label may mix credit and operational events.** The book runs at a **21.7%** first-EMI default rate, but nothing in the source separates credit events from mandate or payment-plumbing failures or observes later cure and realized loss. Operational contamination is plausible, not measured. Any onboarding response requires lender evidence.
- **Loss severity is charged against the wrong event.** The 65% figure is an ultimate-loss assumption applied to loans that missed a *first* instalment. A first-EMI miss is a delinquency flag, not a loss event, and a large share of first-payment defaulters cure. This overstates credit loss by an amount the dataset cannot quantify, because it carries no recovery, roll-rate, or ultimate-default data.
- **Three consecutive months of one quarter, in festival season.** There is no out-of-time validation beyond a single month and no economic cycle. October 2018 falls in the Indian festival period, the peak of the vehicle-sales year, which draws a different applicant mix. Some of the October deterioration may be seasonal.
- **The scores rank; they do not price.** The isotonic calibrator was fitted on September, the quietest month at 19.19% default, and applied to October at 23.51%. Predicted risk sits below observed risk in **all ten deciles**.

Branch, state, supplier and manufacturer are anonymised integers with no published lookup. They are used as drill keys and concentration rankings, never as chart axes, and no real name is inferred from them. The analysis claims no fraud detection, channel strategy, live underwriting, pricing, or adverse-action capability.

## Verified evidence

**Ranking.** The calibrated challenger reaches AUROC **0.64363** against a logistic baseline's 0.62286, PR-AUC 0.33927 against 0.32073, and Brier score 0.17364 against 0.23962. KS is **0.209**. The riskiest decile defaults at 41.0%, a lift of **1.74×** on a book average of 23.5%, and the riskiest fifth of the book carries **31.3%** of all defaults. Published work on this dataset tops out near 0.66–0.68, and KS below 0.30 is under what most institutions deploy. This model rank-orders usefully and weakly.

**Calibration.** Decile ECE is **0.04542** against 0.25169 at baseline. The direction matters more than the magnitude: observed default exceeds predicted in every decile, by +3.0 to +5.5 percentage points, and the admitted book under the conservative band was predicted at 11.2% against **15.2%** observed. Ranking-based decisions are unaffected; anything projecting a predicted rate forward is roughly four points optimistic.

**Bands, with intervals.** At the published assumptions:

| Band | Cut-off | Admitted | Observed default | Review referrals | Net contribution | 95% interval | Above zero |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Conservative | 16% | 44.69% (43,961) | 15.29% | 27,585 (28.04%) | **−₹0.07 cr** | −₹0.65 to +₹0.49 cr | 39% |
| Reference | 22% | 67.04% (65,946) | 18.37% | 15,968 (16.23%) | −₹3.52 cr | −₹4.25 to −₹2.74 cr | 0% |
| Expansion | 28% | 85.99% (84,586) | 21.08% | 19,262 (19.58%) | −₹13.08 cr | −₹14.10 to −₹12.12 cr | 0% |

Intervals come from 400 bootstrap resamples of the October holdout with the cut-offs held fixed. They cover sampling variation only, not the assumptions. The conservative interval does not overlap the reference interval, so the **ranking is solid while the level is indistinguishable from zero**.

**Robustness.** The 27-cell grid (contribution rate 10/12/14%, loss severity 55/65/75%, review cost ₹0/1,500/3,000) is published in `artifacts/strategy_summary.json`. Conservative ranks first in **22 of 27** and reference in 5. In **13 of 27**, no band clears zero at all. Conservative breaks even at a loss severity of 0.648 against the 0.65 assumed  -  it is already the wrong side of that line  -  and at a review cost of ₹1,473 against the ₹1,500 assumed.

**The refusal becomes an evidence request.** Under the explicit assumption that an operational miss cures with zero credit loss, setting net contribution to zero and solving for the operational share gives `1 − breakevenSeverity / severity`. Conservative breaks even at a **0.32%** operational share, reference at **8.02%**, expansion at **19.68%**. The workbench recomputes all three live as the assumptions move. This scenario needs new lender evidence on failure type, cure, and loss before it can support a policy change.

**The three economic assumptions are analyst inputs, not lender figures.** The ₹1,500 review cost is a placeholder with no source at all. All three are exposed as sliders that recalculate every rupee figure live, so a reviewer can replace them rather than accept them.

**Distributional effect.** Under the conservative band, **11 of 18** state codes large enough to read fall below the conventional four-fifths screen. State code 3 clears **60.3%** of its applications and state code 13 clears **10.1%**, a ratio of **0.17**. Part of that gap is risk  -  state 13 runs 32.0% observed default against 19.7%  -  but `STATE_ID` is target-encoded directly into the score, so the model is not neutral on geography. Employment passes the screen at 0.88. The source carries no protected attribute, so this is impact reporting and not a fair-lending opinion; it is published because a policy owner has to decide whether a geography-driven decline is one the business will defend.

**Population stability.** Maximum PSI across every characteristic and month is **0.030**, comfortably stable. The composition of the book did not move; its outcome did, from 21.57% in August to 19.19% in September to 23.51% in October. That is what makes the calibration failure a calibration failure rather than a population shift.

Every product metric carries a contextual label in the application and a method, direction, verified result, and limitation in `docs/metric-glossary.md`.

## Limits and next action

The economic figures are sensitivity estimates, not observed P&L. The evaluation supports a three-month 2018 retrospective test only. No scenario is automatically enacted, and the product makes no borrower-level decision.

The next action is not another modelling pass. It is to obtain the lender's observed first-presentation failure rate, later cure, and realized loss by failure type. Under the zero-loss cure scenario, conservative needs 0.32% of its first-EMI misses to be operational to clear zero. Those operating facts determine whether the scenario is credible; the dataset does not.

After that, a one-parameter calibration shift should be fitted on the most recent closed month, then applied to the next scoring period. Fitting on the month being scored would leak the outcome and is not proposed. A policy owner must also review the three economic assumptions because one has no source at all.

The demo runs on Azure Container Apps and scales to zero, so a first request after idle takes about 22 seconds. The release contract requires `/health` to expose the exact deployed source revision. The portfolio registry compares that value with the GitHub default branch before admitting the release.

## Transferability to fraud-strategy analytics

This dataset measures first-EMI default and contains no fraud outcome. This project makes no fraud-detection or fraud-data claim. The transferability notes below describe analytical patterns only:

- The conservative/reference/expansion bands are the same *strategy cut-design* pattern used to trade fraud loss against growth and friction.
- The manual-review-capacity control is the same pattern used to size a fraud review queue, and costing those reviews is what turned this project's recommendation negative twice.
- The calibrated-challenger comparison (AUROC/PR-AUC/Brier/ECE) plus bootstrap intervals is the same validation pattern used before rolling out a fraud strategy or vendor score.
- The monitoring view  -  population stability by characteristic, and predicted against observed per band  -  is the same post-deployment surveillance a fraud strategy needs.
- The monthly KPI pack (`scripts/build_kpi_pack.py` → `artifacts/kpi_pack/`) mirrors a monthly fraud-KPI leadership report, populated with default-risk KPIs.
- The SQL layer (`sql/schema.sql`, `cohort.sql`, `policy_bands.sql`, `score_deciles.sql`, `segment_risk.sql`, `kpi_monthly.sql`) over a SQLite star schema demonstrates the posting's named SQL requirement directly.

SAS is never used or claimed; SQL files carry `-- SAS PROC SQL equivalent:` comments to document transferability only. Identity-linking of incoming applications, the posting's daily fraud-ring-matching responsibility, is out of scope because this dataset has no identity-linking fields.
