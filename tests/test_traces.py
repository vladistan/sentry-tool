import pytest
import typer
from typer.testing import CliRunner

from sentry_tool.cli import app
from sentry_tool.commands.traces import (
    _build_query,
    _parse_duration_gt,
    _validate_period,
)

runner = CliRunner()


def test_list_transactions_table(live_cli_env):
    result = runner.invoke(app, ["transactions"])

    assert result.exit_code == 0


def test_list_transactions_json(live_cli_env):
    result = runner.invoke(app, ["transactions", "--format", "json"])

    assert result.exit_code == 0


def test_transactions_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "transactions" in result.stdout


def test_trace_lookup_table(live_transaction_cli_env, live_trace_id):
    result = runner.invoke(app, ["trace", live_trace_id])

    assert result.exit_code == 0
    assert "Showing" in result.stdout


def test_trace_lookup_json(live_transaction_cli_env, live_trace_id):
    result = runner.invoke(app, ["trace", live_trace_id, "--format", "json"])

    assert result.exit_code == 0


def test_trace_lookup_max(live_transaction_cli_env, live_trace_id):
    result = runner.invoke(app, ["trace", live_trace_id, "-n", "1"])

    assert result.exit_code == 0
    assert "Showing 1 events" in result.stdout


def test_trace_lookup_invalid_id():
    result = runner.invoke(app, ["trace", "invalid"])

    assert result.exit_code == 2


def test_trace_lookup_invalid_id_too_short():
    result = runner.invoke(app, ["trace", "ZZZZ"])

    assert result.exit_code == 2


def test_trace_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "trace" in result.stdout


def test_transaction_detail_table(live_transaction_cli_env, live_transaction_id):
    result = runner.invoke(app, ["transaction", live_transaction_id])

    assert result.exit_code == 0
    assert "Transaction" in result.stdout


def test_transaction_detail_json(live_transaction_cli_env, live_transaction_id):
    result = runner.invoke(app, ["transaction", live_transaction_id, "--format", "json"])

    assert result.exit_code == 0
    assert '"title"' in result.stdout


def test_transaction_detail_404(live_cli_env):
    result = runner.invoke(app, ["transaction", "definitely_not_a_real_event"])

    assert result.exit_code == 1


def test_transaction_timeline(live_transaction_cli_env, live_transaction_id):
    result = runner.invoke(app, ["transaction", live_transaction_id, "--timeline"])

    assert result.exit_code == 0


def test_transaction_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "transaction" in result.stdout


# ===== _build_query unit tests =====


BASE = "event.type:transaction project:foo"


def test_build_query_no_filters():
    assert _build_query(BASE) == BASE


def test_build_query_transaction_filter():
    assert _build_query(BASE, transaction="/api/v1/*") == f"{BASE} transaction:/api/v1/*"


def test_build_query_status_filter():
    assert _build_query(BASE, status="ok") == f"{BASE} transaction.status:ok"


def test_build_query_duration_filter():
    assert _build_query(BASE, duration_gt_ms=500) == f"{BASE} transaction.duration:>500"


def test_build_query_user_filter():
    assert _build_query(BASE, user="alice@example.com") == f"{BASE} user.email:alice@example.com"


def test_build_query_raw_query_appended_last():
    assert _build_query(BASE, raw_query="release:1.2.3") == f"{BASE} release:1.2.3"


def test_build_query_deterministic_order():
    result = _build_query(
        BASE,
        user="bob@x.com",
        raw_query="release:1.2.3",
        duration_gt_ms=2000,
        status="ok",
        transaction="/api/foo",
    )
    expected = (
        f"{BASE} transaction:/api/foo transaction.status:ok "
        "transaction.duration:>2000 user.email:bob@x.com release:1.2.3"
    )
    assert result == expected


def test_build_query_skips_none_and_empty():
    assert _build_query(BASE, transaction=None, status="", user=None) == BASE


# ===== _validate_period unit tests =====


@pytest.mark.parametrize("value", ["1m", "30m", "24h", "7d", "2w", "365d"])
def test_validate_period_valid(value):
    assert _validate_period(value) == value


def test_validate_period_none_passthrough():
    assert _validate_period(None) is None


@pytest.mark.parametrize("value", ["bad", "24", "h", "24x", "1.5h", "-7d", ""])
def test_validate_period_invalid_rejected(value):
    with pytest.raises(typer.BadParameter):
        _validate_period(value)


# ===== _parse_duration_gt unit tests =====


def test_parse_duration_none_passthrough():
    assert _parse_duration_gt(None) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("500ms", 500),
        ("0", 0),
        ("1500", 1500),
        ("2s", 2000),
        ("0.5s", 500),
        ("1.5s", 1500),
    ],
)
def test_parse_duration_valid(value, expected):
    assert _parse_duration_gt(value) == expected


@pytest.mark.parametrize("value", ["abc", "ms", "5min", "5h", "-100ms", ""])
def test_parse_duration_invalid_rejected(value):
    with pytest.raises(typer.BadParameter):
        _parse_duration_gt(value)


# ===== URL construction tests (mocked api) =====


@pytest.fixture
def mock_api(monkeypatch):
    """Mock sentry_tool.commands.traces.api to capture endpoint and return empty result."""
    captured = {}

    def fake_api(endpoint, token, base_url):
        captured["endpoint"] = endpoint
        captured["token"] = token
        captured["base_url"] = base_url
        return {"data": []}

    monkeypatch.setattr("sentry_tool.commands.traces.api", fake_api)
    return captured


@pytest.fixture
def mock_cli_env(monkeypatch):
    """Stub get_config so URL construction tests don't need a real config file."""

    def fake_get_config():
        return {
            "url": "https://sentry.test",
            "org": "test-org",
            "project": "test-proj",
            "auth_token": "test-token",  # pragma: allowlist secret
        }

    monkeypatch.setattr("sentry_tool.commands.traces.get_config", fake_get_config)


def test_transactions_url_includes_dataset(mock_api, mock_cli_env):
    result = runner.invoke(app, ["transactions"])
    assert result.exit_code == 0
    assert "dataset=transactions" in mock_api["endpoint"]


def test_transactions_url_includes_period(mock_api, mock_cli_env):
    result = runner.invoke(app, ["transactions", "--period", "7d"])
    assert result.exit_code == 0
    assert "statsPeriod=7d" in mock_api["endpoint"]


def test_transactions_url_includes_transaction_filter(mock_api, mock_cli_env):
    result = runner.invoke(app, ["transactions", "--transaction", "/api/foo"])
    assert result.exit_code == 0
    # query is URL-encoded; transaction:/api/foo encodes colons/slashes
    assert "transaction%3A%2Fapi%2Ffoo" in mock_api["endpoint"]


def test_transactions_url_includes_duration_threshold(mock_api, mock_cli_env):
    result = runner.invoke(app, ["transactions", "--duration-gt", "2s"])
    assert result.exit_code == 0
    assert "transaction.duration%3A%3E2000" in mock_api["endpoint"]


def test_transactions_stats_mode_uses_aggregation_fields(mock_api, mock_cli_env):
    result = runner.invoke(app, ["transactions", "--stats"])
    assert result.exit_code == 0
    endpoint = mock_api["endpoint"]
    assert "field=count()" in endpoint
    assert "field=avg(transaction.duration)" in endpoint
    assert "field=p95(transaction.duration)" in endpoint
    assert "sort=-count()" in endpoint


def test_transactions_invalid_period_exits_nonzero(mock_cli_env):
    result = runner.invoke(app, ["transactions", "--period", "bogus"])
    assert result.exit_code != 0


def test_transactions_invalid_duration_exits_nonzero(mock_cli_env):
    result = runner.invoke(app, ["transactions", "--duration-gt", "five-seconds"])
    assert result.exit_code != 0
