"""Tests for reducing traced repeats to one row per logical query."""

import pytest
from mitol.benchmark.aggregate import aggregate, classify, collisions, normalize
from mitol.benchmark.config import Classifier

CLASSIFIERS = (
    # Most specific first: the ordering is the whole contract.
    Classifier(label="count", pattern=r"COUNT\(\*\)"),
    Classifier(label="topics", pattern=r"book_topics"),
    Classifier(label="books", pattern=r'FROM "book"'),
)


def span(sql, dur, gap):
    """Return one database span as the trace pass records it."""
    return {"sql": sql, "dur_ms": dur, "gap_ms": gap}


def trace(*runs):
    """Return a TRACE_RESULT payload holding the given runs."""
    return {"repeats": len(runs), "runs": [{"db": list(run)} for run in runs]}


def test_normalize_collapses_whitespace():
    """Patterns are written against one-line SQL."""
    assert normalize("SELECT\n  a,\n  b") == "SELECT a, b"


def test_first_matching_classifier_wins():
    """Declaration order decides, so specific patterns go first."""
    assert classify('SELECT COUNT(*) FROM "book"', CLASSIFIERS) == "count"
    assert classify('SELECT * FROM "book"', CLASSIFIERS) == "books"


def test_unclassified_sql_falls_back_to_its_own_text():
    """An unlabelled query is still reported, under a truncated label."""
    label = classify("SELECT something_else FROM elsewhere", CLASSIFIERS)
    assert label.startswith("SELECT something_else")


def test_median_across_repeats():
    """One traced request is far too noisy to attribute a gap to a query."""
    payload = trace(
        [span('FROM "book"', 1.0, 10.0)],
        [span('FROM "book"', 5.0, 30.0)],
        [span('FROM "book"', 3.0, 20.0)],
    )
    (row,) = aggregate(payload, CLASSIFIERS)
    assert row["sql_ms"] == 3.0  # noqa: PLR2004
    assert row["gap_ms"] == 20.0  # noqa: PLR2004
    assert row["total_ms"] == 23.0  # noqa: PLR2004
    assert row["per_req"] == 1.0


def test_rows_are_sorted_by_total_cost():
    """The first row is where the request's time goes."""
    payload = trace(
        [
            span("SELECT COUNT(*) FROM x", 0.5, 0.1),
            span('SELECT * FROM "book" b', 1.0, 40.0),
        ]
    )
    assert [row["query"] for row in aggregate(payload, CLASSIFIERS)] == [
        "books",
        "count",
    ]


def test_gaps_are_kept_separate_from_query_time():
    """Serialization lives in the gaps; merging them hides where time goes."""
    payload = trace([span('FROM "book"', 2.0, 98.0)])
    (row,) = aggregate(payload, CLASSIFIERS)
    assert row["sql_ms"] == 2.0  # noqa: PLR2004
    assert row["gap_ms"] == 98.0  # noqa: PLR2004


def test_collisions_flag_an_over_broad_classifier():
    """A fractional per_req means two queries are sharing one label."""
    payload = trace(
        [span('FROM "book" one', 1.0, 1.0), span('FROM "book" two', 1.0, 1.0)],
        [span('FROM "book" one', 1.0, 1.0)],
    )
    rows = aggregate(payload, CLASSIFIERS)
    assert rows[0]["per_req"] == 1.5  # noqa: PLR2004
    assert collisions(rows) == ["books"]


def test_a_whole_number_per_request_is_not_a_collision():
    """A prefetch that genuinely runs twice per request is fine."""
    payload = trace(
        [span('FROM "book" a', 1.0, 1.0), span('FROM "book" b', 1.0, 1.0)],
        [span('FROM "book" a', 1.0, 1.0), span('FROM "book" b', 1.0, 1.0)],
    )
    assert collisions(aggregate(payload, CLASSIFIERS)) == []


@pytest.mark.parametrize("payload", [{}, {"runs": []}, {"runs": [{"db": []}]}])
def test_an_empty_trace_aggregates_to_nothing(payload):
    """No spans is a reportable state, not a crash."""
    assert aggregate(payload, CLASSIFIERS) == []
