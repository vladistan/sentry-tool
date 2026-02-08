"""Generic output formatting for data display."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from rich.console import Console
from rich.table import Table


class OutputFormat(str, Enum):
    table = "table"
    json = "json"


@dataclass
class Column:
    header: str
    key: str
    style: str | None = None
    justify: str | None = None
    max_width: int | None = None


def render(
    data: list[dict[str, Any]],
    format: OutputFormat,
    columns: list[Column] | None = None,
    footer: str | None = None,
) -> None:
    """Render list data as JSON or Rich table.

    For JSON: prints indented JSON to stdout.
    For table: builds a Rich table using column specs for styling (max_width, justify, style).
    The footer (e.g. "Showing 5 issues") is only printed in table mode.
    """
    if format == OutputFormat.json:
        print(json.dumps(data, indent=2))
        return

    console = Console()

    if not data:
        return

    if columns is None:
        columns = [Column(header=key, key=key) for key in data[0]]

    table = Table(show_header=True, header_style="bold")
    for col in columns:
        kwargs: dict[str, Any] = {}
        if col.style is not None:
            kwargs["style"] = col.style
        if col.justify is not None:
            kwargs["justify"] = col.justify
        if col.max_width is not None:
            kwargs["max_width"] = col.max_width
        table.add_column(col.header, **kwargs)

    for row in data:
        values = [str(row.get(col.key, "")) for col in columns]
        table.add_row(*values)

    console.print(table)
    if footer:
        console.print(f"\n{footer}")


# Event-specific formatting helpers (used by `events event` command for Rich detail view)


def print_event_context(console: Console, ctx: dict[str, Any]) -> None:
    console.print("\n[bold]Context:[/bold]")
    if "caller" in ctx:
        console.print(f"  [dim]Caller:[/dim] {ctx['caller']}")
    if "stack" in ctx:
        console.print("  [dim]Stack:[/dim]")
        for line in ctx["stack"].split("\n"):
            console.print(f"    {line}")


def print_exception_entry(console: Console, data: dict[str, Any]) -> None:
    console.print("\n[bold]Exception:[/bold]")
    for exc in data.get("values", []):
        exc_type = exc.get("type", "Exception")
        exc_value = exc.get("value", "")
        console.print(f"  [red]{exc_type}[/red]: {exc_value}")

        stacktrace = exc.get("stacktrace") or {}
        frames = stacktrace.get("frames", []) if stacktrace else []
        if frames:
            console.print("  [dim]Stacktrace:[/dim]")
            for frame in frames[-5:]:
                filename = frame.get("filename", "")
                lineno = frame.get("lineNo", "")
                function = frame.get("function", "")
                console.print(f"    {filename}:{lineno} in {function}")


def render_event_basic_info(console: Console, event: dict[str, Any], short_id: str) -> None:
    console.print(f"\n[bold cyan]=== Latest Event for {short_id} ===[/bold cyan]")

    rows: list[dict[str, str]] = [
        {"field": "Event ID", "value": event.get("eventID", "N/A")},
        {"field": "Title", "value": event.get("title", "N/A")},
        {"field": "Message", "value": event.get("message", "N/A")},
        {"field": "Date", "value": event.get("dateCreated", "N/A")},
    ]

    for tag in event.get("tags", []):
        if tag.get("key") == "server_name":
            rows.append({"field": "Server", "value": tag.get("value", "N/A")})
            break

    sdk = event.get("sdk", {})
    if sdk:
        rows.append({"field": "SDK", "value": f"{sdk.get('name', '')} {sdk.get('version', '')}"})

    release = event.get("release", {})
    if release:
        rows.append({"field": "Release", "value": release.get("version", "N/A")})

    columns = [
        Column("Field", "field", style="bold"),
        Column("Value", "value"),
    ]
    render(rows, OutputFormat.table, columns=columns)
