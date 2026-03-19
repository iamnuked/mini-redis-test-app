# 09. Scenarios, Dashboard, and Observability

## 핵심 질문

- 왜 대시보드는 단순 결과 표가 아니라 그래프와 제어 UI를 같이 가져야 하는가
- 왜 scenario가 중요하고, 왜 잘못 설계하면 Redis가 부당하게 유리해질 수 있는가

## 먼저 볼 파일

- `internal/arena/scenario/runner.py`
- `internal/arena/scenario/workloads.py`
- `internal/arena/control_profiles.py`
- `web/arena_dashboard/index.html`
- `web/arena_dashboard/app.js`
- `web/arena_dashboard/styles.css`

## 시나리오의 역할

Scenario는 “자동화된 workload”다. 여기서 중요한 건 예쁘게 도는 게 아니라, 실제로 비교 의미가 있어야 한다는 점이다.

현재는 세 가지가 있다.

- `Read`
- `Write`
- `Mixed`

그리고 `Read`는 hot-cold 분포를 `0/20/40/60/80/100`으로 조절할 수 있다.

## 왜 Memory와 TTL이 중요한가

Arena는 단순히 read count만 비교하지 않는다.

- Memory profile
  - `256B / 512B / 1024B / 2048B`
- TTL profile
  - `OFF / 0.5s / 1s / 2s / 3s / 5s / 10s`

이 제어값이 있어야 다음 질문이 생긴다.

- working set이 메모리보다 크면 어떻게 되나
- TTL이 짧아지면 hit는 얼마나 무너지나
- write-heavy 환경에서는 왜 Redis+DB가 더 비쌀 수 있나

## 대시보드의 의미

상단 패널은 관측용이다.

- `Latency`
- `Storage Activity`
- `Storage Usage`
- `Answer`

하단 패널은 제어용이다.

- `Status`
- `Manual Command`
- `Input Scenarios`

즉 이 화면은 “설명용 포스터”가 아니라 “실험 콘솔”이다.

## 직접 해볼 것

1. `Read 100%`와 `Read 0%`를 비교해본다.
2. 같은 시나리오를 `256B`와 `2048B`에서 각각 돌려본다.
3. TTL을 `OFF`와 `0.5s`로 바꿔 `Storage Usage`와 `Latency` 차이를 관찰한다.
