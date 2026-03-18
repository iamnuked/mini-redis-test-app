from internal.protocol.resp.messages import RESP_OK
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository


class SetService:
    def __init__(
        self,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
    ) -> None:
        self._store_repository = store_repository
        self._ttl_repository = ttl_repository

    def execute(self, key: str, value: str) -> str:
        self._store_repository.set(key, value)
        self._ttl_repository.delete_expiration(key)
        return RESP_OK
