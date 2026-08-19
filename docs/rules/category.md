# Analytics delivery rules

- Use versioned real public, licensed, or anonymized data first. Synthetic data is the documented final fallback.
- Define the decision owner and metric contract before modeling.
- Establish a documented baseline before adding a more complex model.
- Make data preparation reproducible and test schema, freshness, duplicates, validity, leakage, and failures.
- Use time-safe or group-safe validation when the operating workflow requires it; calibrate probabilities used for decisions.
- Tie thresholds to business cost, capacity, risk, or expected value rather than model accuracy alone.
- Label representative analysis separately from operational performance.
- Keep dashboards decision-oriented, accessible, and explicit about data scope, metric meaning, recommended use, and limitations.
