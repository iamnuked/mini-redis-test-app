#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "$0")" && pwd)/arena-local-common.sh"

stop_managed_service "gateway" "$ARENA_GATEWAY_PORT"
stop_managed_service "lane-a" "$ARENA_LANE_A_PORT"
stop_managed_service "lane-b" "$ARENA_LANE_B_PORT"
stop_managed_service "mini-redis" "$ARENA_MINI_REDIS_PORT"
stop_managed_service "mongo-a" "$ARENA_MONGO_A_PORT"
stop_managed_service "mongo-b" "$ARENA_MONGO_B_PORT"

