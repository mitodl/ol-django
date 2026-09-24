"""
Distil production traces into an artifact that is safe to commit.

A raw OTel export cannot go in a repository. ``db.statement`` carries literal
values, ``http.target`` carries query strings, and spans carry user and tenant
identifiers and absolute timestamps. But a production comparison is worthless
if only the person holding the export can run it, so something has to be
committable.

What gets committed is the *aggregate*: a median per logical query, keyed by
the labels the developer already wrote by hand in ``[[trace.classify]]``. The
safety property is structural rather than a scrubbing pass —

    the only free-text field in the baseline is drawn from a closed set that
    is already committed in the same repository.

That is enforced at the one place it can leak. ``aggregate.classify`` falls
back to the first 60 characters of the statement when no pattern matches, so
this module classifies through :func:`safe_classifier`, which substitutes the
literal string ``"unclassified"`` instead. There is no flag to turn that off,
so no code path exists that can put trace-derived text into the file.

The one deliberate exception is the trace ids. A trace id is a pointer rather
than data: it resolves only for someone who already has access to the tracing
backend, which enforces its own authorisation. It is what lets a reviewer open
the exact production request a number came from. It does record *that* a
request existed, so a team unwilling to publish that should drop the field.
"""

from __future__ import annotations

import json
import statistics
from typing import TYPE_CHECKING, Any

from mitol.benchmark.aggregate import classify
from mitol.benchmark.otel import read_requests, routes, row_floor
from mitol.benchmark.tracing import annotate_gaps

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Sequence
    from pathlib import Path

    from mitol.benchmark.config import BenchmarkConfig, Classifier
    from mitol.benchmark.otel import Request

UNCLASSIFIED = "unclassified"

# The complete set of keys a baseline may contain. Serialising through an
# allowlist, rather than deleting fields from something that came out of a
# trace, is the direction that fails safe: a field nobody thought about is
# absent by default instead of present by default.
BASELINE_KEYS = ("trace_ids", "requests", "queries")
QUERY_KEYS = ("query", "per_req", "sql_ms", "gap_ms", "total_ms", "row_floor")


class BaselineError(RuntimeError):
    """A production baseline could not be built or is not safe to write."""


def safe_classifier(sql: str, classifiers: Sequence[Classifier]) -> str:
    """
    Label a production statement, never with the statement itself.

    ``aggregate.classify`` is reused so local and production rows are grouped
    by identical rules, but its SQL fallback is replaced: anything unmatched
    becomes :data:`UNCLASSIFIED`.
    """
    label = classify(sql, classifiers)
    declared = {classifier.label for classifier in classifiers}
    return label if label in declared else UNCLASSIFIED


def _median(values: Sequence[float]) -> float:
    return round(statistics.median(values), 3) if values else 0.0


def build(
    config: BenchmarkConfig, paths: Sequence[Path]
) -> tuple[dict[str, Any], list[str]]:
    """
    Build a baseline from exported traces, and any warnings worth printing.

    Every distinct trace id becomes one request, so the medians improve as
    more traces are supplied, in the same way ``trace_repeats`` works on the
    local side.
    """
    requests = read_requests(paths)
    warnings = _warnings(requests)

    grouped: dict[str, list[dict[str, float]]] = {}
    for request in requests:
        annotated = annotate_gaps(list(request.spans))
        for span in annotated["db"]:
            label = safe_classifier(span.get("sql", ""), config.trace.classify)
            grouped.setdefault(label, []).append(
                {
                    "sql_ms": span.get("dur_ms", 0.0),
                    "gap_ms": span.get("gap_ms", 0.0),
                    "rows": row_floor(span.get("sql", "")),
                }
            )

    if not grouped:
        msg = (
            "no database spans were found in these traces. The export needs "
            "spans carrying a db.statement attribute — check that the "
            "database instrumentation was enabled when they were captured."
        )
        raise BaselineError(msg)

    count = len(requests)
    queries = [_query_row(label, samples, count) for label, samples in grouped.items()]
    baseline = {
        "trace_ids": sorted(request.trace_id for request in requests),
        "requests": count,
        "queries": sorted(queries, key=lambda row: -row["total_ms"]),
    }
    _assert_safe(baseline, config.trace.classify)
    return baseline, warnings


def _query_row(
    label: str, samples: Sequence[dict[str, float]], requests: int
) -> dict[str, Any]:
    sql_ms = _median([sample["sql_ms"] for sample in samples])
    gap_ms = _median([sample["gap_ms"] for sample in samples])
    row = {
        "query": label,
        "per_req": round(len(samples) / max(requests, 1), 1),
        "sql_ms": sql_ms,
        "gap_ms": gap_ms,
        "total_ms": round(sql_ms + gap_ms, 3),
    }
    floor = max(int(sample["rows"]) for sample in samples)
    if floor:
        row["row_floor"] = floor
    return row


def _warnings(requests: Sequence[Request]) -> list[str]:
    warnings = []
    found = routes(requests)
    if len(found) > 1:
        warnings.append(
            f"these traces cover {len(found)} different routes "
            f"({', '.join(found)}). Their queries are being averaged "
            f"together, which is meaningless unless you meant to include "
            f"them all — check what the glob matched."
        )
    if truncated := _missing_root_span(requests):
        warnings.append(
            f"{truncated} of {len(requests)} request(s) contain no span "
            f"outlasting their final query, so the last query's gap reads as "
            f"zero. That gap is where serialization lives and is often the "
            f"largest single cost. Re-export including the server/root span "
            f"rather than filtering to database spans."
        )
    return warnings


def _missing_root_span(requests: Sequence[Request]) -> int:
    """
    Count requests whose export was filtered down to database spans only.

    A gap is measured to the next query, or for the last query to the end of
    the request. With no enclosing span the request "ends" at its own last
    query, so that final gap silently becomes zero rather than absent — a
    wrong number, not a missing one, and it would be committed.
    """
    truncated = 0
    for request in requests:
        database = [span for span in request.spans if span.get("sql")]
        if not database:
            continue
        if max(span["end"] for span in request.spans) <= max(
            span["end"] for span in database
        ):
            truncated += 1
    return truncated


def _assert_safe(baseline: dict[str, Any], classifiers: Sequence[Classifier]) -> None:
    """
    Refuse to hand back anything whose labels are not from the closed set.

    :func:`safe_classifier` already guarantees this. The assertion exists so
    that a future refactor which reintroduces the SQL fallback fails here
    rather than silently writing a statement into a committed file.
    """
    allowed = {classifier.label for classifier in classifiers} | {UNCLASSIFIED}
    leaked = [
        row["query"] for row in baseline["queries"] if row["query"] not in allowed
    ]
    if leaked:
        msg = (
            f"refusing to emit a baseline containing labels that are not "
            f"declared classifiers: {leaked}. This is a bug in the harness, "
            f"not in your configuration."
        )
        raise BaselineError(msg)


def serialize(baseline: dict[str, Any]) -> str:
    """Render the baseline through the key allowlist, ready to be written."""
    payload = {key: baseline[key] for key in BASELINE_KEYS if key in baseline}
    payload["queries"] = [
        {key: row[key] for key in QUERY_KEYS if key in row}
        for row in baseline.get("queries", [])
    ]
    return json.dumps(payload, indent=2) + "\n"


def load(path: Path) -> dict[str, Any]:
    """Read a committed baseline back, keyed by query label for lookup."""
    try:
        document = json.loads(path.read_text())
    except FileNotFoundError as exc:
        msg = (
            f"{path}: no such baseline. Generate one with "
            f"'ol-benchmark baseline <config> <trace>...'"
        )
        raise BaselineError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"{path}: not valid JSON — {exc}"
        raise BaselineError(msg) from exc
    return document


def by_label(baseline: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index a baseline's rows by query label."""
    if not baseline:
        return {}
    return {row["query"]: row for row in baseline.get("queries", [])}
