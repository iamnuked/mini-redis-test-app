# 03. Protocol, Network, and Session

## 핵심 질문

- Redis 같은 서버는 왜 프로토콜 계층과 비즈니스 계층을 분리해야 하는가
- RESP를 직접 구현하면 무엇을 배우게 되는가

## 먼저 볼 파일

- `internal/protocol/resp/request_decoder.py`
- `internal/protocol/resp/response_encoder.py`
- `internal/protocol/resp/hello_handler.py`
- `internal/server/session_handler.py`
- `internal/server/session_context.py`

## RESP를 구현한다는 것

RESP는 단순 텍스트 규약이 아니다. 길이, 타입 접두사, 배열, null, number, error를 명확히 구분하는 wire protocol이다. 이 프로젝트는 이 계층을 직접 구현했기 때문에, “명령 문자열을 split해서 처리하는 서버”와는 차원이 다르다.

RESP 구현을 통해 배우는 것:

- 바이트 스트림에서 프레임 경계를 읽는 법
- 요청 표현과 응답 표현이 왜 분리돼야 하는지
- `HELLO 3` 같은 세션 협상이 어디에 위치해야 하는지

## 세션 핸들러의 역할

세션 핸들러는 “소켓 코드”와 “명령 코드” 사이를 연결한다.

- 소켓에서 바이트를 읽는다.
- 디코더를 호출한다.
- 서비스 파이프라인을 실행한다.
- 인코더로 응답을 만든다.
- 연결 종료를 정리한다.

이 계층이 따로 있기 때문에, 프로토콜 오류와 명령 오류를 다른 층에서 다룰 수 있다.

## `HELLO 3`가 중요한 이유

이 프로젝트는 RESP3를 목표로 하지만, `redis-py`의 기본 연결을 위해 RESP2 호환성도 고려한다. 이 지점은 “실습 서버”를 넘어 “외부 client가 붙을 수 있는 서버”로 발전하는 핵심 포인트다.

## 직접 해볼 것

1. `request_decoder.py`에서 Array 요청이 어떻게 해석되는지 따라간다.
2. `response_encoder.py`에서 `Simple String`, `Null`, `Map`이 어떻게 만들어지는지 본다.
3. CLI 또는 `redis-py`로 `PING`과 `HELLO 3`을 보내보고 응답 차이를 본다.
