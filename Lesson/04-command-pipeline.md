# 04. Command Pipeline

## 핵심 질문

- 왜 parser, validator, service를 한 파일에 몰아넣지 않았는가
- 이 분리가 실제로 어떤 이점을 주는가

## 먼저 볼 파일

- `internal/command/parser.py`
- `internal/command/validator.py`
- `internal/command/errors.py`
- `internal/service/command_service.py`

## 세 단계 분리

명령 처리는 세 단계로 나뉜다.

1. Parser
   - RESP 배열을 내부 명령 객체로 만든다.
2. Validator
   - 지원 명령인지, 인자 개수가 맞는지, 숫자 형식이 맞는지 확인한다.
3. Service
   - 실제 저장소를 읽고 쓴다.

이 분리는 아주 중요하다.

- parser는 “형태”를 다룬다.
- validator는 “규칙”을 다룬다.
- service는 “동작”을 다룬다.

이 책임이 섞이면 테스트도 복잡해지고, 새로운 명령을 추가할 때 기존 코드를 깨기 쉽다.

## 예시: `EXPIRE`

`EXPIRE key seconds`는 단순해 보이지만 여러 층이 필요하다.

- parser: 명령 이름과 인자 두 개를 추출
- validator: `seconds`가 숫자인지 확인
- service: 키 존재 여부, TTL 저장, 만료 규칙 처리

즉 “단순한 명령”도 파이프라인 분리의 이유를 잘 보여준다.

## 직접 해볼 것

1. `SET`과 `HSET`의 validator를 비교한다.
2. `WRONGTYPE` 오류가 어디서 만들어지는지 찾는다.
3. 새 명령 하나를 추가한다면 어느 파일부터 바꿔야 하는지 적어본다.
