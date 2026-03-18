# Local Mongo Runbook

## 목적

Docker 없이도 Arena를 실제 MongoDB 2개와 함께 로컬에서 재현하기 위한 실행 기준이다.

이 runbook은 다음 구성을 기준으로 한다.

- `gateway`: `127.0.0.1:8200`
- `lane-a (redis + mongo)`: `127.0.0.1:8201`
- `lane-b (mongo only)`: `127.0.0.1:8202`
- `mini-redis`: `127.0.0.1:6380`
- `mongo-a`: `127.0.0.1:27018`
- `mongo-b`: `127.0.0.1:27019`

Mongo 데이터 디렉터리는 저장소 내부에 둔다.

- `.local/arena/mongo-a`
- `.local/arena/mongo-b`

## 빠른 실행

수동 명령 대신 아래 스크립트를 바로 써도 된다.

```bash
./scripts/arena-local-up.sh
./scripts/arena-local-status.sh
./scripts/arena-local-down.sh
```

## 1. 디렉터리 준비

```bash
mkdir -p .local/arena/mongo-a
mkdir -p .local/arena/mongo-b
mkdir -p .local/arena/logs
```

## 2. MongoDB 기동

```bash
/opt/homebrew/bin/mongod \
  --dbpath .local/arena/mongo-a \
  --port 27018 \
  --bind_ip 127.0.0.1
```

```bash
/opt/homebrew/bin/mongod \
  --dbpath .local/arena/mongo-b \
  --port 27019 \
  --bind_ip 127.0.0.1
```

## 3. mini-redis 기동

```bash
env PYTHONPATH=. \
  MINI_REDIS_SERVER_HOST=127.0.0.1 \
  MINI_REDIS_SERVER_PORT=6380 \
  .venv311/bin/python cmd/mini_redis_server/main.py
```

## 4. lane-a 기동

```bash
env PYTHONPATH=. \
  ARENA_LANE_A_HOST=127.0.0.1 \
  ARENA_LANE_A_PORT=8201 \
  ARENA_MONGO_BACKEND=pymongo \
  MONGO_URI=mongodb://127.0.0.1:27018 \
  MONGO_DB_NAME=arena_lane_a \
  ARENA_REDIS_BACKEND=redis_py \
  MINI_REDIS_HOST=127.0.0.1 \
  MINI_REDIS_PORT=6380 \
  .venv311/bin/python cmd/arena_lane_a/main.py
```

## 5. lane-b 기동

```bash
env PYTHONPATH=. \
  ARENA_LANE_B_HOST=127.0.0.1 \
  ARENA_LANE_B_PORT=8202 \
  ARENA_MONGO_BACKEND=pymongo \
  MONGO_URI=mongodb://127.0.0.1:27019 \
  MONGO_DB_NAME=arena_lane_b \
  .venv311/bin/python cmd/arena_lane_b/main.py
```

## 6. gateway 기동

```bash
env PYTHONPATH=. \
  ARENA_HOST=127.0.0.1 \
  ARENA_PORT=8200 \
  ARENA_LANE_A_BASE_URL=http://127.0.0.1:8201 \
  ARENA_LANE_B_BASE_URL=http://127.0.0.1:8202 \
  .venv311/bin/python cmd/arena_gateway/main.py
```

## 7. 헬스체크

```bash
curl http://127.0.0.1:8200/api/health
```

정상 응답 조건:

- `redis_lane.mongo.backend == "pymongo"`
- `db_only_lane.mongo.backend == "pymongo"`
- `redis_lane.redis_backend == "redis_py"`

## 8. 검증 예시

상태 초기화:

```bash
curl -X POST http://127.0.0.1:8200/api/scenarios/reset
```

수동 `SET`:

```bash
curl -X POST http://127.0.0.1:8200/api/manual-command \
  -H 'Content-Type: application/json' \
  -d '{"command":"SET","key":"user:1","value":"{\"name\":\"kim\"}","ttl_enabled":false}'
```

즉시 `GET`:

```bash
curl -X POST http://127.0.0.1:8200/api/manual-command \
  -H 'Content-Type: application/json' \
  -d '{"command":"GET","key":"user:1","ttl_enabled":false}'
```

여기서 `redis_db.path`가 `["redis_read","redis_hit"]`로 나오면 warm cache가 정상이다.

## 9. Mongo 분리 확인

```bash
env PYTHONPATH=. .venv311/bin/python - <<'PY'
from pymongo import MongoClient

for label, uri, db_name in [
    ("lane_a", "mongodb://127.0.0.1:27018", "arena_lane_a"),
    ("lane_b", "mongodb://127.0.0.1:27019", "arena_lane_b"),
]:
    client = MongoClient(uri, serverSelectionTimeoutMS=2000)
    print(label, client[db_name]["documents"].find_one({"_id": "user:1"}))
    client.close()
PY
```

## 10. 주의사항

- 기본 TTL은 `5초`다.
- `ttl_enabled=true`인 경우 `SET` 후 첫 `GET`을 늦게 보내면 Redis miss가 정상적으로 발생할 수 있다.
- warm hit를 확인할 때는 `ttl_enabled=false`로 보거나, TTL 내에 연속 `GET`을 보내야 한다.
- 같은 머신에서 돌리기 때문에 절대 성능 수치보다는 상대 비교와 경로 차이에 더 의미가 있다.
