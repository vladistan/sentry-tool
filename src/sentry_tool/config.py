"""Configuration management with profile support.

Loads configuration from multiple sources with layered precedence:
1. CLI flags (--profile)
2. Environment variables (SENTRY_PROFILE, SENTRY_URL, etc.)
3. Config file (~/.config/sentry-tool/config.toml)
4. Default values (lowest priority)
"""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from sentry_tool.exceptions import ConfigurationError


class SentryProfile(BaseModel):
    """All fields optional in profile, required after resolution with env vars."""

    url: str = Field(
        default="https://sentry.io",
        description="Base URL for Sentry instance",
    )
    org: str = Field(
        default="sentry",
        description="Sentry organization slug",
    )
    project: str = Field(
        default="otel-collector",
        description="Sentry project slug",
    )
    auth_token: str | None = Field(
        default=None,
        description="Sentry API authentication token",
    )


class AppConfig(BaseModel):
    """Application-wide configuration with profile management."""

    default_profile: str = Field(default="default")
    profiles: dict[str, SentryProfile] = Field(default_factory=lambda: {"default": SentryProfile()})


def load_config(config_path: Path | None = None) -> AppConfig:
    """Search order: explicit path > ~/.config/sentry-tool/config.toml > defaults.

    Returns default AppConfig if no file found.
    """
    search_paths = [
        Path.home() / ".config" / "sentry-tool" / "config.toml",
    ]

    if config_path:
        search_paths.insert(0, config_path)

    for path in search_paths:
        if path.exists():
            with path.open("rb") as f:
                config_data = tomllib.load(f)
                return AppConfig(**config_data)

    # No config file found, return defaults
    return AppConfig()


def get_profile(config: AppConfig, profile: str | None = None) -> SentryProfile:
    """Resolution order: explicit profile > SENTRY_PROFILE env > config default.

    Raises ConfigurationError if profile name not found in config.
    """
    profile_name = profile or os.environ.get("SENTRY_PROFILE") or config.default_profile

    if profile_name not in config.profiles:
        available = ", ".join(sorted(config.profiles.keys()))
        raise ConfigurationError(
            f"Profile '{profile_name}' not found. Available profiles: {available}"
        )

    return config.profiles[profile_name]


@dataclass
class EnvOverrides:
    """Environment variable and CLI flag overrides for config resolution."""

    cli_project: str | None = field(default=None)
    url: str | None = field(default=None)
    org: str | None = field(default=None)
    project: str | None = field(default=None)
    auth_token: str | None = field(default=None)


def resolve_sentry_config(
    config: SentryProfile,
    overrides: EnvOverrides | None = None,
    **kwargs: str | None,
) -> dict[str, Any]:
    """Precedence: CLI flags > environment variables > profile > defaults.

    Raises ConfigurationError if final auth_token is empty or missing.

    Accepts either an EnvOverrides object or keyword arguments for backwards compatibility:
        cli_project, env_url, env_org, env_project, env_auth_token
    """
    if overrides is None:
        overrides = EnvOverrides(
            cli_project=kwargs.get("cli_project"),
            url=kwargs.get("env_url"),
            org=kwargs.get("env_org"),
            project=kwargs.get("env_project"),
            auth_token=kwargs.get("env_auth_token"),
        )

    auth_token = overrides.auth_token if overrides.auth_token is not None else config.auth_token

    if not auth_token or not auth_token.strip():
        msg = "SENTRY_AUTH_TOKEN not set in profile or environment"
        raise ConfigurationError(msg)

    # Project precedence: CLI flag > env var > profile
    project = (
        overrides.cli_project
        if overrides.cli_project is not None
        else (overrides.project if overrides.project is not None else config.project)
    )

    return {
        "url": overrides.url if overrides.url is not None else config.url,
        "org": overrides.org if overrides.org is not None else config.org,
        "project": project,
        "auth_token": auth_token.strip(),
    }
