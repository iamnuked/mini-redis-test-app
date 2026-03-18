# redis-benchmark-dashboard-wireframe 완전체 구현 계획

기준일: 2026-03-19

## 1. 문서 목적

이 문서는 `docs/wireframes/redis-benchmark-dashboard-wireframe.svg`를 기준으로, 현재 mini-redis benchmark 앱을 와이어프레임 수준까지 확장 구현하기 위한 전체 계획을 정의한다.

여기서 완전체 버전이란 아래를 모두 포함하는 상태를 뜻한다.

- 와이어프레임 레이아웃을 실제 UI로 구현
- 다중 시나리오 선택
- 실험 설정 패널의 대부분을 실제 실행 파라미터로 연결
- 실행 로그, 최근 기록, KPI, 차트, 흐름 보드를 동기화
- 서비스 미리보기 패널을 비교형 화면으로 제공
- 데이터 적재, Redis 비우기, 화면 초기화, 실행 중지 같은 제어 기능 추가

## 2. 현재 상태 요약

현재 시스템이 이미 갖고 있는 요소는 아래와 같다.

- same-origin 정적 대시보드 서빙
- benchmark run 생성 API
- health check API
- run 목록 및 상세 조회
- event stream 조회
- request timeline read model
- presentation read model
- 단일 시나리오 중심 실행 폼
- replay 기반 흐름 보드

즉, 현재는 "실행 결과를 보여주는 benchmark dashboard v1"은 이미 있다.

부족한 부분은 아래에 가깝다.

- 시나리오 카탈로그
- richer control plane
- service preview 데이터 모델
- 실험 전처리/정리 작업 API
- 진짜 발표형 차트/패널 구도
- 시나리오별 설명과 preset

## 3. 목표 화면 해석

와이어프레임을 기준으로 최종 화면은 여섯 블록으로 나뉜다.

1. 상단 글로벌 헤더
- 제품 제목
- 시나리오 이동
- 기록 보기
- 실행 시작 CTA

2. 현재 데모 시나리오 요약 바
- 현재 선택된 시나리오 설명
- 시나리오 태그
- 캐시 상태 태그
- 요청 규모 요약

3. 실시간 서비스 미리보기
- 좌측 `DB 전용`
- 우측 `Redis + DB`
- 같은 사용자 액션에 대해 다른 결과 화면을 나란히 비교

4. 실시간 비교 패널
- KPI 카드
- 시간대별 지연 차트
- 적중률 대비 평균 지연 차트

5. 실험 설정 패널
- 시나리오
- 데이터 규모
- 캐시 모드
- 반복 횟수
- 동시 요청 수
- TTL
- 키 패턴
- 사전 작업 버튼
- 실행/중지 버튼

6. 실행 로그 패널
- 시계열 로그
- 이벤트성 요약

## 4. 핵심 판단

이 와이어프레임은 현재 앱 구조를 완전히 뒤엎어야 하는 수준은 아니다.

다만 아래 두 가지가 새로 필요하다.

- 대시보드용 UI 현대화
- 실행 컨트롤러를 benchmark launcher에서 demo orchestrator로 확장

즉, 프론트는 Tailwind + daisyUI + ECharts로 재구성하고, 백엔드는 단순 run 생성기에서 시나리오/데이터/캐시 상태를 제어하는 얇은 orchestration API로 한 단계 확장하는 방식이 맞다.

## 5. 전체 구현 전략

구현 전략은 "보이는 화면부터 빠르게 맞추되, 가짜 버튼은 만들지 않는다"로 잡는다.

단계 원칙:

1. 화면 뼈대를 먼저 맞춘다.
2. 현재 API로 연결 가능한 데이터부터 붙인다.
3. 부족한 제어 기능을 백엔드에 추가한다.
4. 서비스 미리보기는 마지막에 도입한다.

이 순서를 지키면 발표 가능한 중간 산출물을 계속 유지할 수 있다.

## 6. 필요한 신규 개념

### 6-1. 시나리오 카탈로그

현재는 `detail_page` 문자열만 다루지만, 완전체 버전은 시나리오 정의 객체가 필요하다.

최소 필드:

- `scenario_id`
- `title`
- `subtitle`
- `description`
- `tags`
- `default_iteration_count`
- `default_concurrency`
- `default_ttl_seconds`
- `default_hit_rate_buckets`
- `supported_cache_modes`
- `supported_data_scales`
- `preview_template`

예시 시나리오:

- `detail_page`
- `search_autocomplete`
- `popular_feed`
- `community_feed`

### 6-2. 실행 프리셋

와이어프레임의 설정은 단순 폼이라기보다 preset selector에 가깝다.

최소 필드:

- `data_scale`
- `cache_mode`
- `key_pattern`
- `warm_state`

권장 enum:

- `data_scale`: `small`, `medium`, `large`
- `cache_mode`: `cold`, `warm`, `mixed`
- `key_pattern`: `same_key`, `random_key`

### 6-3. preview read model

서비스 미리보기 패널을 위해 benchmark 수치 외에 "사용자 화면 표현용 데이터"가 필요하다.

최소 구조:

- `search_query`
- `search_results`
- `featured_items`
- `selected_item`
- `metadata`
- `mode_label`
- `cache_state_label`
- `latency_badge`

중요한 점:

- 이 데이터는 실제 서비스 응답을 1:1 재현할 필요는 없다.
- 발표용 시나리오를 설명하기 위한 deterministic preview payload면 충분하다.

## 7. 백엔드 확장 명세

### 7-1. 신규 API 목록

추가가 필요한 엔드포인트는 아래와 같다.

#### 시나리오/설정

- `GET /api/scenarios`
- `GET /api/scenarios/:id`
- `GET /api/demo-config`

#### 사전 작업

- `POST /api/demo-actions/seed-data`
- `POST /api/demo-actions/clear-redis`
- `POST /api/demo-actions/reset-ui`

#### 실행 제어

- `POST /api/benchmark-runs`
  - 기존 확장
- `POST /api/benchmark-runs/:id/stop`

#### 서비스 미리보기

- `GET /api/benchmark-runs/:id/preview`
- 선택적으로 `GET /api/scenarios/:id/preview-template`

### 7-2. 기존 run 생성 API 확장

현재 `RunConfig`는 아래만 다룬다.

- `scenario`
- `iteration_count`
- `concurrency`
- `hit_rate_buckets`
- `ttl_seconds`
- `include_reference`

완전체 버전에서는 아래 필드가 추가되어야 한다.

- `data_scale`
- `cache_mode`
- `key_pattern`
- `warm_state`
- `scenario_variant`
- `preview_enabled`

### 7-3. stop API 명세

현재는 active run 중복 방지만 있고 중지는 없다.

중지 구현 방향:

- `BenchmarkApplication`에 cancel token 저장
- `BenchmarkRunner` 루프가 단계별로 cancel 상태 확인
- stop 요청 시 run status를 `cancelling`로 전환
- 정리 완료 후 `cancelled`로 기록

수용 기준:

- 사용자가 실행 중지 버튼을 누르면 1초 안에 `cancelling` 상태가 보인다.
- 이미 종료된 run에 stop 요청이 오면 no-op 또는 409로 처리한다.

### 7-4. seed-data API 명세

와이어프레임의 `데이터 적재` 버튼을 살리려면 명시적 seed API가 필요하다.

최소 동작:

- MongoDB baseline 데이터를 seed file 기준으로 upsert
- 결과로 문서 개수와 대상 collection 반환
- 로그에 seed action 기록

응답 예시:

```json
{
  "status": "ok",
  "action": "seed-data",
  "inserted": 0,
  "updated": 1000,
  "collection": "detail_page_records"
}
```

### 7-5. clear-redis API 명세

`Redis 비우기` 버튼을 위해 필요하다.

최소 동작:

- mini-redis 전체 flush 또는 benchmark prefix 기준 삭제

권장 방향:

- 처음에는 benchmark key prefix 기반 삭제를 우선한다.
- 전체 flush는 별도 옵션으로만 제공한다.

이유:

- 데모 앱 외 키까지 지우는 동작은 위험할 수 있다.

### 7-6. reset-ui API 명세

이 API는 서버 상태를 바꾸기보다 프론트 초기 상태를 되돌리는 기준 payload를 줄 수도 있다.

하지만 실제 필요성은 낮다.

권장 판단:

- `화면 초기화`는 프론트 로컬 상태 reset으로 먼저 구현
- 별도 서버 API는 후순위

즉, 와이어프레임의 버튼은 실제로는 프론트 action으로 시작해도 된다.

### 7-7. preview API 명세

이 API가 완전체 버전의 핵심 추가 기능이다.

목적:

- 같은 시나리오를 `DB 전용`과 `Redis + DB` 관점으로 나란히 렌더링
- 성능 수치와 함께 사용자가 보는 서비스 결과를 같이 보여주기

반환 구조 예시:

```json
{
  "scenario": "community_feed",
  "db_only": {
    "mode": "db_only",
    "cache_state": "cold",
    "search_query": "redis",
    "latency_ms": 182,
    "screen": {
      "search_results": [],
      "featured_items": [],
      "selected_item": null
    }
  },
  "cache_aside": {
    "mode": "cache_aside",
    "cache_state": "warm",
    "latency_ms": 24,
    "screen": {
      "search_results": [],
      "featured_items": [],
      "selected_item": null
    }
  }
}
```

권장 구현:

- 첫 버전은 실제 앱 화면이 아니라 scenario template 기반 fake-but-deterministic preview를 사용
- 후속으로 실제 baseline/cache adapter 결과와 연결

## 8. 데이터 모델 변경

### 8-1. RunConfig 확장

`app/benchmark/models.py`의 `RunConfig`는 확장되어야 한다.

추가 필드:

- `data_scale: str = "small"`
- `cache_mode: str = "mixed"`
- `key_pattern: str = "same_key"`
- `warm_state: str = "warm"`
- `scenario_variant: str | None = None`

### 8-2. RunRecord 메타데이터 확장

발표용 기록 보드에는 단순 summary 외에 사람이 읽는 메타 정보가 필요하다.

권장 필드:

- `display_title`
- `display_subtitle`
- `tags`
- `control_snapshot`

### 8-3. 로그 구조 확장

현재 로그가 있다면 단계성 메시지 외에 action log도 구분하는 게 좋다.

권장 필드:

- `kind`: `run`, `action`, `system`
- `stage`
- `message`
- `metadata`

## 9. 프론트엔드 구현 명세

### 9-1. 채택 기술

- `Tailwind CSS`
- `daisyUI`
- `Apache ECharts`

이 조합은 기존 정적 HTML/JS 구조와 가장 잘 맞는다.

### 9-2. 화면 구성

#### 헤더

- 제목
- 현재 시나리오 badge
- 최근 기록 열기 버튼
- 실행 버튼

#### 시나리오 요약 바

- 시나리오 제목, 설명
- `피드 화면`, `검색 부하`, `웜 캐시`, `50 요청` 같은 tag chip

#### 서비스 미리보기 패널

- 좌우 2열
- 동일한 card skeleton을 공유
- 상단에 `DB 전용`, `Redis + DB` 라벨과 cache 상태 badge

#### 실시간 비교 패널

- 상단 KPI stats row
- 하단 차트 2개

#### 실험 설정 패널

- select group + segmented control + action buttons

#### 실행 로그 패널

- scrollable log list
- severity badge
- timestamp

### 9-3. 차트 구현

필수 차트:

1. `시간대별 지연 변화`
- ECharts line chart
- `DB Only`와 `Redis + DB` 두 series

2. `적중률 대비 평균 지연`
- ECharts line chart
- break-even marker line
- hit rate bucket label

3. 선택 추가
- request mix donut
- stage totals horizontal bar

### 9-4. 서비스 미리보기 구현 방식

이 영역은 일반 로그 패널과 달라서 완전히 별도 renderer를 두는 편이 낫다.

권장 파일 분리:

- `previewRenderer`
- `chartRenderer`
- `runController`
- `controlPanel`

미리보기는 실제 DOM 카드 컴포넌트로 구현하고, 차트 라이브러리로 억지로 그리지 않는다.

## 10. 단계별 구현 계획

### 단계 1. UI 기반 교체

작업:

- Tailwind + daisyUI + ECharts 도입
- 전체 레이아웃을 와이어프레임 기준으로 재배치
- 기존 패널을 새 카드 구조에 매핑

완료 기준:

- 와이어프레임 구도와 거의 같은 화면이 뜬다.
- 아직 가짜 데이터가 섞여 있어도 구조는 완성된다.

### 단계 2. 시나리오 카탈로그 도입

작업:

- `GET /api/scenarios`
- 시나리오 메타 JSON 정의
- UI 시나리오 selector 연결

완료 기준:

- 화면 상단과 설정 패널이 같은 시나리오 메타를 바라본다.

### 단계 3. 실험 설정 확장

작업:

- `data_scale`, `cache_mode`, `key_pattern`, `warm_state` 입력 추가
- run 생성 payload 확장
- 기록 패널에 control snapshot 표시

완료 기준:

- 와이어프레임 설정 대부분이 실제 payload에 반영된다.

### 단계 4. 사전 작업 API 추가

작업:

- seed-data
- clear-redis
- reset-ui

완료 기준:

- 설정 패널 하단 버튼이 placeholder가 아니라 실제 동작한다.

### 단계 5. stop API 추가

작업:

- cancel token
- runner polling cancel point
- UI 상태 `cancelling`, `cancelled`

완료 기준:

- 긴 실행을 도중에 중지할 수 있다.

### 단계 6. 미리보기 패널 도입

작업:

- preview template
- preview API 또는 client-side deterministic builder
- 좌우 비교 카드 렌더링

완료 기준:

- 와이어프레임의 좌우 미리보기 영역이 실제 데이터 기반으로 보인다.

### 단계 7. 발표 polish

작업:

- animation
- skeleton
- empty state
- log severity tone
- theme 정교화

완료 기준:

- 데모 시연에 바로 쓸 수 있는 수준의 일관성과 안정성을 갖는다.

## 11. 구현 우선순위

우선순위는 아래 순서가 가장 좋다.

1. UI 레이아웃 재구성
2. ECharts 차트 교체
3. 시나리오 카탈로그
4. 설정 패널 확장
5. seed / clear API
6. stop API
7. preview panel

이 순서가 좋은 이유는, 발표 준비 관점에서 가장 빨리 화면 가치를 올리면서도 뒤에서 제어 계층을 자연스럽게 확장할 수 있기 때문이다.

## 12. 구현 가능성 판단

최종 판단:

- 구현 가능: 예
- 현재 코드베이스와 충돌 여부: 낮음
- 필요한 백엔드 확장 규모: 중간
- 필요한 프론트 개편 규모: 큼
- 가장 어려운 파트: `서비스 미리보기 패널`과 `stop API`

즉, 이 와이어프레임은 무리한 수준은 아니지만, "스타일만 고치면 끝나는 작업"은 아니다.

현재 저장소 기준으로는 아래처럼 보는 게 가장 현실적이다.

- 1주차: 레이아웃 + 차트 + 시나리오 패널
- 2주차: 설정 확장 + 제어 API
- 3주차: preview + polish

## 13. 추천 실행안

실행안은 아래 두 가지 중 하나다.

### 실행안 A

먼저 발표 가능한 화면을 빠르게 만든다.

- Tailwind + daisyUI + ECharts 적용
- 와이어프레임 레이아웃 맞춤
- 현재 API로 연결 가능한 부분 우선 구현
- 미리보기 패널은 임시 deterministic mock으로 시작

장점:

- 빨리 결과가 보인다.

단점:

- 중간에 mock 제거 작업이 한 번 더 필요하다.

### 실행안 B

제어 API부터 먼저 늘린다.

- 시나리오 카탈로그
- seed / clear / stop
- RunConfig 확장
- 이후 UI 구현

장점:

- 데이터 모델이 더 안정적이다.

단점:

- 초반에 화면 변화가 적어 체감 진척이 느리다.

권장안:

- `실행안 A`

이 프로젝트는 발표용 가치가 중요한 만큼, 먼저 화면을 완성도 있게 끌어올리고 부족한 백엔드 기능을 뒤따라 붙이는 편이 더 적합하다.
