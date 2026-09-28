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
from collections import Counter, deque
from typing import TYPE_CHECKING, Any

from mitol.benchmark.django_env import enforce_preconditions
from mitol.benchmark.measure import build_caller

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

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
            f"did not ({objects_per_request:+.0f} per request), so this is the "
            f"allocator holding freed arenas rather than retention — the fix is "
            f"to allocate less per request, not to find a holder"
        )
    return "stable", (
        f"{objects_per_request:+.0f} objects and {mib_per_request:+.2f} MiB per "
        f"request: the process returns to where it started"
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

    # Warm-up is excluded from the series: a worker's first request through an
    # endpoint compiles serializers, fills field caches and opens connections,
    # all of which are one-time and would read as growth.
    for _ in range(memory.warmup):
        call()

    gc.collect()
    gc.collect()
    baseline_rss = rss_bytes()
    baseline_objects = len(gc.get_objects())
    baseline_caches = lru_cache_sizes() if memory.attribute else {}
    # Move the baseline heap into the permanent generation. From here on the
    # collector enumerates only what the run adds, so the retained set needs
    # no id() bookkeeping and cannot be confused by address reuse.
    gc.freeze()

    series = []
    started = time.perf_counter()
    try:
        for index in range(memory.requests):
            call()
            series.append(
                {
                    "request": index + 1,
                    "rss_mib": round(rss_bytes() / (1024 * 1024), 2),
                    # Growth over the frozen baseline. Cheap, unlike the
                    # full-heap enumeration it replaces, whose per-request
                    # allocation inflated the RSS series being measured.
                    "objects": baseline_objects + len(gc.get_objects()),
                }
            )

        gc.collect()
        gc.collect()
        final_rss = rss_bytes()
        # Two full collections move every unfrozen survivor into the oldest
        # generation, so this list is exactly the retained set.
        retained = gc.get_objects(generation=2)
    finally:
        # lru_cache_sizes() and any later pass must see the whole heap again.
        gc.unfreeze()
    final_objects = baseline_objects + len(retained)

    requests = memory.requests
    objects_per_request = (final_objects - baseline_objects) / requests
    mib_per_request = (final_rss - baseline_rss) / (1024 * 1024) / requests
    verdict, reason = _verdict(objects_per_request, mib_per_request, config)

    result: dict[str, Any] = {
        "label": label,
        "url": url,
        "requests": memory.requests,
        "warmup": memory.warmup,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "verdict": verdict,
        "reason": reason,
        "baseline_rss_mib": round(baseline_rss / (1024 * 1024), 2),
        "final_rss_mib": round(final_rss / (1024 * 1024), 2),
        "baseline_objects": baseline_objects,
        "final_objects": final_objects,
        "objects_per_request": round(objects_per_request, 1),
        "mib_per_request": round(mib_per_request, 3),
        "series": series,
        "preconditions": preconditions.as_dict(),
        "knobs": dict(config.knobs),
    }

    if memory.attribute:
        result.update(_attribution(retained, config))
        result["lru_caches_grown"] = _cache_growth(
            baseline_caches, lru_cache_sizes(), requests
        )
    return result


def _cache_growth(
    before: Mapping[str, int], after: Mapping[str, int], requests: int
) -> list[dict[str, Any]]:
    """
    Report every ``lru_cache`` that is larger than it was, biggest first.

    A cache keyed on something request-scoped is the most common way a worker
    grows without any single place looking like a leak. An empty list here is
    informative too: it rules the whole category out, and points at a
    hand-rolled cache instead.
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
