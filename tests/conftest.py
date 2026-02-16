import pytest

from sentry_tool.monitoring import setup_logging

# Configure structlog once for the test session so log.error() writes to stderr
setup_logging()

BASE_URL = "https://sentry.test.local"
API_BASE = f"{BASE_URL}/api/0"
ORG = "test-org"
PROJECT = "test-project"


@pytest.fixture
def mock_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SENTRY_URL", BASE_URL)
    monkeypatch.setenv("SENTRY_ORG", ORG)
    monkeypatch.setenv("SENTRY_PROJECT", PROJECT)
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "test_token_12345")


@pytest.fixture
def mock_sentry_api(mock_config, requests_mock, request):
    """Pre-wires standard API routes using sibling fixtures resolved via request."""
    data = {
        name: request.getfixturevalue(name)
        for name in [
            "sample_issue",
            "sample_issue_list",
            "sample_event",
            "sample_events_list",
            "sample_tag_values",
        ]
    }
    requests_mock.get(
        f"{API_BASE}/projects/{ORG}/{PROJECT}/issues/",
        json=data["sample_issue_list"],
    )
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/issues/20/",
        json=data["sample_issue"],
    )
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/issues/20/events/latest/",
        json=data["sample_event"],
    )
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/issues/20/events/",
        json=data["sample_events_list"],
    )
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/issues/20/tags/server_name/",
        json=data["sample_tag_values"],
    )
    return requests_mock


@pytest.fixture
def sample_issue():
    return {
        "id": "20",
        "shortId": "TEST-PROJECT-K",
        "title": "failed to index document",
        "status": "unresolved",
        "substatus": "ongoing",
        "level": "error",
        "priority": "high",
        "count": 2713930,
        "firstSeen": "2025-12-15T04:41:46.395962Z",
        "lastSeen": "2026-02-02T21:38:16Z",
        "permalink": "https://sentry.test.local/organizations/test-org/issues/20/",
        "tags": [
            {"key": "environment", "totalValues": 2717049},
            {"key": "server_name", "totalValues": 2717049},
        ],
        "firstRelease": {"version": "app@0.1.21"},
        "lastRelease": {"version": "app@0.1.62"},
    }


@pytest.fixture
def sample_issue_list():
    return [
        {
            "id": "20",
            "shortId": "TEST-PROJECT-K",
            "status": "unresolved",
            "level": "error",
            "count": 2713597,
            "title": "failed to index document",
        },
        {
            "id": "19",
            "shortId": "TEST-PROJECT-J",
            "status": "resolved",
            "level": "warning",
            "count": 1234,
            "title": "deprecated API usage",
        },
        {
            "id": "18",
            "shortId": "TEST-PROJECT-H",
            "status": "unresolved",
            "level": "error",
            "count": 5678,
            "title": "database connection timeout",
        },
    ]


@pytest.fixture
def sample_event():
    return {
        "eventID": "d3f1d81247ad4516b61da92f1db050dd",  # pragma: allowlist secret
        "title": "failed to index document",
        "message": "failed to index document",
        "dateCreated": "2026-02-02T21:38:32.038000Z",
        "tags": [
            {"key": "server_name", "value": "test-server-0"},
            {"key": "environment", "value": "production"},
        ],
        "sdk": {"name": "sentry.go", "version": "0.40.0"},
        "release": {"version": "app@0.1.62"},
        "context": {
            "caller": "main.go:123",
            "stack": "goroutine 1 [running]",
        },
        "entries": [
            {"type": "message", "data": {"formatted": "failed to index document"}},
            {
                "type": "exception",
                "data": {
                    "values": [
                        {
                            "type": "IndexError",
                            "value": "document ID not found",
                            "stacktrace": {"frames": []},
                        }
                    ]
                },
            },
        ],
    }


@pytest.fixture
def sample_events_list():
    return [
        {
            "eventID": "4ac1c8d259134c0f86da4247471b82c3",  # pragma: allowlist secret
            "dateCreated": "2026-02-02T21:38:44Z",
            "tags": [{"key": "server_name", "value": "test-server-0"}],
        },
        {
            "eventID": "3bc2d7e248023b1e75cb3146380a91b2",  # pragma: allowlist secret
            "dateCreated": "2026-02-02T21:37:22Z",
            "tags": [{"key": "server_name", "value": "test-server-1"}],
        },
        {
            "eventID": "2ab1c6f137912a0d64ba2035270b80a1",  # pragma: allowlist secret
            "dateCreated": "2026-02-02T21:36:15Z",
            "tags": [{"key": "server_name", "value": "test-server-0"}],
        },
    ]


@pytest.fixture
def sample_tag_values():
    return {
        "uniqueValues": 2717301,
        "topValues": [
            {"value": "test-server-0", "count": 1234567, "percentage": 0.45},
            {"value": "test-server-1", "count": 987654, "percentage": 0.36},
            {"value": "test-server-2", "count": 495080, "percentage": 0.19},
        ],
    }


@pytest.fixture
def sample_project_list():
    return [
        {
            "slug": "otel-collector",
            "name": "OTel Collector",
            "platform": "go",
            "status": "active",
        },
        {
            "slug": "web-frontend",
            "name": "Web Frontend",
            "platform": "javascript",
            "status": "active",
        },
        {
            "slug": "api-gateway",
            "name": "API Gateway",
            "platform": None,
            "status": "active",
        },
    ]


@pytest.fixture
def sample_transactions_list():
    return {
        "data": [
            {
                "id": "7a9d60f0dd2b4cea89c4f7c53b242c47",
                "title": "live-tail",
                "trace": "b9b5253f2a364edab6d15806c6cf4029",
                "transaction.duration": 83067,
                "transaction.status": "unknown",
                "project": "test-project",
                "project.name": "test-project",
                "timestamp": "2026-02-15T13:06:54+00:00",
            },
            {
                "id": "f7b865fe94554bfc87c355d310deb03b",
                "title": "live-tail",
                "trace": "6f07af1a087146a28a640043bcc25161",
                "transaction.duration": 297,
                "transaction.status": "unknown",
                "project": "test-project",
                "project.name": "test-project",
                "timestamp": "2026-02-15T12:48:34+00:00",
            },
        ]
    }


@pytest.fixture
def sample_trace_events():
    return {
        "data": [
            {
                "id": "abc123def456",
                "title": "/api/users",
                "span_id": "a1b2c3d4e5f6",
                "transaction.duration": 142,
                "transaction.status": "ok",
                "project": "test-project",
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
            {
                "id": "def789abc012",
                "title": "/api/auth",
                "span_id": "f6e5d4c3b2a1",
                "transaction.duration": 89,
                "transaction.status": "ok",
                "project": "test-project",
                "timestamp": "2024-01-15T10:30:01+00:00",
            },
        ]
    }


@pytest.fixture
def sample_transaction_detail():
    return {
        "eventID": "d3f1d81247ad4516b61da92f1db050dd",  # pragma: allowlist secret
        "title": "/api/users",
        "dateCreated": "2024-01-15T10:30:00+00:00",
        "contexts": {
            "trace": {
                "trace_id": "abc123def456789012345678901234ab",
                "span_id": "a1b2c3d4e5f6",
                "parent_span_id": "1234567890ab",
                "duration": 142.5,
                "status": "ok",
            }
        },
        "entries": [
            {
                "type": "spans",
                "data": [
                    {
                        "op": "db.query",
                        "description": "SELECT * FROM users",
                        "start_timestamp": 1705319400.100,
                        "timestamp": 1705319400.150,
                    },
                    {
                        "op": "http.client",
                        "description": "GET https://api.example.com/validate",
                        "start_timestamp": 1705319400.160,
                        "timestamp": 1705319400.250,
                    },
                ],
            }
        ],
    }
