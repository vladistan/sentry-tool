"""Tests for Sentry API client with retry logic."""

import pytest

from sentry_tool.client import NotFoundError, api_call

MAX_RETRY_ATTEMPTS = 3


def test_api_call_success(live_config):
    result = api_call(
        f"/organizations/{live_config['org']}/projects/",
        token=live_config["auth_token"],
        base_url=live_config["url"],
    )
    assert isinstance(result, list)


def test_api_call_404_raises_not_found(live_config):
    with pytest.raises(NotFoundError):
        api_call(
            "/organizations/nonexistent-org-xyz/issues/99999999/",
            token=live_config["auth_token"],
            base_url=live_config["url"],
        )


def test_api_call_has_retry_decorator():
    assert hasattr(api_call, "retry")
    assert api_call.retry.stop.max_attempt_number == MAX_RETRY_ATTEMPTS
