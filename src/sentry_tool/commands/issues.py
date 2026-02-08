"""Issue-related commands."""

from typing import Annotated

import typer
from rich.console import Console

from sentry_tool.output import Column, OutputFormat, render
from sentry_tool.utils import api, get_config

app = typer.Typer(help="Issue management commands")


@app.command("list")
def list_issues(
    project: Annotated[str | None, typer.Option("--project", "-p", help="Project slug")] = None,
    all_projects: Annotated[
        bool, typer.Option("--all-projects", "-A", help="List issues across all projects")
    ] = False,
    max_rows: Annotated[int, typer.Option("--max", "-n", help="Maximum issues to show")] = 10,
    status: Annotated[
        str | None,
        typer.Option("--status", "-s", help="Filter by status: resolved, unresolved, muted"),
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """
    List recent issues in a project.

    Use --all-projects/-A to list issues across all projects in the organization.
    The -A flag is mutually exclusive with --project/-p.

    Examples:
        sentry-tool list
        sentry-tool list -p otel-collector -n 5
        sentry-tool list -s unresolved
        sentry-tool list -A
        sentry-tool list --format json
    """
    config = get_config()

    if all_projects and project:
        console = Console()
        console.print("[red]Error: --all-projects/-A and --project/-p are mutually exclusive[/red]")
        raise typer.Exit(1)

    params = ""
    if status:
        params = f"?query=is:{status}"

    if all_projects:
        issues = api(
            f"/organizations/{config['org']}/issues/{params}",
            token=config["auth_token"],
            base_url=config["url"],
        )
    else:
        project = project or config["project"]
        issues = api(
            f"/projects/{config['org']}/{project}/issues/{params}",
            token=config["auth_token"],
            base_url=config["url"],
        )

    console = Console()

    if not issues:
        console.print("No issues found")
        return

    issues = issues[:max_rows]

    rows = []
    for issue in issues:
        row = {
            "id": str(issue.get("id", "")),
            "shortId": issue.get("shortId", ""),
            "status": issue.get("status", ""),
            "level": issue.get("level", ""),
            "count": str(issue.get("count", "")),
            "title": issue.get("title", ""),
        }
        if all_projects:
            proj = issue.get("project", {})
            row["project"] = proj.get("slug", "") if isinstance(proj, dict) else str(proj)
        rows.append(row)

    columns = [
        Column("ID", "id", style="dim", max_width=6),
        Column("Short ID", "shortId", max_width=20),
    ]
    if all_projects:
        columns.append(Column("Project", "project", max_width=20))
    columns.extend([
        Column("Status", "status", max_width=12),
        Column("Level", "level", max_width=8),
        Column("Count", "count", justify="right", max_width=8),
        Column("Title", "title", max_width=50),
    ])

    render(rows, format, columns=columns, footer=f"Showing {len(issues)} issues")


@app.command("show")
def show_issue(
    issue_id: Annotated[
        str, typer.Argument(help="Issue ID (numeric or short ID like OTEL-COLLECTOR-Q)")
    ],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """
    Examples:
        sentry-tool show 24
        sentry-tool show OTEL-COLLECTOR-Q
        sentry-tool show 24 --format json
    """
    config = get_config()

    issue = api(
        f"/organizations/{config['org']}/issues/{issue_id}/",
        token=config["auth_token"],
        base_url=config["url"],
    )

    if format == OutputFormat.json:
        render([issue], format)
        return

    console = Console()

    short_id = issue.get("shortId", issue.get("id"))
    console.print(f"\n[bold cyan]=== Issue {short_id} ===[/bold cyan]")

    status = issue.get("status", "N/A")
    substatus = issue.get("substatus", "")
    status_str = f"{status} ({substatus})" if substatus else status

    rows = [
        {"field": "Title", "value": issue.get("title", "N/A")},
        {"field": "Status", "value": status_str},
        {"field": "Level", "value": issue.get("level", "N/A")},
        {"field": "Priority", "value": str(issue.get("priority", "N/A"))},
        {"field": "Count", "value": f"{issue.get('count', 'N/A')} events"},
        {"field": "First seen", "value": issue.get("firstSeen", "N/A")},
        {"field": "Last seen", "value": issue.get("lastSeen", "N/A")},
        {"field": "URL", "value": issue.get("permalink", "N/A")},
    ]

    first_rel = issue.get("firstRelease", {})
    last_rel = issue.get("lastRelease", {})
    if first_rel:
        rows.append({"field": "First release", "value": first_rel.get("version", "N/A")})
    if last_rel:
        rows.append({"field": "Last release", "value": last_rel.get("version", "N/A")})

    detail_columns = [
        Column("Field", "field", style="bold"),
        Column("Value", "value"),
    ]
    render(rows, OutputFormat.table, columns=detail_columns)

    tags = issue.get("tags", [])
    if tags:
        tag_rows = [
            {"key": tag.get("key", ""), "values": str(tag.get("totalValues", 0))}
            for tag in tags[:8]
        ]
        tag_columns = [
            Column("Tag", "key"),
            Column("Unique Values", "values", justify="right"),
        ]
        console.print()
        render(tag_rows, OutputFormat.table, columns=tag_columns, footer=f"{len(tags)} tag types")

    console.print("\n[dim]Use 'sentry-tool event <id>' to see the latest event[/dim]")
    console.print()
