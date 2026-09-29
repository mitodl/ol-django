"""
The trace pass: where the time actually goes.

This captures OpenTelemetry spans in-process and reports, for every database
span, both its own duration and **the gap until the next one**. The gap is the
point of the exercise: a database span wraps ``cursor.execute`` and nothing
else, so row fetch, model instantiation and serialization all land in the gaps
between spans. A trace that reports only span durations will tell you the
queries are fast while the request is slow.

Instrumentation is not free, and it is normally inert in an application with no
OTLP endpoint configured — which is exactly what keeps the wall-clock pass
clean. The numbers here are therefore for **attribution**, not for the
headline. Quoting a traced total as the benchmark result overstates both arms.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from mitol.benchmark.django_env import enforce_preconditions
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

    from mitol.benchmark.config import BenchmarkConfig

log = logging.getLogger(__name__)

# Instrumentors worth having for an endpoint benchmark, in the order they are
# tried. The psycopg2 variant is last because a project on psycopg 3 has both
# importable surprisingly often.
_INSTRUMENTORS = (
    ("django", "opentelemetry.instrumentation.django", "DjangoInstrumentor"),
    ("psycopg", "opentelemetry.instrumentation.psycopg", "PsycopgInstrumentor"),
    ("psycopg2", "opentelemetry.instrumentation.psycopg2", "Psycopg2Instrumentor"),
)


def install_exporter() -> InMemorySpanExporter:
    """
    Attach an in-memory exporter to the active tracer provider.

    An application that already configured OpenTelemetry (mitol-observability
    does) keeps its provider and gains one more span processor, so the trace
    the benchmark sees is the same one production would emit.
    """
    exporter = InMemorySpanExporter()
    provider = otel_trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        provider = TracerProvider()
        otel_trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def add_otlp_exporter(endpoint: str) -> bool:
    """Additionally ship spans to a real collector. Returns whether it worked."""
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # noqa: PLC0415
    except ImportError:
        log.warning("[trace].otlp_endpoint is set but no OTLP exporter is installed")
        return False
    provider = otel_trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        return False
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    return True


def instrument() -> list[str]:
    """
    Apply the available instrumentors and return the names that took effect.

    This must happen before the first request: the Django instrumentor inserts
    middleware, and a request handler caches its middleware chain on first use.
    """
    applied = []
    for name, module_path, class_name in _INSTRUMENTORS:
        try:
            module = __import__(module_path, fromlist=[class_name])
        except ImportError:
            continue
        try:
            getattr(module, class_name)().instrument(skip_dep_check=True)
        except Exception:  # an instrumentor must never end the run
            log.warning("could not apply the %s instrumentor", name, exc_info=True)
            continue
        applied.append(name)
    return applied


def span_rows(spans: Any) -> list[dict[str, Any]]:
    """Turn finished spans into sorted rows, keeping the SQL where present."""
    rows = [
        {
            "name": span.name,
            "start": span.start_time,
            "end": span.end_time,
            "dur_ms": round((span.end_time - span.start_time) / 1e6, 3),
            "sql": (dict(span.attributes or {}).get("db.statement") or "")[:4000],
        }
        for span in spans
        if span.start_time is not None and span.end_time is not None
    ]
    return sorted(rows, key=lambda row: row["start"])


def annotate_gaps(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Attach the gap after each database span, and the request's wall time.

    The gap is the point of the exercise. A database span wraps
    ``cursor.execute`` only, so row fetch, model instantiation and
    serialization all fall between spans; the last span's gap runs to the end
    of the request.
    """
    if not rows:
        return {"wall_ms": 0.0, "db": []}
    request_end = max(row["end"] for row in rows)
    database = [row for row in rows if row["sql"]]
    for position, row in enumerate(database):
        following = (
            database[position + 1]["start"]
            if position + 1 < len(database)
            else request_end
        )
        row["gap_ms"] = round((following - row["end"]) / 1e6, 3)
    start = database[0]["start"] if database else rows[0]["start"]
    return {"wall_ms": round((request_end - start) / 1e6, 2), "db": database}


def run_trace(
    config: BenchmarkConfig,
    shape: Mapping[str, Any],
    label: str = "unknown",
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Capture ``[measure].trace_repeats`` traced requests and return them."""
    preconditions = enforce_preconditions(config, strict=strict)
    exporter = install_exporter()
    instrumented = instrument()
    otlp = bool(
        config.trace.otlp_endpoint and add_otlp_exporter(config.trace.otlp_endpoint)
    )

    from django.db import connection  # noqa: PLC0415

    # Reconnect, so the connection in use is one the instrumented driver made.
    connection.close()

    # Imported here so the instrumentors above are in place first.
    from mitol.benchmark.measure import build_caller  # noqa: PLC0415

    call, url = build_caller(config, shape)
    for _ in range(min(config.measure.warmup, 3)):
        call()

    runs = []
    response = None
    for _ in range(config.measure.trace_repeats):
        exporter.clear()
        response = call()
        runs.append(annotate_gaps(span_rows(exporter.get_finished_spans())))

    warnings = []
    if not any(run["db"] for run in runs):
        warnings.append(
            "no database spans were captured; install the psycopg (or psycopg2) "
            "OpenTelemetry instrumentation to get per-query attribution"
        )

    return {
        "label": label,
        "url": url,
        "repeats": config.measure.trace_repeats,
        "instrumented": instrumented,
        "otlp_exported": otlp,
        "response_bytes": len(response.content) if response is not None else 0,
        "preconditions": preconditions.as_dict(),
        "warnings": warnings,
        "runs": runs,
    }
