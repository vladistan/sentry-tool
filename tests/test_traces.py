from typer.testing import CliRunner

from sentry_tool.cli import app
from tests.conftest import API_BASE, ORG

runner = CliRunner()


def test_list_transactions_table(mock_config, requests_mock, sample_transactions_list):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json=sample_transactions_list,
    )

    result = runner.invoke(app, ["transactions"])

    assert result.exit_code == 0
    assert "live-tail" in result.stdout
    assert "Showing 2 transactions" in result.stdout


def test_list_transactions_json(mock_config, requests_mock, sample_transactions_list):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json=sample_transactions_list,
    )

    result = runner.invoke(app, ["transactions", "--format", "json"])

    assert result.exit_code == 0
    assert '"live-tail"' in result.stdout
    assert '"trace": "b9b5253f2a364edab6d15806c6cf4029"' in result.stdout


def test_list_transactions_empty(mock_config, requests_mock):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json={"data": []},
    )

    result = runner.invoke(app, ["transactions"])

    assert result.exit_code == 0


def test_transactions_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "transactions" in result.stdout


def test_trace_lookup_table(mock_config, requests_mock, sample_trace_events):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json=sample_trace_events,
    )

    result = runner.invoke(app, ["trace", "abc123def456789012345678901234ab"])

    assert result.exit_code == 0
    assert "/api/users" in result.stdout
    assert "/api/auth" in result.stdout
    assert "Showing 2 events" in result.stdout


def test_trace_lookup_json(mock_config, requests_mock, sample_trace_events):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json=sample_trace_events,
    )

    result = runner.invoke(app, ["trace", "abc123def456789012345678901234ab", "--format", "json"])

    assert result.exit_code == 0
    assert '"/api/users"' in result.stdout
    assert '"/api/auth"' in result.stdout


def test_trace_lookup_max(mock_config, requests_mock, sample_trace_events):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json=sample_trace_events,
    )

    result = runner.invoke(app, ["trace", "abc123def456789012345678901234ab", "-n", "1"])

    assert result.exit_code == 0
    assert "Showing 1 events" in result.stdout


def test_trace_lookup_empty(mock_config, requests_mock):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/",
        json={"data": []},
    )

    result = runner.invoke(app, ["trace", "abc123def456789012345678901234ab"])

    assert result.exit_code == 0


def test_trace_lookup_invalid_id(mock_config):
    result = runner.invoke(app, ["trace", "invalid"])

    assert result.exit_code == 1


def test_trace_lookup_invalid_id_too_short(mock_config):
    result = runner.invoke(app, ["trace", "ZZZZ"])

    assert result.exit_code == 1


def test_trace_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "trace" in result.stdout


def test_transaction_detail_table(mock_config, requests_mock, sample_transaction_detail):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/test-project:d3f1d81247ad4516b61da92f1db050dd/",
        json=sample_transaction_detail,
    )

    result = runner.invoke(app, ["transaction", "d3f1d81247ad4516b61da92f1db050dd"])

    assert result.exit_code == 0
    assert "/api/users" in result.stdout
    assert "abc123def456789012345678901234ab" in result.stdout
    assert "2 spans" in result.stdout


def test_transaction_detail_json(mock_config, requests_mock, sample_transaction_detail):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/test-project:d3f1d81247ad4516b61da92f1db050dd/",
        json=sample_transaction_detail,
    )

    result = runner.invoke(
        app, ["transaction", "d3f1d81247ad4516b61da92f1db050dd", "--format", "json"]
    )

    assert result.exit_code == 0
    assert '"title": "/api/users"' in result.stdout


def test_transaction_detail_no_spans(mock_config, requests_mock):
    transaction_no_spans = {
        "eventID": "test123",
        "title": "/api/simple",
        "dateCreated": "2024-01-15T10:30:00+00:00",
        "contexts": {
            "trace": {
                "trace_id": "abc123",
                "span_id": "def456",
                "parent_span_id": None,
                "duration": 50,
                "status": "ok",
            }
        },
        "entries": [],
    }
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/test-project:test123/",
        json=transaction_no_spans,
    )

    result = runner.invoke(app, ["transaction", "test123"])

    assert result.exit_code == 0
    assert "No span data found" in result.stdout


def test_transaction_detail_404(mock_config, requests_mock):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/test-project:notfound/",
        status_code=404,
    )

    result = runner.invoke(app, ["transaction", "notfound"])

    assert result.exit_code == 1


def test_transaction_timeline(mock_config, requests_mock, sample_transaction_detail):
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/test-project:d3f1d81247ad4516b61da92f1db050dd/",
        json=sample_transaction_detail,
    )

    result = runner.invoke(app, ["transaction", "d3f1d81247ad4516b61da92f1db050dd", "--timeline"])

    assert result.exit_code == 0
    assert "█" in result.stdout
    assert "SELECT" in result.stdout
    assert "GET" in result.stdout
    assert "Span Timeline" in result.stdout


def test_transaction_timeline_no_spans(mock_config, requests_mock):
    transaction_no_spans = {
        "eventID": "test123",
        "title": "/api/simple",
        "dateCreated": "2024-01-15T10:30:00+00:00",
        "contexts": {
            "trace": {
                "trace_id": "abc123",
                "span_id": "def456",
                "parent_span_id": None,
                "duration": 50,
                "status": "ok",
            }
        },
        "entries": [],
    }
    requests_mock.get(
        f"{API_BASE}/organizations/{ORG}/events/test-project:test123/",
        json=transaction_no_spans,
    )

    result = runner.invoke(app, ["transaction", "test123", "--timeline"])

    assert result.exit_code == 0
    assert "No span data found" in result.stdout


def test_transaction_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "transaction" in result.stdout
