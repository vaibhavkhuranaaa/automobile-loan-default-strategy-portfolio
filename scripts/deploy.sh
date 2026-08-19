#!/usr/bin/env bash
#
# Build and deploy the current release to Azure Container Apps, then verify.
#
# Usage:  ./scripts/deploy.sh
#
# Requires: az CLI logged in; a clean tree pushed to origin/main.

set -euo pipefail

REGISTRY="textsqlguardrails278f1d"
IMAGE="automobile-loan-strategy"
APP="ca-automobile-loan-strategy"
GROUP="rg-automobile-loan-strategy"
URL="https://ca-automobile-loan-strategy.mangosand-c2cfc0f3.eastus.azurecontainerapps.io"

cd "$(dirname "$0")/.."

if [ -n "$(git status --porcelain)" ]; then
  echo "refusing: working tree is dirty. Commit first." >&2
  exit 1
fi

SHA="$(git rev-parse HEAD)"
git fetch -q origin
if [ "$SHA" != "$(git rev-parse origin/main)" ]; then
  echo "refusing: HEAD is not origin/main. Push first." >&2
  exit 1
fi

if [ ! -f data/quarantine/loans.db ]; then
  echo "refusing: private SQLite release asset is missing." >&2
  exit 1
fi

# Azure CLI applies Git ignore rules while packing a local build context, which
# correctly keeps the database out of Git but also omits it from ACR builds.
# Stage tracked HEAD plus the private release asset in one disposable context.
CONTEXT="$(mktemp -d "${TMPDIR:-/tmp}/automobile-loan-build.XXXXXX")"
trap 'rm -rf -- "$CONTEXT"' EXIT
git archive HEAD | tar -x -C "$CONTEXT"
rm -f "$CONTEXT/.gitignore"
mkdir -p "$CONTEXT/data/quarantine"
cp data/quarantine/loans.db "$CONTEXT/data/quarantine/loans.db"

echo "==> building $IMAGE:$SHA for linux/amd64"
# Built in ACR rather than locally: Container Apps needs linux/amd64 and the
# usual build host here is an arm64 Mac.
az acr build \
  --registry "$REGISTRY" \
  --image "$IMAGE:$SHA" \
  --image "$IMAGE:latest" \
  --build-arg "SOURCE_SHA=$SHA" \
  --platform linux/amd64 \
  "$CONTEXT" >/dev/null

echo "==> rolling $APP to the new image and source revision"
az containerapp update \
  --name "$APP" --resource-group "$GROUP" \
  --image "$REGISTRY.azurecr.io/$IMAGE:$SHA" \
  --set-env-vars "SOURCE_SHA=$SHA" \
  --query "properties.latestRevisionName" -o tsv

echo "==> waiting for traffic to cut over"
# The first request against a brand-new image pays a full layer pull, so allow
# generous per-request time.
for attempt in $(seq 1 30); do
  live="$(curl -fsS --max-time 120 "$URL/health" 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("source_sha",""))' 2>/dev/null || true)"
  if [ "$live" = "$SHA" ]; then
    echo "==> live /health reports $SHA"
    break
  fi
  if [ "$attempt" = "30" ]; then
    echo "FAILED: live /health reports '${live:-nothing}', expected $SHA." >&2
    exit 1
  fi
  sleep 10
done

echo "==> verifying routes"
for path in / /health /api/analytics/overview /artifacts/strategy_summary.json; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 60 "$URL$path")"
  printf '    %-38s %s\n' "$path" "$code"
  [ "$code" = "200" ] || { echo "FAILED: $path returned $code" >&2; exit 1; }
done

echo
echo "deployed $SHA"
