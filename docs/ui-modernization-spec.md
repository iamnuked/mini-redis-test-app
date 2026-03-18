# mini-redis 벤치마크 대시보드 UI 현대화 명세서

기준일: 2026-03-19

## 1. 문서 목적

이 문서는 현재 `app/ui/static` 기반 정적 프론트엔드에 `Tailwind CSS + daisyUI`를 도입해 UI를 더 빠르게 개선하고, 차트 시각화 라이브러리를 재선정하기 위한 구현 기준을 정의한다.

이 문서는 디자인 취향 메모가 아니라, 실제 작업 시 바로 옮길 수 있는 기술 명세서다.

## 2. 현재 전제

현재 프론트엔드는 아래 구조를 사용한다.

- `app/ui/static/index.html`
- `app/ui/static/app.js`
- `app/ui/static/styles.css`

즉, React/Vite/Next 기반이 아니라 same-origin으로 서빙되는 정적 HTML + CSS + Vanilla JS 구조다.

따라서 이번 UI 개편의 원칙은 아래와 같다.

- 프레임워크 전환 없이 진행한다.
- Python 백엔드와 same-origin 정적 서빙 구조를 유지한다.
- CSS 작성 생산성을 높이되 런타임 의존성은 최소화한다.
- 기존 기능을 깨지 않고 점진적으로 화면을 교체한다.

## 3. 목표

- 대시보드 UI를 지금보다 더 현대적이고 밀도 있게 개선한다.
- 폼, 카드, 상태 배지, 탭, 테이블, 로딩 상태 같은 공통 UI를 직접 다시 만들지 않는다.
- 차트가 발표 화면에서 더 인상적으로 보이도록 시각화 품질을 올린다.
- 현재의 커스텀 흐름 보드와 충돌하지 않는 기술 조합을 선택한다.

## 4. 기술 결정 요약

### 4-1. UI 라이브러리 결정

채택:

- `Tailwind CSS v4` via CLI
- `daisyUI v5`

선정 이유:

- 현재 프로젝트처럼 정적 HTML 기반 구조에서도 바로 붙일 수 있다.
- Tailwind CLI는 HTML과 JS를 스캔해 정적 CSS 파일을 생성하는 zero-runtime 방식이라 현재 구조와 잘 맞는다.
- daisyUI는 버튼, 카드, 입력폼, 배지, 통계 카드, 탭, 테이블, 로딩 상태 등 대시보드용 컴포넌트를 빠르게 제공한다.
- daisyUI는 기본 제공 테마가 많고, 필요하면 커스텀 테마를 직접 정의할 수 있다.

비채택:

- React 전용 UI 라이브러리(`MUI`, `Chakra UI`, `shadcn/ui`)는 현재 구조와 맞지 않으므로 이번 범위에서 제외한다.

### 4-2. 차트 라이브러리 결정

우선 채택:

- `Apache ECharts`

보조 대안:

- `Chart.js`

비권장:

- `ApexCharts`

결론:

- 이번 프로젝트에서는 `Chart.js`보다 `Apache ECharts`를 기본 차트 라이브러리로 채택한다.
- `Chart.js`는 단순 차트에는 충분하지만, 발표용 대시보드에서 원하는 시각적 밀도와 상호작용, 테마 연동, 동적 전환 표현은 `ECharts`가 더 유리하다.
- `ApexCharts`는 보기 좋은 데모가 많지만, 공식 라이선스 기준으로 사용 조건이 더 복잡해졌으므로 기본 선택지로 삼지 않는다.

## 5. 차트 라이브러리 비교

| 후보 | 현재 구조 적합성 | 장점 | 단점 | 결정 |
| --- | --- | --- | --- | --- |
| Apache ECharts | 매우 높음 | Vanilla JS 친화적, 풍부한 차트 종류, 강한 스타일 커스터마이징, 데이터 전환 애니메이션, 모바일 최적화, Canvas/SVG 지원 | API가 Chart.js보다 무겁고 초기 설정량이 더 많음 | 채택 |
| Chart.js | 높음 | 도입이 쉽고 문서가 좋음, 기본 애니메이션이 좋음, 일반적인 라인/바 차트 구현이 빠름 | Canvas 중심이라 세밀한 스타일링과 대시보드형 복합 표현은 상대적으로 제한적 | 보조 대안 |
| ApexCharts | 높음 | 보기 좋은 샘플이 많고 대시보드 친화적 | 최신 라이선스 조건이 복잡함. 조직 규모와 배포 방식에 따라 추가 라이선스 검토가 필요함 | 비채택 |

### 5-1. ECharts를 선택하는 이유

- 공식 문서 기준으로 CDN 또는 로컬 파일로 바로 포함할 수 있어 현재 정적 구조와 잘 맞는다.
- bar, line, pie뿐 아니라 custom series, rich text, dynamic data, data transition, interaction 구성 요소가 풍부하다.
- Canvas와 SVG 렌더링을 모두 지원해 용도에 맞게 선택 가능하다.
- 발표 화면에서 중요한 gradient, emphasis, animation, tooltip, legend, dataZoom 같은 표현을 구조적으로 지원한다.

### 5-2. Chart.js를 기본 선택으로 두지 않는 이유

- Chart.js는 시작이 매우 쉽고 기본 애니메이션도 좋다.
- 다만 공식 문서 기준으로 Canvas 렌더링 중심이며 CSS 스타일링이 직접 적용되지 않아서, 브랜드 톤이 강한 발표용 대시보드에서는 커스터마이징 비용이 더 빨리 커진다.
- 현재 화면은 단순한 통계 차트만이 아니라 설명형 비교 보드에 가까우므로, 더 유연한 표현력이 중요하다.

### 5-3. ApexCharts를 제외하는 이유

- ApexCharts 공식 라이선스 문서 기준으로 현재는 dual-license 모델이다.
- 연 매출 200만 달러 이상 조직은 Commercial License가 필요하다.
- 제3자에게 배포되는 제품이나 플랫폼 성격이면 OEM / Redistribution License 검토가 필요하다.
- 이번 프로젝트는 발표/데모 시스템이라 기술 선택에서 라이선스 불확실성을 늘릴 이유가 없다.

## 6. 구현 범위

이번 단계의 범위는 아래와 같다.

- Tailwind CSS + daisyUI 빌드 파이프라인 추가
- `index.html` 마크업을 utility class + daisyUI 컴포넌트 구조로 재구성
- 기존 `styles.css`의 역할을 축소하고 app-specific 스타일만 남기기
- KPI/비교/버킷 차트 영역을 ECharts 기반으로 재구성
- 현재 커스텀 흐름 레인 보드는 유지하되 주변 패널 스타일만 개편

이번 단계에서 하지 않는 일은 아래와 같다.

- React/Vite 전환
- 디자인 시스템 패키지 분리
- 차트만으로 흐름 레인 보드를 대체
- 서버 렌더링 도입

## 7. 파일 구조 명세

목표 구조는 아래와 같다.

- `package.json`
- `app/ui/static/index.html`
- `app/ui/static/app.js`
- `app/ui/static/tailwind.css`
- `app/ui/static/build.css` 생성물
- `app/ui/static/styles.css` 또는 `app/ui/static/app.css` 최소 커스텀 레이어

권장 원칙:

- `tailwind.css`는 Tailwind import, daisyUI plugin, theme 정의를 담당한다.
- `build.css`는 CLI 산출물이다.
- 커스텀 CSS는 정말 필요한 경우에만 별도 파일로 유지한다.
- 가능한 한 시각 스타일은 utility class와 daisyUI 토큰으로 해결한다.

## 8. 빌드 파이프라인 명세

### 8-1. 패키지 도입

`npm` 기반 최소 Node 프로젝트를 저장소 루트에 추가한다.

필수 패키지:

- `tailwindcss`
- `@tailwindcss/cli`
- `daisyui`
- `echarts`

### 8-2. 스크립트

권장 스크립트:

```json
{
  "scripts": {
    "build:css": "npx @tailwindcss/cli -i ./app/ui/static/tailwind.css -o ./app/ui/static/build.css --minify",
    "dev:css": "npx @tailwindcss/cli -i ./app/ui/static/tailwind.css -o ./app/ui/static/build.css --watch"
  }
}
```

선택 스크립트:

```json
{
  "scripts": {
    "build:ui": "npm run build:css"
  }
}
```

### 8-3. Tailwind 입력 파일

`app/ui/static/tailwind.css`는 최소 아래 구조를 따른다.

```css
@import "tailwindcss" source(".");

@plugin "daisyui" {
  themes: benchmark --default, night;
}

@plugin "daisyui/theme" {
  name: "benchmark";
  default: true;
  prefersdark: false;
  color-scheme: light;

  --color-base-100: oklch(98% 0.01 85);
  --color-base-200: oklch(95% 0.02 85);
  --color-base-300: oklch(90% 0.03 85);
  --color-base-content: oklch(22% 0.03 240);
  --color-primary: oklch(55% 0.16 210);
  --color-primary-content: oklch(98% 0.01 210);
  --color-secondary: oklch(72% 0.17 60);
  --color-secondary-content: oklch(20% 0.04 60);
  --color-accent: oklch(62% 0.18 170);
  --color-accent-content: oklch(98% 0.01 170);
  --color-neutral: oklch(28% 0.03 240);
  --color-neutral-content: oklch(96% 0.01 240);
  --radius-box: 1.5rem;
  --radius-field: 1rem;
  --radius-selector: 1rem;
}
```

설명:

- `source(".")`로 같은 디렉터리의 HTML/JS 파일을 우선 스캔한다.
- 첫 버전은 `benchmark` 라이트 테마와 `night` 다크 테마만 활성화한다.
- 전체 화면은 라이트 기본값으로 두고, 다크 테마는 후속 토글 옵션으로 준비한다.

## 9. UI 구성 명세

### 9-1. 디자인 방향

시각 방향은 "benchmark lab + presentation dashboard"로 잡는다.

핵심 방향:

- 차가운 엔지니어링 대시보드보다, 발표에 강한 시그널 중심 화면으로 만든다.
- 카드가 많은 화면이더라도 밀도만 높고 답답하지 않게 계층을 분명히 한다.
- 따뜻한 배경 톤과 선명한 신호색을 같이 쓴다.
- 상태는 색만으로 전달하지 않고 텍스트와 아이콘을 같이 사용한다.

### 9-2. 레이아웃 원칙

- 최상단은 hero + 핵심 상태 요약
- 좌측 상단은 실행 제어 패널
- 우측 상단은 run summary와 KPI
- 중앙은 발표용 메인 비교 차트
- 하단은 흐름 보드, request detail, logs, recent runs

### 9-3. daisyUI 컴포넌트 매핑

권장 매핑은 아래와 같다.

- 상단 상태 카드: `card`, `badge`, `stat`
- KPI 보드: `stats`, `stat`
- 실행 폼: `fieldset`, `label`, `input`, `select`, `checkbox`, `toggle`
- 버튼: `btn`, `btn-primary`, `btn-secondary`, `btn-outline`, `btn-ghost`
- 로그/보조 정보: `tabs`, `table`, `mockup-code`, `collapse`
- 로딩 상태: `skeleton`, `loading`
- 상태 표시: `badge`, `status`, `alert`

### 9-4. HTML 클래스 작성 원칙

- 큰 레이아웃은 Tailwind utility class로 직접 구성한다.
- 반복되는 구조만 daisyUI 컴포넌트를 사용한다.
- 임의의 긴 클래스 문자열이 계속 반복되면 `@utility` 또는 작은 커스텀 클래스 추출을 허용한다.
- 색상은 raw hex 남발보다 theme token을 우선한다.

## 10. 차트 명세

### 10-1. 채택 라이브러리

기본 차트 라이브러리는 `Apache ECharts`다.

적용 범위:

- 메인 비교 그래프
- hit rate bucket 추세 차트
- 요청 구성 비중 차트
- 상태/성능 미니 차트

제외 범위:

- 시간축 흐름 레인 보드

시간축 흐름 레인 보드는 현재처럼 커스텀 DOM/SVG/Canvas 로직을 유지한다. 이 영역은 일반 차트보다 인터랙션 규칙이 특수해서 ECharts로 억지로 합치지 않는다.

### 10-2. 차트별 역할

1. 메인 비교 그래프

- 형태: 가로 grouped bar 또는 lollipop bar
- 비교 대상: `DB Only`, `Redis Hit`, `Redis Miss`
- 목표: 발표자가 첫 화면에서 차이를 즉시 설명할 수 있게 한다.

2. 적중률 버킷 차트

- 형태: line + area
- X축: hit rate bucket
- Y축: 평균 latency
- 보조 표시: break-even 지점 marker

3. 요청 구성 차트

- 형태: donut 또는 stacked bar
- 구분: `DB Only`, `Redis Hit`, `Redis Miss`, `Fallback`, `Error`
- 목표: 결과를 숫자뿐 아니라 구조적으로 설명한다.

4. 미니 트렌드 차트

- 형태: sparkline
- 위치: KPI 카드 안 또는 보조 패널
- 목표: 정적 숫자 카드보다 생동감을 준다.

### 10-3. ECharts 사용 원칙

- 기본 렌더러는 `canvas`로 시작한다.
- 작은 도형 위주의 보조 차트나 선명도가 중요할 때만 `svg`를 검토한다.
- 모든 차트는 resize 대응을 위해 공통 `resize()` 처리를 둔다.
- 데이터 갱신은 `setOption()` 기반으로 수행한다.
- run 변경 시 차트 인스턴스 dispose 누락이 없도록 중앙 registry를 둔다.

### 10-4. 스타일 원칙

- 배경은 투명 또는 약한 톤을 사용해 카드와 자연스럽게 섞이게 한다.
- grid line은 매우 약하게, 강조선은 명확하게 잡는다.
- `DB Only`, `Redis Hit`, `Redis Miss`는 전 화면에서 동일한 색 의미를 유지한다.
- 툴팁은 값만 보여주지 말고 설명 문구도 포함한다.
- 애니메이션은 항상 켜두되, 과도한 bounce 연출은 피한다.

권장 의미 색상:

- `DB Only`: neutral / slate
- `Redis Hit`: accent / teal
- `Redis Miss`: secondary / amber
- `Error`: error / red
- `Reference`: primary / blue

## 11. JavaScript 구조 명세

### 11-1. 모듈 역할

가능하면 `app.js` 안에서라도 책임을 아래처럼 나눈다.

- DOM 캐시 및 이벤트 바인딩
- API fetch / state 갱신
- 화면 렌더링
- chart option builder
- chart lifecycle 관리

### 11-2. 차트 관리 레이어

최소 아래 함수 집합을 둔다.

- `initializeCharts()`
- `renderLatencyComparisonChart(presentation)`
- `renderBucketTrendChart(presentation)`
- `renderRequestMixChart(requests, presentation)`
- `disposeCharts()`
- `resizeCharts()`

### 11-3. 상태 동기화 원칙

- 차트는 API 응답 원본을 직접 읽지 않고 presentation read model을 우선 사용한다.
- 색상 의미는 차트 내부에서 제각각 정의하지 말고 공통 상수로 관리한다.
- 선택된 run이 바뀌면 차트, KPI, summary, detail panel이 같은 타이밍에 갱신되어야 한다.

## 12. 단계별 적용 계획

### 단계 1. 빌드 기반 추가

- `package.json` 추가
- Tailwind + daisyUI 설치
- `tailwind.css` 추가
- `build.css` 생성 및 `index.html` 링크 연결

완료 기준:

- 기존 화면이 깨지지 않은 상태로 Tailwind utility class를 사용할 수 있다.

### 단계 2. 상단 레이아웃 교체

- hero, 상태 카드, 실행 제어 패널, KPI 카드부터 daisyUI 기반으로 전환

완료 기준:

- 화면 상단 60%가 새 UI 시스템으로 동작한다.

### 단계 3. 차트 교체

- 핵심 비교 그래프와 bucket chart를 ECharts로 교체

완료 기준:

- 발표 화면에서 기존 차트보다 시각적 강조가 좋아지고, run 전환 시 자연스럽게 업데이트된다.

### 단계 4. 하단 패널 정리

- logs, recent runs, request detail을 card/tabs/collapse 패턴으로 정리

완료 기준:

- 정보 밀도는 유지하면서 시선 흐름이 더 좋아진다.

### 단계 5. 테마와 polish

- `benchmark` 커스텀 테마 보정
- dark theme 선택 기능 추가 여부 결정
- spacing, icon, animation, skeleton 상태 마무리

완료 기준:

- 전체 UI가 "임시 대시보드"가 아니라 발표 가능한 제품 수준의 일관성을 가진다.

## 13. 수용 기준

- same-origin 정적 서빙 구조를 유지한다.
- `npm run build:css`로 CSS 산출물을 만들 수 있다.
- daisyUI 컴포넌트 기반으로 주요 레이아웃이 재구성된다.
- 메인 비교 그래프와 bucket chart가 ECharts로 렌더링된다.
- run 변경, replay, refresh 동작 중 차트가 깨지지 않는다.
- 모바일 폭에서도 주요 KPI, 제어 패널, 차트가 읽을 수 있는 수준으로 유지된다.

## 14. 리스크 및 대응

1. Tailwind class가 누락되어 build 결과가 비는 문제

- 대응: `source(".")`와 필요한 `@source`를 명시한다.

2. 기존 CSS와 utility class가 충돌하는 문제

- 대응: 기존 `styles.css`를 전면 유지하지 말고 점진적으로 축소한다.

3. ECharts 인스턴스 중복 생성 문제

- 대응: chart registry와 dispose 규칙을 명확히 둔다.

4. 차트가 예쁘지만 발표 메시지가 약해지는 문제

- 대응: 차트 수를 늘리기보다 메인 비교 차트와 bucket 차트의 설명력을 우선한다.

5. ApexCharts 같은 대안 검토가 다시 나오는 경우

- 대응: 라이선스 검토 비용과 현재 프로젝트 성격을 고려해 우선순위에서 제외한다.

## 15. 참고 링크

- Tailwind CSS CLI: https://tailwindcss.com/docs/installation/tailwind-cli
- Tailwind source detection: https://tailwindcss.com/docs/detecting-classes-in-source-files
- daisyUI CLI 설치: https://daisyui.com/docs/install/cli/
- daisyUI themes: https://daisyui.com/docs/themes/
- daisyUI components: https://daisyui.com/components/
- Apache ECharts Get Started: https://echarts.apache.org/handbook/en/get-started/
- Apache ECharts Features: https://echarts.apache.org/en/feature.html
- Apache ECharts Data Transition: https://echarts.apache.org/handbook/en/how-to/animation/transition/
- Chart.js Getting Started: https://www.chartjs.org/docs/latest/getting-started/
- Chart.js Overview: https://www.chartjs.org/docs/latest/
- ApexCharts License Options: https://apexcharts.com/license/
- ApexCharts New Licencing Model: https://apexcharts.com/new-licencing-model/
