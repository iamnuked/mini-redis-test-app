# 미니 Redis RESP3 API 명세서

## 1. 문서 목적

이 문서는 미니 Redis 서버와 CLI 클라이언트 사이의 RESP3 요청/응답 규약을 정의한다.

본 문서는 [`requirements.md`](requirements.md)와 [`architecture.md`](architecture.md)를 기반으로 하며, 구현 전에 확정되어야 하는 RESP3 통신 계약을 명확히 하는 것을 목적으로 한다.

## 2. 적용 범위

- TCP 소켓 기반 서버와 CLI 클라이언트 간 통신
- RESP3 세션 협상
- 지원 명령 `HELLO`, `SET`, `GET`, `DEL`, `EXPIRE`, `TTL`, `HSET`, `HGET`, `HDEL`, `HGETALL`, `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `LRANGE`, `SADD`, `SREM`, `SMEMBERS`, `SISMEMBER`, `ZADD`, `ZREM`, `ZRANGE`, `ZSCORE`
- 오류 응답 규칙
- 연결 및 세션 처리 규칙

본 명세는 지원 명령 집합에 한정해 Redis RESP3 요청/응답 규약과 호환되는 것을 목표로 한다.

## 3. RESP3 기본 통신 규칙

### 3-1. 전송 방식

- 서버와 CLI는 TCP 소켓으로 통신한다.
- 클라이언트는 서버 주소와 포트를 지정해 연결한다.
- 서버는 지정 포트에서 연결을 수락한다.
- 세션 초기 단계에서 클라이언트는 `HELLO 3`을 보내 RESP3 모드를 협상해야 한다.

### 3-2. 문자 인코딩

- RESP Blob String 및 Simple String의 문자열 데이터는 UTF-8을 기본 인코딩으로 사용한다.
- 요청과 응답은 BOM 없는 UTF-8을 사용한다.

### 3-3. 프레임 규칙

- RESP 프레임은 타입 접두사와 CRLF(`\r\n`)를 사용한다.
- Blob String은 길이 정보를 포함해야 한다.
- Array는 원소 수를 포함해야 한다.
- 프레임 경계는 RESP3 규약을 따라야 한다.

### 3-4. 요청 표현 규칙

- 요청 기본형은 RESP Array여야 한다.
- 명령어와 인자는 Array 원소로 표현해야 한다.
- 명령어와 문자열 인자는 RESP Blob String 또는 Simple String으로 해석할 수 있어야 한다.
- `SET` 값은 RESP Blob String으로 표현되므로 공백과 개행을 포함할 수 있다.
- 자료구조 명령의 멤버, 필드, 값 인자도 문자열로 표현하며 기본적으로 RESP Blob String을 사용한다.

### 3-5. 명령어 대소문자

- 명령어는 대소문자를 구분하지 않는다.
- 서버 내부 처리 시 명령어는 대문자로 정규화한다.

## 4. CLI 실행 방식

### 4-1. 1차 구현 지원 범위

1차 구현에서 CLI는 단일 명령 실행 방식과 대화형 REPL 실행 방식을 모두 지원한다.

예시:

```text
mini-redis-cli --host 127.0.0.1 --port 6379 GET mykey
mini-redis-cli --host 127.0.0.1 --port 6379 SET mykey "hello world"
```

설명:

- 사용자-facing 실행 명령은 `mini-redis-cli`이다.
- 내부 파이썬 패키지 경로는 `cmd/mini_redis_cli`이다.

### 4-2. 대화형 모드

- 사용자가 명령 없이 `mini-redis-cli`를 실행하면 대화형 REPL 모드로 진입할 수 있어야 한다.
- REPL은 프롬프트를 반복 표시하고, 사용자가 한 줄에 한 명령씩 입력할 수 있어야 한다.
- 사용자가 빈 줄을 입력하면 명령을 전송하지 않고 다음 프롬프트를 표시해야 한다.
- 사용자가 `exit` 또는 `quit`를 입력하면 REPL을 종료해야 한다.
- 현재 서버는 연결당 요청 1개를 처리하므로, REPL 구현은 사용자에게는 연속 입력처럼 보이되 내부적으로는 명령마다 새 연결을 사용할 수 있다.
- REPL에서는 각 명령 전송 전에 `HELLO 3`을 수행해야 한다.
- REPL에서는 개별 명령 오류가 발생해도 전체 REPL 세션은 유지할 수 있어야 한다.

### 4-3. CLI 오류 처리

- 필수 인자가 없으면 CLI는 서버에 연결하지 않고 사용법 오류를 출력해야 한다.
- 서버 연결 실패 시 CLI는 연결 오류를 출력해야 한다.
- 서버 응답 수신 실패 시 CLI는 통신 오류를 출력해야 한다.
- CLI는 세션 시작 시 `HELLO 3`을 사용해야 한다.

### 4-4. CLI 출력 규칙

- RESP3 성공 응답은 표준 출력으로 표시한다.
- RESP3 오류 응답은 표준 오류로 표시한다.
- CLI는 응답을 사람이 읽기 쉬운 형태로 렌더링할 수 있어야 한다.
- CLI는 서버로부터 성공 응답을 받으면 종료 코드 `0`을 반환해야 한다.
- CLI는 서버로부터 오류 응답을 받으면 종료 코드 `4`를 반환해야 한다.

## 5. 서버 연결 및 동시성 정책

### 5-1. 연결 처리

- 서버는 하나 이상의 클라이언트 연결을 수락할 수 있어야 한다.
- 각 연결은 요청 1개를 처리한 뒤 응답 1개를 반환하고 종료할 수 있다.
- 1차 구현에서는 연결 지속 유지보다 요청-응답 완료를 우선한다.
- 서버는 요청 단위 오류가 발생해도 다른 연결 처리에는 영향을 주지 않아야 한다.
- RESP3 협상 실패 시 서버는 오류 응답 또는 연결 종료 정책을 적용할 수 있다.

### 5-2. 동시성 정책

- 1차 구현에서는 복수 클라이언트의 동시 연결은 허용한다.
- 다만 명령 실행은 단일 스레드 또는 직렬 처리 방식으로 구현할 수 있다.
- 즉, 여러 연결이 들어와도 저장소 변경은 순차적으로 처리되는 것을 기본 정책으로 한다.
- 향후 확장 시 읽기/쓰기 분리, 이벤트 루프, 워커 풀 구조로 발전할 수 있으나 본 명세의 요청/응답 계약은 유지해야 한다.

### 5-3. 타임아웃 및 종료

- 연결 종료 세부 정책은 구현체에 위임한다.
- 다만 요청을 정상 처리한 경우 서버는 응답 송신 후 연결을 종료할 수 있다.
- 서버는 종료 시 새 연결 수락 중단 후 진행 중 요청을 정리하는 graceful shutdown 전략을 가질 수 있다.

### 5-4. 자원 보호 정책

- 서버는 과도한 요청 크기를 거부할 수 있어야 한다.
- 서버는 연결 수 상한을 둘 수 있어야 한다.
- 서버는 과도한 RESP 중첩 깊이와 과도한 배열 원소 수를 거부할 수 있어야 한다.
- 자원 제한 위반 시 서버는 요청 거부 또는 연결 종료를 수행할 수 있다.

## 6. RESP3 응답 형식 규약

서버는 RESP3 타입으로 응답을 반환한다.

1차 구현에서 사용하는 주요 RESP3 응답 타입은 다음과 같다.

- Simple String: `+OK\r\n`
- Blob String: `$<len>\r\n<data>\r\n`
- Number: `:<number>\r\n`
- Null: `_\r\n`
- Simple Error: `-ERR <message>\r\n`
- Map: `%<count>\r\n...`
- Array: `*<count>\r\n...`

## 7. 명령별 RESP3 요청/응답 명세

### 7-1. HELLO

요청 형식:

```text
*2\r\n$5\r\nHELLO\r\n:3\r\n
```

성공 응답:

- RESP3 세션 메타데이터를 담은 Map

예시:

```text
%3
+server
+mini-redis
+version
+1.0
+proto
:3
```

오류 응답:

```text
-ERR unsupported protocol version
```

### 7-2. SET

요청 형식:

```text
*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n
```

성공 응답:

```text
+OK
```

오류 응답:

```text
-ERR wrong number of arguments
```

동작 규칙:

- 키에 값을 저장한다.
- 저장 결과 키의 자료형은 `string`이다.
- 기존 값이 있으면 덮어쓴다.
- 기존 TTL이 있으면 제거한다.

### 7-3. GET

요청 형식:

```text
*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n
```

성공 응답:

- 값이 존재하는 경우

```text
$<len>\r\n<value>\r\n
```

- 키가 없거나 만료된 경우

```text
_
```

오류 응답:

```text
-ERR wrong number of arguments
-WRONGTYPE Operation against a key holding the wrong kind of value
```

### 7-4. DEL

요청 형식:

```text
*2\r\n$3\r\nDEL\r\n$3\r\nkey\r\n
```

성공 응답:

- 삭제 성공

```text
:1
```

- 삭제 대상 없음

```text
:0
```

오류 응답:

```text
-ERR wrong number of arguments
```

### 7-5. EXPIRE

요청 형식:

```text
*3\r\n$6\r\nEXPIRE\r\n$3\r\nkey\r\n:10\r\n
```

성공 응답:

- TTL 설정 성공

```text
:1
```

- 대상 키 없음

```text
:0
```

오류 응답:

```text
-ERR wrong number of arguments
-ERR invalid integer
-ERR invalid ttl
```

동작 규칙:

- `seconds`는 1 이상의 정수여야 한다.
- `seconds`가 0 이하이면 오류로 처리한다.
- 대상 키가 없으면 TTL을 설정하지 않고 `:0`을 반환한다.

### 7-6. TTL

요청 형식:

```text
*2\r\n$3\r\nTTL\r\n$3\r\nkey\r\n
```

성공 응답:

- TTL이 존재하는 경우

```text
:<remaining-seconds>
```

- 키가 존재하지 않는 경우

```text
:-2
```

- 키는 존재하지만 TTL이 없는 경우

```text
:-1
```

오류 응답:

```text
-ERR wrong number of arguments
```

### 7-7. Hash 명령군

지원 명령:

- `HSET key field value`
- `HGET key field`
- `HDEL key field`
- `HGETALL key`

요청 형식:

- `HSET`: `*4\r\n$4\r\nHSET\r\n$<klen>\r\n<key>\r\n$<flen>\r\n<field>\r\n$<vlen>\r\n<value>\r\n`
- `HGET`: `*3\r\n$4\r\nHGET\r\n$<klen>\r\n<key>\r\n$<flen>\r\n<field>\r\n`
- `HDEL`: `*3\r\n$4\r\nHDEL\r\n$<klen>\r\n<key>\r\n$<flen>\r\n<field>\r\n`
- `HGETALL`: `*2\r\n$7\r\nHGETALL\r\n$<klen>\r\n<key>\r\n`

응답 규칙:

- `HSET`: 새 필드 생성 시 `:1`, 기존 필드 덮어쓰기 시 `:0`
- `HGET`: 값이 있으면 Blob String, 없으면 Null
- `HDEL`: 삭제 성공 시 `:1`, 대상 없음 시 `:0`
- `HGETALL`: 존재하면 field/value 쌍을 담은 RESP3 Map, 없으면 빈 Map

동작 규칙:

- 없는 키에 대한 `HSET`은 `hash` 타입 엔트리를 생성해야 한다.
- `HGET`, `HDEL`, `HGETALL`은 없는 키를 빈 hash처럼 처리해야 한다.
- 대상 키가 다른 자료형을 보유하면 타입 오류를 반환해야 한다.

### 7-8. List 명령군

지원 명령:

- `LPUSH key value [value ...]`
- `RPUSH key value [value ...]`
- `LPOP key`
- `RPOP key`
- `LRANGE key start stop`

요청 형식:

- `LPUSH`/`RPUSH`: 첫 원소는 명령어, 둘째는 key, 셋째 이후는 하나 이상의 value를 담는 RESP Array
- `LPOP`/`RPOP`: `*2` 배열
- `LRANGE`: `*4` 배열, `start`와 `stop`은 RESP Number 또는 정수 문자열

응답 규칙:

- `LPUSH`/`RPUSH`: push 후 리스트 길이를 Number로 반환
- `LPOP`/`RPOP`: 원소가 있으면 Blob String, 없으면 Null
- `LRANGE`: 범위 결과를 RESP3 Array로 반환, 없으면 빈 Array

동작 규칙:

- 없는 키에 대한 `LPUSH`/`RPUSH`는 `list` 타입 엔트리를 생성해야 한다.
- `LPOP`, `RPOP`, `LRANGE`는 없는 키를 빈 list처럼 처리해야 한다.
- `LRANGE`는 음수 인덱스를 허용할 수 있으며, 구체 규칙은 Redis와 호환되게 구현해야 한다.
- 대상 키가 다른 자료형을 보유하면 타입 오류를 반환해야 한다.

### 7-9. Set 명령군

지원 명령:

- `SADD key member [member ...]`
- `SREM key member [member ...]`
- `SMEMBERS key`
- `SISMEMBER key member`

요청 형식:

- `SADD`/`SREM`: 첫 원소는 명령어, 둘째는 key, 셋째 이후는 하나 이상의 member를 담는 RESP Array
- `SMEMBERS`: `*2` 배열
- `SISMEMBER`: `*3` 배열

응답 규칙:

- `SADD`: 실제로 추가된 멤버 수를 Number로 반환
- `SREM`: 실제로 제거된 멤버 수를 Number로 반환
- `SMEMBERS`: 멤버 목록을 RESP3 Array로 반환, 없으면 빈 Array
- `SISMEMBER`: 존재하면 `:1`, 없으면 `:0`

동작 규칙:

- 없는 키에 대한 `SADD`는 `set` 타입 엔트리를 생성해야 한다.
- `SREM`, `SMEMBERS`, `SISMEMBER`는 없는 키를 빈 set처럼 처리해야 한다.
- `SMEMBERS`의 반환 순서는 정렬되지 않을 수 있으므로 테스트에서는 집합 동등성으로 검증해야 한다.
- 대상 키가 다른 자료형을 보유하면 타입 오류를 반환해야 한다.

### 7-10. Sorted Set 명령군

지원 명령:

- `ZADD key score member [score member ...]`
- `ZREM key member [member ...]`
- `ZRANGE key start stop`
- `ZSCORE key member`

요청 형식:

- `ZADD`: 첫 원소는 명령어, 둘째는 key, 셋째 이후는 score/member 쌍
- `ZREM`: 첫 원소는 명령어, 둘째는 key, 셋째 이후는 하나 이상의 member
- `ZRANGE`: `*4` 배열, `start`와 `stop`은 RESP Number 또는 정수 문자열
- `ZSCORE`: `*3` 배열

응답 규칙:

- `ZADD`: 새로 추가된 멤버 수를 Number로 반환
- `ZREM`: 실제로 제거된 멤버 수를 Number로 반환
- `ZRANGE`: 점수 오름차순 기준 멤버 목록을 RESP3 Array로 반환
- `ZSCORE`: 점수가 있으면 Blob String 또는 Number 성격 응답, 없으면 Null

동작 규칙:

- 없는 키에 대한 `ZADD`는 `zset` 타입 엔트리를 생성해야 한다.
- `ZREM`, `ZRANGE`, `ZSCORE`는 없는 키를 빈 zset처럼 처리해야 한다.
- `ZADD`의 score는 부동소수점 문자열 또는 수치형 인자를 허용할 수 있으나, 구현과 테스트에서 동일한 파싱 정책을 사용해야 한다.
- 대상 키가 다른 자료형을 보유하면 타입 오류를 반환해야 한다.

## 8. 공통 오류 응답 명세

### 8-1. 지원하지 않는 명령

```text
-ERR unsupported command
```

### 8-2. 빈 요청

```text
-ERR empty command
```

### 8-3. 요청 형식 오류

```text
-ERR invalid request
```

### 8-4. 내부 처리 오류

```text
-ERR internal error
```

### 8-4-1. 타입 불일치 오류

```text
-WRONGTYPE Operation against a key holding the wrong kind of value
```

### 8-5. 자원 제한 초과

```text
-ERR resource limit exceeded
```

### 8-6. 서버 과부하

```text
-ERR server busy
```

## 9. 예시 시나리오

### 9-1. HELLO 3 협상

요청:

```text
*2
$5
HELLO
:3
```

응답:

```text
%3
+server
+mini-redis
+version
+1.0
+proto
:3
```

### 9-2. 기본 저장과 조회

요청:

```text
*3
$3
SET
$5
user1
$5
hello
```

응답:

```text
+OK
```

요청:

```text
*2
$3
GET
$5
user1
```

응답:

```text
$5
hello
```

### 9-3. TTL 없는 키 조회

요청:

```text
*2
$3
TTL
$5
user1
```

응답:

```text
:-1
```

### 9-4. 존재하지 않는 키

요청:

```text
*2
$3
GET
$7
missing
```

응답:

```text
_
```

## 10. 구현 유의사항

- 서버와 CLI는 RESP3 프레임 형식을 사용해야 한다.
- Response Formatter와 Response Encoder는 본 명세의 RESP3 응답 형식을 일관되게 따라야 한다.
- Command Validator는 인자 수, 정수 형식, 지원 명령 여부를 우선 검증해야 한다.
- TTL 계산과 만료 정리 결과는 본 명세의 `TTL`, `GET`, `DEL`, `EXPIRE` 응답 규칙과 일치해야 한다.
- `HELLO 3` 이후 세션은 RESP3 응답 타입을 사용해야 한다.
- CLI는 RESP3 응답을 받아 성공/실패 여부를 명확히 구분해 출력해야 한다.

## 11. 운영 및 확장 고려사항

- 서버는 요청 수, 오류 수, 연결 수를 기록할 수 있어야 한다.
- 오류 로그는 네트워크 오류, 파싱 오류, 검증 오류, 내부 처리 오류를 구분하는 것이 바람직하다.
- 운영 환경에서는 헬스 체크와 메트릭 노출 인터페이스를 추가할 수 있다.
- 장기적으로 영속성, 복제, 샤딩이 도입되더라도 RESP3 명령/응답 계약은 유지하는 것이 바람직하다.
