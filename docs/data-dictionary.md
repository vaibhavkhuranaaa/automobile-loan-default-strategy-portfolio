# Data dictionary

Source: local `Vehicle Loan Default Prediction` archive. Provenance is retained in private delivery records. Fields below are assessed for retrospective first-EMI-default analysis only. Selected non-identifying values appear in four fixed record-review shortlists under opaque, release-specific `VL-XXXXXXXXXXXX` references; raw rows and prohibited fields are not published or downloadable.

| Source field | Business label | Treatment | Restriction |
| --- | --- | --- | --- |
| `LOAN_DEFAULT` | First-EMI default | Binary outcome | Target only; visible as retrospective outcome, never a model input |
| `UNIQUEID` | Application identifier | Drop | Direct identifier |
| `DISBURSAL_DATE` | Disbursal date | Parse day-first; temporal split only | Month-level vintage only in record review; never a model input |
| `DISBURSED_AMOUNT` | Loan amount disbursed | Numeric candidate | Aggregate analysis and bounded record review; no raw export |
| `ASSET_COST` | Vehicle asset cost | Numeric candidate | Aggregate analysis and bounded record review; no raw export |
| `LTV` | Loan-to-value ratio | Numeric candidate | Validate range before use |
| `EMPLOYMENT_TYPE` | Employment type | Categorical candidate | 7,661 missing values must be explicit category |
| `PERFORM_CNS_SCORE` | Bureau score | Numeric candidate | Treat no-bureau code separately; bounded record review only |
| `PERFORM_CNS_SCORE_DESCRIPTION` | Bureau-score band | Categorical candidate | Redundant with score; assess leakage/duplication |
| `PRI_NO_OF_ACCTS` | Primary-account count | Numeric candidate | Pre-disbursal only |
| `PRI_ACTIVE_ACCTS` | Active primary accounts | Numeric candidate | Pre-disbursal only |
| `PRI_OVERDUE_ACCTS` | Overdue primary accounts | Numeric candidate | Pre-disbursal only |
| `PRI_CURRENT_BALANCE` | Primary-account balance | Numeric candidate | Pre-disbursal only |
| `PRI_SANCTIONED_AMOUNT` | Primary-account sanctioned amount | Numeric candidate | Pre-disbursal only |
| `PRI_DISBURSED_AMOUNT` | Primary-account disbursed amount | Numeric candidate | Pre-disbursal only |
| `SEC_NO_OF_ACCTS` | Secondary-account count | Numeric candidate | Pre-disbursal only |
| `SEC_ACTIVE_ACCTS` | Active secondary accounts | Numeric candidate | Pre-disbursal only |
| `SEC_OVERDUE_ACCTS` | Overdue secondary accounts | Numeric candidate | Pre-disbursal only |
| `SEC_CURRENT_BALANCE` | Secondary-account balance | Numeric candidate | Pre-disbursal only |
| `SEC_SANCTIONED_AMOUNT` | Secondary-account sanctioned amount | Numeric candidate | Pre-disbursal only |
| `SEC_DISBURSED_AMOUNT` | Secondary-account disbursed amount | Numeric candidate | Pre-disbursal only |
| `PRIMARY_INSTAL_AMT` | Primary installment amount | Numeric candidate | Pre-disbursal only |
| `SEC_INSTAL_AMT` | Secondary installment amount | Numeric candidate | Pre-disbursal only |
| `NEW_ACCTS_IN_LAST_SIX_MONTHS` | New accounts, six months | Numeric candidate | Pre-disbursal only |
| `DELINQUENT_ACCTS_IN_LAST_SIX_MONTHS` | Delinquent accounts, six months | Numeric candidate | Pre-disbursal only |
| `AVERAGE_ACCT_AGE` | Average account age | Parse duration to months | Pre-disbursal only |
| `CREDIT_HISTORY_LENGTH` | Credit-history length | Parse duration to months | Pre-disbursal only |
| `NO_OF_INQUIRIES` | Credit inquiries | Numeric candidate | Pre-disbursal only |
| `BRANCH_ID` | Disbursing branch | Candidate portfolio segment | High-cardinality/proxy review; aggregate only |
| `SUPPLIER_ID` | Vehicle dealer | Candidate portfolio segment | Portfolio-level concentration only; omitted from record review |
| `MANUFACTURER_ID` | Vehicle manufacturer | Candidate portfolio segment | Aggregate only; no causal claim |
| `STATE_ID` | Disbursal state | Candidate portfolio segment | Aggregate only; proxy review required |
| `CURRENT_PINCODE_ID` | Customer postcode | Drop | Precise location / proxy risk |
| `DATE_OF_BIRTH` | Date of birth | Drop | Personal attribute; do not derive age |
| `EMPLOYEE_CODE_ID` | Originating employee identifier | Drop | Workforce identifier |
| `MOBILENO_AVL_FLAG` | Mobile-number supplied | Drop | Identity/contact attribute |
| `AADHAR_FLAG` | Aadhaar supplied | Drop | Identity-document attribute |
| `PAN_FLAG` | PAN supplied | Drop | Identity-document attribute |
| `VOTERID_FLAG` | Voter ID supplied | Drop | Identity-document attribute |
| `DRIVING_FLAG` | Driving licence supplied | Drop | Identity-document attribute |
| `PASSPORT_FLAG` | Passport supplied | Drop | Identity-document attribute |

## Data-quality gates

- Verify each candidate feature is available before disbursal and is not target-derived.
- Retain only August data for training, September for calibration/tuning, and October for final retrospective test.
- Fail the pipeline if identifiers or prohibited identity/document/location fields reach the feature matrix.
- Do not infer fraud, branch-versus-digital channel, pricing, or automated-decision outcomes: none is observed in this source.
