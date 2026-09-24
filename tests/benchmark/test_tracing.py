"""Tests for span capture and gap annotation."""

from types import SimpleNamespace

from mitol.benchmark.tracing import annotate_gaps, span_rows

MS = 1_000_000


def span(name, start_ms, end_ms, sql=""):
    """Return a finished span as the SDK exposes it."""
    return SimpleNamespace(
        name=name,
        start_time=start_ms * MS,
        end_time=end_ms * MS,
        attributes={"db.statement": sql} if sql else {},
    )


def test_spans_are_sorted_and_timed():
    """Rows come out in start order with durations in milliseconds."""
    rows = span_rows([span("b", 20, 25, "SELECT 2"), span("a", 0, 10, "SELECT 1")])
    assert [row["name"] for row in rows] == ["a", "b"]
    assert rows[0]["dur_ms"] == 10.0  # noqa: PLR2004
    assert rows[1]["sql"] == "SELECT 2"


def test_gap_runs_to_the_next_query():
    """Between two queries, the gap is everything not spent in either."""
    rows = span_rows([span("q1", 0, 10, "SELECT 1"), span("q2", 40, 50, "SELECT 2")])
    annotated = annotate_gaps(rows)
    assert annotated["db"][0]["gap_ms"] == 30.0  # noqa: PLR2004


def test_the_last_gap_runs_to_the_end_of_the_request():
    """Serialization happens after the final query, and must be counted."""
    rows = span_rows([span("request", 0, 100), span("q1", 10, 20, "SELECT 1")])
    annotated = annotate_gaps(rows)
    assert annotated["db"][0]["gap_ms"] == 80.0  # noqa: PLR2004


def test_non_database_spans_are_not_reported_as_queries():
    """A request span is not a query; only its timing bounds the last gap."""
    annotated = annotate_gaps(
        span_rows([span("request", 0, 50), span("q", 5, 6, "SELECT 1")])
    )
    assert len(annotated["db"]) == 1
    assert annotated["wall_ms"] == 45.0  # noqa: PLR2004


def test_no_spans_is_a_reportable_state():
    """A missing instrumentor must not look like a zero-cost request."""
    assert annotate_gaps([]) == {"wall_ms": 0.0, "db": []}


def test_spans_without_an_end_are_skipped():
    """An unfinished span carries no usable duration."""
    unfinished = SimpleNamespace(name="x", start_time=0, end_time=None, attributes={})
    assert span_rows([unfinished]) == []
