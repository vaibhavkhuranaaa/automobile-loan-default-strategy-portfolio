# Single-container deployment: FastAPI serves the built React workbench, the
# JSON API, and the report artifacts. One process fits one scale-to-zero
# container.
#
# The React bundle is built in a first stage so Node is not shipped in the
# runtime image.

FROM node:22-slim AS web
WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build


FROM python:3.12-slim

# Run the public service without root privileges.
RUN useradd -m -u 1000 app
WORKDIR /home/app

# --no-default-groups drops the `pipeline` group (scikit-learn, matplotlib,
# openpyxl and their transitive weight). Those build the artifacts on a developer
# machine; the container only serves what they already wrote. Leaving them out
# keeps roughly 180 MB of site-packages out of every image pull, which is time a
# visitor waits through when the app scales up from zero.
COPY --chown=app:app pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv export --frozen --no-default-groups --no-emit-project -o requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y uv && \
    rm requirements.txt

COPY --chown=app:app api/ ./api/
COPY --chown=app:app bi/ ./bi/
COPY --chown=app:app scripts/ ./scripts/
COPY --chown=app:app sql/ ./sql/
COPY --chown=app:app artifacts/ ./artifacts/
COPY --chown=app:app app.py ./
COPY --chown=app:app --from=web /build/dist ./web/dist

# The built SQLite store. The demo reads every one of its 233,154 loans; the
# raw source CSVs are not shipped.
COPY --chown=app:app data/quarantine/loans.db ./data/quarantine/loans.db

ARG SOURCE_SHA=""

USER app
ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SOURCE_SHA=${SOURCE_SHA}
EXPOSE 7860

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:7860/health').read()"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
