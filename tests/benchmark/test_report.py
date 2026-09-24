"""Tests for the verdict and the rendered report."""

import pytest
from mitol.benchmark import config as cfg
from mitol.benchmark.report import (
    VERDICT_INCONCLUSIVE,
    VERDICT_OK,
    VERDICT_VOID,
    compare,
    equivalence_mismatches,
    render_markdown,
)


@pytest.fixture
def config():
    """Return a minimal configuration with one query classifier."""
    return cfg.from_merged(
        {
            "benchmark": {"name": "report test", "description": "a description"},
            "django": {"settings_module": "x"},
            "database": {"name": "bench_report"},
            "target": {"path": "/x/"},
            "knobs": {"rows": 10},
            "trace": {"classify": [{"label": "books", "pattern": "FROM book"}]},
            "calibration": {
                "observable": [
                    {
                        "name": "rows per page",
                        "source": "response",
                        "production": 100,
                        "seed_step": "books",
                    }
                ]
            },
        }
    )


def arm(label, *, median, minimum, maximum=None, queries=5, **overrides):
    """Return a BENCH_RESULT payload with sensible defaults."""
    return {
        "label": label,
        "ref": f"{label}-sha",
        "total_ms_min": minimum,
        "total_ms_median": median,
        "total_ms_max": maximum if maximum is not None else median * 3,
        "total_ms_stdev": 1.0,
        "sql_ms_capture_pass": 5.0,
        "python_ms_est": median - 5.0,
        "queries": queries,
        "response_bytes": 1000,
        "count": 42,
        "results": 10,
        "nested.books": 80,
        "preconditions": {"debug_forced_off": True},
        **overrides,
    }


def trace_payload(gap):
    """Return a TRACE_RESULT with one classified query at the given gap."""
    return {
        "repeats": 1,
        "runs": [{"db": [{"sql": "SELECT * FROM book", "dur_ms": 1.0, "gap_ms": gap}]}],
    }


class TestVerdict:
    """What the harness will and will not call a speed-up."""

    def test_differing_responses_are_void(self, config):
        """Different work was done; no delta may be quoted from it."""
        result = compare(
            config,
            arm("base", median=100, minimum=95),
            arm("branch", median=50, minimum=45, response_bytes=900),
        )
        assert result["verdict"] == VERDICT_VOID
        assert "response_bytes" in result["reason"]

    def test_a_dropped_nested_collection_is_void(self, config):
        """Same row count, fewer nested rows, is a regression not a win."""
        result = compare(
            config,
            arm("base", median=100, minimum=95),
            arm("branch", median=50, minimum=45, **{"nested.books": 10}),
        )
        assert result["verdict"] == VERDICT_VOID

    def test_a_difference_inside_the_noise_is_inconclusive(self, config):
        """Reporting a number here would be reporting the machine's mood."""
        result = compare(
            config,
            arm("base", median=100, minimum=80),
            arm("branch", median=98, minimum=79),
        )
        assert result["verdict"] == VERDICT_INCONCLUSIVE

    def test_min_and_median_disagreeing_is_inconclusive(self, config):
        """Two statistics pointing opposite ways is not a result."""
        result = compare(
            config,
            arm("base", median=100, minimum=99),
            arm("branch", median=80, minimum=101),
        )
        assert result["verdict"] == VERDICT_INCONCLUSIVE

    def test_a_clear_win_is_ok(self, config):
        """A difference beyond the noise, agreed by both statistics."""
        result = compare(
            config,
            arm("base", median=100, minimum=98),
            arm("branch", median=50, minimum=48),
        )
        assert result["verdict"] == VERDICT_OK
        assert "50.00 ms faster" in result["reason"]

    def test_a_regression_is_also_ok_as_a_verdict(self, config):
        """'ok' means the measurement holds, not that the change is good."""
        result = compare(
            config,
            arm("base", median=50, minimum=48),
            arm("branch", median=100, minimum=98),
        )
        assert result["verdict"] == VERDICT_OK
        assert "slower" in result["reason"]

    def test_an_outlier_does_not_make_everything_inconclusive(self, config):
        """One scheduling spike must not set the noise floor."""
        result = compare(
            config,
            arm("base", median=100, minimum=98, maximum=900),
            arm("branch", median=50, minimum=48, maximum=800),
        )
        assert result["verdict"] == VERDICT_OK


def test_equivalence_mismatches_lists_every_field():
    """The caller is told which fields disagreed, not just that some did."""
    mismatches = equivalence_mismatches(
        {"response_bytes": 1, "count": 2, "results": 3},
        {"response_bytes": 9, "count": 2, "results": 4},
    )
    assert [item["field"] for item in mismatches] == ["response_bytes", "results"]


def test_per_query_attribution_joins_both_arms(config):
    """A query present in one arm only still appears, with a zero opposite."""
    result = compare(
        config,
        arm("base", median=100, minimum=98),
        arm("branch", median=50, minimum=48),
        traces={"base": trace_payload(40.0), "branch": trace_payload(10.0)},
    )
    (row,) = result["per_query"]
    assert row["query"] == "books"
    assert row["base_total_ms"] == 41.0  # noqa: PLR2004
    assert row["branch_total_ms"] == 11.0  # noqa: PLR2004
    assert row["delta_ms"] == -30.0  # noqa: PLR2004


def test_shape_and_calibration_travel_with_the_number(config):
    """A result is never quoted without the shape it was measured at."""
    result = compare(
        config,
        arm("base", median=100, minimum=98),
        arm("branch", median=50, minimum=48),
        shape={"counts": {"books": 300}, "m2m_pairs": {"a.b": 12}, "warnings": ["w"]},
    )
    assert result["shape"]["knobs"] == {"rows": 10}
    assert result["shape"]["counts"] == {"books": 300}
    assert result["shape"]["warnings"] == ["w"]
    assert result["calibration"][0]["production"] == 100  # noqa: PLR2004
    assert result["calibration"][0]["seed"] == 300  # noqa: PLR2004


def test_the_local_measurement_caveat_is_always_present(config):
    """A local number is a floor; the report never lets that be dropped."""
    result = compare(
        config,
        arm("base", median=100, minimum=98),
        arm("branch", median=50, minimum=48),
    )
    assert "floor, not an estimate" in result["caveat"]


class TestRendering:
    """The markdown a reviewer actually reads."""

    def test_a_void_report_leads_with_the_disagreement(self, config):
        """The first thing on the page is that no delta may be quoted."""
        result = compare(
            config,
            arm("base", median=100, minimum=95),
            arm("branch", median=50, minimum=45, count=41),
        )
        rendered = render_markdown(result)
        assert "VOID — do not quote a delta" in rendered
        assert "## The arms disagree" in rendered

    def test_a_normal_report_has_every_section(self, config):
        """Wall clock, attribution, shape, calibration and conditions."""
        result = compare(
            config,
            arm("base", median=100, minimum=98),
            arm("branch", median=50, minimum=48),
            traces={"base": trace_payload(40.0), "branch": trace_payload(10.0)},
            shape={"counts": {"books": 300}},
        )
        rendered = render_markdown(result)
        for heading in (
            "## Wall clock",
            "## Per-query attribution",
            "## Shape measured",
            "## Calibration against production",
            "## Conditions",
        ):
            assert heading in rendered
        assert "base-sha" in rendered

    def test_classifier_collisions_are_called_out(self, config):
        """A label mixing two queries invalidates its own median."""
        colliding = {
            "repeats": 1,
            "runs": [
                {
                    "db": [
                        {"sql": "SELECT a FROM book", "dur_ms": 1.0, "gap_ms": 1.0},
                        {"sql": "SELECT b FROM book", "dur_ms": 1.0, "gap_ms": 1.0},
                    ]
                },
                {"db": [{"sql": "SELECT a FROM book", "dur_ms": 1.0, "gap_ms": 1.0}]},
            ],
        }
        result = compare(
            config,
            arm("base", median=100, minimum=98),
            arm("branch", median=50, minimum=48),
            traces={"base": colliding, "branch": colliding},
        )
        assert result["classifier_collisions"] == ["books"]
        assert "Classifier collision" in render_markdown(result)
