from unittest.mock import MagicMock, patch

from sentry_tool.monitoring import get_logger, resolve_dsn, setup_logging, setup_sentry


def test_setup_sentry_does_not_crash():
    setup_sentry()


def test_setup_sentry_with_environment():
    setup_sentry(environment="test")


def test_setup_logging_does_not_crash():
    setup_logging()


def test_setup_logging_verbose_enables_debug():
    setup_logging(verbose=True)


def test_get_logger_returns_bound_logger():
    setup_logging()
    logger = get_logger("test")
    assert hasattr(logger, "bind")


def test_resolve_dsn_returns_env_var_when_set(monkeypatch):
    env_dsn = "https://envtoken@sentry.example.com/1"
    monkeypatch.setenv("SENTRY_DSN", env_dsn)

    assert resolve_dsn() == env_dsn


def test_resolve_dsn_falls_back_to_config_file(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    config_dsn = "https://configtoken@sentry.example.com/2"
    mock_config = MagicMock()
    mock_config.sentry_dsn = config_dsn

    with patch("sentry_tool.monitoring.load_config", return_value=mock_config):
        assert resolve_dsn() == config_dsn


def test_resolve_dsn_returns_none_for_hardcoded_default(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    mock_config = MagicMock()
    mock_config.sentry_dsn = None

    with patch("sentry_tool.monitoring.load_config", return_value=mock_config):
        assert resolve_dsn() is None


def test_resolve_dsn_env_var_takes_priority_over_config(monkeypatch):
    env_dsn = "https://envtoken@sentry.example.com/1"
    monkeypatch.setenv("SENTRY_DSN", env_dsn)

    with patch("sentry_tool.monitoring.load_config") as mock_load:
        result = resolve_dsn()

    mock_load.assert_not_called()
    assert result == env_dsn
