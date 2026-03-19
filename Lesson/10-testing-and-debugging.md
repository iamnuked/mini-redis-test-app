# 10. Testing and Debugging

## 핵심 질문

- 이 프로젝트는 무엇을 어떻게 검증하고 있는가
- 주니어 개발자가 이 저장소를 읽을 때 어떤 순서로 디버깅해야 하는가

## 먼저 볼 파일

- `tests/test_command_service.py`
- `tests/test_redis_py_compatibility.py`
- `tests/arena/test_gateway_contracts.py`
- `tests/arena/test_redis_db_adapter.py`
- `tests/arena/test_scenario_runner.py`
- `scripts/arena-local-up.sh`
- `scripts/arena-local-status.sh`

## 테스트 층

테스트는 크게 세 층이다.

1. core unit
   - 서비스, validator, expiration
2. protocol/client compatibility
   - RESP, `redis-py`
3. arena integration
   - gateway, lane, scenario, health, control

이 분리 덕분에 문제가 생겼을 때 범위를 빨리 좁힐 수 있다.

## 디버깅 순서

문제가 생기면 아래 순서로 접근하는 편이 좋다.

1. 증상이 core 문제인지 Arena 문제인지 먼저 나눈다.
2. Arena 문제면 lane-a, lane-b, gateway 중 어디서 틀어졌는지 나눈다.
3. health와 storage 수치가 논리적으로 맞는지 본다.
4. 마지막에 UI 렌더링 문제인지 확인한다.

## 실전 체크리스트

- `node --check web/arena_dashboard/app.js`
- `python -m pytest -q`
- `./scripts/arena-local-status.sh`
- `curl http://127.0.0.1:8200/api/health`

## 주의할 점

`tests/test_redis_py_compatibility.py`는 loopback bind가 필요한 테스트라, 일부 제한된 환경에서는 코드와 무관하게 실패할 수 있다. 이 경우 먼저 환경 제약인지부터 확인해야 한다.

## 직접 해볼 것

1. `GET` hit와 miss 경로를 각각 테스트로 찾아본다.
2. `scenario_finished`가 health에 반영되는 흐름을 따라간다.
3. 일부러 TTL을 매우 짧게 두고 UI와 health 값이 함께 바뀌는지 확인한다.
