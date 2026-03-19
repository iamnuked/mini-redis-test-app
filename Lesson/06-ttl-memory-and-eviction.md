# 06. TTL, Memory, and Eviction

## 핵심 질문

- TTL과 eviction은 각각 무엇을 해결하는가
- 둘이 동시에 들어가면 캐시 서버는 어떻게 달라지는가

## 먼저 볼 파일

- `internal/expiration/expiration_manager.py`
- `internal/expiration/expiration_sweeper.py`
- `internal/expiration/ttl_calculator.py`
- `internal/service/expire_service.py`
- `internal/service/ttl_service.py`
- `internal/service/command_service.py`

## TTL

TTL은 “값이 언제 사라져야 하는가”를 정의한다.

이 프로젝트는 두 가지 방식을 같이 쓴다.

- lazy expiration
  - 접근 시점에 만료 확인
- background sweep
  - 접근이 없어도 주기적으로 정리

이 조합은 단순하면서도 현실적이다.

## maxmemory와 eviction

Arena 실험을 위해 `maxmemory`와 eviction이 들어갔다.

- `INFO MEMORY`
- `CONFIG SET maxmemory`
- strict cap enforcement
- eviction counter

이 덕분에 작은 메모리에서 miss/fill/eviction이 실제로 발생한다.

## 왜 중요한가

TTL만 있으면 “언제 지울지”를 배운다.  
Eviction까지 있으면 “메모리가 찼을 때 무엇을 지울지”를 배우게 된다.

즉 이 프로젝트는 단순 key-value 저장소보다 훨씬 현실적인 캐시 실험 대상이 된다.

## 직접 해볼 것

1. TTL을 `0.5s`로 두고 값을 넣은 뒤 언제 사라지는지 본다.
2. memory를 `256B`로 두고 read scenario를 돌려 eviction이 발생하는지 본다.
3. `used_memory > maxmemory`가 남지 않도록 최근 수정된 strict cap 로직을 읽어본다.
