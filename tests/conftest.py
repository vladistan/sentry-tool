import os

import pytest

from sentry_tool.client import api_call
from sentry_tool.config import get_profile, load_config, resolve_sentry_config
from sentry_tool.monitoring import setup_logging

# Configure structlog once for the test session so log.error() writes to stderr
setup_logging()


@pytest.fixture(scope="session")
def live_config():
    """Load real Sentry config. Skip all live tests if unavailable."""
    try:
        app_config = load_config()
    except Exception:
        pytest.skip("No sentry-tool config file found")

    profile_name = os.environ.get("SENTRY_TEST_PROFILE")
    try:
        profile = get_profile(app_config, profile_name)
    except Exception:
        pytest.skip(f"Profile '{profile_name}' not found in config")

    try:
        resolved = resolve_sentry_config(profile)
    except Exception:
        pytest.skip("No valid auth token available for testing")

    return resolved


@pytest.fixture(scope="session")
def live_issue_id(live_config):
    """Discover a real issue ID from the configured project."""
    issues = api_call(
        f"/projects/{live_config['org']}/{live_config['project']}/issues/",
        token=live_config["auth_token"],
        base_url=live_config["url"],
    )
    if not issues:
        pytest.skip("No issues found in configured project")
    return str(issues[0]["id"])


@pytest.fixture(scope="session")
def live_event(live_config, live_issue_id):
    """Discover latest event for the first issue."""
    return api_call(
        f"/organizations/{live_config['org']}/issues/{live_issue_id}/events/latest/",
        token=live_config["auth_token"],
        base_url=live_config["url"],
    )


@pytest.fixture(scope="session")
def live_transaction(live_config):
    """Discover a real transaction from any project in the org."""
    response = api_call(
        f"/organizations/{live_config['org']}/events/"
        "?query=event.type:transaction"
        "&field=title&field=id&field=trace&field=transaction.duration"
        "&field=transaction.status&field=project&field=timestamp"
        "&sort=-timestamp",
        token=live_config["auth_token"],
        base_url=live_config["url"],
    )
    events = response.get("data", [])
    if not events:
        pytest.skip("No transactions found in org")
    return events[0]


@pytest.fixture(scope="session")
def live_transaction_project(live_transaction):
    """Extract the project slug that owns the discovered transaction."""
    project = live_transaction.get("project")
    if not project:
        pytest.skip("Discovered transaction has no project field")
    return project


@pytest.fixture(scope="session")
def live_transaction_id(live_transaction):
    """Extract transaction event ID."""
    return live_transaction["id"]


@pytest.fixture(scope="session")
def live_trace_id(live_transaction):
    """Extract trace ID from discovered transaction."""
    trace_id = live_transaction.get("trace")
    if not trace_id:
        pytest.skip("Discovered transaction has no trace ID")
    return trace_id


@pytest.fixture(scope="session")
def live_tag_key(live_config, live_issue_id):
    """Find a tag key that exists on the discovered issue."""
    issue = api_call(
        f"/organizations/{live_config['org']}/issues/{live_issue_id}/",
        token=live_config["auth_token"],
        base_url=live_config["url"],
    )
    tags = issue.get("tags", [])
    if not tags:
        pytest.skip("Issue has no tags")
    return tags[0]["key"]


@pytest.fixture
def live_transaction_cli_env(live_config, live_transaction_project, monkeypatch):
    """Set SENTRY_* env vars with the transaction's project for CLI tests."""
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)
    monkeypatch.setenv("SENTRY_URL", live_config["url"])
    monkeypatch.setenv("SENTRY_ORG", live_config["org"])
    monkeypatch.setenv("SENTRY_PROJECT", live_transaction_project)
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", live_config["auth_token"])


@pytest.fixture(scope="session")
def live_span_ops(live_config, live_transaction_id, live_transaction_project):
    """Discover span operation types from a real transaction."""
    event = api_call(
        f"/organizations/{live_config['org']}/events/"
        f"{live_transaction_project}:{live_transaction_id}/",
        token=live_config["auth_token"],
        base_url=live_config["url"],
    )
    for entry in event.get("entries", []):
        if entry.get("type") == "spans":
            spans = entry.get("data", [])
            ops = list({s.get("op") for s in spans if s.get("op")})
            if ops:
                return ops
    pytest.skip("Transaction has no spans with operation types")


@pytest.fixture
def live_cli_env(live_config, monkeypatch):
    """Set SENTRY_* env vars from live config for CLI tests."""
    monkeypatch.delenv("SENTRY_PROFILE", raising=False)
    monkeypatch.setenv("SENTRY_URL", live_config["url"])
    monkeypatch.setenv("SENTRY_ORG", live_config["org"])
    monkeypatch.setenv("SENTRY_PROJECT", live_config["project"])
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", live_config["auth_token"])


# ===== Synthetic fixtures for span tree unit tests =====


@pytest.fixture
def sample_transaction_spans():
    base_time = 1705319400.0
    return {
        "eventID": "b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5",  # pragma: allowlist secret
        "title": "GET /api/items",
        "dateCreated": "2024-01-15T10:30:00+00:00",
        "contexts": {
            "trace": {
                "span_id": "root001",
                "duration": 500,
            }
        },
        "entries": [
            {
                "type": "spans",
                "data": [
                    {
                        "span_id": "child001",
                        "parent_span_id": "root001",
                        "op": "db.query",
                        "description": "SELECT * FROM users",
                        "start_timestamp": base_time,
                        "timestamp": base_time + 0.050,
                    },
                    {
                        "span_id": "child002",
                        "parent_span_id": "root001",
                        "op": "http.client",
                        "description": "GET https://api.example.com/data",
                        "start_timestamp": base_time,
                        "timestamp": base_time + 0.200,
                    },
                    {
                        "span_id": "grandchild001",
                        "parent_span_id": "child002",
                        "op": "db.query",
                        "description": "SELECT * FROM cache",
                        "start_timestamp": base_time,
                        "timestamp": base_time + 0.100,
                    },
                ],
            }
        ],
    }
