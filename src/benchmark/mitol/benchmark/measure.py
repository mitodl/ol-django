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

*Both arms must have returned something.* Two arms that each serialize an empty
page agree perfectly, so the equivalence check passes, the timings are real,
and the number describes nothing. An empty collection is refused before the
timed loop rather than compared between arms, because it is not a property of
the change under test — it means the request was not the one intended. The
usual cause is authorization failing open: a filterset that returns an empty
queryset for a caller without the right membership renders as a 200 carrying no
rows, not as a 403, so ``expect_status`` is satisfied and nothing downstream
notices.
"""

from __future__ import annotations

import statistics
import time
from typing import TYPE_CHECKING, Any

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
    method = getattr(client, config.target.method, None)
    if method is None:
        msg = f"[target].method = {config.target.method!r} is not supported"
        raise MeasurementError(msg)
    expected = config.target.expect_status

    def call() -> Any:
        response = method(url, params)
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
        fields[f"nested.{key}"] = _nested_total(results, key)
    return fields


def _nested_total(results: Any, key: str) -> int:
    """Total the lengths of one nested collection across every result row."""
    return sum(len(row.get(key) or []) for row in results if isinstance(row, dict))


def _empty_reason(config: BenchmarkConfig, response: Any) -> str | None:
    """
    Return why this response has nothing to measure, or ``None`` if it has.

    Only collections the configuration actually names are judged. A detail
    endpoint has no ``results`` key at all, and a body that is not JSON cannot
    be read this way — in neither case is anything missing, so neither is
    refused.
    """
    body = _body_of(response)
    results_key = config.target.results_key
    if results_key not in body:
        return None
    results = body.get(results_key)
    if not isinstance(results, list):
        return None
    if not results:
        count = body.get(config.target.count_key)
        return f"the response carried no {results_key!r}" + (
            f" (and {config.target.count_key} = {count})" if count == 0 else ""
        )

    # A nested collection is declared in `nested_keys` because the author
    # considers what is inside each row material to the change. Zero of them
    # across every row is the same failure one level down: the rows are there,
    # but the thing being measured is not.
    for key in config.target.nested_keys:
        if _nested_total(results, key) == 0:
            return (
                f"every row came back with an empty {key!r}, which "
                f"[target].nested_keys declares as material to this benchmark"
            )
    return None


def refuse_empty_response(
    config: BenchmarkConfig,
    response: Any,
    opening: str = "refusing to time an empty response",
    consequence: str = (
        "Both arms would agree and the timings would be real, so nothing "
        "downstream can tell you the number meant nothing."
    ),
) -> None:
    """
    Raise unless the response has something in it to measure.

    The opening clause and the consequence are arguments because the retention
    pass shares this check, and it times nothing and compares nothing — but the
    fault it is guarding against, and the two things worth checking when it
    fires, are identical.
    """
    if config.target.allow_empty:
        return
    reason = _empty_reason(config, response)
    if reason is None:
        return
    msg = (
        f"{opening}: {reason}.\n"
        f"{consequence}\n"
        f"Check the seed produced rows, and that [auth] names a user the "
        f"endpoint's filtering accepts — a caller without the right "
        f"membership is usually answered with an empty 200, not a 403.\n"
        f"Set [target].allow_empty = true if an empty response is genuinely "
        f"what this benchmark measures."
    )
    raise MeasurementError(msg)


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

    # Before the timed loop, not after it: an empty response is a setup fault,
    # and the run should say so immediately rather than at the end of an
    # iteration count someone chose to be slow. This call doubles as warm-up.
    refuse_empty_response(config, call())

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
        "total_ms_stdev": (
            round(statistics.stdev(timings), 2) if len(timings) > 1 else 0.0
        ),
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
