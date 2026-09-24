"""
The wall-clock pass: what the headline number comes from.

Two rules shape this module.

*The timed calls are uninstrumented.* ``CaptureQueriesContext`` forces a debug
cursor that times every statement and retains every SQL string, and that cost
grows with statement size. So the query capture is a separate call made after
the timed loop, and its SQL total is reported as what it is — a figure from a
different, slower pass.

*Both arms must have done the same work.* The result carries response byte
length and item counts precisely so the comparison can be declared void when
they disagree. A delta between two arms that returned different things is not
a speed-up, it is a bug.
"""

from __future__ import annotations

import statistics
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from mitol.benchmark.django_env import enforce_preconditions
from mitol.benchmark.resolve import ResolutionContext, resolve
from mitol.benchmark.seeding import exports_of

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Mapping

    from mitol.benchmark.config import BenchmarkConfig


class MeasurementError(RuntimeError):
    """The endpoint under test could not be called as configured."""


def build_client(config: BenchmarkConfig, ids: Mapping[str, Any]) -> Any:
    """
    Return a test client, authenticated as the benchmark's user.

    DRF's ``APIClient`` is preferred because ``force_authenticate`` bypasses
    the login round-trip that would otherwise be timed. Django's own client is
    the fallback for a project that does not install DRF.
    """
    user = _load_user(config, ids)
    try:
        from rest_framework.test import APIClient  # noqa: PLC0415
    except ImportError:
        from django.test import Client  # noqa: PLC0415

        client = Client()
        if user is not None:
            client.force_login(user)
        return client

    client = APIClient()
    if user is not None:
        client.force_authenticate(user=user)
    return client


def _load_user(config: BenchmarkConfig, ids: Mapping[str, Any]) -> Any:
    from django.contrib.auth import get_user_model  # noqa: PLC0415

    context = ResolutionContext(knobs=config.knobs, ids=exports_of(ids))
    model = get_user_model()
    if config.auth.user_id is not None:
        return model.objects.get(pk=resolve(config.auth.user_id, context))
    if config.auth.username:
        field = model.USERNAME_FIELD
        return model.objects.get(**{field: resolve(config.auth.username, context)})
    return None


def resolve_url(config: BenchmarkConfig, ids: Mapping[str, Any]) -> str:
    """Return the path to request, from either ``reverse`` or ``path``."""
    context = ResolutionContext(knobs=config.knobs, ids=exports_of(ids))
    target = config.target
    if target.path:
        return str(resolve(target.path, context))

    from django.urls import NoReverseMatch, reverse  # noqa: PLC0415

    try:
        return reverse(
            target.reverse,
            args=resolve(list(target.reverse_args), context),
            kwargs=resolve(dict(target.reverse_kwargs), context),
        )
    except NoReverseMatch as exc:
        msg = f"[target].reverse = {target.reverse!r} does not resolve — {exc}"
        raise MeasurementError(msg) from exc


def build_caller(
    config: BenchmarkConfig, ids: Mapping[str, Any]
) -> tuple[Callable[[], Any], str]:
    """
    Return a zero-argument callable that issues the request under test.

    Everything that can be computed once — the client, the URL, the resolved
    parameters — is computed here, so the timed section contains the request
    and nothing else.
    """
    context = ResolutionContext(knobs=config.knobs, ids=exports_of(ids))
    client = build_client(config, ids)
    url = resolve_url(config, ids)
    params = resolve(dict(config.target.params), context)
    data = resolve(dict(config.target.data), context) if config.target.data else None
    headers = {str(k): str(v) for k, v in config.target.headers.items()}
    method = getattr(client, config.target.method, None)
    if method is None:
        msg = f"[target].method = {config.target.method!r} is not supported"
        raise MeasurementError(msg)
    expected = config.target.expect_status

    # A body-carrying method has no second slot for the query string, so the
    # parameters go onto the URL instead of being silently dropped.
    if data is not None and params:
        url = f"{url}?{urlencode(params, doseq=True)}"
    payload = data if data is not None else params
    # Only pass headers when there are some: an empty mapping is not a
    # universally accepted keyword across client versions.
    extra = {"headers": headers} if headers else {}

    def call() -> Any:
        response = method(url, payload, **extra)
        if response.status_code != expected:
            body = bytes(response.content)[:400]
            msg = (
                f"{config.target.method.upper()} {url}: expected "
                f"{expected}, got {response.status_code}: {body!r}"
            )
            raise MeasurementError(msg)
        return response

    return call, url


def _body_of(response: Any) -> dict[str, Any]:
    try:
        body = response.json()
    except (ValueError, AttributeError):
        return {}
    return body if isinstance(body, dict) else {"results": body}


def _equivalence(config: BenchmarkConfig, response: Any) -> dict[str, Any]:
    """
    Fields that must match between arms, or the comparison means nothing.

    Nested collection lengths are included because a serializer change can
    keep the row count identical while quietly dropping what is inside each
    row — a saving that is really a regression.
    """
    body = _body_of(response)
    results = body.get(config.target.results_key) or []
    fields: dict[str, Any] = {
        "response_bytes": len(response.content),
        "count": body.get(config.target.count_key),
        "results": len(results) if isinstance(results, list) else None,
    }
    for key in config.target.nested_keys:
        fields[f"nested.{key}"] = sum(
            len(row.get(key) or []) for row in results if isinstance(row, dict)
        )
    return fields


def run_bench(
    config: BenchmarkConfig,
    ids: Mapping[str, Any],
    label: str = "unknown",
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Time the endpoint and return the ``BENCH_RESULT`` payload."""
    from django.db import connection  # noqa: PLC0415
    from django.test.utils import CaptureQueriesContext  # noqa: PLC0415

    preconditions = enforce_preconditions(config, strict=strict)
    call, url = build_caller(config, ids)

    # Warm-up absorbs content-type caches, first-call imports and any lazily
    # built per-process state, none of which a production request pays.
    for _ in range(config.measure.warmup):
        call()

    timings: list[float] = []
    for _ in range(config.measure.iterations):
        start = time.perf_counter()
        call()
        timings.append((time.perf_counter() - start) * 1000)

    # Separate pass: see the module docstring. These numbers are attribution,
    # not the headline.
    with CaptureQueriesContext(connection) as captured:
        capture_response = call()
    sql_ms = sum(float(query["time"]) for query in captured.captured_queries) * 1000

    return {
        "label": label,
        "url": url,
        "iterations": config.measure.iterations,
        "warmup": config.measure.warmup,
        "total_ms_min": round(min(timings), 2),
        "total_ms_median": round(statistics.median(timings), 2),
        "total_ms_max": round(max(timings), 2),
        "total_ms_stdev": round(statistics.pstdev(timings), 2),
        "queries": len(captured.captured_queries),
        "sql_ms_capture_pass": round(sql_ms, 2),
        # Row fetch, model instantiation and serialization: what over-fetching
        # actually costs, as distinct from what the database spent.
        "python_ms_est": round(min(timings) - sql_ms, 2),
        **_equivalence(config, capture_response),
        "knobs": dict(config.knobs),
        "seed": {
            "counts": dict(ids.get("counts", {})),
            "m2m_pairs": dict(ids.get("m2m_pairs", {})),
        },
        "preconditions": preconditions.as_dict(),
        "timings_ms": [round(value, 3) for value in timings],
    }
