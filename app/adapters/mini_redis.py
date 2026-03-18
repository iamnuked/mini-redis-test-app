from __future__ import annotations

import socket
import threading
from typing import Any


class MiniRedisError(Exception):
    pass


class MiniRedisClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, timeout_seconds: float = 1.0) -> None:
        self._host = host
        self._port = port
        self._timeout_seconds = timeout_seconds
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    def close(self) -> None:
        with self._lock:
            self._close_socket()

    def health_check(self) -> bool:
        response = self._send_command(["HELLO", 3])
        return isinstance(response, dict) and response.get("server") == "mini-redis"

    def get(self, key: str) -> str | None:
        response = self._send_command(["GET", key])
        if response is None:
            return None
        if not isinstance(response, str):
            raise MiniRedisError(f"unexpected GET response type: {type(response).__name__}")
        return response

    def set(self, key: str, value: str) -> bool:
        response = self._send_command(["SET", key, value])
        return response == "OK"

    def delete(self, key: str) -> int:
        response = self._send_command(["DEL", key])
        if not isinstance(response, int):
            raise MiniRedisError(f"unexpected DEL response type: {type(response).__name__}")
        return response

    def expire(self, key: str, seconds: int) -> int:
        response = self._send_command(["EXPIRE", key, seconds])
        if not isinstance(response, int):
            raise MiniRedisError(f"unexpected EXPIRE response type: {type(response).__name__}")
        return response

    def ttl(self, key: str) -> int:
        response = self._send_command(["TTL", key])
        if not isinstance(response, int):
            raise MiniRedisError(f"unexpected TTL response type: {type(response).__name__}")
        return response

    def _send_command(self, parts: list[str | int]) -> Any:
        with self._lock:
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    sock = self._get_socket()
                    sock.sendall(_encode_command(parts))
                    return _parse_resp(sock)
                except (OSError, MiniRedisError) as exc:
                    self._close_socket()
                    last_error = exc
                    if attempt == 0 and _is_retryable_connection_error(exc):
                        continue
                    raise MiniRedisError(str(exc)) from exc

            if last_error is not None:
                raise MiniRedisError(str(last_error)) from last_error
            raise MiniRedisError("unknown mini-redis command failure")

    def _get_socket(self) -> socket.socket:
        if self._sock is None:
            try:
                self._sock = socket.create_connection((self._host, self._port), timeout=self._timeout_seconds)
                self._sock.settimeout(self._timeout_seconds)
            except OSError as exc:
                raise MiniRedisError(str(exc)) from exc
        return self._sock

    def _close_socket(self) -> None:
        if self._sock is None:
            return
        try:
            self._sock.close()
        finally:
            self._sock = None


def _encode_command(parts: list[str | int]) -> bytes:
    chunks = [f"*{len(parts)}\r\n".encode()]
    for part in parts:
        if isinstance(part, int):
            encoded = str(part).encode()
        else:
            encoded = part.encode()
        chunks.append(f"${len(encoded)}\r\n".encode())
        chunks.append(encoded + b"\r\n")
    return b"".join(chunks)


def _readline(sock: socket.socket) -> bytes:
    data = bytearray()
    while True:
        chunk = sock.recv(1)
        if not chunk:
            raise MiniRedisError("connection closed while reading response")
        data.extend(chunk)
        if data.endswith(b"\r\n"):
            return bytes(data[:-2])


def _parse_resp(sock: socket.socket) -> Any:
    prefix = sock.recv(1)
    if not prefix:
        raise MiniRedisError("empty response")

    if prefix == b"+":
        return _readline(sock).decode()
    if prefix == b"$":
        length = int(_readline(sock).decode())
        if length == -1:
            return None
        payload = bytearray()
        while len(payload) < length + 2:
            chunk = sock.recv(length + 2 - len(payload))
            if not chunk:
                raise MiniRedisError("connection closed while reading bulk string")
            payload.extend(chunk)
        return bytes(payload[:-2]).decode()
    if prefix == b":":
        return int(_readline(sock).decode())
    if prefix == b"_":
        _readline(sock)
        return None
    if prefix == b"-":
        raise MiniRedisError(_readline(sock).decode())
    if prefix == b"%":
        count = int(_readline(sock).decode())
        result: dict[str, Any] = {}
        for _ in range(count):
            key = _parse_resp(sock)
            value = _parse_resp(sock)
            result[str(key)] = value
        return result
    if prefix == b"*":
        count = int(_readline(sock).decode())
        return [_parse_resp(sock) for _ in range(count)]

    raise MiniRedisError(f"unsupported RESP prefix: {prefix!r}")


def _is_retryable_connection_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        fragment in message
        for fragment in (
            "empty response",
            "connection closed",
            "broken pipe",
            "reset by peer",
        )
    )
