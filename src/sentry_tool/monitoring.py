"""Monitoring setup: Sentry error tracking and structlog logging.

Logging goes to stderr to keep stdout clean for data output (piping).
Sentry is initialized after logging for self-monitoring.
DSN is read from SENTRY_DSN environment variable (optional for public distribution).
"""

import logging
import os
import sys
from typing import Any

import sentry_sdk
import structlog

from sentry_tool.__about__ import __version__

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


def setup_sentry(environment: str = "local") -> None:
    """Configure error tracking for this CLI tool instance.

    Reads DSN from SENTRY_DSN environment variable. Skips initialization if unset,
    allowing the tool to run without error tracking in public distributions.
    """
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        log = structlog.get_logger()
        log.info("Sentry DSN not configured, skipping error tracking setup")
        return

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=0.03,
        environment=environment,
        release=__version__,
        attach_stacktrace=True,
        send_default_pii=False,
    )
