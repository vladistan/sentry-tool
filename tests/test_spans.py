from io import StringIO

import pytest
from rich.console import Console
from typer.testing import CliRunner

from sentry_tool.cli import app
from sentry_tool.commands.traces import (
    SpanNode,
    _build_span_tree,
    _extract_spans,
    _render_span_tree,
)

runner = CliRunner()


# ===== SpanNode dataclass tests =====


def test_spannode_construction():
    node = SpanNode(
        span_id="abc",
        parent_span_id="parent",
        op="db.query",
        description="SELECT 1",
        duration=0.050,
    )
    assert node.span_id == "abc"
    assert node.parent_span_id == "parent"
    assert node.op == "db.query"
    assert node.description == "SELECT 1"
    assert node.duration == 0.050
    assert node.children == []


def test_spannode_children_are_mutable():
    parent = SpanNode(span_id="p", parent_span_id=None, op="http", description="", duration=0.1)
    child = SpanNode(span_id="c", parent_span_id="p", op="db", description="", duration=0.05)
    parent.children.append(child)
    assert len(parent.children) == 1
    assert parent.children[0] is child


# ===== _extract_spans tests =====


def test_extract_spans_returns_correct_data(sample_transaction_spans):
    spans, root_span_id, txn_duration = _extract_spans(sample_transaction_spans)
    assert len(spans) == 3
    assert root_span_id == "root001"
    assert txn_duration == pytest.approx(0.500)


def test_extract_spans_no_spans_entry():
    event = {}
    spans, root_span_id, txn_duration = _extract_spans(event)
    assert spans == []
    assert root_span_id is None
    assert txn_duration == 0.0


def test_extract_spans_missing_duration(sample_transaction_spans):
    event = {
        "contexts": {"trace": {"span_id": "root001"}},
        "entries": sample_transaction_spans["entries"],
    }
    _, root_span_id, txn_duration = _extract_spans(event)
    assert root_span_id == "root001"
    assert txn_duration == 0.0


def test_extract_spans_missing_root_span_id(sample_transaction_spans):
    event = {
        "contexts": {"trace": {"duration": 500}},
        "entries": sample_transaction_spans["entries"],
    }
    _, root_span_id, txn_duration = _extract_spans(event)
    assert root_span_id is None
    assert txn_duration == pytest.approx(0.500)


# ===== _build_span_tree tests =====


def test_build_span_tree_hierarchy():
    spans = [
        {
            "span_id": "child",
            "parent_span_id": "root",
            "op": "http",
            "description": "GET /",
            "start_timestamp": 0.0,
            "timestamp": 0.1,
        },
        {
            "span_id": "grandchild",
            "parent_span_id": "child",
            "op": "db",
            "description": "SELECT 1",
            "start_timestamp": 0.01,
            "timestamp": 0.05,
        },
    ]
    root = _build_span_tree(spans, "root")
    assert len(root.children) == 1
    assert root.children[0].span_id == "child"
    assert len(root.children[0].children) == 1
    assert root.children[0].children[0].span_id == "grandchild"


def test_build_span_tree_fixture_hierarchy(sample_transaction_spans):
    spans = sample_transaction_spans["entries"][0]["data"]
    root = _build_span_tree(spans, "root001")
    child_ids = {c.span_id for c in root.children}
    assert child_ids == {"child001", "child002"}
    child002 = next(c for c in root.children if c.span_id == "child002")
    assert len(child002.children) == 1
    assert child002.children[0].span_id == "grandchild001"


def test_build_span_tree_orphan_attaches_to_root():
    spans = [
        {
            "span_id": "orphan",
            "parent_span_id": "nonexistent",
            "op": "db",
            "description": "SELECT 1",
            "start_timestamp": 0.0,
            "timestamp": 0.1,
        },
    ]
    root = _build_span_tree(spans, "root")
    assert len(root.children) == 1
    assert root.children[0].span_id == "orphan"


def test_build_span_tree_none_root_id():
    spans = [
        {
            "span_id": "s1",
            "parent_span_id": "unknown",
            "op": "http",
            "description": "GET /",
            "start_timestamp": 0.0,
            "timestamp": 0.1,
        },
        {
            "span_id": "s2",
            "parent_span_id": None,
            "op": "db",
            "description": "SELECT 1",
            "start_timestamp": 0.0,
            "timestamp": 0.05,
        },
    ]
    root = _build_span_tree(spans, None)
    assert root.span_id == "root"
    assert len(root.children) == 2


def test_build_span_tree_duplicate_span_id():
    spans = [
        {
            "span_id": "dup",
            "parent_span_id": "root",
            "op": "db",
            "description": "first",
            "start_timestamp": 0.0,
            "timestamp": 0.1,
        },
        {
            "span_id": "dup",
            "parent_span_id": "root",
            "op": "http",
            "description": "second",
            "start_timestamp": 0.0,
            "timestamp": 0.2,
        },
    ]
    root = _build_span_tree(spans, "root")
    assert len(root.children) == 1
    assert root.children[0].description == "first"


def test_build_span_tree_empty_spans():
    root = _build_span_tree([], "root001")
    assert root.span_id == "root001"
    assert root.children == []


# ===== _render_span_tree tests =====


@pytest.fixture
def rich_console():
    buf = StringIO()
    return Console(file=buf, width=200, highlight=False, no_color=True), buf


def test_render_span_tree_contains_op_and_description(rich_console):
    root = SpanNode(
        span_id="root", parent_span_id=None, op="transaction", description="", duration=0.0
    )
    root.children = [
        SpanNode(
            span_id="c1",
            parent_span_id="root",
            op="db.query",
            description="SELECT * FROM users",
            duration=0.050,
        ),
        SpanNode(
            span_id="c2",
            parent_span_id="root",
            op="http.client",
            description="GET /api",
            duration=0.200,
        ),
    ]

    console, buf = rich_console
    _render_span_tree(root, 2, 0.500, console=console)
    output = buf.getvalue()

    assert "db.query" in output
    assert "SELECT * FROM users" in output
    assert "http.client" in output
    assert "GET /api" in output


def test_render_span_tree_duration_format(rich_console):
    root = SpanNode(
        span_id="root", parent_span_id=None, op="transaction", description="", duration=0.0
    )
    root.children = [
        SpanNode(span_id="c", parent_span_id="root", op="db", description="query", duration=0.050),
    ]

    console, buf = rich_console
    _render_span_tree(root, 1, 0.500, console=console)
    output = buf.getvalue()

    assert "0.050s" in output


def test_render_span_tree_description_truncation(rich_console):
    long_desc = "A" * 60
    root = SpanNode(
        span_id="root", parent_span_id=None, op="transaction", description="", duration=0.0
    )
    root.children = [
        SpanNode(
            span_id="c", parent_span_id="root", op="http", description=long_desc, duration=0.1
        ),
    ]

    console, buf = rich_console
    _render_span_tree(root, 1, 0.100, console=console)
    output = buf.getvalue()

    assert "..." in output
    assert long_desc not in output


def test_render_span_tree_placeholders(rich_console):
    root = SpanNode(
        span_id="root", parent_span_id=None, op="transaction", description="", duration=0.0
    )
    root.children = [
        SpanNode(
            span_id="c",
            parent_span_id="root",
            op="(unknown)",
            description="(no description)",
            duration=0.1,
        ),
    ]

    console, buf = rich_console
    _render_span_tree(root, 1, 0.100, console=console)
    output = buf.getvalue()

    assert "(unknown)" in output
    assert "(no description)" in output


def test_render_span_tree_footer(rich_console):
    root = SpanNode(
        span_id="root", parent_span_id=None, op="transaction", description="", duration=0.0
    )

    console, buf = rich_console
    _render_span_tree(root, 3, 0.500, console=console)
    output = buf.getvalue()

    assert "3 spans" in output
    assert "0.500s total" in output


# ===== CLI integration tests =====


def test_spans_tree_output(live_transaction_cli_env, live_transaction_id):
    result = runner.invoke(app, ["spans", live_transaction_id])

    assert result.exit_code == 0


def test_spans_json_output(live_transaction_cli_env, live_transaction_id):
    result = runner.invoke(app, ["spans", live_transaction_id, "--format", "json"])

    assert result.exit_code == 0


def test_spans_op_filter_single(live_transaction_cli_env, live_transaction_id, live_span_ops):
    result = runner.invoke(app, ["spans", live_transaction_id, "--op", live_span_ops[0]])

    assert result.exit_code == 0
    assert live_span_ops[0] in result.stdout


def test_spans_op_filter_multiple(live_transaction_cli_env, live_transaction_id, live_span_ops):
    if len(live_span_ops) < 2:
        pytest.skip("Transaction has fewer than 2 distinct span ops")
    ops = f"{live_span_ops[0]},{live_span_ops[1]}"
    result = runner.invoke(app, ["spans", live_transaction_id, "--op", ops])

    assert result.exit_code == 0


def test_spans_op_filter_no_match(live_transaction_cli_env, live_transaction_id):
    result = runner.invoke(app, ["spans", live_transaction_id, "--op", "nonexistent.op"])

    assert result.exit_code == 0


def test_spans_404(live_cli_env):
    result = runner.invoke(app, ["spans", "definitely_not_real_event_id"])

    assert result.exit_code == 1


def test_spans_in_help():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "spans" in result.stdout


def test_spans_command_help():
    result = runner.invoke(app, ["spans", "--help"])

    assert result.exit_code == 0
    assert "--op" in result.stdout
    assert "--format" in result.stdout
