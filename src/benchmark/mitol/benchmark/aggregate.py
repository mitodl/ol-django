"""
Reduce a set of traced requests to one row per logical query.

A single traced request is far too noisy to attribute a gap to a query, so the
trace pass repeats the request and this module takes the **median** of each
query position across the repeats.

Queries are grouped by a label from ``[[trace.classify]]``, applied in
declaration order, most specific first — a broad pattern placed early will
swallow the ones after it. The ``per_req`` column is the check on that: if a
label shows a non-integer or unexpectedly high count, two different queries are
colliding under one name and their medians are being mixed.
"""

from __future__ import annotations

import re
import statistics
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping, Sequence

    from mitol.benchmark.config import Classifier

# How much of an unclassified statement is used as its label.
_FALLBACK_LABEL_CHARS = 60
_WHITESPACE = re.compile(r"\s+")


def normalize(sql: str) -> str:
    """Collapse whitespace so patterns can be written against one-line SQL."""
    return _WHITESPACE.sub(" ", sql).strip()


def classify(sql: str, classifiers: Sequence[Classifier]) -> str:
    """Return the logical query label for one SQL statement."""
    statement = normalize(sql)
    for classifier in classifiers:
        if re.search(classifier.pattern, statement):
            return classifier.label
    return statement[:_FALLBACK_LABEL_CHARS]


def _median(values: Sequence[float]) -> float:
    return round(statistics.median(values), 3) if values else 0.0


def aggregate(
    trace: Mapping[str, Any], classifiers: Sequence[Classifier]
) -> list[dict[str, Any]]:
    """
    Aggregate a ``TRACE_RESULT`` payload into one row per logical query.

    Rows are sorted by total cost descending, so the first row is where the
    request's time goes.
    """
    runs = trace.get("runs") or []
    repeats = max(len(runs), 1)
    grouped: dict[str, list[tuple[float, float]]] = {}
    for run in runs:
        for span in run.get("db", []):
            label = classify(span.get("sql", ""), classifiers)
            grouped.setdefault(label, []).append(
                (span.get("dur_ms", 0.0), span.get("gap_ms", 0.0))
            )

    rows = []
    for label, samples in grouped.items():
        sql_ms = _median([sample[0] for sample in samples])
        gap_ms = _median([sample[1] for sample in samples])
        rows.append(
            {
                "query": label,
                "per_req": round(len(samples) / repeats, 1),
                "sql_ms": sql_ms,
                "gap_ms": gap_ms,
                "total_ms": round(sql_ms + gap_ms, 3),
            }
        )
    return sorted(rows, key=lambda row: -row["total_ms"])


def collisions(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """
    Report labels whose per-request count suggests the classifier is too broad.

    A logical query that runs a whole number of times per request is normal —
    a prefetch runs once, a paginator count runs once. A fractional count means
    the label is catching statements that are not the same query.
    """
    return [str(row["query"]) for row in rows if row["per_req"] != int(row["per_req"])]
