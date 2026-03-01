from typer.testing import CliRunner

from sentry_tool.cli import app

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
