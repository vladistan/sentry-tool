"""Tests for Sentry monitoring and logging setup."""

from sentry_tool.monitoring import get_logger, setup_logging, setup_sentry


def test_setup_sentry_does_not_crash():
    setup_sentry()


def test_setup_sentry_with_custom_environment():
    setup_sentry(environment="test")


def test_setup_logging_does_not_crash():
    setup_logging()


def test_setup_logging_verbose():
    setup_logging(verbose=True)


def test_get_logger_returns_logger():
    setup_logging()
    logger = get_logger("test")
    assert logger is not None
