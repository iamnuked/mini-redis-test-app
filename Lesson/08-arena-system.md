# 08. Arena System

## 핵심 질문

- Arena는 왜 gateway, lane-a, lane-b, Mongo, mini-redis를 분리했는가
- 왜 같은 프로세스 안 어댑터 구조보다 이 방식이 더 좋은가

## 먼저 볼 파일

- `internal/arena/api/app.py`
- `internal/arena/gateway/service.py`
- `internal/arena/gateway/lane_client.py`
- `internal/arena/lane/redis_db_adapter.py`
- `internal/arena/lane/db_only_adapter.py`
- `cmd/arena_gateway/main.py`
- `cmd/arena_lane_a/main.py`
- `cmd/arena_lane_b/main.py`

## 구조 요약

```text
Browser -> Gateway
Gateway -> Lane A (mini-redis + Mongo)
Gateway -> Lane B (Mongo only)
Lane A -> mini-redis
Lane A -> Mongo A
Lane B -> Mongo B
```

이 구조는 비교 공정성을 위해 필요하다.

## 왜 분리했는가

예전처럼 gateway 내부에서 두 lane을 직접 실행하면:

- 스케줄링 간섭이 생긴다.
- 같은 프로세스 메모리를 공유한다.
- DB-only가 RAM dict처럼 너무 유리해질 수 있다.

현재 구조는 lane을 분리하고 실제 Mongo를 붙여 비교 의미를 살렸다.

## Gateway의 역할

- 같은 요청을 두 lane에 fan-out
- request id 부여
- 결과 정규화
- SSE 이벤트 발행
- control 상태 관리

즉 gateway는 비교 실험의 orchestrator다.

## 직접 해볼 것

1. lane-a와 lane-b의 adapter 코드를 비교한다.
2. 같은 `GET`이 lane-a와 lane-b에서 어떻게 다르게 흐르는지 적어본다.
3. gateway가 직접 Redis/Mongo를 다루지 않는 이유를 설명해본다.
