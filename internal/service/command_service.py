from internal.clock.clock import Clock
from internal.command.command import Command
from internal.command.errors import CommandValidationError
from internal.protocol.resp.types import RespValue
from internal.repository.store_repository import StoreRepository
from internal.repository.ttl_repository import TtlRepository
from internal.service.del_service import DelService
from internal.service.expire_service import ExpireService
from internal.service.get_service import GetService
from internal.service.set_service import SetService
from internal.service.ttl_service import TtlService
from internal.expiration.expiration_manager import ExpirationManager
from internal.expiration.ttl_calculator import TtlCalculator


class CommandService:
    def __init__(
        self,
        clock: Clock,
        store_repository: StoreRepository,
        ttl_repository: TtlRepository,
    ) -> None:
        ttl_calculator = TtlCalculator()
        expiration_manager = ExpirationManager(
            clock=clock,
            ttl_calculator=ttl_calculator,
            store_repository=store_repository,
            ttl_repository=ttl_repository,
        )
        self._set_service = SetService(store_repository, ttl_repository)
        self._get_service = GetService(store_repository, expiration_manager)
        self._del_service = DelService(
            store_repository,
            ttl_repository,
            expiration_manager,
        )
        self._expire_service = ExpireService(
            clock,
            ttl_calculator,
            store_repository,
            ttl_repository,
            expiration_manager,
        )
        self._ttl_service = TtlService(
            store_repository,
            ttl_repository,
            expiration_manager,
        )

    def execute(self, command: Command) -> RespValue:
        if command.name == "SET":
            return RespValue(
                kind="simple_string",
                value=self._set_service.execute(command.arguments[0], command.arguments[1]),
            )
        if command.name == "GET":
            value = self._get_service.execute(command.arguments[0])
            if value is None:
                return RespValue(kind="null", value=None)
            return RespValue(kind="blob_string", value=value)
        if command.name == "DEL":
            return RespValue(
                kind="number",
                value=self._del_service.execute(command.arguments[0]),
            )
        if command.name == "EXPIRE":
            ttl_seconds = self._parse_expire_seconds(command.arguments[1])
            return RespValue(
                kind="number",
                value=self._expire_service.execute(command.arguments[0], ttl_seconds),
            )
        if command.name == "TTL":
            return RespValue(
                kind="number",
                value=self._ttl_service.execute(command.arguments[0]),
            )
        raise CommandValidationError("unsupported command")

    def _parse_expire_seconds(self, value: str) -> int:
        try:
            ttl_seconds = int(value)
        except ValueError as error:
            raise CommandValidationError("invalid integer") from error

        if ttl_seconds <= 0:
            raise CommandValidationError("invalid ttl")

        return ttl_seconds
