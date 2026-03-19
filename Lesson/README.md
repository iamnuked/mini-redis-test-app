# Lesson

이 폴더는 `mini-redis`와 Arena를 학습 자료 형태로 다시 풀어쓴 문서 모음이다. 목적은 “코드를 그냥 읽는 것”이 아니라, 어떤 질문을 던지며 읽어야 하는지까지 같이 제공하는 데 있다.

## 학습 자료 전략

이 프로젝트는 개념이 많다.

- TCP 서버
- RESP 프로토콜
- 명령 파싱과 검증
- in-memory 자료구조
- TTL과 background sweep
- maxmemory와 eviction
- CLI
- `redis-py` 호환
- gateway/lane 구조
- 실시간 대시보드
- 시나리오 기반 비교 실험

그래서 학습 자료는 “파일 설명”보다 “개념 단위”로 나눈다. 각 문서는 아래 순서를 따른다.

1. 왜 이 개념이 필요한가
2. 이 저장소에서는 어디에 구현돼 있는가
3. 실제 코드에서 무엇을 확인해야 하는가
4. 직접 손으로 바꿔보면 무엇을 배울 수 있는가

## 추천 읽는 순서

1. [01-project-map.md](01-project-map.md)
2. [02-mini-redis-core.md](02-mini-redis-core.md)
3. [03-protocol-network-and-session.md](03-protocol-network-and-session.md)
4. [04-command-pipeline.md](04-command-pipeline.md)
5. [05-data-structures-and-storage.md](05-data-structures-and-storage.md)
6. [06-ttl-memory-and-eviction.md](06-ttl-memory-and-eviction.md)
7. [07-cli-and-client-compatibility.md](07-cli-and-client-compatibility.md)
8. [08-arena-system.md](08-arena-system.md)
9. [09-scenarios-dashboard-and-observability.md](09-scenarios-dashboard-and-observability.md)
10. [10-testing-and-debugging.md](10-testing-and-debugging.md)

## 이 폴더를 읽는 방법

- 처음엔 각 문서의 `먼저 볼 파일`만 따라가도 충분하다.
- 두 번째 읽을 때는 `직접 해볼 것`을 실제로 수행해보는 편이 좋다.
- Arena를 보기 전에 `mini-redis` 코어를 먼저 이해해야 비교 의미가 선명해진다.

## 학습 목표

이 폴더를 다 읽고 나면 다음을 설명할 수 있어야 한다.

- RESP 기반 key-value server가 어떻게 동작하는가
- 왜 parser, validator, service를 나누는가
- TTL과 eviction은 각각 어떤 문제를 해결하는가
- Redis-compatible client 경계는 왜 중요한가
- 같은 요청을 `Redis + DB`와 `DB Only`로 비교하려면 어떤 구조가 필요한가
- 대시보드가 보여주는 수치가 실제로 무엇을 의미하는가
