"""The platform: one React application, one JSON API, one port.

Queries data/quarantine/loans.db (git-ignored; built by scripts/build_db.py)
via parameterized SQL, reusing sql/cohort.sql for the cohort aggregate and the
analytical queries in sql/ for the risk views.

The built React application is served at `/`, the report-pack files at
`/artifacts`, and the JSON API at `/api`. There is no separate landing page and
no second dashboard server: the page that used to sit at `/` was documentation
about the build rather than the product, and the reporting views that ran as a
Plotly/Dash process are now views in the same application.

Direct identifiers and identity-document fields are excluded from every
response because they do not serve this decision workflow. That is a
product-control choice, not evidence that the source lacked those fields.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .analytics import router as analytics_router

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "quarantine" / "loans.db"
COHORT_SQL = (ROOT / "sql" / "cohort.sql").read_text(encoding="utf-8")
APP_DIR = ROOT / "web" / "dist"
ARTIFACTS_DIR = ROOT / "artifacts"


def _source_sha() -> str:
    baked = os.environ.get("SOURCE_SHA", "").strip()
    if baked:
        return baked
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


SOURCE_SHA = _source_sha()


app = FastAPI(title="Vehicle-loan policy workbench API", version="0.3.0")
# The workbench is same-origin when served from /workbench; these origins keep
# `vite dev` on its own port working for development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://localhost:5173", "http://localhost:5174"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
# Added last, so it wraps everything else and compresses static assets and JSON
# alike. Nothing in front of this container does it: measured against the live
# host, the workbench bundle was served as 212,469 uncompressed bytes even when
# the browser asked for gzip. That is the single largest cost of a first visit,
# and it is one line to remove.
app.add_middleware(GZipMiddleware, minimum_size=500)

# Registered before the static mounts below, which are catch-alls.
app.include_router(analytics_router)


class CachedStaticFiles(StaticFiles):
    """Static files with cache lifetimes that match how the files actually behave.

    Vite writes content-hashed asset filenames, so the bytes behind
    `/assets/index-<hash>.js` can never change, so that URL is safe to
    cache for a year. `index.html` is the opposite: it names the current hashes,
    so caching it would pin a returning visitor to a stale bundle. Everything
    else, including the regenerated report artifacts, revalidates.

    This matters more here than on an always-warm host. The app scales to zero,
    so a revalidation a returning visitor does not need can cost them a full
    cold start to be told nothing changed.
    """

    def file_response(self, full_path, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(full_path, *args, **kwargs)
        immutable = f"{os.sep}assets{os.sep}" in str(full_path)
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if immutable else "no-cache"
        )
        return response


def connection() -> sqlite3.Connection:
    if not DB_PATH.is_file():
        raise FileNotFoundError(
            f"Missing SQLite store: {DB_PATH}. Run `uv run python scripts/build_db.py` first."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def filter_params(state_id: int | None, employment_type: str | None, min_ltv: float | None, max_ltv: float | None) -> dict[str, object]:
    return {
        "state_id": state_id,
        "employment_type": employment_type,
        "min_ltv": min_ltv,
        "max_ltv": max_ltv,
    }


def where_clause(state_id: int | None, employment_type: str | None, min_ltv: float | None, max_ltv: float | None) -> tuple[str, dict[str, object]]:
    clauses = []
    params: dict[str, object] = {}
    if state_id is not None:
        clauses.append("f.state_id = :state_id")
        params["state_id"] = state_id
    if employment_type:
        clauses.append("e.employment_type = :employment_type")
        params["employment_type"] = employment_type
    if min_ltv is not None:
        clauses.append("f.ltv >= :min_ltv")
        params["min_ltv"] = min_ltv
    if max_ltv is not None:
        clauses.append("f.ltv <= :max_ltv")
        params["max_ltv"] = max_ltv
    sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return sql, params


@app.get("/workbench", include_in_schema=False)
@app.get("/workbench/", include_in_schema=False)
def workbench_redirect() -> RedirectResponse:
    """The workbench used to be its own path, and that URL is published.

    It is now one view inside the application, so the old link resolves to the
    view rather than 404ing on a reader who followed it from the case study.
    """
    return RedirectResponse(url="/#/policy", status_code=308)


@app.get("/health")
def health() -> dict[str, object]:
    conn = connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM fact_loan").fetchone()[0]
    finally:
        conn.close()
    return {
        "status": "ok",
        "records": count,
        "source": "SQLite star schema (data/quarantine/loans.db)",
        "source_sha": SOURCE_SHA,
    }


@app.get("/api/filter-options")
def filter_options() -> dict[str, object]:
    conn = connection()
    try:
        states = [row[0] for row in conn.execute("SELECT state_id FROM dim_state ORDER BY state_id")]
        employment_types = [row[0] for row in conn.execute("SELECT employment_type FROM dim_employment ORDER BY employment_type")]
        min_ltv, max_ltv = conn.execute("SELECT MIN(ltv), MAX(ltv) FROM fact_loan").fetchone()
    finally:
        conn.close()
    return {
        "states": states,
        "employmentTypes": employment_types,
        "ltvRange": {"min": round(float(min_ltv), 2), "max": round(float(max_ltv), 2)},
    }


@app.get("/api/cohort")
def cohort(
    state_id: int | None = None,
    employment_type: str | None = None,
    min_ltv: float | None = Query(default=None, ge=0),
    max_ltv: float | None = Query(default=None, ge=0),
) -> dict[str, object]:
    conn = connection()
    try:
        params = filter_params(state_id, employment_type, min_ltv, max_ltv)
        row = conn.execute(COHORT_SQL, params).fetchone()
    finally:
        conn.close()
    count = row["count"] or 0
    return {
        "count": count,
        "defaultRate": round(float(row["default_rate"]), 5) if count else 0,
        "disbursedAmountInr": round(float(row["disbursed_amount_inr"]), 2) if count else 0.0,
        "averageLtv": round(float(row["average_ltv"]), 2) if count else 0,
        "averageBureauScore": round(float(row["average_bureau_score"]), 2) if count else 0,
    }


# Mounted last so they never shadow an API route: FastAPI matches routes before
# mounts, so /api, /health and /workbench above still resolve even though the
# application mount below is at the root. The mount is skipped when the bundle
# has not been built, so the API still starts and reports why rather than the
# whole process failing at import time.
if ARTIFACTS_DIR.is_dir():
    app.mount("/artifacts", CachedStaticFiles(directory=ARTIFACTS_DIR), name="artifacts")

if (APP_DIR / "index.html").is_file():
    app.mount("/", CachedStaticFiles(directory=APP_DIR, html=True), name="app")
