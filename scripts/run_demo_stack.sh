#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_VENV_PYTHON="$ROOT_DIR/.venv/bin/python"
SETTINGS_FILE="${APP_SETTINGS_FILE:-$ROOT_DIR/config/mongodb.local.json}"
TMP_DIR="$ROOT_DIR/.tmp"
PID_DIR="$TMP_DIR/pids"
LOG_DIR="$TMP_DIR/logs"
MONGO_LOG="$LOG_DIR/mongodb.log"
MINI_REDIS_LOG="$LOG_DIR/mini-redis.log"
BACKEND_LOG="$LOG_DIR/backend.log"
MONGO_PID_FILE="$PID_DIR/mongodb.pid"
MINI_REDIS_PID_FILE="$PID_DIR/mini-redis.pid"
BACKEND_PID_FILE="$PID_DIR/backend.pid"

mkdir -p "$PID_DIR" "$LOG_DIR" "$TMP_DIR/mongodb-data"

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "[error] ${label} not found: $path" >&2
    exit 1
  fi
}

require_file "$APP_VENV_PYTHON" "app virtualenv python"
require_file "$SETTINGS_FILE" "app settings file"

is_benchmark_server_pid() {
  local pid="$1"
  local command
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command" == *"app.api.server"* ]]
}

port_open() {
  local host="$1"
  local port="$2"
  "$APP_VENV_PYTHON" - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
sock = socket.socket()
sock.settimeout(0.5)
try:
    sock.connect((host, port))
except OSError:
    print("0")
else:
    print("1")
finally:
    sock.close()
PY
}

latest_backend_signature() {
  local root_status
  local options_status
  root_status="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)"
  options_status="$(curl -sS -o /dev/null -w '%{http_code}' -X OPTIONS http://127.0.0.1:8000/api/benchmark-runs || true)"
  [[ "$root_status" == "200" && "$options_status" == "204" ]]
}

kill_process_on_port() {
  local port="$1"
  local label="$2"
  if ! command -v lsof >/dev/null 2>&1; then
    echo "[warn] lsof is not available, so stale ${label} detection is limited"
    return 0
  fi

  local pids
  pids="$(lsof -ti tcp:"$port" || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi

  echo "[stop] stale ${label} on port ${port}: ${pids//$'\n'/ }"
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    kill "$pid" >/dev/null 2>&1 || true
  done <<< "$pids"
  sleep 1
}

stop_stale_benchmark_servers() {
  if ! command -v lsof >/dev/null 2>&1; then
    echo "[warn] lsof is not available, so stale benchmark server cleanup is limited"
    return 0
  fi

  local port
  for port in $(seq 8000 8020); do
    local pids
    pids="$(lsof -ti tcp:"$port" || true)"
    [[ -z "$pids" ]] && continue

    while IFS= read -r pid; do
      [[ -z "$pid" ]] && continue
      if is_benchmark_server_pid "$pid"; then
        echo "[stop] old benchmark server on ${port}: ${pid}"
        kill "$pid" >/dev/null 2>&1 || true
      fi
    done <<< "$pids"
  done

  sleep 1
}

wait_for_port() {
  local host="$1"
  local port="$2"
  local label="$3"
  local attempts="${4:-40}"
  local delay="${5:-0.25}"
  local i
  for ((i=0; i<attempts; i+=1)); do
    if [[ "$(port_open "$host" "$port")" == "1" ]]; then
      echo "[ok] ${label} is listening on ${host}:${port}"
      return 0
    fi
    sleep "$delay"
  done
  echo "[error] ${label} did not start on ${host}:${port}" >&2
  return 1
}

start_mongodb() {
  if [[ "$(port_open 127.0.0.1 27017)" == "1" ]]; then
    echo "[skip] MongoDB already available on 127.0.0.1:27017"
    return 0
  fi

  if ! command -v mongod >/dev/null 2>&1; then
    echo "[error] mongod is not on PATH. Start MongoDB manually or install the server binary." >&2
    exit 1
  fi

  echo "[start] MongoDB"
  mongod \
    --dbpath "$TMP_DIR/mongodb-data" \
    --bind_ip 127.0.0.1 \
    --port 27017 \
    --logpath "$MONGO_LOG" \
    --fork >/dev/null

  local mongo_pid
  mongo_pid="$(pgrep -n -f "mongod.*$TMP_DIR/mongodb-data" || true)"
  if [[ -n "$mongo_pid" ]]; then
    echo "$mongo_pid" > "$MONGO_PID_FILE"
  fi

  wait_for_port 127.0.0.1 27017 "MongoDB"
}

seed_mongodb() {
  echo "[seed] MongoDB seed data"
  APP_SETTINGS_FILE="$SETTINGS_FILE" "$APP_VENV_PYTHON" "$ROOT_DIR/scripts/seed_mongodb.py"
}

start_mini_redis() {
  if [[ "$(port_open 127.0.0.1 6379)" == "1" ]]; then
    echo "[skip] mini-redis already available on 127.0.0.1:6379"
    return 0
  fi

  local mini_root="$ROOT_DIR/.tmp/mini-redis-dev"
  require_file "$mini_root/cmd/mini_redis_server/main.py" "mini-redis server entrypoint"

  echo "[start] mini-redis"
  (
    cd "$mini_root"
    export PYTHONPATH="$mini_root"
    nohup python3 cmd/mini_redis_server/main.py >>"$MINI_REDIS_LOG" 2>&1 < /dev/null &
    echo $! > "$MINI_REDIS_PID_FILE"
  )

  wait_for_port 127.0.0.1 6379 "mini-redis"
}

start_backend() {
  stop_stale_benchmark_servers

  if [[ "$(port_open 127.0.0.1 8000)" == "1" ]]; then
    if latest_backend_signature; then
      echo "[skip] latest benchmark backend already available on 127.0.0.1:8000"
      return 0
    fi
    kill_process_on_port 8000 "benchmark backend"
  fi

  echo "[start] benchmark backend"
  (
    cd "$ROOT_DIR"
    export APP_SETTINGS_FILE="$SETTINGS_FILE"
    nohup "$APP_VENV_PYTHON" -m app.api.server >>"$BACKEND_LOG" 2>&1 < /dev/null &
    echo $! > "$BACKEND_PID_FILE"
  )

  wait_for_port 127.0.0.1 8000 "benchmark backend"
}

autostart_benchmark_run() {
  local api_url="http://127.0.0.1:8000/api/benchmark-runs"
  local payload='{
    "scenario":"detail_page",
    "iteration_count":10,
    "concurrency":1,
    "ttl_seconds":30,
    "hit_rate_buckets":[0,50,100],
    "include_reference":false
  }'

  local resp_path="$TMP_DIR/autostart_benchmark_run_response.json"
  : > "$resp_path"

  local http_code
  http_code="$(
    curl -sS -o "$resp_path" -w "%{http_code}" \
      -X POST "$api_url" \
      -H "Content-Type: application/json" \
      --data "$payload" || true
  )"

  echo "[autostart] POST /api/benchmark-runs -> HTTP ${http_code:-unknown}"
  if [[ "$http_code" == "201" ]]; then
    cat "$resp_path"
  elif [[ "$http_code" == "409" ]]; then
    echo "[autostart] 이미 실행 중인 run이 있어 자동 실행을 건너뜁니다."
  else
    # 실패 원인을 확인하기 위해 response body를 함께 출력합니다.
    if [[ -s "$resp_path" ]]; then
      cat "$resp_path"
    fi
  fi
}

print_summary() {
  cat <<EOF
[done] demo stack is ready
- frontend url: http://127.0.0.1:8000/
- api health:   http://127.0.0.1:8000/api/health
- settings:     $SETTINGS_FILE
- logs:
  - mongodb:    $MONGO_LOG
  - mini-redis: $MINI_REDIS_LOG
  - backend:    $BACKEND_LOG
EOF
}

start_mongodb
seed_mongodb
start_mini_redis
start_backend
autostart_benchmark_run
print_summary
