import socket
import threading

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


def create_command_service() -> CommandService:
    return CommandService(
        clock=FakeClock(current_time=100.0),
        store_repository=InMemoryStoreRepository(),
        ttl_repository=InMemoryTtlRepository(),
    )


def create_resource_guard() -> ResourceGuard:
    return ResourceGuard(
        ResourceLimits(
            max_connections=4,
            max_request_size_bytes=1024,
            max_array_items=16,
            max_resp_depth=4,
            max_blob_size_bytes=1024,
        )
    )


def run_session(request_bytes: bytes, command_service: CommandService) -> bytes:
    server_socket, client_socket = socket.socketpair()
    metrics = Metrics()
    handler = SessionHandler(
        client_socket=server_socket,
        protocol_handler=ProtocolHandler(),
        command_service=command_service,
        response_encoder=RespResponseEncoder(),
        resource_guard=create_resource_guard(),
        metrics=metrics,
    )

    thread = threading.Thread(target=handler.handle)
    thread.start()
    try:
        client_socket.sendall(request_bytes)
        response = client_socket.recv(4096)
    finally:
        client_socket.close()
        server_socket.close()
        thread.join(timeout=1)

    return response


def test_session_integration_returns_hello_response() -> None:
    response = run_session(
        b"*2\r\n$5\r\nHELLO\r\n:3\r\n",
        create_command_service(),
    )

    assert response.startswith(b"%3\r\n")


def test_session_integration_supports_set_then_get_across_sessions() -> None:
    command_service = create_command_service()

    set_response = run_session(
        b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n",
        command_service,
    )
    get_response = run_session(
        b"*2\r\n$3\r\nGET\r\n$3\r\nkey\r\n",
        command_service,
    )

    assert set_response == b"+OK\r\n"
    assert get_response == b"$5\r\nvalue\r\n"


def test_session_integration_returns_error_for_invalid_request() -> None:
    response = run_session(
        b"+PING\r\n",
        create_command_service(),
    )

    assert response == b"-ERR protocol error\r\n"


def test_session_integration_supports_hash_round_trip() -> None:
    command_service = create_command_service()

    set_response = run_session(
        b"*4\r\n$4\r\nHSET\r\n$4\r\nuser\r\n$4\r\nname\r\n$4\r\nmini\r\n",
        command_service,
    )
    get_response = run_session(
        b"*3\r\n$4\r\nHGET\r\n$4\r\nuser\r\n$4\r\nname\r\n",
        command_service,
    )

    assert set_response == b":1\r\n"
    assert get_response == b"$4\r\nmini\r\n"


def test_session_integration_returns_wrongtype_error() -> None:
    command_service = create_command_service()
    run_session(
        b"*3\r\n$3\r\nSET\r\n$3\r\nkey\r\n$5\r\nvalue\r\n",
        command_service,
    )

    response = run_session(
        b"*3\r\n$4\r\nHGET\r\n$3\r\nkey\r\n$5\r\nfield\r\n",
        command_service,
    )

    assert response == (
        b"-ERR WRONGTYPE Operation against a key holding the wrong kind of value\r\n"
    )


def test_session_integration_supports_list_round_trip() -> None:
    command_service = create_command_service()

    push_response = run_session(
        b"*4\r\n$5\r\nRPUSH\r\n$5\r\nqueue\r\n$1\r\na\r\n$1\r\nb\r\n",
        command_service,
    )
    range_response = run_session(
        b"*4\r\n$6\r\nLRANGE\r\n$5\r\nqueue\r\n:0\r\n:-1\r\n",
        command_service,
    )

    assert push_response == b":2\r\n"
    assert range_response == b"*2\r\n$1\r\na\r\n$1\r\nb\r\n"


def test_session_integration_supports_zset_round_trip() -> None:
    command_service = create_command_service()

    add_response = run_session(
        b"*6\r\n$4\r\nZADD\r\n$4\r\nrank\r\n$1\r\n2\r\n$4\r\nbeta\r\n$1\r\n1\r\n$5\r\nalpha\r\n",
        command_service,
    )
    range_response = run_session(
        b"*4\r\n$6\r\nZRANGE\r\n$4\r\nrank\r\n:0\r\n:-1\r\n",
        command_service,
    )

    assert add_response == b":2\r\n"
    assert range_response == b"*2\r\n$5\r\nalpha\r\n$4\r\nbeta\r\n"
