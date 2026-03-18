# mini-redis Integration Notes

## 1. 연동 원칙

- `mini-redis`는 독립 프로세스로 실행되는 TCP 기반 서버다.
- Arena는 `mini-redis` 내부 모듈을 직접 호출하지 않는다.
- Arena는 `redis-py`를 통해 네트워크 경계로만 붙는다.

## 2. Arena가 사용하는 명령

Arena MVP는 아래 다섯 명령만 전제로 한다.

- `SET`
- `GET`
- `DEL`
- `EXPIRE`
- `TTL`

## 3. Arena 코드에 반영한 구조

- Redis client 경계: `internal/arena/lane/redis_client.py`
- lane-a는 기본적으로 `ARENA_REDIS_BACKEND=redis_py` 경로를 사용한다.
- 테스트와 최소 개발 시나리오에서는 `ARENA_REDIS_BACKEND=inmemory` fallback도 가능하다.
- reset은 Arena가 추적한 key만 `DEL`로 정리한다.

## 4. 실행 메모

`mini-redis` 서버 실행:

```bash
python cmd/mini_redis_server/main.py
```

Arena 실행:

```bash
python cmd/arena_gateway/main.py
```

lane-a 실행:

```bash
python cmd/arena_lane_a/main.py
```

lane-b 실행:

```bash
python cmd/arena_lane_b/main.py
```

실제 서버에 붙으려면 Arena 프로세스에서 아래 환경변수를 준다.

```bash
export ARENA_REDIS_BACKEND=redis_py
export MINI_REDIS_HOST=127.0.0.1
export MINI_REDIS_PORT=6379
```

속도 비교 기준 구조와 compose 예시는 `benchmark-architecture.md`와 `deploy/docker-compose.arena.yml`을 참고한다.
