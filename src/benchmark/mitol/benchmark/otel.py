"""
Read an exported OpenTelemetry trace into the shape the harness already uses.

This is the production side of the comparison. A trace exported from a
collector is the only artifact that says what an endpoint really costs under
real data, real concurrency and a real network, and the only one that can
falsify a seed.

The output of this module is deliberately the *same* per-span dict that
:mod:`mitol.benchmark.tracing` produces locally — ``{name, start, end, dur_ms,
sql}`` — so that gap annotation, classification and aggregation are literally
the same code on both sides. A production number and a local number that were
computed by different paths would not be comparable.

Nothing here is written anywhere. Everything read from a trace stays in
memory; see :mod:`mitol.benchmark.baseline` for what is allowed to reach disk.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable, Sequence
    from pathlib import Path

# Placeholders a driver leaves in a parameterised statement. Counting them is
# how a prefetch's IN-list gives a floor on the rows production loaded.
_PLACEHOLDER = re.compile(r"%s|\$\d+")

# Attributes read from a span. Everything else in an export is ignored rather
# than carried around, so there is less to accidentally serialise later.
_SQL_KEYS = ("db.statement", "db.query.text")
_ROUTE_KEYS = ("http.route", "http.target", "url.path")


class TraceReadError(ValueError):
    """An exported trace could not be read in any recognised shape."""


@dataclass
class Request:
    """One traced request: its id, its route, and its spans in time order."""

    trace_id: str
    route: str = ""
    spans: list[dict[str, Any]] = field(default_factory=list)


def _attribute_value(value: Any) -> Any:
    """
    Unwrap an OTLP JSON typed value.

    Attributes are encoded as ``{"stringValue": "..."}`` and friends in the
    protobuf JSON mapping, but a few exporters flatten them already.
    """
    if not isinstance(value, dict):
        return value
    for key in (
        "stringValue",
        "intValue",
        "doubleValue",
        "boolValue",
    ):
        if key in value:
            return value[key]
    return value.get("value", value)


def _attributes(span: dict[str, Any]) -> dict[str, Any]:
    raw = span.get("attributes") or []
    if isinstance(raw, dict):
        return {key: _attribute_value(value) for key, value in raw.items()}
    return {
        entry.get("key"): _attribute_value(entry.get("value"))
        for entry in raw
        if isinstance(entry, dict) and entry.get("key")
    }


def _first(attributes: dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = attributes.get(key)
        if value:
            return str(value)
    return ""


def _nanos(value: Any) -> int | None:
    """Return a span timestamp in nanoseconds, however the export wrote it."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def iter_spans(document: Any) -> Iterable[dict[str, Any]]:
    """
    Yield every span in an export, whichever of the two layouts it uses.

    ``resourceSpans[].scopeSpans[].spans[]`` is what current collectors emit;
    ``batches[].instrumentationLibrarySpans[].spans[]`` is the older OTLP JSON
    mapping. Both appear in exports people actually have, and a single
    invocation may be given a mixture of the two.
    """
    if isinstance(document, list):
        for entry in document:
            yield from iter_spans(entry)
        return
    if not isinstance(document, dict):
        return

    groups = document.get("resourceSpans") or document.get("batches") or []
    for group in groups:
        scopes = (group.get("scopeSpans") or []) + (
            group.get("instrumentationLibrarySpans") or []
        )
        for scope in scopes:
            for span in scope.get("spans") or []:
                if isinstance(span, dict):
                    yield span


def read_requests(paths: Sequence[Path]) -> list[Request]:
    """
    Read every file into one request per distinct trace id.

    Grouping happens across files, not within them, so it does not matter how
    an export was split up — and a trace that appears in two files is one
    request, not two.
    """
    requests: dict[str, Request] = {}
    for path in paths:
        try:
            document = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            msg = f"{path}: not valid JSON — {exc}"
            raise TraceReadError(msg) from exc

        found = False
        for span in iter_spans(document):
            found = True
            _collect_span(span, requests)
        if not found:
            msg = (
                f"{path}: no spans found. Expected an OTLP JSON export with "
                f"either 'resourceSpans' or 'batches' at the top level."
            )
            raise TraceReadError(msg)

    if not requests:
        msg = "no spans with usable timestamps were found in any trace"
        raise TraceReadError(msg)

    for request in requests.values():
        request.spans.sort(key=lambda row: row["start"])
    return [requests[key] for key in sorted(requests)]


def _collect_span(span: dict[str, Any], requests: dict[str, Request]) -> None:
    start = _nanos(span.get("startTimeUnixNano"))
    end = _nanos(span.get("endTimeUnixNano"))
    if start is None or end is None:
        return

    trace_id = str(span.get("traceId") or span.get("trace_id") or "unknown")
    attributes = _attributes(span)
    request = requests.setdefault(trace_id, Request(trace_id=trace_id))

    route = _first(attributes, _ROUTE_KEYS)
    if route and not request.route:
        # Keep only the path; a query string can carry identifiers and this is
        # used for a warning, never written anywhere.
        request.route = route.split("?")[0]

    request.spans.append(
        {
            "name": span.get("name", ""),
            "start": start,
            "end": end,
            "dur_ms": round((end - start) / 1e6, 3),
            "sql": _first(attributes, _SQL_KEYS),
        }
    )


def row_floor(statement: str) -> int:
    """
    Return the rows a statement provably touched, from its placeholder count.

    A prefetch's ``IN (%s, %s, ...)`` list is the one row count a trace states
    outright. Exporters commonly truncate ``db.statement``, so a count taken
    at the truncation point is a floor rather than a total — which is why the
    field it feeds is named for a floor.
    """
    return len(_PLACEHOLDER.findall(statement))


def routes(requests: Sequence[Request]) -> list[str]:
    """Return the distinct routes the requests covered, for the mixing check."""
    return sorted({request.route for request in requests if request.route})
