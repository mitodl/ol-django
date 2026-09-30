"""
What the process keeps: the pass that runs after the endpoint is exonerated.

A latency benchmark can come back clean and leave the question open. An
endpoint that answers in 350 ms locally, against a seed calibrated to
production, can still stall for seconds in production — and when it does, the
cause is often not in the request at all but in the heap the request leaves
behind. A worker that grows every request eventually spends its life at
whatever ceiling bounds it, where stop-the-world collections are longest and
a process manager may recycle it mid-request.

This module answers a narrower question than a profiler does: *after serving
this endpoint N times and collecting, what is still here?*

Three series, because no one of them can be read alone:

*RSS* is what a memory ceiling and an OOM killer see, and it is the one number
that cannot distinguish a leak from a high-water mark. CPython returns a freed
arena to the operating system only when every object in it is gone, so a
request that transiently allocates and frees a large working set still leaves
RSS elevated. Rising RSS on its own is not evidence of retention.

*Live object count* is. It is taken after a forced collection, so anything it
counts is reachable, not merely uncollected. Growth here means something holds
a reference across requests.

*Retained objects by type* says what is held, which is usually enough to name
the holder without walking anything.

Where it is not enough, `holders` walks the reference graph upward. That walk
is breadth-first under a hard budget for a reason: `gc.get_referrers` scans
every tracked object on each call, so a depth-first search with any branching
costs thousands of full-heap scans and appears to hang rather than fail. The
shortest path to something named is also the most legible one.

The retained set is delimited with ``gc.freeze()`` rather than ``id()`` sets:
the baseline heap is moved to the permanent generation, so everything the
collector can still enumerate afterwards is, by construction, what the run
added. That sidesteps address reuse entirely, and makes the per-request object
count a count of *growth* rather than a full-heap enumeration — which matters,
because materialising a list of every tracked object on each request inflated
the very RSS series being measured.

*The instrument retains more per request than the threshold allows*, so it is
taken out of the way rather than reported. Django's test client re-connects
three signals on every request — `template_rendered` and
`got_request_exception` in `Client.request`, `request_started` and
`request_finished` in its handler — and `Signal.connect` registers a
`weakref.finalize` against the owner of each receiver. Two of those owners
never die: `close_old_connections` is a module-level function, and
`store_exc_info` is bound to the long-lived client. So every request leaves
finalizers in `weakref.finalize._registry` for the life of the process: twelve
objects a request, measured, before the endpoint has done anything at all.
Without addressing it a view returning a fixed string reads `retaining` and
the command exits 1.

Each is detached after the request that created it — a detachment the
client's own explicit `disconnect` has already made redundant. The match is
deliberately two-part, on the callback *and* on what the finalizer is held
against, so that only something a test client can own qualifies: an
application that re-connects its own long-lived receiver every request leaks
the same way in production, and that is the finding rather than the
instrument.

Detaching rather than subtracting an estimate, because the two are not
equivalent. The obvious estimate — the same request against a path the URL
resolver rejects — measures 44 objects a request rather than twelve in this
repository, the difference being a `LogRecord` per request and the
`WSGIRequest` each one pins, held by a log handler that a 200 never reaches.
Subtracting that would have hidden a leak of thirty objects a request. A
no-op view reads 0.3 objects a request once the finalizers are detached.

One limit is worth knowing before reading a result. *Only tracked containers
are visible.* CPython untracks a tuple or dict whose contents are all
themselves untracked, so an object held only in such a container has no
discoverable referrers and the walk reports nothing. In practice a leak worth
finding holds model instances, querysets or closures, all of which keep their
containers tracked.
"""

from __future__ import annotations

import functools
import gc
import os
import sys
import time
import weakref
from collections import Counter, deque
from typing import TYPE_CHECKING, Any, NamedTuple

from mitol.benchmark.django_env import enforce_preconditions
from mitol.benchmark.measure import build_caller, refuse_empty_response

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Mapping

    from mitol.benchmark.config import BenchmarkConfig

# Types that say nothing about a leak: every request allocates them and the
# interpreter interns or pools many of them. Reported, but never chosen as the
# subject of a reference walk.
_UNINFORMATIVE = frozenset(
    {
        "builtins.dict",
        "builtins.list",
        "builtins.tuple",
        "builtins.set",
        "builtins.str",
        "builtins.int",
        "builtins.frozenset",
        "builtins.method",
        "builtins.function",
        "builtins.cell",
    }
)


def rss_bytes() -> int:
    """
    Return this process's resident set size, or 0 where it cannot be read.

    ``/proc/self/statm`` is preferred because it is the current value.
    ``ru_maxrss`` is a high-water mark, so on a platform without procfs the
    per-request deltas flatten to zero once the peak is reached — which is
    reported rather than silently treated as stability.
    """
    try:
        with open("/proc/self/statm") as handle:  # noqa: PTH123
            return int(handle.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    except (OSError, IndexError, ValueError):
        pass
    try:
        import resource  # noqa: PLC0415

        maximum = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, OSError):
        return 0
    # Linux reports KiB, macOS bytes. Only the former reaches this fallback in
    # practice, but the scale difference is worth not guessing about.
    return maximum * 1024 if sys.platform != "darwin" else maximum


def lru_cache_sizes() -> dict[str, int]:
    """
    Return the current size of every ``functools.lru_cache`` in the process.

    Matched on the wrapper's type, never by probing objects for a
    ``cache_info`` attribute. The heap holds lazy module proxies whose
    ``__getattr__`` imports on first touch, so attribute probing walks straight
    into importing whatever they shadow and can fail on an absent optional
    dependency.
    """
    sizes: dict[str, int] = {}
    for obj in gc.get_objects():
        if type(obj) is not functools._lru_cache_wrapper:  # noqa: SLF001
            continue
        try:
            wrapped = obj.__wrapped__
            name = (
                f"{getattr(wrapped, '__module__', '?')}."
                f"{getattr(wrapped, '__qualname__', '?')}"
            )
            sizes[name] = obj.cache_info().currsize
        except Exception:  # noqa: BLE001, S112 - arbitrary objects, best effort
            continue
    return sizes


def _type_name(obj: Any) -> str:
    kind = type(obj)
    return f"{kind.__module__}.{kind.__name__}"


def _describe(obj: Any) -> str:
    """Return a short, identifying label for one node in a reference chain."""
    kind = type(obj)
    if kind.__name__ == "module":
        return f"MODULE {obj.__name__}"
    if isinstance(obj, type):
        return f"CLASS {obj.__module__}.{obj.__name__}"
    if isinstance(obj, dict):
        keys = [repr(key)[:24] for key in list(obj)[:4]]
        return f"dict(len={len(obj)}, keys=[{', '.join(keys)}])"
    if isinstance(obj, (list, tuple, set, frozenset, deque)):
        return f"{kind.__name__}(len={len(obj)})"
    if kind.__name__ == "function":
        return f"function {getattr(obj, '__qualname__', '?')}"
    return _type_name(obj)


def _is_root(obj: Any) -> bool:
    """Classes and modules live for the process; a chain ending there is held."""
    return isinstance(obj, type) or type(obj).__name__ == "module"


def holders(
    start: Any, forbidden: frozenset[int], budget: int
) -> tuple[list[str] | None, int]:
    """
    Walk references upward to the first named holder. Returns (chain, budget).

    Breadth-first and budgeted: ``gc.get_referrers`` is a full-heap scan, so
    the cost is the number of calls, not the depth reached. A depth-first walk
    with branching factor four to depth seven is sixteen thousand scans of a
    million-object heap, which does not return in any useful time. Breadth-
    first also yields the shortest chain, which is the one worth reading.
    """
    queue: deque[tuple[Any, list[str]]] = deque([(start, [_describe(start)])])
    seen = {id(start)}
    while queue and budget > 0:
        obj, path = queue.popleft()
        budget -= 1
        for ref in gc.get_referrers(obj):
            if id(ref) in seen or id(ref) in forbidden:
                continue
            # A frame is this walk's own stack, not the holder being looked for.
            if type(ref).__name__ == "frame":
                continue
            seen.add(id(ref))
            chain = [_describe(ref), *path]
            if _is_root(ref):
                return chain, budget
            owner = _owner_of(ref)
            if owner is not None:
                return [owner, *chain], budget
            if len(chain) < 12:  # noqa: PLR2004 - a longer chain is unreadable anyway
                queue.append((ref, chain))
    return None, budget


def _owner_of(ref: Any) -> str | None:
    """
    Name the module or class whose ``__dict__`` this is, if it is one.

    A process-lifetime cache almost always lives in a module global or a class
    attribute, and the chain only becomes actionable once that owner is named:
    "a dict of 175 entries" is a fact, "``Course.get_filtered_runs._caches``"
    is a bug report.
    """
    if not isinstance(ref, dict):
        return None
    for owner in gc.get_referrers(ref):
        if type(owner).__name__ == "module":
            return f"MODULE {owner.__name__}"
        if isinstance(owner, type):
            return f"CLASS {owner.__module__}.{owner.__name__}"
    return None


def _verdict(
    objects_per_request: float, mib_per_request: float, config: BenchmarkConfig
) -> tuple[str, str]:
    """Classify the growth, by the rule the configuration states."""
    memory = config.memory
    if objects_per_request >= memory.retained_objects_per_request:
        return "retaining", (
            f"{objects_per_request:.0f} objects per request are still reachable "
            f"after a forced collection, so something holds them across "
            f"requests; at {mib_per_request:.2f} MiB per request this is what "
            f"grows the worker"
        )
    if mib_per_request >= memory.highwater_mib_per_request:
        return "high-water", (
            f"RSS grew {mib_per_request:.2f} MiB per request while live objects "
            f"did not ({objects_per_request:+.0f} per request), which is what "
            f"the allocator holding freed arenas looks like rather than "
            f"retention, so the fix is to allocate less per request rather "
            f"than to find a holder — bearing in mind that retention the "
            f"collector cannot enumerate reads exactly the same way"
        )
    return "stable", (
        f"{objects_per_request:+.0f} objects and {mib_per_request:+.2f} MiB per "
        f"request, so neither rate [memory] sets was crossed — which is not the "
        f"same as nothing being held: growth under the thresholds, and anything "
        f"the collector cannot see, both read as stable"
    )


def _attribution(retained: list[Any], config: BenchmarkConfig) -> dict[str, Any]:
    """Name what is still reachable, and optionally what holds it."""
    # One exemplar per type, not every retained object: during a memory
    # measurement, holding strong references to the whole retained set is the
    # worst possible bookkeeping.
    counts: Counter[str] = Counter()
    exemplars: dict[str, Any] = {}
    for obj in retained:
        name = _type_name(obj)
        counts[name] += 1
        exemplars.setdefault(name, obj)

    # These containers are themselves new objects; excluding them keeps the
    # walk from reporting this function as the holder of everything it
    # examines.
    forbidden = frozenset({id(retained), id(counts), id(exemplars)})

    chains = []
    budget = config.memory.scan_budget
    informative = [
        (name, count)
        for name, count in counts.most_common()
        if name not in _UNINFORMATIVE
    ]
    for name, _ in informative[: config.memory.holders]:
        if budget <= 0:
            break
        chain, budget = holders(exemplars[name], forbidden, budget)
        chains.append({"type": name, "chain": chain})

    return {
        "retained_objects": len(retained),
        "retained_by_type": [
            {"type": name, "count": count} for name, count in counts.most_common(20)
        ],
        "holders": chains,
        "scan_budget_left": budget,
    }


class _Arm(NamedTuple):
    """One measured loop, and the accounting the verdict is read from."""

    baseline_rss: int
    final_rss: int
    baseline_objects: int
    final_objects: int
    objects_per_request: float
    mib_per_request: float
    series: list[dict[str, Any]]
    retained: list[Any]
    harness_finalizers_detached: int | None


def harness_finalizer_test() -> Callable[[Any], bool] | None:
    """
    Return a test for "this finalizer is the harness's", or ``None``.

    Narrow on purpose, and on two counts rather than one. The callback has to
    be the one ``Signal.connect`` registers, *and* the thing it is held against
    has to be something that exists only because a test client is driving the
    request: ``close_old_connections``, which the client's handler re-connects
    twice a request, or the client itself, whose ``store_exc_info`` is
    re-connected a third time.

    Matching on the callback alone would be wrong. An application that calls
    ``connect`` on every request with a receiver that outlives it leaks a
    finalizer a request in production too, and that is the finding — not the
    instrument. It has to stay visible.

    ``None`` means this Django does not register finalizers where the pass
    looks for them, so nothing is detached and the result says so rather than
    quietly reporting the test client's retention as though it were the
    endpoint's.
    """
    from django.db import close_old_connections  # noqa: PLC0415
    from django.dispatch import Signal  # noqa: PLC0415
    from django.test import Client  # noqa: PLC0415

    remove_receiver = getattr(Signal, "_remove_receiver", None)
    if remove_receiver is None:
        return None

    def is_the_harness_s(candidate: Any) -> bool:
        # peek() rather than attribute access: these are arbitrary finalizers,
        # and one whose referent has already died has nothing left to compare.
        peeked = candidate.peek()
        if peeked is None:
            return False
        referent, callback, _, _ = peeked
        if getattr(callback, "__func__", None) is not remove_receiver:
            return False
        return referent is close_old_connections or isinstance(referent, Client)

    return is_the_harness_s


def _sweep(is_the_harness_s: Callable[[Any], bool] | None) -> tuple[int, int]:
    """
    Count what the run has added, detaching the harness's own artifacts.

    One enumeration for both jobs. After ``gc.freeze()`` this walks only the
    collector's unfrozen generations, which is the run's own growth rather than
    the whole heap, so it is cheap enough to do on every request — and doing it
    per request is what keeps the series a picture of the endpoint instead of a
    line with the client's slope added to it.

    A detached finalizer is garbage the moment the list holding it is dropped,
    so it is excluded from the count rather than counted and subtracted later.
    """
    tracked = gc.get_objects()
    if is_the_harness_s is None:
        return len(tracked), 0

    detached = 0
    for obj in tracked:
        if type(obj) is weakref.finalize and is_the_harness_s(obj):
            obj.detach()
            detached += 1
    return len(tracked) - detached, detached


def _measure_arm(call: Callable[[], Any], requests: int) -> _Arm:
    """Serve one call `requests` times and report what the process kept."""
    is_the_harness_s = harness_finalizer_test()

    gc.collect()
    gc.collect()

    # RSS is read last of the baseline readings, after the enumeration below
    # it and after whatever cache census the caller takes before calling here.
    # `gc.get_objects()` materialises a list of every tracked object — a
    # million entries in a mature Django process — and glibc keeps that arena
    # resident long after the list is freed. Read first, the baseline is low
    # by whatever the measurement itself cost and the difference is charged to
    # the requests: on a no-op view that reads 0.23 MiB per request, over the
    # high-water threshold, where reading it last reads zero.
    baseline_objects = len(gc.get_objects())
    baseline_rss = rss_bytes()

    # Move the baseline heap into the permanent generation. From here on the
    # collector enumerates only what the run adds, so the retained set needs
    # no id() bookkeeping and cannot be confused by address reuse.
    gc.freeze()

    series: list[dict[str, Any]] = []
    detached_total = 0
    try:
        for index in range(requests):
            call()
            growth, detached = _sweep(is_the_harness_s)
            detached_total += detached
            series.append(
                {
                    "request": index + 1,
                    "rss_mib": round(rss_bytes() / (1024 * 1024), 2),
                    # Growth over the frozen baseline. Cheap, unlike the
                    # full-heap enumeration it replaces, whose per-request
                    # allocation inflated the RSS series being measured.
                    "objects": baseline_objects + growth,
                }
            )

        gc.collect()
        gc.collect()
        # Read before the enumeration on the next line, which is the mirror of
        # the baseline reading coming after one: both then sit on the same
        # allocator high-water mark, and their difference is the requests.
        final_rss = rss_bytes()
        # Two full collections move every unfrozen survivor into the oldest
        # generation, so this list is exactly the retained set.
        retained = gc.get_objects(generation=2)
    finally:
        # lru_cache_sizes() and anything after this must see the whole heap.
        gc.unfreeze()

    final_objects = baseline_objects + len(retained)
    return _Arm(
        baseline_rss=baseline_rss,
        final_rss=final_rss,
        baseline_objects=baseline_objects,
        final_objects=final_objects,
        objects_per_request=(final_objects - baseline_objects) / requests,
        mib_per_request=(final_rss - baseline_rss) / (1024 * 1024) / requests,
        series=series,
        retained=retained,
        harness_finalizers_detached=(
            None if is_the_harness_s is None else detached_total
        ),
    )


def run_memory(
    config: BenchmarkConfig,
    ids: Mapping[str, Any],
    label: str = "unknown",
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Serve the endpoint repeatedly and report what the process kept."""
    preconditions = enforce_preconditions(config, strict=strict)
    call, url = build_caller(config, ids)
    memory = config.memory

    # Before anything is measured, and refused here for the reason the A/B
    # refuses it there: an endpoint serving nothing has an admirably flat heap.
    # This call doubles as the first warm-up.
    refuse_empty_response(
        config,
        call(),
        opening="refusing to measure retention on an empty response",
        consequence=(
            "An endpoint serving nothing leaves an admirably flat heap, so the "
            "verdict would read as stable and nothing downstream could tell "
            "you the request was not the one intended."
        ),
    )

    # Warm-up is excluded from the series: a worker's first request through an
    # endpoint compiles serializers, fills field caches and opens connections,
    # all of which are one-time and would read as growth.
    for _ in range(memory.warmup):
        call()

    started = time.perf_counter()
    # Taken before the arm, so the arm's baseline RSS reading comes after this
    # enumeration rather than before it. See the comment there.
    baseline_caches = lru_cache_sizes() if memory.attribute else {}
    arm = _measure_arm(call, memory.requests)

    verdict, reason = _verdict(arm.objects_per_request, arm.mib_per_request, config)

    result: dict[str, Any] = {
        "label": label,
        "url": url,
        "requests": memory.requests,
        "warmup": memory.warmup,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "verdict": verdict,
        "reason": reason,
        "baseline_rss_mib": round(arm.baseline_rss / (1024 * 1024), 2),
        "final_rss_mib": round(arm.final_rss / (1024 * 1024), 2),
        "baseline_objects": arm.baseline_objects,
        "final_objects": arm.final_objects,
        "objects_per_request": round(arm.objects_per_request, 1),
        "mib_per_request": round(arm.mib_per_request, 3),
        "harness_finalizers_detached": arm.harness_finalizers_detached,
        "series": arm.series,
        "preconditions": preconditions.as_dict(),
        "knobs": dict(config.knobs),
    }

    if memory.attribute:
        result.update(_attribution(arm.retained, config))
        result["lru_caches_grown"] = _cache_growth(
            baseline_caches, lru_cache_sizes(), memory.requests
        )
    return result


def _cache_growth(
    before: Mapping[str, int], after: Mapping[str, int], requests: int
) -> list[dict[str, Any]]:
    """
    Report every ``lru_cache`` that is larger than it was, biggest first.

    A cache keyed on something request-scoped is the most common way a worker
    grows without any single place looking like a leak. An empty list here is
    informative too, but it narrows the category rather than closing it: the
    comparison is on ``cache_info().currsize``, so a cache that gains no
    entries while the values already in it accumulate references does not
    appear.
    """
    grown = []
    for name, size in after.items():
        delta = size - before.get(name, 0)
        if delta > 0:
            grown.append(
                {
                    "cache": name,
                    "entries_added": delta,
                    "current_size": size,
                    "per_request": round(delta / requests, 1),
                }
            )
    return sorted(grown, key=lambda row: -row["entries_added"])[:15]
