"""Tests for the wall-clock pass and its preconditions."""

import pytest
from django.test import override_settings
from mitol.benchmark import config as cfg
from mitol.benchmark.django_env import (
    PreconditionError,
    enforce_preconditions,
    parse_database_url,
)
from mitol.benchmark.measure import MeasurementError, build_caller, run_bench
from mitol.benchmark.seeding import run_seed

pytestmark = pytest.mark.django_db


def make_config(**sections):
    """Return a configuration for the testapp's libraries endpoint."""
    merged = {
        "benchmark": {"name": "measure test"},
        "django": {"settings_module": "main.settings.test"},
        "database": {"name": "bench_measure"},
        "target": {
            "path": "/api/libraries/",
            "params": {"page_size": 5},
            "nested_keys": ["books"],
        },
        "measure": {"warmup": 1, "iterations": 3, "trace_repeats": 2},
        "seed": {
            "step": [
                {
                    "name": "authors",
                    "factory": "libraries.factories:AuthorFactory",
                    "count": 3,
                },
                {
                    "name": "books",
                    "factory": "libraries.factories:BookFactory",
                    "count": 6,
                    "kwargs": {"author": "$cycle:authors"},
                },
                {
                    "name": "libraries",
                    "factory": "libraries.factories:LibraryFactory",
                    "count": 4,
                    "m2m": {"books": {"source": "books", "per": 2}},
                },
            ]
        },
        **sections,
    }
    return cfg.from_merged(merged)


@pytest.fixture
def seeded():
    """Return a configuration whose dataset has been built."""
    config = make_config()
    return config, run_seed(config).as_dict()


def test_bench_result_shape(seeded):
    """The result carries timings, query count and the equivalence fields."""
    config, shape = seeded
    result = run_bench(config, shape, "branch", strict=False)

    assert result["label"] == "branch"
    assert result["iterations"] == 3  # noqa: PLR2004
    assert len(result["timings_ms"]) == 3  # noqa: PLR2004
    assert result["total_ms_min"] <= result["total_ms_median"]
    assert result["queries"] > 0
    assert result["count"] == 4  # noqa: PLR2004
    assert result["results"] == 4  # noqa: PLR2004
    assert result["response_bytes"] > 0
    # Four libraries of two books each: the nested length is what catches a
    # serializer change that keeps the row count but drops its contents.
    assert result["nested.books"] == 8  # noqa: PLR2004
    assert result["seed"]["counts"]["books"] == 6  # noqa: PLR2004


def test_the_capture_pass_is_separate_from_the_timings(seeded):
    """A debug cursor costs more, so it must not contaminate the timings."""
    config, shape = seeded
    result = run_bench(config, shape, strict=False)

    # The capture pass is one extra call beyond the timed ones, and its SQL
    # total is reported under a name that says so.
    assert "sql_ms_capture_pass" in result
    assert len(result["timings_ms"]) == config.measure.iterations


def test_a_wrong_status_stops_the_run(seeded):
    """Measuring an error page would produce a fast, meaningless number."""
    config, shape = seeded
    broken = cfg.from_merged(
        {**config.as_dict(), "target": {"path": "/api/nope/", "expect_status": 200}}
    )
    with pytest.raises(MeasurementError, match="expected 200, got 404"):
        build_caller(broken, shape)[0]()


def test_reverse_targets_are_resolved(seeded):
    """A URL name is the more robust way to name an endpoint."""
    config, shape = seeded
    by_name = cfg.from_merged(
        {**config.as_dict(), "target": {"reverse": "library-list"}}
    )
    _, url = build_caller(by_name, shape)
    assert url == "/api/libraries/"


def test_an_unresolvable_reverse_is_explained(seeded):
    """A typo in a URL name says so rather than failing at request time."""
    config, shape = seeded
    broken = cfg.from_merged({**config.as_dict(), "target": {"reverse": "nope-list"}})
    with pytest.raises(MeasurementError, match="does not resolve"):
        build_caller(broken, shape)


class TestPreconditions:
    """What the harness refuses to measure, and what it fixes."""

    def test_a_profiler_is_refused(self):
        """Its cost scales with hydrated objects, inflating one arm."""
        config = make_config()
        with (
            override_settings(
                MIDDLEWARE=["zeal.middleware.zeal_middleware"], DEBUG=False
            ),
            pytest.raises(PreconditionError, match="profiler middleware"),
        ):
            enforce_preconditions(config)

    def test_a_profiler_can_be_stripped_on_the_record(self):
        """Stripping is explicit and reported; there is no silent removal."""
        config = make_config(measure={"middleware_exclude": ["zeal"]})
        with override_settings(
            MIDDLEWARE=["zeal.middleware.zeal_middleware", "other.Middleware"],
            DEBUG=False,
        ):
            found = enforce_preconditions(config, strict=False)
        assert found.middleware_stripped == ["zeal.middleware.zeal_middleware"]
        assert found.profilers_active == []

    def test_allowing_a_profiler_is_recorded_rather_than_hidden(self):
        """Opting in still has to show up in the result."""
        config = make_config(measure={"allow_profilers": True})
        with override_settings(
            MIDDLEWARE=["zeal.middleware.zeal_middleware"], DEBUG=False
        ):
            found = enforce_preconditions(config, strict=False)
        # Only the pytest blocker remains; the profiler has been accepted.
        assert found.profilers_active == []
        assert all("profiler middleware" not in r for r in found.blockers())

    def test_debug_is_forced_off_and_reported(self):
        """Dev settings hardcode DEBUG; refusing would make this unusable."""
        config = make_config()
        with override_settings(DEBUG=True, MIDDLEWARE=[]):
            found = enforce_preconditions(config, strict=False)
            assert found.debug_forced_off is True

    def test_running_under_pytest_is_visible_in_the_result(self):
        """The conditions a number was measured under travel with it."""
        config = make_config()
        with override_settings(MIDDLEWARE=[], DEBUG=False):
            found = enforce_preconditions(config, strict=False)
        assert found.under_pytest is True
        assert any("pytest" in reason for reason in found.blockers())


class TestDatabaseUrlParsing:
    """Pointing Django at the scratch database, not the developer's."""

    def test_postgres_url(self):
        """A DSN becomes DATABASES entries."""
        parsed = parse_database_url("postgres://bob:s3cret@db.example:6543/bench_x")
        assert parsed["NAME"] == "bench_x"
        assert parsed["HOST"] == "db.example"
        assert str(parsed["PORT"]) == "6543"
        assert parsed["USER"] == "bob"
