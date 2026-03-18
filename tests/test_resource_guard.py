from internal.guard.limits import ResourceLimits
from internal.guard.resource_guard import ResourceGuard


def create_resource_guard() -> ResourceGuard:
    return ResourceGuard(
        ResourceLimits(
            max_connections=2,
            max_request_size_bytes=8,
            max_array_items=16,
            max_resp_depth=4,
            max_blob_size_bytes=32,
        )
    )


def test_is_request_size_allowed_returns_true_within_limit() -> None:
    guard = create_resource_guard()

    assert guard.is_request_size_allowed(8) is True


def test_is_connection_allowed_returns_false_at_limit() -> None:
    guard = create_resource_guard()

    assert guard.is_connection_allowed(2) is False


def test_validate_request_size_matches_new_request_size_check() -> None:
    guard = create_resource_guard()

    assert guard.validate_request_size(7) is True
    assert guard.validate_request_size(9) is False
