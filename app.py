"""Single-process entry point: the whole platform on one port.

One FastAPI app serves the React application at `/`, the JSON API under `/api`,
and the report artifacts at `/artifacts`. There is no second server and no
second UI framework: the reporting views that used to run as a separate
Plotly/Dash process are now views inside the same application, reading the same
API as the policy workbench.

    uv run uvicorn app:app --host 0.0.0.0 --port 7860
"""

from __future__ import annotations

from api.main import app

__all__ = ["app"]
