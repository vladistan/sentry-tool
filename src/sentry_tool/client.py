"""Sentry API client with automatic retry for transient failures."""

from typing import Any

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from sentry_tool.monitoring import get_logger

log = get_logger("client")

HTTP_NOT_FOUND = 404


class NotFoundError(Exception):
    """Raised when a Sentry API resource is not found (404)."""


@retry(
    retry=retry_if_exception_type(requests.exceptions.RequestException),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def api_call(endpoint: str, token: str, base_url: str) -> Any:
    full_url = f"{base_url}/api/0{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(full_url, headers=headers, timeout=30)

    if response.status_code == HTTP_NOT_FOUND:
        raise NotFoundError(endpoint)

    response.raise_for_status()
    return response.json()
