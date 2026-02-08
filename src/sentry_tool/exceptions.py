"""Custom exceptions for sentry-tool."""


class ConfigurationError(Exception):
    """Profile not found, auth token missing, or config file parsing failed."""
