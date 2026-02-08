"""Utility functions for config resolution and API interaction."""

import os
from typing import Any

import typer
from rich.console import Console

from sentry_tool.client import NotFoundError, api_call
from sentry_tool.config import (
    AppConfig,
    EnvOverrides,
    SentryProfile,
    get_profile,
    load_config,
    resolve_sentry_config,
)
from sentry_tool.exceptions import ConfigurationError
from sentry_tool.monitoring import get_logger

_active_profile: str | None = None
_active_project: str | None = None


def mask_token(token: str | None) -> str:
    if token:
        return f"***...{token[-4:]}"
    return "(not set)"


def set_active_profile(profile: str | None) -> None:
    global _active_profile  # noqa: PLW0603
    _active_profile = profile


def set_active_project(project: str | None) -> None:
    global _active_project  # noqa: PLW0603
    _active_project = project


def get_config() -> dict[str, Any]:
    """Precedence (highest to lowest):
    1. CLI --project/-p flag
    2. CLI --profile/-P flag
    3. SENTRY_PROFILE environment variable
    4. default_profile in config file
    5. Environment variables (SENTRY_URL, SENTRY_ORG, SENTRY_PROJECT, SENTRY_AUTH_TOKEN)
    """
    try:
        app_config: AppConfig = load_config()
        profile_config: SentryProfile = get_profile(app_config, _active_profile)

        overrides = EnvOverrides(
            cli_project=_active_project,
            url=os.environ.get("SENTRY_URL"),
            org=os.environ.get("SENTRY_ORG"),
            project=os.environ.get("SENTRY_PROJECT"),
            auth_token=os.environ.get("SENTRY_AUTH_TOKEN"),
        )
        resolved = resolve_sentry_config(profile_config, overrides)
        return resolved
    except ConfigurationError as exc:
        Console().print(f"[red]Error: {exc}[/red]")
        raise typer.Exit(1) from None


def api(endpoint: str, token: str, base_url: str) -> Any:
    log = get_logger("cli")
    try:
        return api_call(endpoint, token=token, base_url=base_url)
    except NotFoundError:
        log.error("not found", endpoint=endpoint)
        raise typer.Exit(1) from None
