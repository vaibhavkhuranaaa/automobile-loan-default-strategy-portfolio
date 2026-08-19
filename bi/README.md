# BI exports

`build_exports.py` writes git-ignored grouped CSV rollups from the private SQLite
star schema into `bi/exports/`. **This dataset measures first-EMI default, not fraud**, and nothing
built from these files makes a live approval, denial, pricing, or automated
decision. See `PROJECT.md` and `.project/data.md` for the full scope and boundary.

```bash
uv run python bi/build_exports.py
```

## What consumes them

`scripts/build_kpi_pack.py` reads them to produce the monthly KPI one-pager in
`artifacts/kpi_pack/` (public PNG plus git-ignored CSV and Excel working files).

The application does not. Its reporting views query SQLite directly through the
API, so a rollup can never drift from what the product shows.

## Removed: the Power BI Project

`bi/powerbi/VehicleLoanKPI.pbip` was a hand-authored TMDL semantic model and PBIR
report over these exports. It was removed on 2026-08-10.

It had never been opened in Power BI Desktop, which is Windows-only, so no `.pbix`
ever existed and its correctness was never established. It was authored as a
replica of the Plotly/Dash KPI dashboard, and when that dashboard was retired the
replica mirrored a surface that no longer existed. Keeping an unverifiable
artifact that duplicates nothing invites a capability claim the project cannot
support, so it was deleted rather than carried. It remains in Git history if a
Windows machine ever makes validating it worthwhile.
