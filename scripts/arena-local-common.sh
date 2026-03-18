#!/usr/bin/env bash
set -euo pipefail

ARENA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARENA_LOCAL_DIR="${ARENA_LOCAL_DIR:-$ARENA_ROOT/.local/arena}"
ARENA_RUN_DIR="${ARENA_RUN_DIR:-$ARENA_LOCAL_DIR/run}"
ARENA_LOG_DIR="${ARENA_LOG_DIR:-$ARENA_LOCAL_DIR/logs}"
ARENA_MONGO_A_DBPATH="${ARENA_MONGO_A_DBPATH:-$ARENA_LOCAL_DIR/mongo-a}"
ARENA_MONGO_B_DBPATH="${ARENA_MONGO_B_DBPATH:-$ARENA_LOCAL_DIR/mongo-b}"

ARENA_HOST="${ARENA_HOST:-127.0.0.1}"
ARENA_GATEWAY_PORT="${ARENA_GATEWAY_PORT:-8200}"
ARENA_LANE_A_PORT="${ARENA_LANE_A_PORT:-8201}"
ARENA_LANE_B_PORT="${ARENA_LANE_B_PORT:-8202}"
ARENA_MINI_REDIS_PORT="${ARENA_MINI_REDIS_PORT:-6380}"
ARENA_MONGO_A_PORT="${ARENA_MONGO_A_PORT:-27018}"
ARENA_MONGO_B_PORT="${ARENA_MONGO_B_PORT:-27019}"

ARENA_PYTHON="${ARENA_PYTHON:-$ARENA_ROOT/.venv311/bin/python}"
ARENA_MONGOD_BIN="${ARENA_MONGOD_BIN:-/opt/homebrew/bin/mongod}"

ARENA_MONGO_A_URI="${ARENA_MONGO_A_URI:-mongodb://$ARENA_HOST:$ARENA_MONGO_A_PORT}"
ARENA_MONGO_B_URI="${ARENA_MONGO_B_URI:-mongodb://$ARENA_HOST:$ARENA_MONGO_B_PORT}"
ARENA_MONGO_A_DB_NAME="${ARENA_MONGO_A_DB_NAME:-arena_lane_a}"
ARENA_MONGO_B_DB_NAME="${ARENA_MONGO_B_DB_NAME:-arena_lane_b}"

mkdir -p "$ARENA_RUN_DIR" "$ARENA_LOG_DIR" "$ARENA_MONGO_A_DBPATH" "$ARENA_MONGO_B_DBPATH"

pid_file_for() {
  printf '%s\n' "$ARENA_RUN_DIR/$1.pid"
}

log_file_for() {
  printf '%s\n' "$ARENA_LOG_DIR/$1.log"
}

listener_pid_for_port() {
  local port="$1"
  lsof -t -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1 || true
}

is_pid_running() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  kill -0 "$pid" 2>/dev/null
}

read_pid_file() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    tr -d '[:space:]' <"$pid_file"
  fi
}

clear_stale_pid_file() {
  local pid_file="$1"
  local pid
  pid="$(read_pid_file "$pid_file")"
  if [[ -n "$pid" ]] && ! is_pid_running "$pid"; then
    rm -f "$pid_file"
  fi
}

ensure_prerequisites() {
  if [[ ! -x "$ARENA_PYTHON" ]]; then
    echo "Python runtime not found: $ARENA_PYTHON" >&2
    return 1
  fi
  if [[ ! -x "$ARENA_MONGOD_BIN" ]]; then
    echo "mongod binary not found: $ARENA_MONGOD_BIN" >&2
    return 1
  fi
}

wait_for_port() {
  local port="$1"
  local name="$2"
  local attempt
  for attempt in $(seq 1 50); do
    if [[ -n "$(listener_pid_for_port "$port")" ]]; then
      return 0
    fi
    sleep 0.2
  done
  echo "$name failed to open port $port" >&2
  return 1
}

wait_for_port_closed() {
  local port="$1"
  local name="$2"
  local attempt
  for attempt in $(seq 1 50); do
    if [[ -z "$(listener_pid_for_port "$port")" ]]; then
      return 0
    fi
    sleep 0.2
  done
  echo "$name did not release port $port" >&2
  return 1
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local attempt
  for attempt in $(seq 1 50); do
    if curl -sf "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  echo "$name failed health check: $url" >&2
  return 1
}

ensure_port_is_available() {
  local name="$1"
  local port="$2"
  local pid_file
  local pid
  local listener_pid

  pid_file="$(pid_file_for "$name")"
  clear_stale_pid_file "$pid_file"
  pid="$(read_pid_file "$pid_file")"

  if [[ -n "$pid" ]] && is_pid_running "$pid"; then
    echo "$name already running with pid $pid"
    return 10
  fi

  listener_pid="$(listener_pid_for_port "$port")"
  if [[ -n "$listener_pid" ]]; then
    echo "$name cannot start because port $port is already in use by pid $listener_pid" >&2
    return 20
  fi

  return 0
}

start_python_service() {
  local name="$1"
  local port="$2"
  shift 2

  local pid_file
  local log_file
  local service_pid

  ensure_port_is_available "$name" "$port" || {
    local status="$?"
    if [[ "$status" -eq 10 ]]; then
      return 0
    fi
    return "$status"
  }

  pid_file="$(pid_file_for "$name")"
  log_file="$(log_file_for "$name")"

  nohup "$@" >"$log_file" 2>&1 </dev/null &
  service_pid=$!
  disown "$service_pid" 2>/dev/null || true
  echo "$service_pid" >"$pid_file"

  wait_for_port "$port" "$name"
  echo "$name started on $ARENA_HOST:$port (pid $service_pid)"
}

start_mongod_service() {
  local name="$1"
  local port="$2"
  local dbpath="$3"
  local pid_file
  local log_file
  local service_pid

  ensure_port_is_available "$name" "$port" || {
    local status="$?"
    if [[ "$status" -eq 10 ]]; then
      return 0
    fi
    return "$status"
  }

  pid_file="$(pid_file_for "$name")"
  log_file="$(log_file_for "$name")"

  nohup \
    "$ARENA_MONGOD_BIN" \
    --dbpath "$dbpath" \
    --port "$port" \
    --bind_ip "$ARENA_HOST" >"$log_file" 2>&1 </dev/null &
  service_pid=$!
  disown "$service_pid" 2>/dev/null || true
  echo "$service_pid" >"$pid_file"

  wait_for_port "$port" "$name"
  echo "$name started on $ARENA_HOST:$port (pid $service_pid)"
}

stop_managed_service() {
  local name="$1"
  local port="$2"
  local pid_file
  local pid

  pid_file="$(pid_file_for "$name")"
  pid="$(read_pid_file "$pid_file")"

  if [[ -z "$pid" ]]; then
    echo "$name not managed by scripts"
    return 0
  fi

  if ! is_pid_running "$pid"; then
    rm -f "$pid_file"
    echo "$name already stopped"
    return 0
  fi

  kill "$pid"
  wait_for_port_closed "$port" "$name" || true
  rm -f "$pid_file"
  echo "$name stopped"
}

print_status_line() {
  local name="$1"
  local port="$2"
  local pid_file
  local pid
  local listener_pid

  pid_file="$(pid_file_for "$name")"
  pid="$(read_pid_file "$pid_file")"
  listener_pid="$(listener_pid_for_port "$port")"

  if [[ -n "$pid" ]] && is_pid_running "$pid"; then
    echo "$name: running pid=$pid port=$port"
    return 0
  fi

  if [[ -n "$listener_pid" ]]; then
    echo "$name: unmanaged pid=$listener_pid port=$port"
    return 0
  fi

  echo "$name: stopped port=$port"
}
