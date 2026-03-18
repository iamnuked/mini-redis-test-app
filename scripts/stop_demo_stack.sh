#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/.tmp/pids"

is_benchmark_server_pid() {
  local pid="$1"
  local command
  command="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  [[ "$command" == *"app.api.server"* ]]
}

stop_from_pid_file() {
  local pid_file="$1"
  local label="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "[skip] no pid file for ${label}"
    return 0
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
    echo "[stop] ${label} (${pid})"
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  else
    echo "[skip] ${label} is not running"
  fi

  rm -f "$pid_file"
}

stop_from_pid_file "$PID_DIR/backend.pid" "benchmark backend"
stop_from_pid_file "$PID_DIR/mini-redis.pid" "mini-redis"
stop_from_pid_file "$PID_DIR/mongodb.pid" "mongodb"

if command -v lsof >/dev/null 2>&1; then
  for port in $(seq 8000 8020); do
    pids="$(lsof -ti tcp:"$port" || true)"
    if [[ -n "$pids" ]]; then
      while IFS= read -r pid; do
        [[ -z "$pid" ]] && continue
        if is_benchmark_server_pid "$pid"; then
          echo "[stop] extra backend process on ${port}: ${pid}"
          kill "$pid" >/dev/null 2>&1 || true
        fi
      done <<< "$pids"
    fi
  done
fi
