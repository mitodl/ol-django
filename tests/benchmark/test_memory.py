"""Tests for the retention pass."""

import functools
import gc

import pytest
from mitol.benchmark import config as cfg
from mitol.benchmark.memory import (
    _verdict,
    holders,
    lru_cache_sizes,
    rss_bytes,
    run_memory,
)
from mitol.benchmark.report import render_memory_markdown
from mitol.benchmark.seeding import run_seed

pytestmark = pytest.mark.django_db


def make_config(**sections):
    """Return a configuration for the testapp's libraries endpoint."""
    merged = {
        "benchmark": {"name": "memory test"},
        "django": {"settings_module": "main.settings.test"},
        "database": {"name": "bench_memory"},
        "target": {"path": "/api/libraries/", "params": {"page_size": 5}},
        "memory": {"requests": 4, "warmup": 1, "holders": 1, "scan_budget": 40},
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


def test_rss_is_readable():
    """Without this the whole pass silently reports zeros."""
    assert rss_bytes() > 0


def test_the_accounting_is_coherent(seeded):
    """
    Whatever the verdict, the numbers behind it have to add up.

    Deliberately not asserting that the testapp is clean: it retains about
    twelve objects a request in `weakref.finalize._registry`, which is a
    finding rather than a fixture, and a test that assumed otherwise would be
    testing the app rather than the measurement.
    """
    config, shape = seeded
    result = run_memory(config, shape, strict=False)

    assert result["verdict"] in {"stable", "high-water", "retaining"}
    assert result["requests"] == 4  # noqa: PLR2004
    assert len(result["series"]) == 4  # noqa: PLR2004
    assert result["baseline_objects"] > 0
    assert result["objects_per_request"] == pytest.approx(
        (result["final_objects"] - result["baseline_objects"]) / 4, abs=0.1
    )


def test_the_series_carries_both_signals(seeded):
    """RSS alone cannot tell retention from a high-water mark."""
    config, shape = seeded
    result = run_memory(config, shape, strict=False)

    for point in result["series"]:
        assert point["rss_mib"] > 0
        assert point["objects"] > 0


class TestTheVerdictRule:
    """
    Which of the three readings a pair of growth rates produces.

    Unit-tested on synthetic rates rather than through a live endpoint: the
    rule is the part that has to be right, and driving it from a real request
    would make the test depend on how clean the testapp happens to be.
    """

    def test_reachable_growth_is_retention(self):
        """Objects surviving a forced collection mean something holds them."""
        verdict, reason = _verdict(50.0, 1.0, make_config())
        assert verdict == "retaining"
        assert "still reachable" in reason

    def test_rss_growth_without_object_growth_is_a_high_water_mark(self):
        """
        The distinction that decides the fix.

        CPython frees an arena to the OS only when every object in it is gone,
        so a request with a large transient working set leaves RSS up while
        holding nothing. That calls for allocating less, not for a holder
        hunt, and the two are easy to confuse from RSS alone.
        """
        verdict, reason = _verdict(0.0, 5.0, make_config())
        assert verdict == "high-water"
        assert "allocate less" in reason

    def test_neither_growing_is_stable(self):
        """The common case, and it has to be sayable."""
        verdict, _ = _verdict(-1.0, 0.0, make_config())
        assert verdict == "stable"

    def test_the_thresholds_are_configuration(self):
        """One project's noise is another's leak, so the rule is tunable."""
        strict = make_config(memory={"retained_objects_per_request": 1.0})
        assert _verdict(5.0, 0.0, strict)[0] == "retaining"

        loose = make_config(memory={"retained_objects_per_request": 10_000})
        assert _verdict(5.0, 0.0, loose)[0] == "stable"


class TestHolders:
    """Walking references upward to something with a name."""

    def test_a_module_level_holder_is_named(self):
        """The common shape: a process-lifetime container in a module global."""
        target = object()
        globals()["_holder_for_test"] = [target]
        try:
            chain, budget = holders(target, frozenset(), 200)
        finally:
            del globals()["_holder_for_test"]

        assert chain is not None
        assert any("MODULE" in step or "CLASS" in step for step in chain)
        assert budget < 200  # noqa: PLR2004

    def test_a_class_level_holder_is_named(self):
        """A dict on a class is the shape this was built to find."""

        class Keeper:
            cache = {}

        # A list, not a bare object(): CPython untracks a dict whose keys and
        # values are all untracked, and an untracked container is invisible to
        # gc.get_referrers. A real retained value is a model instance or a
        # queryset, which keeps its container tracked - but a test that plants
        # object() finds nothing and looks like a bug in the walk.
        target = ["held"]
        Keeper.cache["k"] = target
        try:
            chain, _ = holders(target, frozenset(), 200)
        finally:
            Keeper.cache.clear()

        assert chain is not None
        assert any("Keeper" in step for step in chain)

    def test_an_untracked_container_is_invisible(self):
        """
        The limit, asserted so it is a known property rather than a surprise.

        A dict holding only untracked values is itself untracked, so nothing
        can be walked back to it. Worth pinning: it is the one case where the
        walk truthfully reports nothing while something really does hold the
        object.
        """

        class Keeper:
            cache = {}

        target = object()
        Keeper.cache["k"] = target
        try:
            chain, _ = holders(target, frozenset(), 200)
        finally:
            Keeper.cache.clear()

        assert chain is None

    def test_the_budget_is_a_hard_stop(self):
        """
        Each call is a full-heap scan, so the budget is the real cost control.

        A depth-first walk with branching is thousands of scans and appears to
        hang; the budget is what makes an unbounded search safe to ship.
        """
        target = object()
        globals()["_holder_for_test"] = [target]
        try:
            chain, budget = holders(target, frozenset(), 0)
        finally:
            del globals()["_holder_for_test"]

        assert chain is None
        assert budget == 0

    def test_an_unheld_object_returns_no_chain(self):
        """Nothing holds a local, and the walk has to say so rather than loop."""
        chain, _ = holders(object(), frozenset(), 50)
        assert chain is None


class TestLruCacheEnumeration:
    """Finding every functools cache without importing the world."""

    def test_caches_are_found_by_type(self):
        """A cache in the process shows up with its qualified name."""

        @functools.cache
        def cached_for_test(value):
            return value * 2

        cached_for_test(1)
        cached_for_test(2)
        try:
            sizes = lru_cache_sizes()
        finally:
            cached_for_test.cache_clear()

        matching = [name for name in sizes if "cached_for_test" in name]
        assert matching
        assert sizes[matching[0]] == 2  # noqa: PLR2004

    def test_a_lazy_module_proxy_is_not_probed(self):
        """
        Attribute probing walks into lazy imports; type matching does not.

        `six.moves`-style proxies import on first `__getattr__`, so asking
        every heap object whether it has `cache_info` can try to import an
        absent optional dependency and take the whole pass down with it.
        """

        class ExplodingProxy:
            def __getattr__(self, name):
                msg = f"should never be probed for {name!r}"
                raise AssertionError(msg)

        proxy = ExplodingProxy()
        gc.collect()
        try:
            lru_cache_sizes()
        finally:
            del proxy


def test_the_report_leads_with_the_verdict(seeded):
    """A reader needs to know whether there is anything to chase."""
    config, shape = seeded
    result = run_memory(config, shape, strict=False)
    markdown = render_memory_markdown(result)
    headline = {"retaining": "RETAINED"}.get(
        result["verdict"], result["verdict"].upper()
    )

    assert "# Retention:" in markdown
    assert headline in markdown
    assert "live objects" in markdown


def test_attribution_can_be_switched_off(seeded):
    """The heap scans are the expensive part, so they have to be optional."""
    config = make_config(memory={"requests": 2, "attribute": False})
    _, shape = seeded
    result = run_memory(config, shape, strict=False)

    assert "retained_by_type" not in result
    assert "lru_caches_grown" not in result
    assert result["objects_per_request"] is not None
