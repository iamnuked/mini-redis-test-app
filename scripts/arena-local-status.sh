#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/arena-local-common.sh"

echo "Arena root: $ARENA_ROOT"
echo "Run dir:    $ARENA_RUN_DIR"
echo "Log dir:    $ARENA_LOG_DIR"
echo

print_status_line "mongo-a" "$ARENA_MONGO_A_PORT"
print_status_line "mongo-b" "$ARENA_MONGO_B_PORT"
print_status_line "mini-redis" "$ARENA_MINI_REDIS_PORT"
print_status_line "lane-a" "$ARENA_LANE_A_PORT"
print_status_line "lane-b" "$ARENA_LANE_B_PORT"
print_status_line "gateway" "$ARENA_GATEWAY_PORT"

echo
if curl -sf "http://$ARENA_HOST:$ARENA_GATEWAY_PORT/api/health" >/dev/null 2>&1; then
  echo "gateway health: ok"
  curl -s "http://$ARENA_HOST:$ARENA_GATEWAY_PORT/api/health"
  echo
else
  echo "gateway health: unavailable"
fi
