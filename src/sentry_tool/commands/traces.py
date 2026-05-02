"""Trace and transaction commands."""

import re
from dataclasses import dataclass, field
from typing import Annotated, Any
from urllib.parse import quote_plus

import structlog
import typer
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from sentry_tool.output import Column, OutputFormat, render
from sentry_tool.utils import api, get_config

TRACE_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
MAX_DESCRIPTION_LENGTH = 50
PERIOD_PATTERN = re.compile(r"^\d+[mhdw]$")
DURATION_PATTERN = re.compile(r"^(\d+(?:\.\d+)?)(ms|s)?$")


@dataclass
class SpanNode:
    span_id: str
    parent_span_id: str | None
    op: str
    description: str
    duration: float
    children: list["SpanNode"] = field(default_factory=list)


def _build_query(  # noqa: PLR0913
    base_query: str,
    transaction: str | None = None,
    status: str | None = None,
    duration_gt_ms: int | None = None,
    user: str | None = None,
    raw_query: str | None = None,
) -> str:
    parts = [base_query]
    if transaction:
        parts.append(f"transaction:{transaction}")
    if status:
        parts.append(f"transaction.status:{status}")
    if duration_gt_ms is not None:
        parts.append(f"transaction.duration:>{duration_gt_ms}")
    if user:
        parts.append(f"user.email:{user}")
    if raw_query:
        parts.append(raw_query)
    return " ".join(parts)


def _validate_period(value: str | None) -> str | None:
    if value is None:
        return None
    if not PERIOD_PATTERN.match(value):
        raise typer.BadParameter(
            f"Invalid period '{value}'. Expected format: <number><unit> where unit is "
            "m/h/d/w (e.g. 24h, 7d, 2w)."
        )
    return value


def _parse_duration_gt(value: str | None) -> int | None:
    if value is None:
        return None
    match = DURATION_PATTERN.match(value.strip())
    if not match:
        raise typer.BadParameter(
            f"Invalid duration '{value}'. Expected format: <number>[ms|s] (e.g. 500ms, 2s, 1500)."
        )
    number = float(match.group(1))
    unit = match.group(2) or "ms"
    ms = number * 1000 if unit == "s" else number
    return int(ms)


def _format_stat(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(round(float(value)))
    except (TypeError, ValueError):
        return str(value)


def _render_stats_table(
    events: list[dict[str, Any]],
    format: OutputFormat,
    footer: str,
) -> None:
    if format == OutputFormat.json:
        render(events, format)
        return

    rows = [
        {
            "transaction": evt.get("transaction", ""),
            "count": str(evt.get("count()", "")),
            "avg": _format_stat(evt.get("avg(transaction.duration)")),
            "min": _format_stat(evt.get("min(transaction.duration)")),
            "max": _format_stat(evt.get("max(transaction.duration)")),
            "p95": _format_stat(evt.get("p95(transaction.duration)")),
        }
        for evt in events
    ]

    columns = [
        Column("Transaction", "transaction", max_width=50),
        Column("Count", "count", justify="right"),
        Column("Avg (ms)", "avg", justify="right"),
        Column("Min (ms)", "min", justify="right"),
        Column("Max (ms)", "max", justify="right"),
        Column("P95 (ms)", "p95", justify="right"),
    ]

    render(rows, format, columns=columns, footer=footer)


def list_transactions(  # noqa: PLR0913
    max_rows: Annotated[int, typer.Option("--max", "-n", help="Maximum transactions to show")] = 10,
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
    query: Annotated[
        str | None,
        typer.Option("--query", "-q", help="Raw Sentry search syntax appended to base query"),
    ] = None,
    transaction: Annotated[
        str | None,
        typer.Option("--transaction", "-T", help="Filter by transaction name (supports globs)"),
    ] = None,
    status: Annotated[
        str | None,
        typer.Option("--status", help="Filter by transaction status (e.g. ok, internal_error)"),
    ] = None,
    period: Annotated[
        str | None,
        typer.Option("--period", help="Time window (e.g. 24h, 7d, 2w)"),
    ] = None,
    duration_gt: Annotated[
        str | None,
        typer.Option(
            "--duration-gt",
            help="Filter to transactions slower than this (e.g. 500ms, 2s, 1500)",
        ),
    ] = None,
    user: Annotated[
        str | None,
        typer.Option("--user", help="Filter by user email"),
    ] = None,
    stats: Annotated[
        bool,
        typer.Option(
            "--stats",
            help="Aggregation mode: count/avg/min/max/p95 grouped by transaction name",
        ),
    ] = False,
) -> None:
    """List recent transactions, with optional filtering and aggregation.

    Examples:
        sentry-tool transactions
        sentry-tool transactions -n 5
        sentry-tool transactions --format json
        sentry-tool transactions --transaction "/api/v1/*" --status ok
        sentry-tool transactions --duration-gt 500ms --period 24h
        sentry-tool transactions --query "user.id:123"
        sentry-tool transactions --stats --period 7d
    """
    log = structlog.get_logger()
    config = get_config()

    validated_period = _validate_period(period)
    duration_gt_ms = _parse_duration_gt(duration_gt)

    base = f"event.type:transaction project:{config['project']}"
    composed_query = _build_query(
        base,
        transaction=transaction,
        status=status,
        duration_gt_ms=duration_gt_ms,
        user=user,
        raw_query=query,
    )
    encoded_query = quote_plus(composed_query)

    if stats:
        url = (
            f"/organizations/{config['org']}/events/"
            f"?query={encoded_query}"
            "&field=transaction"
            "&field=count()"
            "&field=avg(transaction.duration)"
            "&field=max(transaction.duration)"
            "&field=min(transaction.duration)"
            "&field=p95(transaction.duration)"
            "&sort=-count()"
            "&dataset=transactions"
        )
        if validated_period:
            url += f"&statsPeriod={validated_period}"

        response = api(url, token=config["auth_token"], base_url=config["url"])
        events = response.get("data", [])

        if not events:
            log.info("No transactions found", project=config["project"])
            return

        events = events[:max_rows]
        period_label = validated_period or "default"
        _render_stats_table(
            events,
            format,
            footer=f"Showing {len(events)} endpoints (period: {period_label})",
        )
        return

    url = (
        f"/organizations/{config['org']}/events/"
        f"?query={encoded_query}"
        "&field=title&field=id&field=trace&field=transaction.duration"
        "&field=transaction.status&field=project&field=timestamp"
        "&sort=-timestamp"
        "&dataset=transactions"
    )
    if validated_period:
        url += f"&statsPeriod={validated_period}"

    response = api(url, token=config["auth_token"], base_url=config["url"])
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
    """Look up all events belonging to a trace by its 32-character hex ID.

    Examples:
        sentry-tool trace abc123def456789012345678901234ab
        sentry-tool trace abc123def456789012345678901234ab -n 10
        sentry-tool trace abc123def456789012345678901234ab --format json
    """
    log = structlog.get_logger()
    if not TRACE_ID_PATTERN.match(trace_id):
        log.error("Invalid trace ID format", trace_id=trace_id, expected="32-character hex string")
        raise typer.Exit(2)

    config = get_config()

    response = api(
        f"/organizations/{config['org']}/events/?query=trace:{trace_id}"
        "&field=title&field=id&field=span_id&field=transaction.duration"
        "&field=transaction.status&field=project&field=timestamp"
        "&dataset=discover",
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


def _extract_spans(event: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None, float]:
    trace_ctx = event.get("contexts", {}).get("trace", {})
    root_span_id = trace_ctx.get("span_id")
    raw_duration = trace_ctx.get("duration")
    txn_duration = raw_duration / 1000.0 if raw_duration is not None else 0.0
    for entry in event.get("entries", []):
        if entry.get("type") == "spans":
            return entry.get("data", []), root_span_id, txn_duration
    return [], root_span_id, txn_duration


def _build_span_tree(spans: list[dict[str, Any]], root_span_id: str | None) -> SpanNode:
    log = structlog.get_logger()
    root = SpanNode(
        span_id=root_span_id or "root",
        parent_span_id=None,
        op="transaction",
        description="",
        duration=0.0,
    )

    node_map: dict[str, SpanNode] = {}
    for span in spans:
        span_id = span.get("span_id", "")
        if not span_id:
            continue
        if span_id in node_map:
            log.warning("Duplicate span_id skipped", span_id=span_id)
            continue
        duration = span.get("timestamp", 0) - span.get("start_timestamp", 0)
        node_map[span_id] = SpanNode(
            span_id=span_id,
            parent_span_id=span.get("parent_span_id"),
            op=span.get("op", "(unknown)"),
            description=span.get("description", "(no description)"),
            duration=duration,
        )

    node_map[root.span_id] = root

    for node in node_map.values():
        if node is root:
            continue
        parent_id = node.parent_span_id
        if parent_id and parent_id in node_map:
            node_map[parent_id].children.append(node)
        else:
            root.children.append(node)

    return root


def _render_span_tree(
    root: SpanNode,
    total_spans: int,
    txn_duration: float,
    console: Console | None = None,
) -> None:
    if console is None:
        console = Console()

    tree = Tree(f"[bold]{root.op}[/bold] {root.description}")

    def _add_children(parent_tree: Tree, node: SpanNode) -> None:
        for child in node.children:
            desc = child.description
            if len(desc) > MAX_DESCRIPTION_LENGTH:
                desc = desc[: MAX_DESCRIPTION_LENGTH - 3] + "..."
            label = f"[cyan]{child.op}[/cyan] {desc} [dim]{child.duration:.3f}s[/dim]"
            branch = parent_tree.add(label)
            _add_children(branch, child)

    _add_children(tree, root)
    console.print(tree)
    console.print(f"\n{total_spans} spans | {txn_duration:.3f}s total")


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
        f"/organizations/{config['org']}/events/{config['project']}:{event_id}/"
        "?dataset=transactions",
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


def show_spans(
    event_id: Annotated[str, typer.Argument(help="Event ID")],
    format: Annotated[
        OutputFormat,
        typer.Option("--format", "-f", help="Output format"),
    ] = OutputFormat.table,
    op: Annotated[
        str | None,
        typer.Option("--op", help="Filter spans by operation type (comma-separated)"),
    ] = None,
) -> None:
    """Display transaction spans as a tree with optional operation filtering.

    Examples:
        sentry-tool spans d3f1d81247ad4516b61da92f1db050dd
        sentry-tool spans d3f1d81247ad4516b61da92f1db050dd --format json
        sentry-tool spans d3f1d81247ad4516b61da92f1db050dd --op db.query
    """
    log = structlog.get_logger()
    config = get_config()

    event = api(
        f"/organizations/{config['org']}/events/{config['project']}:{event_id}/"
        "?dataset=transactions",
        token=config["auth_token"],
        base_url=config["url"],
    )

    spans, root_span_id, txn_duration = _extract_spans(event)

    if not spans:
        log.info("No span data found", event_id=event_id)
        return

    if op:
        op_filters = {o.strip() for o in op.split(",")}
        spans = [s for s in spans if s.get("op") in op_filters]
        if not spans:
            log.info("No spans matching op filter", op=op)
            return

    if format == OutputFormat.json:
        render(spans, format)
        return

    root = _build_span_tree(spans, root_span_id)
    _render_span_tree(root, len(spans), txn_duration)
