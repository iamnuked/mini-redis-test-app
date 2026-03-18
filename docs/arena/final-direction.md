# mini-redis Arena 최종 방향

## 1. 제품 정의

Arena는 `mini-redis`를 실제 캐시 엔진으로 사용해, `Redis + DB` 구조와 `DB only` 구조의 차이를 응답 중심으로 학습하는 Cache Architecture Arena다.

핵심은 세 가지다.

1. 같은 입력을 두 레인에 동시에 넣는다.
2. 두 레인의 응답, 처리 경로, 저장 변화가 즉시 드러난다.
3. Redis가 왜 유리한지 latency와 Mongo read 차이로 설명할 수 있다.

## 2. MVP 범위

비교 레인:

- Lane A: `mini-redis + MongoDB`
- Lane B: `MongoDB only`

수동 명령:

- `SET key value`
- `GET key`
- `DEL key`

TTL:

- UI 토글로만 제어한다.
- TTL ON이면 Redis 저장과 cache fill에 기본 TTL을 건다.

시나리오:

- `Hot Key`
- `TTL Expiry`

시각화:

- latency 비교
- Mongo read 비교

## 3. 기술 방향

- HTTP API: `FastAPI`
- 실시간 이벤트: `SSE`
- 대시보드: 정적 HTML/CSS/JS
- `mini-redis` 연동: `redis-py`
- 원본 저장소: MVP에서는 인메모리 Mongo fallback

## 4. 구현 구조

```text
cmd/
  arena_gateway/
  arena_lane_a/
  arena_lane_b/
internal/
  arena/
    api/
    common/
    events/
    gateway/
    lane/
    lane_a/
    lane_b/
    mongo/
    scenario/
web/
  arena_dashboard/
tests/
  arena/
```
