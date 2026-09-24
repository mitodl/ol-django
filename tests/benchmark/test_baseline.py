"""
Tests for distilling production traces into a committable baseline.

The first two classes are the reason the feature is shaped the way it is: a
production trace cannot be committed, so what gets committed must provably
carry none of it.
"""

import json

import pytest
from mitol.benchmark import config as cfg
from mitol.benchmark.baseline import (
    UNCLASSIFIED,
    BaselineError,
    build,
    by_label,
    safe_classifier,
    serialize,
)
from mitol.benchmark.otel import TraceReadError, read_requests, routes, row_floor

MS = 1_000_000

# Statements shaped like the things a production export really leaks.
SENSITIVE = {
    "email": "SELECT * FROM users WHERE email = 'alice@example.com'",
    "token": "SELECT * FROM keys WHERE secret = 'sk-live-91f3ab77c0'",
    "tenant": "SELECT * FROM orgs WHERE slug = 'acme-holdings-internal'",
}


def span(sql, start_ms, end_ms, *, attrs=None):
    """Return one OTLP JSON span in the current collector shape."""
    attributes = [{"key": "db.statement", "value": {"stringValue": sql}}]
    for key, value in (attrs or {}).items():
        attributes.append({"key": key, "value": {"stringValue": value}})
    return {
        "name": "SELECT",
        "traceId": "aaaa",
        "startTimeUnixNano": str(start_ms * MS),
        "endTimeUnixNano": str(end_ms * MS),
        "attributes": attributes,
    }


def export(spans, *, legacy=False, trace_id=None):
    """Wrap spans in either of the two export layouts."""
    if trace_id:
        spans = [{**s, "traceId": trace_id} for s in spans]
    scope = {"spans": spans}
    if legacy:
        return {"batches": [{"instrumentationLibrarySpans": [scope]}]}
    return {"resourceSpans": [{"scopeSpans": [scope]}]}


def write(tmp_path, name, document):
    """Write an export to disk and return its path."""
    path = tmp_path / name
    path.write_text(json.dumps(document))
    return path


def make_config(**classify):
    """Return a config whose classifiers are the given label -> pattern map."""
    return cfg.from_merged(
        {
            "benchmark": {"name": "baseline test"},
            "django": {"settings_module": "x"},
            "database": {"name": "bench_baseline"},
            "target": {"path": "/x/"},
            "trace": {
                "classify": [
                    {"label": label, "pattern": pattern}
                    for label, pattern in classify.items()
                ]
            },
        }
    )


class TestNothingSensitiveEscapes:
    """The property the whole design exists to provide."""

    def test_no_production_sql_reaches_the_artifact(self, tmp_path):
        """An email, an API key and a tenant name must all be absent."""
        config = make_config(users="FROM users", keys="FROM keys", orgs="FROM orgs")
        spans = [
            span(SENSITIVE["email"], 0, 10),
            span(SENSITIVE["token"], 20, 25),
            span(SENSITIVE["tenant"], 40, 50),
        ]
        built, _ = build(config, [write(tmp_path, "t.json", export(spans))])
        rendered = serialize(built)

        for secret in ("alice@example.com", "sk-live-91f3ab77c0", "acme-holdings"):
            assert secret not in rendered
        # The numbers did survive, so this is not passing vacuously.
        assert {row["query"] for row in built["queries"]} == {"users", "keys", "orgs"}

    def test_an_unmatched_span_becomes_the_literal_unclassified(self, tmp_path):
        """The SQL fallback in aggregate.classify must not reach the file."""
        config = make_config(users="FROM users")
        spans = [span(SENSITIVE["email"], 0, 10), span(SENSITIVE["token"], 20, 25)]
        built, _ = build(config, [write(tmp_path, "t.json", export(spans))])
        rendered = serialize(built)

        labels = {row["query"] for row in built["queries"]}
        assert labels == {"users", UNCLASSIFIED}
        assert "sk-live" not in rendered
        assert "FROM keys" not in rendered

    def test_distinct_unmatched_statements_collapse_into_one_row(self, tmp_path):
        """One anonymous bucket, not one row per unknown query."""
        config = make_config(users="FROM users")
        spans = [
            span(SENSITIVE["token"], 0, 5),
            span(SENSITIVE["tenant"], 10, 15),
            span("SELECT 1 FROM somewhere_else", 20, 25),
        ]
        built, _ = build(config, [write(tmp_path, "t.json", export(spans))])

        rows = [r for r in built["queries"] if r["query"] == UNCLASSIFIED]
        assert len(rows) == 1
        assert rows[0]["per_req"] == 3.0  # noqa: PLR2004

    def test_other_span_attributes_are_never_serialised(self, tmp_path):
        """Only an allowlist of keys is written, so new attributes cannot leak."""
        config = make_config(users="FROM users")
        spans = [
            span(
                SENSITIVE["email"],
                0,
                10,
                attrs={
                    "http.target": "/api/v1/users?email=alice@example.com",
                    "enduser.id": "user-99312",
                },
            )
        ]
        built, _ = build(config, [write(tmp_path, "t.json", export(spans))])
        rendered = serialize(built)

        assert "enduser" not in rendered
        assert "user-99312" not in rendered
        assert set(json.loads(rendered)) == {"trace_ids", "requests", "queries"}
        assert set(json.loads(rendered)["queries"][0]) <= {
            "query",
            "per_req",
            "sql_ms",
            "gap_ms",
            "total_ms",
            "row_floor",
        }

    def test_absolute_timestamps_are_not_written(self, tmp_path):
        """Durations and gaps only; a wall-clock time points at a request."""
        config = make_config(users="FROM users")
        spans = [span(SENSITIVE["email"], 1_700_000_000_000, 1_700_000_000_010)]
        built, _ = build(config, [write(tmp_path, "t.json", export(spans))])
        assert "1700000000" not in serialize(built)


class TestSafeClassifier:
    """The substitution that makes the guarantee structural."""

    def test_a_declared_label_is_kept(self):
        """Matching spans keep the label the developer wrote."""
        config = make_config(books="FROM book")
        assert safe_classifier("SELECT * FROM book", config.trace.classify) == "books"

    def test_anything_else_is_the_literal_string(self):
        """There is no flag and no path that returns statement text."""
        config = make_config(books="FROM book")
        assert (
            safe_classifier("SELECT * FROM secrets", config.trace.classify)
            == UNCLASSIFIED
        )

    def test_the_serialiser_refuses_a_label_from_outside_the_closed_set(self):
        """A future refactor reintroducing the fallback fails loudly here."""
        from mitol.benchmark.baseline import _assert_safe  # noqa: PLC0415

        config = make_config(books="FROM book")
        leaked = {"queries": [{"query": "SELECT * FROM users WHERE email ="}]}
        with pytest.raises(BaselineError, match="not declared classifiers"):
            _assert_safe(leaked, config.trace.classify)


class TestReadingExports:
    """Both layouts, any number of files."""

    def test_both_export_shapes_produce_the_same_rows(self, tmp_path):
        """Old OTLP JSON and current collector output are interchangeable."""
        spans = [span("SELECT * FROM book", 0, 10)]
        modern = read_requests([write(tmp_path, "a.json", export(spans))])
        legacy = read_requests([write(tmp_path, "b.json", export(spans, legacy=True))])
        assert modern[0].spans == legacy[0].spans

    def test_the_two_shapes_can_be_mixed_in_one_invocation(self, tmp_path):
        """A glob over a directory may sweep up exports of either vintage."""
        config = make_config(books="FROM book")
        paths = [
            write(
                tmp_path,
                "a.json",
                export([span("SELECT * FROM book", 0, 10)], trace_id="t1"),
            ),
            write(
                tmp_path,
                "b.json",
                export([span("SELECT * FROM book", 0, 20)], legacy=True, trace_id="t2"),
            ),
        ]
        built, _ = build(config, paths)
        assert built["requests"] == 2  # noqa: PLR2004
        assert built["trace_ids"] == ["t1", "t2"]

    def test_requests_are_grouped_by_trace_id_across_files(self, tmp_path):
        """How an export was split up must not change the arithmetic."""
        config = make_config(books="FROM book")
        one_file = build(
            config,
            [
                write(
                    tmp_path,
                    "all.json",
                    export(
                        [
                            {**span("SELECT * FROM book", 0, 10), "traceId": "t1"},
                            {**span("SELECT * FROM book", 0, 20), "traceId": "t2"},
                        ]
                    ),
                )
            ],
        )[0]
        split = build(
            config,
            [
                write(
                    tmp_path,
                    "1.json",
                    export([span("SELECT * FROM book", 0, 10)], trace_id="t1"),
                ),
                write(
                    tmp_path,
                    "2.json",
                    export([span("SELECT * FROM book", 0, 20)], trace_id="t2"),
                ),
            ],
        )[0]
        assert one_file["queries"] == split["queries"]
        assert one_file["requests"] == split["requests"] == 2  # noqa: PLR2004

    def test_the_same_trace_in_two_files_is_counted_once(self, tmp_path):
        """Exporting a trace twice must not double its weight."""
        config = make_config(books="FROM book")
        document = export([span("SELECT * FROM book", 0, 10)], trace_id="dup")
        built, _ = build(
            config,
            [write(tmp_path, "a.json", document), write(tmp_path, "b.json", document)],
        )
        assert built["requests"] == 1
        assert built["trace_ids"] == ["dup"]

    def test_trace_ids_are_sorted_for_a_stable_diff(self, tmp_path):
        """The file is committed, so regenerating must not churn it."""
        config = make_config(books="FROM book")
        paths = [
            write(
                tmp_path,
                f"{name}.json",
                export([span("SELECT * FROM book", 0, 10)], trace_id=name),
            )
            for name in ("zebra", "alpha", "middle")
        ]
        built, _ = build(config, paths)
        assert built["trace_ids"] == ["alpha", "middle", "zebra"]

    def test_medians_improve_with_more_requests(self, tmp_path):
        """The median is taken across requests, not within a file."""
        config = make_config(books="FROM book")
        paths = [
            write(
                tmp_path,
                f"{i}.json",
                export([span("SELECT * FROM book", 0, duration)], trace_id=f"t{i}"),
            )
            for i, duration in enumerate([10, 20, 90])
        ]
        built, _ = build(config, paths)
        (row,) = [r for r in built["queries"] if r["query"] == "books"]
        assert row["sql_ms"] == 20.0  # the median, not the mean  # noqa: PLR2004

    def test_a_file_with_no_spans_is_an_error_naming_the_file(self, tmp_path):
        """Pointing at the wrong JSON should say so, not silently do nothing."""
        path = write(tmp_path, "wrong.json", {"something": "else"})
        with pytest.raises(TraceReadError, match=r"wrong\.json"):
            read_requests([path])

    def test_invalid_json_names_the_file(self, tmp_path):
        """Same for a truncated download."""
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        with pytest.raises(TraceReadError, match=r"bad\.json"):
            read_requests([path])


class TestDerivedNumbers:
    """Gaps, floors and the mixed-endpoint guard."""

    def test_the_gap_to_the_next_query_is_measured(self, tmp_path):
        """Serialization lives between spans on the production side too."""
        config = make_config(books="FROM book", topics="FROM topic")
        spans = [span("SELECT * FROM book", 0, 10), span("SELECT * FROM topic", 90, 95)]
        built, _ = build(config, [write(tmp_path, "t.json", export(spans))])
        (books,) = [r for r in built["queries"] if r["query"] == "books"]
        assert books["gap_ms"] == 80.0  # noqa: PLR2004

    @pytest.mark.parametrize(
        ("statement", "expected"),
        [
            ("SELECT * FROM t WHERE id IN (%s, %s, %s)", 3),
            ("SELECT * FROM t WHERE id IN ($1, $2)", 2),
            ("SELECT * FROM t", 0),
        ],
    )
    def test_row_floor_counts_placeholders(self, statement, expected):
        """An IN-list is the one row count a trace states outright."""
        assert row_floor(statement) == expected

    def test_a_truncated_statement_still_gives_a_lower_bound(self, tmp_path):
        """Exporters cut db.statement; the count stays a floor, never wrong."""
        config = make_config(books="FROM book")
        truncated = "SELECT * FROM book WHERE id IN (%s, %s, %s, %s"
        built, _ = build(
            config, [write(tmp_path, "t.json", export([span(truncated, 0, 10)]))]
        )
        assert built["queries"][0]["row_floor"] == 4  # noqa: PLR2004

    def test_mixed_routes_are_warned_about(self, tmp_path):
        """A glob can sweep in traces for an endpoint you did not mean."""
        config = make_config(books="FROM book")
        paths = [
            write(
                tmp_path,
                "a.json",
                export(
                    [
                        span(
                            "SELECT * FROM book",
                            0,
                            10,
                            attrs={"http.route": "/api/books/"},
                        )
                    ],
                    trace_id="t1",
                ),
            ),
            write(
                tmp_path,
                "b.json",
                export(
                    [
                        span(
                            "SELECT * FROM book",
                            0,
                            10,
                            attrs={"http.route": "/api/authors/"},
                        )
                    ],
                    trace_id="t2",
                ),
            ),
        ]
        _, warnings = build(config, paths)
        assert warnings
        assert "different routes" in warnings[0]

    def test_one_route_produces_no_warning(self, tmp_path):
        """The common case must stay quiet."""
        config = make_config(books="FROM book")
        paths = [
            write(
                tmp_path,
                f"{i}.json",
                export(
                    [
                        {
                            "name": "GET /api/books/",
                            "traceId": f"t{i}",
                            "startTimeUnixNano": "0",
                            "endTimeUnixNano": str(50 * MS),
                            "attributes": [
                                {
                                    "key": "http.route",
                                    "value": {"stringValue": "/api/books/"},
                                }
                            ],
                        },
                        span(
                            "SELECT * FROM book",
                            0,
                            10,
                            attrs={"http.route": "/api/books/"},
                        ),
                    ],
                    trace_id=f"t{i}",
                ),
            )
            for i in range(2)
        ]
        assert build(config, paths)[1] == []

    def test_a_query_string_is_not_kept_as_the_route(self, tmp_path):
        """http.target carries identifiers; only the path is used, and only
        for the warning.
        """
        config = make_config(books="FROM book")  # noqa: F841
        path = write(
            tmp_path,
            "a.json",
            export(
                [
                    span(
                        "SELECT * FROM book",
                        0,
                        10,
                        attrs={"http.target": "/api/books/?email=alice@example.com"},
                    )
                ]
            ),
        )
        (request,) = read_requests([path])
        assert request.route == "/api/books/"
        assert routes([request]) == ["/api/books/"]


class TestLoading:
    """Reading a committed baseline back."""

    def test_by_label_indexes_the_rows(self):
        """The report looks queries up by classifier label."""
        indexed = by_label({"queries": [{"query": "books", "total_ms": 3.0}]})
        assert indexed["books"]["total_ms"] == 3.0  # noqa: PLR2004

    def test_by_label_of_nothing_is_empty(self):
        """A benchmark with no baseline is the normal case, not an error."""
        assert by_label(None) == {}

    def test_a_missing_baseline_says_how_to_make_one(self, tmp_path):
        """The config referenced a file that is not there."""
        from mitol.benchmark.baseline import load  # noqa: PLC0415

        with pytest.raises(BaselineError, match="ol-benchmark baseline"):
            load(tmp_path / "absent.json")


def test_traces_with_no_database_spans_are_an_error(tmp_path):
    """A trace captured without DB instrumentation says nothing useful."""
    path = tmp_path / "t.json"
    path.write_text(
        json.dumps(
            {
                "resourceSpans": [
                    {
                        "scopeSpans": [
                            {
                                "spans": [
                                    {
                                        "name": "GET /api/books/",
                                        "traceId": "t1",
                                        "startTimeUnixNano": "0",
                                        "endTimeUnixNano": str(100 * MS),
                                        "attributes": [],
                                    }
                                ]
                            }
                        ]
                    }
                ]
            }
        )
    )
    config = make_config(books="FROM book")
    with pytest.raises(BaselineError, match="no database spans"):
        build(config, [path])


class TestTruncatedExports:
    """A trace filtered to database spans loses its last gap."""

    def test_a_missing_root_span_is_warned_about(self, tmp_path):
        """Otherwise the final query's serialization cost reads as zero."""
        config = make_config(books="FROM book")
        spans = [span("SELECT * FROM book", 0, 10)]
        _, warnings = build(config, [write(tmp_path, "t.json", export(spans))])
        assert any("reads as zero" in warning for warning in warnings)

    def test_an_enclosing_span_measures_the_final_gap(self, tmp_path):
        """With the server span present, the last gap is the real one."""
        config = make_config(books="FROM book")
        root = {
            "name": "GET /api/books/",
            "traceId": "aaaa",
            "startTimeUnixNano": "0",
            "endTimeUnixNano": str(100 * MS),
            "attributes": [],
        }
        spans = [root, span("SELECT * FROM book", 0, 10)]
        built, warnings = build(config, [write(tmp_path, "t.json", export(spans))])
        assert warnings == []
        assert built["queries"][0]["gap_ms"] == 90.0  # noqa: PLR2004
