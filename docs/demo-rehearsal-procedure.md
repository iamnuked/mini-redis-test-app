# mini-redis 벤치마크 UI 데모 리허설 절차

## 1. 목적

이 문서는 발표 직전 `mini-redis` 벤치마크 UI 데모를 안정적으로 리허설하기 위한 실행 절차를 정리한다.

핵심 목표는 아래 세 가지다.

- 발표 중 백엔드, `mini-redis`, 프론트 연결이 꼬이지 않도록 미리 확인한다.
- 청중에게 보여줄 시나리오와 설명 순서를 고정한다.
- 문제가 생겼을 때 바로 우회할 수 있는 fallback 절차를 준비한다.

## 2. 리허설 범위

이 절차는 아래 구성을 기준으로 한다.

- `mini-redis` 서버
- benchmark API 서버
- same-origin 또는 연결 가능한 상태의 프론트엔드 대시보드
- `detail_page` 시나리오
- `DB Only` vs `Redis + DB`
- 선택적 `Redis Only Reference`

## 3. 리허설 전 준비물

- 최신 코드가 반영된 작업 디렉터리
- 실행 가능한 `mini-redis`
- Python 실행 환경
- 브라우저
- 발표용 화면 해상도 확인

권장:

- 기존에 떠 있던 오래된 백엔드 프로세스는 정리하고 시작한다.
- 브라우저 탭은 대시보드 하나만 남기고 정리한다.
- `localStorage`에 남은 `apiBase` override가 있으면 확인한다.
- 반복 실행이 많으면 `scripts/run_demo_stack.sh`, `scripts/check_demo_stack.sh`, `scripts/stop_demo_stack.sh` 를 사용한다.

## 4. 사전 점검

### 4-1. 문서 기준 확인

리허설 전에 아래 문서를 한 번 훑는다.

- [requirements.md](/Users/jeongbeomjin/Hex/jungle/mini-redis-test-app/docs/requirements.md)
- [benchmark-ui-system-design.md](/Users/jeongbeomjin/Hex/jungle/mini-redis-test-app/docs/benchmark-ui-system-design.md)
- [api-spec.md](/Users/jeongbeomjin/Hex/jungle/mini-redis-test-app/docs/api-spec.md)
- [frontend-backend-connection-checklist.md](/Users/jeongbeomjin/Hex/jungle/mini-redis-test-app/docs/frontend-backend-connection-checklist.md)

확인 포인트:

- 메인 비교축은 `DB Only` vs `Redis + DB`다.
- `Redis Only`는 참고선이다.
- request detail은 `/requests`, KPI/차트는 `/presentation` 기준이다.

### 4-2. 코드/프로세스 상태 확인

확인 항목:

- 현재 백엔드 서버가 최신 코드 기준으로 재시작되어 있는지
- `mini-redis`가 실제로 떠 있는지
- 프론트가 같은 origin 또는 유효한 API base를 바라보는지

## 5. 런타임 점검 절차

### 5-0. 권장 스크립트 실행 절차

반복 리허설이나 발표 직전 확인에서는 수동 실행보다 아래 스크립트 흐름을 우선 사용하는 편이 덜 꼬인다.

권장 순서:

1. `./scripts/stop_demo_stack.sh`
2. `./scripts/run_demo_stack.sh`
3. `./scripts/check_demo_stack.sh`

역할:

- `run_demo_stack.sh`
  - MongoDB 포트 확인
  - 필요 시 로컬 `mongod` 실행
  - Mongo seed 실행
  - `mini-redis` 실행
  - 백엔드 실행
  - 프론트 접속 URL 출력

- `check_demo_stack.sh`
  - `/`
  - `/api/health`
  - `/api/benchmark-runs`
  - Mongo baseline seed 문서 조회
  를 빠르게 점검한다.

- `stop_demo_stack.sh`
  - 스크립트가 띄운 backend, `mini-redis`, MongoDB PID를 정리한다.

주의:

- 기존 `8000`, `6379`, `27017` 포트에 오래된 프로세스가 떠 있으면 예상과 다른 서버에 붙을 수 있다.
- 발표 직전에는 `stop -> run -> check` 순서를 한 번 타는 것이 가장 안전하다.

### 5-1. mini-redis 기동

먼저 `mini-redis`를 실행한다.

기대 결과:

- `127.0.0.1:6379`에서 응답 가능
- health check가 실패하지 않음

### 5-2. benchmark API 서버 기동

백엔드 서버를 최신 코드 기준으로 실행한다.

기대 결과:

- `GET /` 로 프론트 정적 페이지 접근 가능
- `GET /api/health` 응답 가능
- `OPTIONS /api/health` 응답 가능

### 5-3. 프론트 대시보드 열기

브라우저에서 대시보드를 연다.

기대 결과:

- 첫 화면이 정상 렌더링됨
- `API 기준 경로` 카드가 의도한 base를 가리킴
- `미니 레디스 상태` 카드가 `정상`으로 표시됨

### 5-4. 핵심 API 확인

최소 확인 대상:

- `GET /api/health`
- `GET /api/benchmark-runs`
- `POST /api/benchmark-runs`
- `GET /api/benchmark-runs/{run_id}`
- `GET /api/benchmark-runs/{run_id}/requests`
- `GET /api/benchmark-runs/{run_id}/presentation`

기대 결과:

- run 생성이 `201 Created`
- run 상태가 `queued`에서 `completed` 또는 `failed`로 정상 전이
- `requests`와 `presentation` 응답이 비어 있지 않음

## 6. 발표용 기본 시나리오

### 6-1. 권장 입력값

기본 리허설 입력값:

```json
{
  "scenario": "detail_page",
  "iteration_count": 10,
  "concurrency": 1,
  "ttl_seconds": 30,
  "hit_rate_buckets": [0, 50, 100],
  "include_reference": true
}
```

설명 포인트:

- `concurrency`는 현재 메타데이터 용도이며 실제 실행은 순차다.
- `include_reference`는 참고선 설명이 필요할 때만 켠다.

### 6-2. 발표 흐름

권장 발표 순서:

1. health와 run 상태를 보여준다.
2. 시나리오와 설정값을 짚는다.
3. KPI 카드에서 평균 지연시간과 성능 역전 기준 적중률을 설명한다.
4. 흐름 레인에서 `DB Only`, `Redis hit`, `Redis miss` 차이를 보여준다.
5. request detail에서 path summary와 stage duration을 짚는다.
6. 보조 차트에서 경로 분포와 stage 누적량을 짚는다.
7. 필요하면 replay를 실행해 다시 보여준다.

## 7. 화면별 체크 포인트

### 7-1. 헤더/상태 카드

- `미니 레디스 상태`가 정상인지
- `현재 Run` 상태가 최신 run과 맞는지
- `API 기준 경로`가 예상한 값인지

### 7-2. KPI 보드

- `DB 평균`
- `Redis + DB 평균`
- `속도 향상`
- `성능 역전 기준 적중률`
- `캐시 적중률`
- `오류 수`

확인 포인트:

- 값이 `--`에 머물러 있지 않은지
- 실패 run인데 완료 run처럼 보이지 않는지

### 7-3. 흐름 레인

- `DB 전용` lane 표시
- `Redis + DB` lane 표시
- 선택 시 `요청 상세` 패널 동기화
- reference를 켠 경우만 `Redis 기준선` lane 표시

### 7-4. 요청 상세 패널

- `request id`
- `mode`
- `total duration`
- `cache status`
- `path summary`
- `stage duration`

확인 포인트:

- `hit`, `miss`, `fallback` 설명이 자연스러운지
- stage 수치가 비어 있지 않은지

### 7-5. 차트 영역

- 지연시간 비교 차트
- 요청 경로 분포
- stage 누적량 chip/grid

확인 포인트:

- `presentation` 응답 기반 수치와 화면 값이 크게 어긋나지 않는지

## 8. Replay 리허설

확인 항목:

- replay 버튼이 정상 동작하는지
- 재생 속도 변경이 반영되는지
- 요청이 순서대로 나타나는지
- replay 중 선택한 request 상세가 일관되게 보이는지

주의:

- 현재 replay는 절대 시각 재현이 아니다.
- `requests` 배열 순서와 고정 step 기반 시각화다.
- 발표 때는 이 점을 과장하지 말고 "흐름 설명용 재생"이라고 표현하는 게 맞다.

## 9. 실패 대응 절차

### 9-1. health 실패

점검 순서:

1. `mini-redis` 프로세스 확인
2. `127.0.0.1:6379` 포트 확인
3. 백엔드 재시작
4. 브라우저 새로고침

### 9-2. run 생성 실패

점검 순서:

1. 이미 실행 중인 run이 있는지 확인
2. payload 값 검증
3. 백엔드 로그 확인
4. 오래된 서버 프로세스가 아닌지 확인

### 9-3. 화면은 뜨는데 데이터가 안 보임

점검 순서:

1. `API 기준 경로` 확인
2. 브라우저 네트워크 탭에서 `/requests`, `/presentation` 확인
3. cross-origin이면 CORS/프록시 상태 확인
4. 최신 서버 코드로 재시작

### 9-4. 차트/레인이 비정상

점검 순서:

1. 해당 run이 `completed`인지 확인
2. `presentation` 응답 존재 여부 확인
3. `requests` 응답 존재 여부 확인
4. reference 모드를 끄고 다시 실행

## 10. 최종 리허설 완료 기준

아래가 모두 만족되면 발표 직전 상태로 본다.

- `mini-redis` health가 정상이다.
- 백엔드가 최신 코드 기준으로 실행 중이다.
- 프론트 첫 화면이 same-origin 기준으로 열린다.
- run 생성부터 완료까지 한 번 성공했다.
- `requests` 응답과 `presentation` 응답이 실제로 채워진다.
- KPI, 레인, 요청 상세, 차트, replay를 최소 1회씩 확인했다.
- 실패 시 fallback 절차를 발표자가 알고 있다.

## 11. 권장 마무리

발표 직전 마지막으로 할 일:

1. 브라우저를 새로고침한다.
2. 가장 최근 성공 run을 하나 다시 선택한다.
3. 필요하면 새 run을 1회 더 실행한다.
4. `API 기준 경로`, `미니 레디스 상태`, `현재 Run` 카드만 마지막으로 확인한다.

이 네 가지가 맞으면 발표 시작 기준으로는 충분하다.
