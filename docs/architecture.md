# 미니 Redis 아키텍처 설계 문서

## 1. 문서 개요

이 문서는 학습용 미니 Redis의 아키텍처 설계를 정의한다.

본 문서는 [`requirements.md`](requirements.md)를 상위 기능 기준으로 삼고, 해당 요구사항을 어떤 구성요소와 흐름으로 구현할지 설명한다.

문서의 목적은 다음과 같다.

- 요구사항을 만족하는 시스템 구조를 정의한다.
- 구성요소의 책임과 경계를 명확히 한다.
- 명령 처리 흐름과 TTL 처리 위치를 설명한다.
- 필수 기능 구현과 선택 기능 확장을 위한 구조적 기준을 제공한다.

## 2. 아키텍처 목표

이번 미니 Redis의 목표는 Redis의 모든 기능을 재현하는 것이 아니라, 핵심 개념을 학습할 수 있는 최소 기능의 서버와 CLI를 올바른 구조로 구현하는 것이다.

핵심 목표는 다음과 같다.

- 문자열 기반 키-값 저장소를 단순한 구조로 구현한다.
- TCP 소켓 기반 서버 요청/응답 구조를 구현한다.
- CLI를 통해 서버에 명령을 전달할 수 있도록 한다.
- 명령 파싱, 검증, 실행, 응답 생성을 분리한다.
- TTL 기반 만료 처리를 공통화한다.
- 테스트 가능한 구조를 유지한다.
- 선택 기능이 추가되더라도 기존 구조를 크게 흔들지 않도록 한다.

## 3. 시스템 범위와 전제

- 본 시스템은 단일 프로세스, 인메모리 저장소를 전제로 한다.
- 본 시스템은 학습용 구현이며 영속성을 제공하지 않는다.
- 본 시스템은 분산 처리, 복제, 클러스터링을 다루지 않는다.
- 본 시스템은 TCP 소켓 기반 서버를 포함한다.
- 본 시스템은 CLI 클라이언트를 포함한다.
- 본 시스템은 지원 명령 집합에 한정해 Redis RESP3 요청/응답 규약과 호환되는 것을 목표로 한다.
- 본 시스템은 문자열 키와 문자열 값만 지원한다.

단, 아키텍처는 향후 `Hash`, `List`, `Set`, `Sorted Set`을 수용할 수 있도록 확장 가능해야 한다.

## 4. 상위 아키텍처 개요

미니 Redis는 다음 구성요소로 나눈다.

- CLI Client
- Server Listener
- Client Session Handler
- Request Decoder
- Command Parser
- Command Validator
- Command Service
- In-Memory Repository
- Expiration Manager
- Expiration Sweeper
- Response Encoder
- Response Formatter

전체 구조는 다음 원칙을 따른다.

- 네트워크 연결 처리와 명령 실행 책임을 분리한다.
- RESP3 프레이밍과 비즈니스 명령 처리를 분리한다.
- 파싱 책임과 비즈니스 규칙 책임을 분리한다.
- 저장소 접근은 서비스 계층을 통해서만 수행한다.
- TTL 만료 검사는 공통 컴포넌트로 모아 중복을 줄인다.
- 응답 형식 결정은 실행 로직과 분리한다.
- 지연 삭제와 주기적 정리의 책임을 분리한다.

## 5. 구성요소 설계

### 5-1. CLI Client

역할:

- 사용자가 단일 명령 실행 방식으로 서버에 접속하고 명령을 전송할 수 있게 한다.

책임:

- 서버 주소와 포트 해석
- 단일 명령 인자 처리
- 요청 송신 및 응답 출력

비책임:

- 명령 실행
- 저장소 접근
- TTL 정책 판단

### 5-2. Server Listener

역할:

- 지정된 포트에서 TCP 연결을 수락한다.

책임:

- 서버 소켓 바인딩
- 연결 수락
- 세션 핸들러로 연결 위임

비책임:

- 명령 파싱
- 비즈니스 로직 실행

### 5-3. Client Session Handler

역할:

- 개별 클라이언트 연결의 요청/응답 생명주기를 관리한다.

책임:

- 소켓에서 요청 읽기
- Request Decoder 호출
- 명령 처리 파이프라인 호출
- 응답을 Response Encoder에 전달
- 연결 종료 처리

비책임:

- 비즈니스 정책 결정
- 저장소 직접 접근

### 5-4. Request Decoder

역할:

- 네트워크 요청 바이트를 RESP 프레임으로 해석하고 내부 명령 모델로 변환한다.

책임:

- RESP3 프레임 경계 식별
- RESP3 타입 해석
- `HELLO 3` 협상 요청 해석
- 잘못된 RESP 프레임 식별

비책임:

- 명령 유효성 검증
- 명령 실행

### 5-5. Command Parser

역할:

- RESP 명령 배열을 내부 명령 객체로 변환한다.
- 명령어와 인자를 분리한다.
- 명령 형태가 파싱 규약에 맞지 않는 요청을 식별한다.

책임:

- RESP 요청에서 명령 토큰 추출
- 명령어 토큰 추출
- 인자 목록 추출

비책임:

- 비즈니스 규칙 판단
- 저장소 조회 및 수정
- TTL 검사

### 5-6. Command Validator

역할:

- 파싱된 명령이 지원 대상인지 확인한다.
- 명령별 인자 수와 자료형 요구사항을 검증한다.

책임:

- 지원 명령 판별
- 인자 개수 검증
- `EXPIRE`의 초 단위 정수 여부 검증

비책임:

- 실제 명령 실행
- 저장소 상태 판단

### 5-7. Command Service

역할:

- 명령의 실제 비즈니스 동작을 수행한다.
- 각 명령의 요구사항에 맞는 처리 순서를 보장한다.

책임:

- `SET`, `GET`, `DEL`, `EXPIRE`, `TTL` 실행
- 저장소 접근 조정
- TTL 검사 호출
- 응답 생성에 필요한 결과 모델 반환

비책임:

- 원시 입력 문자열 파싱
- 최종 출력 형식 문자열 결정

### 5-8. In-Memory Repository

역할:

- 실제 데이터와 TTL 메타데이터를 메모리 내에서 저장하고 조회한다.

구조 예시:

- 값 저장소: `Map<String, String>`
- 만료 저장소: `Map<String, Long>`

책임:

- 키별 값 저장 및 조회
- 키별 만료 시각 저장 및 조회
- 키 삭제 시 값과 TTL 메타데이터 정리

비책임:

- 만료 여부 판단 정책
- 명령별 비즈니스 규칙

### 5-9. Expiration Manager

역할:

- 키의 만료 여부를 판단하고 필요 시 정리한다.

책임:

- 현재 시각과 만료 시각 비교
- 만료된 키를 값 저장소와 만료 저장소에서 함께 제거
- TTL 계산에 필요한 남은 시간 산출

비책임:

- 명령 파싱
- 명령 유효성 검증
- 응답 포맷 생성

### 5-10. Expiration Sweeper

역할:

- 백그라운드에서 주기적으로 만료 키를 찾아 정리한다.

책임:

- 일정 주기마다 만료 대상 키 검사
- 배치 단위 만료 키 정리
- 서버 종료 시 안전한 중지

비책임:

- 명령 요청 처리
- 응답 생성
- TTL 반환값 결정

### 5-11. Response Formatter

역할:

- 서비스 실행 결과를 RESP 의미 모델로 변환한다.

책임:

- 성공 응답, 오류 응답, null 성격 응답 표현
- RESP3 타입 선택
- 향후 응답 규격이 확정될 경우 해당 규격을 일관되게 적용

비책임:

- 저장소 수정
- 비즈니스 정책 결정

### 5-12. Response Encoder

역할:

- 포맷터 결과를 RESP3 프레임으로 직렬화한다.

책임:

- RESP3 타입별 직렬화
- Blob String, Simple String, Number, Null, Error, Map 프레임 생성

비책임:

- 비즈니스 로직 실행
- 저장소 접근

### 5-13. Observability Adapter

역할:

- 운영 관점의 로그, 메트릭, 장애 분석 데이터를 수집한다.

책임:

- 요청 수, 오류 수, 연결 수 등의 메트릭 기록
- 구조화 로그 출력
- 장애 조사에 필요한 최소 이벤트 기록

비책임:

- 명령 실행
- 응답 형식 결정

### 5-14. Resource Guard

역할:

- 연결 수, 요청 크기, 메모리 사용량 등 자원 보호 정책을 적용한다.

책임:

- 연결 상한 검증
- 요청 크기 제한
- 과부하 시 요청 거부 또는 연결 종료 정책 적용

비책임:

- 비즈니스 명령 실행
- 영속성 처리

## 6. 책임 분리 원칙

본 설계는 다음 책임 분리 원칙을 따른다.

- CLI는 사용자와 서버 사이의 입력/출력만 담당한다.
- Server Listener와 Session Handler는 연결과 전송만 담당한다.
- Decoder와 Encoder는 RESP3 메시지 변환만 담당한다.
- Parser는 문법적 해석만 담당한다.
- Validator는 입력 유효성만 담당한다.
- Service는 명령별 비즈니스 규칙만 담당한다.
- Repository는 저장과 조회만 담당한다.
- Expiration Manager는 TTL 관련 공통 정책만 담당한다.
- Expiration Sweeper는 백그라운드 만료 정리만 담당한다.
- Response Formatter는 결과 표현만 담당한다.
- Observability Adapter는 관측 데이터 기록만 담당한다.
- Resource Guard는 자원 보호 정책만 담당한다.

이 구조를 따르면 비즈니스 로직이 입력 처리 코드나 저장소 코드에 흩어지지 않는다.

## 7. 데이터 모델 설계

### 7-1. 값 저장소

- 역할: 실제 문자열 값을 저장한다.
- 구조 예시: `Map<String, String>`
- 조회, 삽입, 삭제를 빠르게 처리할 수 있어야 한다.

현재 1차 구현은 문자열 값만 저장한다.

### 7-2. 만료 저장소

- 역할: 각 키의 만료 시각을 저장한다.
- 구조 예시: `Map<String, Long>`
- 값은 현재 시각 기준으로 계산된 절대 만료 시각으로 저장하는 것을 기본 정책으로 한다.

### 7-3. 절대 만료 시각 선택 이유

- 현재 시각과 직접 비교하기 쉽다.
- TTL 남은 시간을 계산하기 쉽다.
- 테스트에서 시간 이동을 모의하기 쉽다.
- `EXPIRE` 처리 시 `현재 시각 + seconds` 규칙을 명확히 적용할 수 있다.

### 7-4. 자료형 확장 방향

현재 값 저장소는 문서 이해를 위해 `Map<String, String>`으로 설명하지만, 장기적으로는 다음과 같은 추상 모델로 확장할 수 있어야 한다.

- `Map<String, RedisValue>`

`RedisValue`는 자료형 태그와 실제 값을 함께 가지는 구조로 확장할 수 있다.

예시 개념:

- `StringValue`
- `HashValue`
- `ListValue`
- `SetValue`
- `SortedSetValue`

이 방향을 따르면 키별 자료형 검증과 자료구조별 명령 분기를 서비스 계층에서 명확히 처리할 수 있다.

## 8. 명령 처리 흐름

공통 처리 흐름은 다음과 같다.

1. 사용자가 CLI에서 명령을 입력한다.
2. CLI Client가 서버에 요청을 전송한다.
3. Server Listener가 연결을 수락한다.
4. Resource Guard가 연결 수와 요청 크기 정책을 검사한다.
5. Client Session Handler가 요청을 읽는다.
6. Request Decoder가 RESP 프레임을 해석한다.
7. 세션 시작 시 `HELLO 3` 협상을 처리한다.
8. Command Parser가 RESP 명령 배열을 내부 명령 객체로 변환한다.
9. Command Validator가 명령어와 인자를 검증한다.
10. Command Service가 명령 종류에 따라 실행 경로를 선택한다.
11. 필요한 경우 Expiration Manager가 키의 만료 여부를 먼저 검사한다.
12. Service가 Repository를 통해 값을 조회하거나 수정한다.
13. Service가 실행 결과를 도메인 결과로 반환한다.
14. Response Formatter가 RESP 의미 모델을 결정한다.
15. Response Encoder가 RESP3 프레임으로 직렬화한다.
16. Client Session Handler가 응답을 클라이언트에 전송한다.
17. Observability Adapter가 처리 결과와 오류를 기록한다.
18. CLI Client가 응답을 사용자에게 출력한다.

백그라운드 흐름은 다음과 같다.

1. 서버 시작 시 Expiration Sweeper를 함께 시작한다.
2. Sweeper는 일정 주기마다 TTL 저장소를 조회한다.
3. 만료된 키를 배치 단위로 선택한다.
4. Store Repository와 TTL Repository에서 해당 키를 제거한다.
5. 서버 종료 시 Sweeper를 중지하고 정리한다.

예를 들어 `GET key1`의 흐름은 다음과 같다.

1. CLI가 `GET key1`을 서버로 전송한다.
2. Session Handler가 RESP 요청 프레임을 읽고 Decoder에 전달한다.
3. Decoder가 배열 형태 명령을 해석한다.
4. Parser가 `GET`과 `key1`을 내부 명령으로 변환한다.
5. Validator가 인자 수를 검증한다.
6. Service가 `key1` 조회 전 Expiration Manager를 호출한다.
7. 키가 만료되었으면 Repository에서 값과 TTL 정보를 제거한다.
8. 키가 유효하면 값을 조회한다.
9. Formatter가 RESP3 Blob String 또는 Null 응답을 만든다.
10. Encoder가 응답을 직렬화하고 서버가 CLI로 반환한다.

## 9. 명령별 아키텍처 동작

### 9-1. SET

- Service는 키와 값을 저장소에 기록한다.
- 동일한 키가 이미 있으면 새 값으로 덮어쓴다.
- 기존 TTL이 있으면 제거한다.
- 결과는 성공 응답용 결과 모델로 반환한다.

### 9-2. GET

- Service는 조회 전 Expiration Manager를 호출한다.
- 키가 만료되었다면 삭제 후 null 성격 결과를 반환한다.
- 키가 존재하면 값을 반환한다.

### 9-3. DEL

- Service는 삭제 전 Expiration Manager를 호출해 만료 상태를 정리한다.
- 삭제 대상이 유효하게 존재하면 값과 TTL을 함께 제거한다.
- 존재하지 않으면 미삭제 결과를 반환한다.

### 9-4. EXPIRE

- Validator는 `seconds`가 정수인지 검증한다.
- Service는 대상 키 존재 여부를 먼저 확인한다.
- 필요 시 Expiration Manager로 만료 상태를 먼저 정리한다.
- 키가 유효하면 절대 만료 시각을 계산해 저장한다.

### 9-5. TTL

- Service는 조회 전 Expiration Manager를 호출한다.
- 키가 없으면 미존재 결과를 반환한다.
- TTL 정보가 없으면 TTL 없음 결과를 반환한다.
- TTL 정보가 있으면 남은 시간을 정수 초 단위로 계산해 반환한다.

## 10. TTL 처리 설계

### 10-1. 기본 정책

- TTL은 키 단위로 관리한다.
- 만료 시각은 절대 시각으로 저장한다.
- 만료 검사는 지연 삭제 방식으로 수행한다.
- 만료된 키는 접근 시 제거한다.

### 10-2. 만료 검사 적용 지점

최소한 다음 명령은 실행 전에 만료 검사를 수행해야 한다.

- `GET`
- `DEL`
- `EXPIRE`
- `TTL`

선택 기능 추가 시 다음 명령에도 동일한 정책을 적용해야 한다.

- `EXISTS`
- `KEYS pattern`

### 10-3. 지연 삭제 역할

- 접근 시점의 TTL 정확성을 보장한다.
- 응답 직전 상태를 일관되게 유지한다.
- 명령 처리 결과와 저장소 상태가 어긋나지 않게 한다.

### 10-4. 주기적 정리 역할

- 접근이 없는 만료 키도 메모리에서 제거한다.
- 메모리 회수 지연을 줄인다.
- 장시간 남아 있는 만료 키를 줄인다.

### 10-5. 병행 사용 원칙

- 지연 삭제는 기본 메커니즘으로 유지한다.
- 주기적 정리는 보조 메커니즘으로 추가한다.
- 두 메커니즘 모두 동일한 TTL 저장소 기준을 사용해야 한다.

### 10-6. 지연 삭제 방식 선택 이유

- 구현이 단순하다.
- 학습용 프로젝트에 적합하다.
- 백그라운드 스레드나 스케줄러가 없어도 된다.
- 필수 요구사항을 만족하기에 충분하다.

### 10-7. 구현 고려사항

- 지연 삭제와 주기적 정리는 동일 키에 대해 경쟁할 수 있으므로 저장소 접근 일관성을 고려해야 한다.
- Sweeper는 전체 스캔 또는 배치 스캔 중 하나를 선택할 수 있어야 한다.
- Sweep 주기와 배치 크기는 운영 설정으로 조정 가능해야 한다.

## 11. 요구사항 매핑

[`requirements.md`](requirements.md)의 핵심 요구사항과 아키텍처 대응 관계는 다음과 같다.

- TCP 소켓 기반 서버 실행
Server Listener와 Client Session Handler가 연결 수락과 세션 처리를 담당한다.

- CLI 기반 클라이언트 실행
CLI Client가 사용자 입력, 서버 연결, 응답 출력을 담당한다.

- 서버와 클라이언트 간 명령 송수신
Request Decoder, Response Encoder, Session Handler가 요청/응답 경로를 구성한다.

- RESP3 프로토콜 호환
Request Decoder, Response Formatter, Response Encoder가 RESP3 계약을 담당한다.

- 필수 명령 지원
Command Service가 명령별 실행 경로를 제공하고, Validator가 입력 형식을 보장한다.

- 문자열 키-값 저장
In-Memory Repository가 문자열 기반 저장소를 관리한다.

- TTL 기반 만료 처리
Expiration Manager가 공통 만료 정책과 정리 로직을 담당한다.

- 잘못된 입력에 대한 일관된 오류 응답
Command Validator와 Response Formatter가 함께 담당한다.

- 테스트 가능한 구조
Parser, Validator, Service, Repository, Expiration Manager를 분리해 단위 테스트 대상을 명확히 한다.

- `SET` 시 기존 TTL 제거
Command Service가 `SET` 실행 중 TTL 메타데이터 제거 정책을 적용한다.

- 접근 시 만료된 키 자동 정리
Service가 각 명령 실행 전에 Expiration Manager를 호출해 보장한다.

- 요청 단위 장애 격리 및 운영 관측
Client Session Handler, Observability Adapter, Resource Guard가 함께 담당한다.

- 접근 없는 만료 키의 주기적 메모리 정리
Expiration Sweeper가 백그라운드 정리를 담당한다.

## 12. 선택 기능 확장 포인트

### 12-1. `SET key value EX seconds`

- 기존 `SET` 처리 흐름을 재사용할 수 있다.
- Validator에 옵션 인자 규칙을 추가한다.
- Service에서 값 저장 후 만료 시각 저장 단계를 추가한다.

### 12-2. `EXISTS key`

- `GET`과 유사하게 만료 검사를 먼저 수행한다.
- Service에서 값 존재 여부만 반환하는 경로를 추가하면 된다.

### 12-3. `KEYS pattern`

- Repository에서 전체 키 조회 기능이 필요하다.
- 조회 전 각 키에 대한 만료 정리 정책을 정의해야 한다.
- 패턴 매칭 범위는 단순 와일드카드 수준으로 제한하는 것이 바람직하다.

## 13. 자료구조 확장 로드맵

### 13-1. `Hash`

- 권장 내부 표현: `Map<String, Map<String, String>>` 또는 `Map<String, HashValue>`
- 대표 명령 예시: `HSET`, `HGET`, `HDEL`, `HGETALL`
- 서비스 확장 포인트: `hash_service.*`

### 13-2. `List`

- 권장 내부 표현: `Map<String, Deque<String>>` 또는 `Map<String, ListValue>`
- 대표 명령 예시: `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `LRANGE`
- 서비스 확장 포인트: `list_service.*`

### 13-3. `Set`

- 권장 내부 표현: `Map<String, Set<String>>` 또는 `Map<String, SetValue>`
- 대표 명령 예시: `SADD`, `SREM`, `SMEMBERS`, `SISMEMBER`
- 서비스 확장 포인트: `set_service.*`

### 13-4. `Sorted Set`

- 권장 내부 표현: 점수 맵과 정렬 구조의 조합 또는 `Map<String, SortedSetValue>`
- 대표 명령 예시: `ZADD`, `ZREM`, `ZRANGE`, `ZSCORE`
- 서비스 확장 포인트: `zset_service.*`

### 13-5. 확장 원칙

- 자료형별 명령은 독립 서비스로 분리한다.
- 공통 TTL 정책은 자료형과 무관하게 키 단위로 유지한다.
- 프로토콜 계층은 새 명령을 수용하되 기본 요청/응답 형식은 유지한다.
- 자료형 불일치 시 명확한 오류 응답을 반환할 수 있어야 한다.

## 14. RESP3 호환 전략

### 14-1. 기본 방향

- 서버는 지원 명령 집합에 대해 RESP3 프레임을 정확히 해석하고 생성해야 한다.
- 1차 구현의 CLI는 세션 시작 시 `HELLO 3`을 먼저 전송하고, 서버는 이를 처리해 RESP3 모드로 협상할 수 있어야 한다.
- 지원하지 않는 Redis 명령은 RESP3 오류 응답으로 처리한다.

### 14-2. 타입 모델

- 요청 기본형: Array of Blob String
- 응답 기본형: Simple String, Blob String, Number, Null, Simple Error, Map
- 운영 및 메타 정보는 RESP3 Map으로 확장할 수 있다.

### 14-3. 확장 방향

- 향후 자료구조 확장 시 Set, Map, Array 응답을 RESP3 타입으로 자연스럽게 확장한다.
- 서버 푸시 메시지는 현재 범위 밖이지만 구조적으로 추가 가능해야 한다.

## 15. 테스트 관점

아키텍처 관점에서 테스트는 다음 단위로 나눌 수 있다.

- CLI 테스트: 인자 해석, 요청 송신, 응답 출력이 올바른지 확인
- Server Listener/Session 테스트: 연결 수락과 요청/응답 흐름이 올바른지 확인
- Decoder/Encoder 테스트: RESP3 요청/응답 직렬화 규칙이 올바른지 확인
- RESP3 협상 테스트: `HELLO 3` 처리와 세션 모드 전환이 올바른지 확인
- Resource Guard 테스트: 연결 수, 요청 크기, 과부하 정책이 올바른지 확인
- Observability 테스트: 오류 및 요청 메트릭이 기록되는지 확인
- Parser 테스트: 명령어와 인자 분리가 올바른지 확인
- Validator 테스트: 인자 수와 정수 검증이 올바른지 확인
- Service 테스트: 명령별 비즈니스 규칙이 올바른지 확인
- Expiration Manager 테스트: 만료 판단과 정리가 올바른지 확인
- Integration 테스트: 입력부터 응답까지 전체 흐름이 요구사항을 만족하는지 확인

핵심 검증 항목은 다음과 같다.

- CLI가 서버에 연결할 수 있는지 확인
- CLI가 명령을 보내고 응답을 출력하는지 확인
- RESP3 프레임 요청이 정확히 파싱되는지 확인
- RESP3 응답 타입이 명세와 일치하는지 확인
- 비정상 요청이 전체 서버 중단으로 이어지지 않는지 확인
- 연결 과다 또는 큰 요청이 자원 보호 정책에 따라 제어되는지 확인
- 접근이 없는 만료 키가 백그라운드에서 정리되는지 확인
- `SET` 후 `GET`이 값을 반환하는지 확인
- `SET` 후 `EXPIRE`가 적용되는지 확인
- `SET` 재실행 시 기존 TTL이 제거되는지 확인
- 만료 후 `GET` 시 값이 정리되는지 확인
- 만료 후 `TTL` 시 미존재 응답이 반환되는지 확인
- 잘못된 명령 형식에 대해 일관된 오류 응답이 나오는지 확인

## 16. 단계별 구현 전략

복잡도를 낮추기 위해 다음 순서로 구현한다.

1. In-Memory Repository와 기본 값 저장 기능을 구현한다.
2. Command Parser와 Validator를 구현한다.
3. `SET`, `GET`, `DEL` 중심의 Command Service를 구현한다.
4. Expiration Manager와 TTL 저장소를 추가한다.
5. `EXPIRE`, `TTL`을 구현한다.
6. RESP3 타입 모델, Request Decoder, Response Formatter, Response Encoder를 구현한다.
7. Server Listener, Client Session Handler, Resource Guard를 구현한다.
8. Expiration Sweeper를 구현한다.
9. CLI Client와 Observability Adapter를 구현한다.
10. 단위 테스트와 통합 테스트를 보강한다.

## 17. 장애 대응 및 확장 전략

### 17-1. 장애 대응 전략

- 요청 처리 예외는 세션 단위에서 포착하고 전체 서버 중단을 방지한다.
- 네트워크 오류와 명령 처리 오류를 구분해 기록한다.
- graceful shutdown 시 새 연결 수락을 중단하고 진행 중 요청 정리 후 종료한다.
- 운영자가 원인 파악을 할 수 있도록 최소한 연결 이벤트, 오류 이벤트, 요청 처리 결과를 로그에 남긴다.

### 17-2. 프로덕션 확장 전략

- 영속성 계층 추가
현재 Repository 아래에 스냅샷 또는 append-only 로그 계층을 추가할 수 있다.

- 복제 확장
쓰기 리더와 읽기 복제본 구조를 도입할 수 있도록 Service와 Repository 경계를 유지한다.

- 샤딩 확장
키 라우팅 계층을 Server Listener와 Service 사이 또는 상위 라우터 계층으로 분리할 수 있다.

- 운영 인터페이스 확장
헬스 체크, 메트릭 노출, 관리자 명령 채널을 별도 인터페이스로 추가할 수 있다.

- 성능 확장
직렬 처리에서 이벤트 루프 또는 워커 풀 구조로 발전시키더라도 명령 실행 계약은 유지되도록 한다.

## 18. 향후 상세화 필요 항목

다음 항목은 구현 전에 추가 합의가 필요하다.

- 연결 종료 및 타임아웃 처리 정책
- 로그 스키마와 메트릭 수집 방법
- 메모리 제한 및 요청 크기 상한값
- graceful shutdown 절차
- 향후 영속성 및 복제 도입 시 일관성 모델
- RESP3 서버 푸시 메시지 지원 여부
