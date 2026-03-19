#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/arena-local-common.sh"

ensure_prerequisites

cd "$ARENA_ROOT"

start_mongod_service "mongo-a" "$ARENA_MONGO_A_PORT" "$ARENA_MONGO_A_DBPATH"
start_mongod_service "mongo-b" "$ARENA_MONGO_B_PORT" "$ARENA_MONGO_B_DBPATH"

start_python_service \
  "mini-redis" \
  "$ARENA_MINI_REDIS_PORT" \
  env \
  PYTHONPATH="$ARENA_ROOT" \
  MINI_REDIS_SERVER_HOST="$ARENA_HOST" \
  MINI_REDIS_SERVER_PORT="$ARENA_MINI_REDIS_PORT" \
  "$ARENA_PYTHON" \
  cmd/mini_redis_server/main.py

start_python_service \
  "lane-a" \
  "$ARENA_LANE_A_PORT" \
  env \
  PYTHONPATH="$ARENA_ROOT" \
  ARENA_LANE_A_HOST="$ARENA_HOST" \
  ARENA_LANE_A_PORT="$ARENA_LANE_A_PORT" \
  ARENA_MONGO_BACKEND="pymongo" \
  MONGO_URI="$ARENA_MONGO_A_URI" \
  MONGO_DB_NAME="$ARENA_MONGO_A_DB_NAME" \
  ARENA_REDIS_BACKEND="redis_py" \
  MINI_REDIS_HOST="$ARENA_HOST" \
  MINI_REDIS_PORT="$ARENA_MINI_REDIS_PORT" \
  "$ARENA_PYTHON" \
  cmd/arena_lane_a/main.py

start_python_service \
  "lane-b" \
  "$ARENA_LANE_B_PORT" \
  env \
  PYTHONPATH="$ARENA_ROOT" \
  ARENA_LANE_B_HOST="$ARENA_HOST" \
  ARENA_LANE_B_PORT="$ARENA_LANE_B_PORT" \
  ARENA_MONGO_BACKEND="pymongo" \
  MONGO_URI="$ARENA_MONGO_B_URI" \
  MONGO_DB_NAME="$ARENA_MONGO_B_DB_NAME" \
  "$ARENA_PYTHON" \
  cmd/arena_lane_b/main.py

start_python_service \
  "gateway" \
  "$ARENA_GATEWAY_PORT" \
  env \
  PYTHONPATH="$ARENA_ROOT" \
  ARENA_HOST="$ARENA_HOST" \
  ARENA_PORT="$ARENA_GATEWAY_PORT" \
  ARENA_RESET_ON_START="1" \
  ARENA_LANE_A_BASE_URL="http://$ARENA_HOST:$ARENA_LANE_A_PORT" \
  ARENA_LANE_B_BASE_URL="http://$ARENA_HOST:$ARENA_LANE_B_PORT" \
  "$ARENA_PYTHON" \
  cmd/arena_gateway/main.py

wait_for_http "http://$ARENA_HOST:$ARENA_GATEWAY_PORT/api/health" "gateway"

echo
echo "Arena local stack is ready."
echo "Gateway: http://$ARENA_HOST:$ARENA_GATEWAY_PORT"
echo "Lane A:   http://$ARENA_HOST:$ARENA_LANE_A_PORT/health"
echo "Lane B:   http://$ARENA_HOST:$ARENA_LANE_B_PORT/health"
echo "Mongo A:  $ARENA_MONGO_A_URI ($ARENA_MONGO_A_DBPATH)"
echo "Mongo B:  $ARENA_MONGO_B_URI ($ARENA_MONGO_B_DBPATH)"
