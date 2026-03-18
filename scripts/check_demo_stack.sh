#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
SETTINGS_FILE="${APP_SETTINGS_FILE:-$ROOT_DIR/config/mongodb.local.json}"

if [[ ! -f "$APP_VENV_PYTHON" ]]; then
  echo "[error] app virtualenv is missing: $APP_VENV_PYTHON" >&2
  exit 1
fi

if [[ ! -f "$SETTINGS_FILE" ]]; then
  echo "[error] settings file is missing: $SETTINGS_FILE" >&2
  exit 1
fi

echo "[check] frontend root"
curl -sS -i http://127.0.0.1:8000/ | sed -n '1,8p'

echo
echo "[check] api health"
curl -sS http://127.0.0.1:8000/api/health

echo
echo "[check] backend list endpoint"
curl -sS http://127.0.0.1:8000/api/benchmark-runs

echo
echo "[check] mongodb seed read"
APP_SETTINGS_FILE="$SETTINGS_FILE" "$APP_VENV_PYTHON" - <<'PY'
from app.api.config import ControllerSettings
from app.adapters.mongodb_baseline import MongoBaselineClient

settings = ControllerSettings.from_env()
client = MongoBaselineClient(
    uri=settings.mongodb_uri,
    db_name=settings.mongodb_db_name,
    collection_name=settings.mongodb_collection,
    seed_file=settings.mongodb_seed_file,
    connect_timeout_ms=settings.mongodb_connect_timeout_ms,
)
print(client.fetch_detail("0"))
PY
