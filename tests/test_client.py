"""Tests for Sentry API client with retry logic."""

import pytest

from sentry_tool.client import NotFoundError, api_call

MAX_RETRY_ATTEMPTS = 3


def test_api_call_success(requests_mock):
    requests_mock.get(
        "https://sentry.test.local/api/0/test/endpoint",
        json={"result": "ok"},
    )

    result = api_call(
        "/test/endpoint",
        token="test-token",
        base_url="https://sentry.test.local",
    )

    assert result == {"result": "ok"}


def test_api_call_sends_auth_header(requests_mock):
    requests_mock.get(
        "https://sentry.test.local/api/0/test/endpoint",
        json={},
    )

    api_call("/test/endpoint", token="my-secret-token", base_url="https://sentry.test.local")

    assert requests_mock.last_request.headers["Authorization"] == "Bearer my-secret-token"


def test_api_call_404_raises_not_found(requests_mock):
    requests_mock.get(
        "https://sentry.test.local/api/0/missing",
        status_code=404,
    )

    with pytest.raises(NotFoundError):
        api_call("/missing", token="test-token", base_url="https://sentry.test.local")


def test_api_call_has_retry_decorator():
    assert hasattr(api_call, "retry")
    assert api_call.retry.stop.max_attempt_number == MAX_RETRY_ATTEMPTS
