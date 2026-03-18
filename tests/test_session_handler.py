from internal.command.command import Command
from internal.clock.fake_clock import FakeClock
from internal.guard.limits import ResourceLimits
from internal.guard.resource_guard import ResourceGuard
from internal.observability.metrics import Metrics
from internal.protocol.resp.protocol_handler import ProtocolHandler
from internal.protocol.resp.response_encoder import RespResponseEncoder
from internal.repository.in_memory_store import InMemoryStoreRepository
from internal.repository.in_memory_ttl import InMemoryTtlRepository
from internal.server.session_handler import SessionHandler
from internal.service.command_service import CommandService


class FakeSocket:
    def __init__(self, request_bytes: bytes | list[bytes]) -> None:
        if isinstance(request_bytes, list):
            self._request_chunks = list(request_bytes)
        else:
            self._request_chunks = [request_bytes]
        self.sent_data = b""
        self.timeout_history: list[float] = []

    def recv(self, size: int) -> bytes:
        if not self._request_chunks:
            return b""
        data = self._request_chunks.pop(0)[:size]
        return data

    def sendall(self, data: bytes) -> None:
        self.sent_data += data

    def settimeout(self, timeout: float) -> None:
        self.timeout_history.append(timeout)


class FakeLogger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.error_messages: list[str] = []

    def info(self, message: str) -> None:
        self.info_messages.append(message)

    def error(self, message: str) -> None:
        self.error_messages.append(message)


def create_command_service() -> CommandService:
    return CommandService(
        clock=FakeClock(current_time=100.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
    )


def create_resource_guard(max_request_size_bytes: int = 1024) -> ResourceGuard:
    return ResourceGuard(
        ResourceLimits(
            max_connections=4,
            max_request_size_bytes=max_request_size_bytes,
            max_array_items=16,
            max_resp_depth=4,
            max_blob_size_bytes=1024,
        )
    )


def test_handle_returns_immediate_hello_response() -> None:
    fake_socket = FakeSocket(b"*2\r\n$5\r\nHELLO\r\n:3\r\n")
    metrics = Metrics()
    logger = FakeLogger()
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=create_command_service(),
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
        logger=logger,
    )

    handler.handle()

    assert fake_socket.sent_data.startswith(b"%3\r\n")
    assert metrics.requests_total == 1
    assert metrics.errors_total == 0
    assert fake_socket.timeout_history == [5, 5, 5]


def test_handle_executes_regular_command_and_writes_response() -> None:
    fake_socket = FakeSocket(b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n")
    metrics = Metrics()
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=create_command_service(),
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
    )

    handler.handle()

    assert fake_socket.sent_data == b"+OK\r\n"
    assert metrics.requests_total == 1
    assert metrics.errors_total == 0
    assert fake_socket.timeout_history == [5, 5, 5]


def test_handle_rejects_request_when_size_limit_is_exceeded() -> None:
    fake_socket = FakeSocket(b"*2\r\n$5\r\nHELLO\r\n:3\r\n")
    metrics = Metrics()
    logger = FakeLogger()
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=create_command_service(),
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(max_request_size_bytes=4),
        metrics=metrics,
        logger=logger,
    )

    handler.handle()

    assert fake_socket.sent_data == b""
    assert metrics.requests_total == 0
    assert metrics.errors_total == 1
    assert logger.error_messages == ["request size limit exceeded"]


def test_handle_logs_protocol_error_and_increments_error_metric() -> None:
    fake_socket = FakeSocket(b"+PING\r\n")
    metrics = Metrics()
    logger = FakeLogger()
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=create_command_service(),
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
        logger=logger,
    )

    handler.handle()

    assert fake_socket.sent_data == b"-ERR protocol error\r\n"
    assert metrics.requests_total == 1
    assert metrics.errors_total == 0
    assert logger.error_messages == []


def test_handle_processes_multiple_requests_on_same_connection() -> None:
    fake_socket = FakeSocket(
        [
            b"*1\r\n$4\r\nPING\r\n",
            b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n",
            b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n",
            b"",
        ]
    )
    metrics = Metrics()
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=create_command_service(),
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
    )

    handler.handle()

    assert fake_socket.sent_data == b"+PONG\r\n+OK\r\n$5\r\nvalue\r\n"
    assert metrics.requests_total == 3
    assert metrics.errors_total == 0


def test_handle_uses_resp2_encoding_before_hello_negotiation() -> None:
    fake_socket = FakeSocket(
        [
            b"*2\r\n$3\r\nGET\r\n$7\r\nmissing\r\n",
            b"",
        ]
    )
    metrics = Metrics()
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=create_command_service(),
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
    )

    handler.handle()

    assert fake_socket.sent_data == b"$-1\r\n"


def test_handle_switches_to_resp3_after_hello() -> None:
    fake_socket = FakeSocket(
        [
            b"*2\r\n$5\r\nHELLO\r\n:3\r\n",
            b"*2\r\n$7\r\nHGETALL\r\n$4\r\nuser\r\n",
            b"",
        ]
    )
    metrics = Metrics()
    command_service = create_command_service()
    command_service.execute(Command(name="HSET", arguments=("user", "name", "mini")))
    handler = SessionHandler(
        client_socket=fake_socket,
        protocol_handler=ProtocolHandler(),
        command_service=command_service,
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
    )

    handler.handle()

    assert b"%1\r\n" in fake_socket.sent_data
