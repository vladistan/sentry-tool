"""Trace and transaction commands."""

import re
from typing import Annotated, Any

import structlog
import typer
from rich.console import Console
from rich.table import Table

from sentry_tool.output import Column, OutputFormat, render
from sentry_tool.utils import api, get_config

log = structlog.get_logger()

TRACE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")


def list_transactions(
    max_rows: Annotated[int, typer.Option("--max", "-n", help="Maximum transactions to show")] = 10,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """List recent transactions for the active project.

    Examples:
        sentry-tool transactions
        sentry-tool transactions -n 5
        sentry-tool transactions --format json
    """
    config = get_config()

    response = api(
        f"/organizations/{config['org']}/events/"
        f"?query=event.type:transaction project:{config['project']}"
        "&field=title&field=id&field=trace&field=transaction.duration"
        "&field=transaction.status&field=project&field=timestamp"
        "&sort=-timestamp",
        token=config["auth_token"],
        base_url=config["url"],
    )

    events = response.get("data", [])

    if not events:
        log.info("No transactions found", project=config["project"])
        return

    events = events[:max_rows]

    if format == OutputFormat.json:
        render(events, format)
        return

    rows = [
        {
            "title": evt.get("title", ""),
            "id": evt.get("id", ""),
            "trace": evt.get("trace", ""),
            "duration": str(evt.get("transaction.duration", "")),
            "status": evt.get("transaction.status", ""),
            "timestamp": evt.get("timestamp", "")[:19],
        }
        for evt in events
    ]

    columns = [
        Column("Transaction", "title", max_width=30),
        Column("Event ID", "id", style="dim", max_width=36),
        Column("Trace ID", "trace", style="dim", max_width=36),
        Column("Duration (ms)", "duration", justify="right"),
        Column("Status", "status"),
        Column("Timestamp", "timestamp"),
    ]

    render(rows, format, columns=columns, footer=f"Showing {len(events)} transactions")


def lookup_trace(
    trace_id: Annotated[str, typer.Argument(help="Trace ID (32-character hex string)")],
    max_rows: Annotated[int, typer.Option("--max", "-n", help="Maximum events to show")] = 25,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
) -> None:
    """Examples:
    sentry-tool trace abc123def456789012345678901234ab
    sentry-tool trace abc123def456789012345678901234ab -n 10
    sentry-tool trace abc123def456789012345678901234ab --format json
    """
    if not TRACE_ID_PATTERN.match(trace_id):
        log.error("Invalid trace ID format", trace_id=trace_id, expected="32-character hex string")
        raise typer.Exit(1)

    config = get_config()

    response = api(
        f"/organizations/{config['org']}/events/?query=trace:{trace_id}"
        "&field=title&field=id&field=span_id&field=transaction.duration"
        "&field=transaction.status&field=project&field=timestamp",
        token=config["auth_token"],
        base_url=config["url"],
    )

    events = response.get("data", [])

    if not events:
        log.info("No events found for trace", trace_id=trace_id)
        return

    events.sort(key=lambda e: e.get("timestamp", ""))
    events = events[:max_rows]

    if format == OutputFormat.json:
        render(events, format)
        return

    rows = [
        {
            "title": evt.get("title", ""),
            "span_id": evt.get("span_id", ""),
            "duration": str(evt.get("transaction.duration", "")),
            "status": evt.get("transaction.status", ""),
            "project": evt.get("project", ""),
            "timestamp": evt.get("timestamp", "")[:19],
        }
        for evt in events
    ]

    columns = [
        Column("Transaction", "title", max_width=40),
        Column("Span ID", "span_id", style="dim", max_width=16),
        Column("Duration", "duration", justify="right"),
        Column("Status", "status"),
        Column("Project", "project"),
        Column("Timestamp", "timestamp"),
    ]

    render(rows, format, columns=columns, footer=f"Showing {len(events)} events")


def _render_timeline(spans: list[dict[str, Any]], console: Console) -> None:
    min_start = min(s.get("start_timestamp", 0) for s in spans)
    max_end = max(s.get("timestamp", 0) for s in spans)
    total_duration = max_end - min_start

    if total_duration <= 0:
        console.print("\n[dim]Cannot render timeline (zero duration)[/dim]")
        return

    bar_width = 40

    table = Table(title="Span Timeline")
    table.add_column("Op", style="cyan", max_width=20)
    table.add_column("Description", max_width=35)
    table.add_column("Start", justify="right")
    table.add_column("Dur (s)", justify="right")
    table.add_column("Timeline", no_wrap=True)

    for span in spans:
        start = span.get("start_timestamp", 0)
        end = span.get("timestamp", 0)
        offset = start - min_start
        duration = end - start

        pos = int(offset / total_duration * bar_width)
        length = max(1, int(duration / total_duration * bar_width))
        bar = " " * pos + "█" * length

        table.add_row(
            span.get("op", ""),
            span.get("description", "")[:35],
            f"{offset:.3f}s",
            f"{duration:.3f}s",
            bar,
        )

    console.print()
    console.print(table)
    console.print(f"\n  Total duration: {total_duration:.3f}s")


def show_transaction(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
    timeline: Annotated[
        bool,
        typer.Option("--timeline", "-t", help="Show Gantt-chart timeline of spans"),
    ] = False,
) -> None:
    """Fetch and display detailed transaction information including spans.

    Examples:
        sentry-tool transaction d3f1d81247ad4516b61da92f1db050dd
        sentry-tool transaction d3f1d81247ad4516b61da92f1db050dd --format json
    """
    config = get_config()

    event = api(
        f"/organizations/{config['org']}/events/{config['project']}:{event_id}/",
        token=config["auth_token"],
        base_url=config["url"],
    )

    if format == OutputFormat.json:
        render([event], format)
        return

    console = Console()
    console.print(f"\n[bold cyan]=== Transaction {event_id[:8]}... ===[/bold cyan]")

    rows = [
        {"field": "Transaction", "value": event.get("title", "N/A")},
        {"field": "Event ID", "value": event.get("eventID", "N/A")},
        {
            "field": "Trace ID",
            "value": event.get("contexts", {}).get("trace", {}).get("trace_id", "N/A"),
        },
        {
            "field": "Span ID",
            "value": event.get("contexts", {}).get("trace", {}).get("span_id", "N/A"),
        },
        {
            "field": "Parent Span",
            "value": event.get("contexts", {}).get("trace", {}).get("parent_span_id", "N/A"),
        },
        {
            "field": "Duration",
            "value": f"{event.get('contexts', {}).get('trace', {}).get('duration', 'N/A')} ms",
        },
        {
            "field": "Status",
            "value": event.get("contexts", {}).get("trace", {}).get("status", "N/A"),
        },
        {"field": "Timestamp", "value": event.get("dateCreated", "N/A")},
    ]

    detail_columns = [
        Column("Field", "field", style="bold"),
        Column("Value", "value"),
    ]
    render(rows, OutputFormat.table, columns=detail_columns)

    entries = event.get("entries", [])
    spans = []
    for entry in entries:
        if entry.get("type") == "spans":
            spans = entry.get("data", [])
            break

    if spans:
        if timeline:
            _render_timeline(spans, console)
        else:
            span_rows = [
                {
                    "operation": span.get("op", ""),
                    "description": span.get("description", "")[:50],
                    "duration": f"{span.get('timestamp', 0) - span.get('start_timestamp', 0):.3f}",
                }
                for span in spans
            ]

            span_columns = [
                Column("Operation", "operation", max_width=20),
                Column("Description", "description", max_width=50),
                Column("Duration (s)", "duration", justify="right"),
            ]
            console.print()
            render(
                span_rows, OutputFormat.table, columns=span_columns, footer=f"{len(spans)} spans"
            )
    else:
        console.print("\n[dim]No span data found[/dim]")

    console.print()
