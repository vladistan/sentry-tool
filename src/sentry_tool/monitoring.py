"""Monitoring setup: Sentry error tracking and structlog logging.

Logging goes to stderr to keep stdout clean for data output (piping).
Sentry is initialized after logging for self-monitoring.
DSN resolution order: SENTRY_DSN env var > config file sentry_dsn > hardcoded default.
"""

import logging
import os
import sys
from typing import Any

import sentry_sdk
import structlog

from sentry_tool.__about__ import __version__
from sentry_tool.config import load_config

_LOG_LEVELS: dict[str, int] = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


def setup_logging(verbose: bool = False) -> None:
    log_level = "debug" if verbose else "info"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(_LOG_LEVELS[log_level]),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger=name)
    return logger


_DEFAULT_DSN = "https://a176b6acecc8529b8f985532d49e2e04@o4508594232426496.ingest.us.sentry.io/4510896961093633"


def resolve_dsn() -> str | None:
    """Check SENTRY_DSN env var first, then config file sentry_dsn field.

    Returns an override DSN if configured, or None to use the hardcoded default.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if dsn:
        return dsn

    config = load_config()
    return config.sentry_dsn


def setup_sentry(environment: str = "local") -> None:
    sentry_sdk.init(
        dsn=resolve_dsn() or _DEFAULT_DSN,
        traces_sample_rate=0.03,
        environment=environment,
        release=__version__,
        attach_stacktrace=True,
        send_default_pii=False,
    )
