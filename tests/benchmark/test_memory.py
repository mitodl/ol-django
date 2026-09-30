"""Tests for the retention pass."""

import functools
import gc
import weakref

import pytest
from django.db import close_old_connections
from django.dispatch import Signal
from django.test import Client
from libraries.models import Library
from mitol.benchmark import config as cfg
from mitol.benchmark.measure import MeasurementError
from mitol.benchmark.memory import (
    _measure_arm,
    _verdict,
    harness_finalizer_test,
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
    """Whatever the verdict, the numbers behind it have to add up."""
    config, shape = seeded
    result = run_memory(config, shape, strict=False)

    assert result["verdict"] in {"stable", "high-water", "retaining"}
    assert result["requests"] == 4  # noqa: PLR2004
    assert len(result["series"]) == 4  # noqa: PLR2004
    assert result["baseline_objects"] > 0
    assert result["objects_per_request"] == pytest.approx(
        (result["final_objects"] - result["baseline_objects"]) / 4, abs=0.1
    )


def test_a_view_that_does_nothing_is_stable(seeded):
    """
    The test that makes the rest of this worth reading.

    Django's test client re-connects three signals on every request and
    `Signal.connect` leaves a `weakref.finalize` against the owner of each
    receiver; two of those owners have process lifetime, so about twelve
    objects a request accumulate before the endpoint does anything. Unless
    they are taken out of the way, a view that returns a fixed string reports
    `retaining` and the command exits 1 — which is to say the pass reports the
    retention of its own instrument.
    """
    _, shape = seeded
    config = make_config(
        target={"path": "/api/noop/"},
        memory={"requests": 20, "warmup": 2, "holders": 1, "scan_budget": 40},
    )
    result = run_memory(config, shape, strict=False)

    assert result["verdict"] == "stable", result["reason"]
    assert result["harness_finalizers_detached"] > 0


def test_the_series_carries_both_signals(seeded):
    """RSS alone cannot tell retention from a high-water mark."""
    config, shape = seeded
    result = run_memory(config, shape, strict=False)

    for point in result["series"]:
        assert point["rss_mib"] > 0
        assert point["objects"] > 0


class TestTheHarnessArtifact:
    """Taking the measurement's own retention out of the measurement."""

    def test_the_test_client_s_finalizers_are_detached(self, seeded):
        """
        Three a request, and each one costs four objects.

        `ClientHandler.__call__` re-connects `request_started` and
        `request_finished` against `close_old_connections`, and
        `Client.request` re-connects `got_request_exception` against a method
        bound to the client. All three owners outlive the request, so the
        finalizers never fire and never leave `weakref.finalize._registry`.
        """
        config, shape = seeded
        result = run_memory(config, shape, strict=False)

        assert result["harness_finalizers_detached"] == 3 * result["requests"]

    def test_a_receiver_the_application_re_connects_is_left_alone(self):
        """
        The narrow half of the match, and the reason it is narrow.

        An application that calls `connect` on every request with a receiver
        that outlives it leaks a finalizer a request in production too. That
        is the finding, not the instrument, so matching on the callback alone
        would turn a real leak into a silent one. Only a finalizer held
        against `close_old_connections` or a test client can be the harness's.
        """
        signal = Signal()

        def receiver(**kwargs):
            """Receive nothing; the signal only weakly references this."""

        def call():
            signal.connect(receiver)
            signal.disconnect(receiver)

        arm = _measure_arm(call, 10)

        assert arm.harness_finalizers_detached == 0
        # One finalizer, its _Info, the weakref inside it and the bound
        # _remove_receiver: four objects a request that nothing detaches.
        assert arm.objects_per_request >= 3  # noqa: PLR2004

    def test_the_test_recognises_only_the_harness_s_finalizers(self):
        """The predicate itself, away from any measurement."""
        is_the_harness_s = harness_finalizer_test()
        assert is_the_harness_s is not None

        client = Client()
        signal = Signal()

        def unrelated(**kwargs):
            """Receive nothing, on behalf of nothing the harness owns."""

        signal.connect(close_old_connections)
        signal.connect(client.store_exc_info)
        signal.connect(unrelated)
        gc.collect()
        finalizers = [obj for obj in gc.get_objects() if type(obj) is weakref.finalize]
        recognised = [
            peeked[0]
            for obj in finalizers
            if is_the_harness_s(obj) and (peeked := obj.peek()) is not None
        ]

        assert close_old_connections in recognised
        assert client in recognised
        assert unrelated not in recognised

    def test_a_django_without_that_callback_detaches_nothing(self, monkeypatch):
        """
        The guard, so a future Django cannot make this silently wrong.

        `Signal._remove_receiver` is private. If it goes, the pass must stop
        detaching rather than carry on matching something else.
        """

        class Signalless:
            """A `Signal` that registers its finalizers some other way."""

        monkeypatch.setattr("django.dispatch.Signal", Signalless)

        assert harness_finalizer_test() is None

    def test_detaching_nothing_is_reported_rather_than_assumed(
        self, seeded, monkeypatch
    ):
        """
        And when it does stop, the result has to say so.

        Silently not detaching puts the client's twelve objects a request back
        into the endpoint's figure, where they read as a leak. A result that
        admits the instrument is still inside the number is weaker than one
        that does not, but it is not a wrong answer.
        """
        monkeypatch.setattr(
            "mitol.benchmark.memory.harness_finalizer_test", lambda: None
        )
        config, shape = seeded
        result = run_memory(config, shape, strict=False)

        assert result["harness_finalizers_detached"] is None
        assert "could not be taken out" in render_memory_markdown(result)


class TestAnEmptyResponse:
    """
    The refusal the A/B has, which this pass was missing.

    An endpoint serving nothing has an admirably flat heap, so it reads
    `stable` and the reader is told the request is clean rather than that it
    was never really made.
    """

    def test_it_is_refused(self, seeded):
        config, shape = seeded
        Library.objects.all().delete()

        with pytest.raises(MeasurementError, match="refusing to measure retention"):
            run_memory(config, shape, strict=False)

    def test_the_refusal_names_authorization_as_the_usual_cause(self, seeded):
        """A filterset returning nothing answers 200, so the hint is needed."""
        config, shape = seeded
        Library.objects.all().delete()

        with pytest.raises(MeasurementError, match=r"\[auth\]"):
            run_memory(config, shape, strict=False)

    def test_allow_empty_opts_back_in(self, seeded):
        """Where an empty response is the measurement, it stays available."""
        _, shape = seeded
        Library.objects.all().delete()
        config = make_config(
            target={
                "path": "/api/libraries/",
                "params": {"page_size": 5},
                "allow_empty": True,
            }
        )

        assert run_memory(config, shape, strict=False)["requests"] == 4  # noqa: PLR2004


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
    # The reader has to be told the figure is the endpoint's and not the
    # client's, because the difference is larger than the threshold.
    assert "finalizers left by the test client" in markdown


def test_attribution_can_be_switched_off(seeded):
    """The heap scans are the expensive part, so they have to be optional."""
    config = make_config(memory={"requests": 2, "attribute": False})
    _, shape = seeded
    result = run_memory(config, shape, strict=False)

    assert "retained_by_type" not in result
    assert "lru_caches_grown" not in result
    assert result["objects_per_request"] is not None
