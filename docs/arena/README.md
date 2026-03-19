# Arena Docs Start Here

## 1. 목적

이 디렉터리는 `mini-redis`를 활용한 Arena 프로젝트의 활성 문서를 모아두는 공간이다.

Arena는 `mini-redis`를 실제 캐시 엔진으로 쓰면서, 같은 요청을 `Redis + DB`와 `DB only`에 동시에 흘려 보내 응답과 처리 경로 차이를 학습하는 데 집중한다.

현재 Arena의 단일 기준 저장소는 `mini-redis`다. 별도 프로토타입 저장소나 과거 협업용 문서는 활성 기준으로 사용하지 않는다.

## 2. 문서 읽는 순서

1. `final-direction.md`
2. `mini-redis-integration.md`
3. `benchmark-architecture.md`
4. `local-mongo-runbook.md`
5. `implementation-reference.md`

기존 `docs/*.md`는 `mini-redis` 자체 설명이고, Arena 구현 판단은 이 디렉터리 문서를 우선한다.

## 3. 기본 원칙

- Arena는 `mini-redis` 내부 객체를 직접 import 하지 않는다.
- Arena는 `redis-py` 클라이언트 경계로 `mini-redis` 서버에 붙는다.
- 속도 비교 모드에서는 lane별 실제 MongoDB를 사용한다.
- 수동 명령은 `SET`, `GET`, `DEL`, `HSET`, `HGET`, `HGETALL`을 지원한다.
- 시나리오는 `Read`, `Write`, `Mixed` 세 개를 제공한다.
- 협업용 문서와 업무분장 문서는 활성 개발 기준에서 제외한다.
