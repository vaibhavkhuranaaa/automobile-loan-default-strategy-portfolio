-- Star schema for the vehicle-loan first-EMI default strategy workbench.
-- Loaded by scripts/build_db.py into the git-ignored SQLite file
-- data/quarantine/loans.db. No raw row ever leaves this file into a
-- committed artifact; everything downstream is aggregated or limited to the
-- bounded, pseudonymous record inspector.
--
-- SAS PROC SQL equivalent: this is the transferable equivalent of
--   PROC SQL;
--     CREATE TABLE work.dim_date   (...);
--     CREATE TABLE work.fact_loan  (...);
--   QUIT;
-- i.e. the DDL a SAS analyst would issue against a permanent library to
-- stand up a fraud-schema mart. This project never claims SAS proficiency;
-- the comment documents transferability only.

CREATE TABLE IF NOT EXISTS dim_date (
    date_id TEXT PRIMARY KEY,      -- ISO date, e.g. '2018-08-15'
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    split TEXT NOT NULL            -- 'train' (Aug 2018) | 'calibration' (Sep 2018) | 'test' (Oct 2018)
);

CREATE TABLE IF NOT EXISTS dim_state (
    state_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS dim_employment (
    employment_type_id INTEGER PRIMARY KEY,
    employment_type TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_manufacturer (
    manufacturer_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS fact_loan (
    loan_id INTEGER PRIMARY KEY,                                  -- source UNIQUEID; internal key only, never exposed as an "identity" field
    public_ref TEXT NOT NULL UNIQUE,                              -- release-stable random reference; no derivation from source identifiers
    disbursal_date_id TEXT NOT NULL REFERENCES dim_date(date_id),
    state_id INTEGER REFERENCES dim_state(state_id),
    branch_id INTEGER,
    manufacturer_id INTEGER REFERENCES dim_manufacturer(manufacturer_id),
    employment_type_id INTEGER REFERENCES dim_employment(employment_type_id),
    disbursed_amount REAL NOT NULL,
    asset_cost REAL,
    ltv REAL,
    perform_cns_score REAL,
    loan_default INTEGER NOT NULL,                                -- verified first-EMI default outcome; not a fraud label
    risk_score REAL                                                -- calibrated-challenger probability from scripts/run_evaluation.py; populated for all three vintages. Join dim_date.split for provenance: 'test' (October) is the clean holdout and the only split any policy or performance claim may use; 'train' (August) is the fitting sample and 'calibration' (September) fitted the isotonic calibrator, so both are in-sample and optimistic
);

CREATE INDEX IF NOT EXISTS idx_fact_loan_state ON fact_loan(state_id);
CREATE INDEX IF NOT EXISTS idx_fact_loan_employment ON fact_loan(employment_type_id);
CREATE INDEX IF NOT EXISTS idx_fact_loan_date ON fact_loan(disbursal_date_id);
