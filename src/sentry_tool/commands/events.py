"""Event-related commands."""

from typing import Annotated

import typer
from rich.console import Console

from sentry_tool.output import (
    Column,
    OutputFormat,
    print_event_context,
    print_exception_entry,
    render,
    render_event_basic_info,
)
from sentry_tool.services import resolve_issue_to_numeric
from sentry_tool.utils import api, get_config

app = typer.Typer(help="Event management commands")


@app.command("event")
def show_event(
    issue_id: Annotated[str, typer.Argument(help="Issue ID (numeric or short ID)")],
    event_id: Annotated[
        str | None, typer.Option("--event", "-e", help="Specific event ID (default: latest)")
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
    context: Annotated[
        bool, typer.Option("--context", "-c", help="Show only context/stacktrace")
    ] = False,
) -> None:
    """
    Show event details for an issue.

    By default shows the latest event. Use --event to specify a particular event.

    Examples:
        sentry-tool event 24                    # Latest event for issue 24
        sentry-tool event OTEL-COLLECTOR-Q      # Latest event by short ID
        sentry-tool event 24 -c                 # Show just context/stacktrace
        sentry-tool event 24 --format json      # Full JSON output
    """
    config = get_config()

    numeric_id, short_id = resolve_issue_to_numeric(config, issue_id)

    if event_id:
        event = api(
            f"/organizations/{config['org']}/issues/{numeric_id}/events/{event_id}/",
            token=config["auth_token"],
            base_url=config["url"],
        )
    else:
        event = api(
            f"/organizations/{config['org']}/issues/{numeric_id}/events/latest/",
            token=config["auth_token"],
            base_url=config["url"],
        )

    if format == OutputFormat.json:
        render([event], format)
        return

    console = Console()

    render_event_basic_info(console, event, short_id)

    ctx = event.get("context", {})
    if ctx:
        print_event_context(console, ctx)

    entries = event.get("entries", [])
    for entry in entries:
        entry_type = entry.get("type", "")
        data = entry.get("data", {})

        if entry_type == "message" and not context:
            formatted = data.get("formatted", "")
            if formatted:
                console.print(f"\n[bold]Formatted Message:[/bold]\n  {formatted}")

        elif entry_type == "exception":
            print_exception_entry(console, data)

    console.print()


@app.command("events")
def list_events(
    issue_id: Annotated[str, typer.Argument(help="Issue ID (numeric or short ID)")],
    max_rows: Annotated[int, typer.Option("--max", "-n", help="Maximum events to show")] = 10,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """
    List recent events for an issue.

    Examples:
        sentry-tool events 24
        sentry-tool events OTEL-COLLECTOR-Q -n 5
        sentry-tool events 24 --format json
    """
    config = get_config()

    numeric_id, _short_id = resolve_issue_to_numeric(config, issue_id)

    events = api(
        f"/organizations/{config['org']}/issues/{numeric_id}/events/",
        token=config["auth_token"],
        base_url=config["url"],
    )

    if not events:
        Console().print("No events found")
        return

    events = events[:max_rows]

    rows = []
    for evt in events:
        evt_id = evt.get("eventID", evt.get("id", ""))
        date = evt.get("dateCreated", "")[:19]

        server = "-"
        for tag in evt.get("tags", []):
            if tag.get("key") == "server_name":
                server = tag.get("value", "-")
                break

        rows.append({"eventID": evt_id, "date": date, "server": server})

    columns = [
        Column("Event ID", "eventID", style="dim", max_width=36),
        Column("Date", "date"),
        Column("Server", "server"),
    ]

    render(rows, format, columns=columns, footer=f"Showing {len(events)} events")


@app.command("tags")
def show_tags(
    issue_id: Annotated[str, typer.Argument(help="Issue ID (numeric or short ID)")],
    tag_key: Annotated[
        str | None, typer.Argument(help="Tag key to show values for (e.g., server_name)")
    ] = None,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """
    Show tag values for an issue.

    Without TAG_KEY, lists available tags. With TAG_KEY, shows values for that tag.

    Examples:
        sentry-tool tags OTEL-COLLECTOR-14              # List available tags
        sentry-tool tags OTEL-COLLECTOR-14 server_name  # Show affected hosts
        sentry-tool tags OTEL-COLLECTOR-14 release      # Show affected releases
        sentry-tool tags 14 server_name --format json
    """
    config = get_config()

    numeric_id, _short_id = resolve_issue_to_numeric(config, issue_id)

    console = Console()

    if tag_key:
        tag_data = api(
            f"/organizations/{config['org']}/issues/{numeric_id}/tags/{tag_key}/",
            token=config["auth_token"],
            base_url=config["url"],
        )

        top_values = tag_data.get("topValues", [])
        if not top_values:
            console.print(f"No values found for tag '{tag_key}'")
            return

        rows = []
        for val in top_values:
            name = val.get("value", "")[:30]
            count = val.get("count", 0)
            pct = val.get("percentage", 0) * 100
            rows.append({"value": name, "count": str(count), "percent": f"{pct:.1f}%"})

        columns = [
            Column("Value", "value", max_width=30),
            Column("Count", "count", justify="right"),
            Column("Percent", "percent", justify="right"),
        ]

        render(
            rows,
            format,
            columns=columns,
            footer=f"Total unique values: {tag_data.get('uniqueValues', 'N/A')}",
        )
    else:
        issue = api(
            f"/organizations/{config['org']}/issues/{numeric_id}/",
            token=config["auth_token"],
            base_url=config["url"],
        )
        tags = issue.get("tags", [])
        if not tags:
            console.print("No tags found")
            return

        rows = [
            {"key": tag.get("key", ""), "total": str(tag.get("totalValues", 0))}
            for tag in tags
        ]

        columns = [
            Column("Tag Key", "key"),
            Column("Unique Values", "total", justify="right"),
        ]

        render(rows, format, columns=columns)
