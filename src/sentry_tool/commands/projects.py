"""Project-related commands."""

import webbrowser
from typing import Annotated

import typer
from rich.console import Console

from sentry_tool.output import Column, OutputFormat, render
from sentry_tool.utils import api, get_config

app = typer.Typer(help="Project management commands")


@app.command("list-projects")
def list_projects(
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """List all projects in the configured organization.

    Examples:
        sentry-tool list-projects
        sentry-tool list-projects --format json
    """
    config = get_config()

    projects = api(
        f"/organizations/{config['org']}/projects/",
        token=config["auth_token"],
        base_url=config["url"],
    )

    if not projects:
        Console().print("No projects found")
        return

    rows = [
        {
            "slug": proj.get("slug", ""),
            "name": proj.get("name", ""),
            "platform": proj.get("platform", "") or "",
            "status": proj.get("status", ""),
        }
        for proj in projects
    ]

    columns = [
        Column("Slug", "slug", style="cyan"),
        Column("Name", "name"),
        Column("Platform", "platform"),
        Column("Status", "status"),
    ]

    render(rows, format, columns=columns, footer=f"{len(projects)} projects")


@app.command("open")
def open_sentry(
    issue_id: Annotated[
        str | None, typer.Argument(help="Issue ID to open directly (optional)")
    ] = None,
) -> None:
    """Open Sentry web UI in browser.

    Without arguments, opens organization dashboard. With an issue ID, opens that issue.

    Examples:
        sentry-tool open
        sentry-tool open 24
    """
    config = get_config()

    base = config["url"].rstrip("/")
    org = config["org"]

    if issue_id:
        url = f"{base}/organizations/{org}/issues/{issue_id}/"
    else:
        url = f"{base}/organizations/{org}/issues/"

    webbrowser.open(url)
    console = Console()
    console.print(f"Opened: {url}")
