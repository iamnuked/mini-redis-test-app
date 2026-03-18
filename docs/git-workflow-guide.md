# 미니 Redis Git 작업 흐름 안내서

## 1. 문서 목적

이 문서는 팀원이 이슈를 만들고, 이슈 기반 브랜치를 생성하고, 작업 후 `dev` 브랜치에 병합하는 과정을 쉽게 따라할 수 있도록 설명한다.

본 문서는 [`collaboration-rules.md`](collaboration-rules.md)와 [`team-work-allocation.md`](team-work-allocation.md)를 바탕으로 하며, 실제 협업에서 반복적으로 사용하는 Git 흐름을 단계별로 안내하는 것을 목적으로 한다.

## 2. 기본 개념

팀은 다음 3가지 종류의 브랜치를 사용한다.

- `main`
  - 안정 상태를 유지하는 브랜치
- `dev`
  - 팀이 함께 개발 내용을 모으는 브랜치
- 작업 브랜치
  - 각자 맡은 이슈를 구현하는 브랜치

기본 흐름은 다음과 같다.

1. 이슈를 만든다.
2. 이슈 번호로 작업 브랜치를 만든다.
3. 작업하고 커밋한다.
4. 작업 브랜치를 원격에 올린다.
5. `dev`에 병합한다.
6. 팀 전체 검증이 끝나면 나중에 `dev`를 `main`에 병합한다.

## 3. 왜 이슈를 먼저 만드는가

이슈를 먼저 만들면 좋은 점은 다음과 같다.

- 작업 목적이 분명해진다.
- 누가 무엇을 하는지 추적하기 쉽다.
- 브랜치 이름을 일관되게 만들 수 있다.
- 리뷰할 때 변경 이유를 설명하기 쉽다.

즉, 브랜치를 먼저 만들기보다 이슈를 먼저 만드는 것이 팀 협업에 더 유리하다.

## 4. 이슈에는 무엇을 적는가

이슈에는 아래 정도만 적어도 충분하다.

- 제목
  - 예: `RESP3 request decoder 구현`
- 작업 목적
  - 왜 필요한지 한두 줄
- 작업 범위
  - 어떤 파일이나 모듈을 건드릴지
- 완료 조건
  - 무엇이 되면 끝난 것으로 볼지

예시:

```text
제목: RESP3 request decoder 구현

목적:
- 서버가 RESP3 Array 요청을 읽을 수 있도록 한다.

범위:
- internal/protocol/resp/request_decoder.py
- internal/protocol/resp/types.py

완료 조건:
- HELLO 3 요청을 읽을 수 있다.
- SET/GET/DEL/EXPIRE/TTL 기본 요청을 파싱할 수 있다.
```

## 5. 이슈를 만든 뒤 브랜치를 만드는 방법

브랜치 이름은 보통 다음 형식을 사용한다.

```text
<type>/<issue-id>-<short-description>
```

예시:

- `feat/12-request-decoder`
- `feat/18-expire-ttl-service`
- `fix/27-session-handler-error-path`
- `test/31-cli-integration`
- `docs/35-git-workflow-guide`

### 브랜치 만들기 예시

먼저 `dev` 최신 상태에서 시작하는 것이 좋다.

```bash
git checkout dev
git pull origin dev
git checkout -b feat/12-request-decoder
```

이렇게 하면 `dev`를 기준으로 새 작업 브랜치가 만들어진다.

## 6. 작업 중에는 어떻게 커밋하는가

작업 브랜치에서 파일을 수정한 뒤, 의미 있는 단위로 커밋한다.

예시:

```bash
git status
git add internal/protocol/resp/request_decoder.py
git add internal/protocol/resp/types.py
git commit -m "feat: add RESP3 request decoder skeleton"
```

좋은 커밋 메시지 예시:

- `feat: add RESP3 request decoder skeleton`
- `feat: implement ttl service`
- `fix: handle invalid expire argument`
- `test: add cli integration test`
- `docs: add git workflow guide`

한 번에 너무 많은 내용을 커밋하지 않는 것이 좋다.

## 7. 작업 브랜치를 원격에 올리는 방법

작업을 백업하고 팀과 공유하려면 원격 저장소에 브랜치를 올린다.

```bash
git push -u origin feat/12-request-decoder
```

처음 한 번은 `-u` 옵션을 붙여두면 이후에는 `git push`만 써도 된다.

## 8. 작업이 끝난 뒤 `dev`에 병합하는 방법

권장 방식은 다음 둘 중 하나다.

- Pull Request를 만들어 `dev`에 병합
- 로컬에서 `dev`를 최신화한 뒤 직접 병합

팀 협업에서는 보통 Pull Request 방식이 더 안전하다.

### 방법 1. Pull Request 방식

1. 작업 브랜치를 원격에 push 한다.
2. 저장소에서 base를 `dev`로 두고 PR을 만든다.
3. 변경 내용을 확인한다.
4. 리뷰 또는 간단한 확인 후 `dev`에 병합한다.

이 방식이 가장 추천된다.

### 방법 2. 로컬 병합 방식

```bash
git checkout dev
git pull origin dev
git merge feat/12-request-decoder
git push origin dev
```

이 방식은 작은 팀에서 빠르게 작업할 때 쓸 수 있지만, 공통 조정 파일이 많은 경우에는 PR이 더 안전하다.

## 9. 병합 전에 꼭 확인할 것

- 내가 수정한 파일이 내 담당 범위인지
- 공동 조정 파일이면 담당자와 합의했는지
- 문서를 함께 수정해야 하는 변경인지
- 최소한의 테스트 또는 수동 검증을 했는지
- `dev` 기준으로 충돌이 없는지

## 10. 충돌이 나면 어떻게 하는가

예를 들어 `dev`가 먼저 바뀌었는데 내 브랜치도 같은 파일을 수정했다면 충돌이 날 수 있다.

이럴 때는 보통 아래 순서로 해결한다.

```bash
git checkout dev
git pull origin dev
git checkout feat/12-request-decoder
git merge dev
```

그 다음 충돌 난 파일을 열어서 직접 정리하고:

```bash
git add <충돌 해결한 파일>
git commit -m "merge dev into feat/12-request-decoder"
```

중요한 점은, 충돌 파일이 공동 조정 파일이면 혼자 판단하지 말고 담당자와 먼저 맞추는 것이다.

## 11. `main`에는 언제 병합하는가

개별 작업 브랜치는 바로 `main`으로 가지 않는다.

순서는 다음과 같다.

1. 작업 브랜치 -> `dev`
2. 팀 통합 검증
3. `dev` -> `main`

즉, `main`은 개별 작업의 바로 다음 목적지가 아니라, 팀 통합이 끝난 뒤 가는 브랜치다.

## 12. 자주 쓰는 명령 모음

### 새 작업 시작

```bash
git checkout dev
git pull origin dev
git checkout -b feat/12-request-decoder
```

### 현재 상태 확인

```bash
git status
git branch
```

### 작업 저장

```bash
git add .
git commit -m "feat: add request decoder"
```

### 원격에 올리기

```bash
git push -u origin feat/12-request-decoder
```

### `dev`에 병합

```bash
git checkout dev
git pull origin dev
git merge feat/12-request-decoder
git push origin dev
```

## 13. 이슈 템플릿 예시

이슈는 아래 형식으로 간단하게 작성해도 충분하다.

```text
제목:

목적:

범위:

완료 조건:

담당자:
```

예시:

```text
제목: RESP3 request decoder 구현

목적:
- 서버가 RESP3 Array 요청을 해석할 수 있도록 한다.

범위:
- internal/protocol/resp/request_decoder.py
- internal/protocol/resp/types.py

완료 조건:
- HELLO 3 요청을 읽을 수 있다.
- SET/GET/DEL/EXPIRE/TTL 요청을 파싱할 수 있다.
- 잘못된 요청에 대해 에러 모델을 반환할 수 있다.

담당자:
- 담당자 1
```

문서 변경용 예시:

```text
제목: Git 협업 규칙 문서 보강

목적:
- 팀이 같은 Git 흐름을 사용하도록 문서를 보강한다.

범위:
- docs/git-workflow-guide.md
- docs/collaboration-rules.md

완료 조건:
- 브랜치 생성 절차가 문서화되어 있다.
- dev 병합 절차가 문서화되어 있다.
- 이슈 템플릿 예시가 포함되어 있다.

담당자:
- 담당자 4
```

## 14. 가장 쉬운 실전 요약

가장 단순하게 기억하면 아래 순서만 지키면 된다.

1. 이슈를 만든다.
2. `dev`에서 브랜치를 딴다.
3. 작업하고 커밋한다.
4. 브랜치를 push 한다.
5. `dev`로 PR을 보내거나 병합한다.
6. 팀 검증 후 `main`으로 간다.

이 문서는 Git에 익숙하지 않은 팀원이 동일한 방식으로 작업하기 위한 기본 안내서로 사용한다.
