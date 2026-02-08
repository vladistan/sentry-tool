"""Configuration management commands."""

import json
import os
from typing import Annotated, Any

import typer
from rich.console import Console

from sentry_tool.client import NotFoundError, api_call
from sentry_tool.config import AppConfig, load_config
from sentry_tool.exceptions import ConfigurationError
from sentry_tool.monitoring import get_logger
from sentry_tool.output import Column, OutputFormat, render
from sentry_tool.utils import mask_token

config_app = typer.Typer(help="Configuration management commands")


@config_app.command("show")
def show(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """Display current configuration including active profile and all configured profiles.

    Examples:
        sentry-tool config show
        sentry-tool config show --format json
    """
    try:
        app_config = load_config()
    except ConfigurationError as e:
        Console().print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from e

    env: dict[str, str | None] = {
        "profile": os.getenv("SENTRY_PROFILE"),
        "url": os.getenv("SENTRY_URL"),
        "org": os.getenv("SENTRY_ORG"),
        "project": os.getenv("SENTRY_PROJECT"),
        "auth_token": os.getenv("SENTRY_AUTH_TOKEN"),
    }

    active_name = env["profile"] or app_config.default_profile
    active_profile = app_config.profiles.get(active_name)

    if format == OutputFormat.json:
        _print_show_json(app_config, env, active_name, active_profile)
    else:
        _print_show_tables(app_config, env, active_name, active_profile)


def _print_show_json(
    app_config: AppConfig,
    env: dict[str, str | None],
    active_name: str | None,
    active_profile: Any,
) -> None:
    def _effective(field: str) -> Any:
        env_val = env.get(field)
        if env_val is not None:
            return env_val
        return getattr(active_profile, field, None) if active_profile else None

    effective_token = env["auth_token"] or (
        active_profile.auth_token if active_profile else None
    )
    output = {
        "default_profile": app_config.default_profile,
        "active_profile": active_name,
        "effective": {
            "url": _effective("url"),
            "org": _effective("org"),
            "project": _effective("project"),
            "auth_token": mask_token(effective_token),
        },
        "profiles": {
            name: {
                "url": profile.url,
                "org": profile.org,
                "project": profile.project,
                "auth_token": mask_token(profile.auth_token),
            }
            for name, profile in app_config.profiles.items()
        },
    }
    print(json.dumps(output, indent=2))


def _print_show_tables(
    app_config: AppConfig,
    env: dict[str, str | None],
    active_name: str | None,
    active_profile: Any,
) -> None:
    console = Console()

    console.print(f"\n[bold]Default profile:[/bold] {app_config.default_profile}")
    if env["profile"]:
        console.print(f"  [dim](override: SENTRY_PROFILE={env['profile']})[/dim]")

    if active_profile:
        rows = []
        for field, env_key in [("url", "url"), ("org", "org"), ("project", "project")]:
            value = env[env_key] if env[env_key] else getattr(active_profile, field)
            source = f"SENTRY_{env_key.upper()}" if env[env_key] else "profile"
            rows.append({"setting": field, "value": str(value), "source": source})

        auth_token = env["auth_token"] if env["auth_token"] else active_profile.auth_token
        source = "SENTRY_AUTH_TOKEN" if env["auth_token"] and auth_token else "profile"
        rows.append({
            "setting": "auth_token",
            "value": mask_token(auth_token),
            "source": source,
        })

        columns = [
            Column("Setting", "setting", style="cyan"),
            Column("Value", "value"),
            Column("Source", "source", style="dim"),
        ]
        console.print()
        render(rows, OutputFormat.table, columns=columns, footer="Effective Settings")

    if not app_config.profiles:
        console.print("\nNo profiles configured")
        return

    profile_rows = [
        {
            "name": name,
            "default": "*" if name == app_config.default_profile else "",
            "url": profile.url,
            "org": profile.org,
            "project": profile.project,
            "auth_token": mask_token(profile.auth_token),
        }
        for name, profile in app_config.profiles.items()
    ]

    profile_columns = [
        Column("Name", "name", style="cyan"),
        Column("Default", "default", justify="center"),
        Column("URL", "url"),
        Column("Org", "org"),
        Column("Project", "project"),
        Column("Auth Token", "auth_token", style="dim"),
    ]
    console.print()
    render(
        profile_rows,
        OutputFormat.table,
        columns=profile_columns,
        footer=f"{len(app_config.profiles)} profiles",
    )


@config_app.command("profiles")
def list_profiles(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """List configured profile names with default marked.

    Examples:
        sentry-tool config profiles
        sentry-tool config profiles --format json
    """
    try:
        app_config = load_config()
    except ConfigurationError as e:
        Console().print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from e

    if not app_config.profiles:
        Console().print("No profiles configured.")
        return

    rows = [
        {
            "name": name,
            "default": "*" if name == app_config.default_profile else "",
        }
        for name in app_config.profiles
    ]

    columns = [
        Column("Name", "name", style="cyan"),
        Column("Default", "default", justify="center"),
    ]

    render(rows, format, columns=columns, footer=f"{len(rows)} profiles")


@config_app.command("list-projects")
def list_projects(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """Enumerate Sentry projects for each configured profile.

    Profiles with missing auth tokens are skipped with error message.

    Examples:
        sentry-tool config list-projects
        sentry-tool config list-projects --format json
    """
    log = get_logger("config")
    console = Console()

    try:
        app_config = load_config()
    except ConfigurationError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from e

    if not app_config.profiles:
        console.print("No profiles configured.")
        return

    rows: list[dict[str, str]] = []
    for profile_name, profile in app_config.profiles.items():
        if not profile.auth_token or not profile.auth_token.strip():
            rows.append({"profile": profile_name, "project": "(no auth token)"})
            log.warning("profile_missing_token", profile=profile_name)
            continue

        try:
            projects = api_call(
                f"/organizations/{profile.org}/projects/",
                token=profile.auth_token.strip(),
                base_url=profile.url,
            )

            if not projects:
                rows.append({"profile": profile_name, "project": "(no projects)"})
            else:
                rows.extend(
                    {"profile": profile_name, "project": proj.get("slug", "unknown")}
                    for proj in projects
                )

        except NotFoundError:
            rows.append({
                "profile": profile_name,
                "project": f"(org '{profile.org}' not found)",
            })
            log.error("org_not_found", profile=profile_name, org=profile.org)
        except Exception as e:
            rows.append({"profile": profile_name, "project": f"(error: {e})"})
            log.error("profile_api_error", profile=profile_name, error=str(e))

    columns = [
        Column("Profile", "profile", style="cyan"),
        Column("Project", "project"),
    ]

    render(rows, format, columns=columns)


@config_app.command("validate")
def validate(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """Verify connectivity to all configured profiles by querying projects.

    Reports project count and slugs per profile. Useful after initial setup.

    Examples:
        sentry-tool config validate
        sentry-tool config validate --format json
    """
    log = get_logger("config")
    console = Console()

    try:
        app_config = load_config()
    except ConfigurationError as e:
        console.print(f"[red]Config error: {e}[/red]")
        raise typer.Exit(1) from e

    if not app_config.profiles:
        console.print("No profiles configured.")
        return

    rows: list[dict[str, str]] = []
    for profile_name, profile in app_config.profiles.items():
        if not profile.auth_token or not profile.auth_token.strip():
            rows.append({
                "profile": profile_name,
                "status": "FAIL",
                "projects": "No auth token configured",
            })
            log.warning("profile_missing_token", profile=profile_name)
            continue

        try:
            projects = api_call(
                f"/organizations/{profile.org}/projects/",
                token=profile.auth_token.strip(),
                base_url=profile.url,
            )

            slugs = [proj.get("slug", "unknown") for proj in projects]
            slugs_str = ", ".join(slugs) if slugs else "(none)"

            rows.append({
                "profile": profile_name,
                "status": "OK",
                "projects": f"{len(projects)} projects — {slugs_str}",
            })

        except NotFoundError:
            rows.append({
                "profile": profile_name,
                "status": "FAIL",
                "projects": f"Organization '{profile.org}' not found",
            })
            log.error("org_not_found", profile=profile_name, org=profile.org)
        except Exception as e:
            rows.append({
                "profile": profile_name,
                "status": "FAIL",
                "projects": str(e),
            })
            log.error("profile_api_error", profile=profile_name, error=str(e))

    columns = [
        Column("Profile", "profile", style="cyan"),
        Column("Status", "status"),
        Column("Projects", "projects"),
    ]

    render(rows, format, columns=columns)
