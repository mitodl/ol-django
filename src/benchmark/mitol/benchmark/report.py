"""
Turn two arms into a verdict, and a verdict into something a reviewer can read.

Three things have to be checked before any delta may be quoted, and this module
refuses to produce a headline number until they are:

1. **Both arms did the same work.** If response bytes or item counts differ,
   the comparison is *void* — whatever was measured, it was not one change.
2. **The delta exceeds the run-to-run spread.** If min and median disagree
   about which arm is faster, or the difference is inside the noise, the
   result is *inconclusive*, which is a real answer and not a failure.
3. **The saving is where the change aims.** Per-query attribution is part of
   the output, not an optional extra, so a reviewer can see that nothing else
   regressed to pay for it.

What is measured locally is also a **floor**, never an estimate of production:
there is no network round-trip, the cache is warm and nothing else is
contending for the database. All three penalise larger result sets
disproportionately in production, so the real saving is usually larger — but
that is an argument, not a measurement, and the report says so rather than
scaling the number.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mitol.benchmark.aggregate import aggregate, collisions
from mitol.benchmark.baseline import by_label
from mitol.benchmark.baseline import load as load_baseline

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping, Sequence

    from mitol.benchmark.config import BenchmarkConfig

VERDICT_OK = "ok"
VERDICT_VOID = "void"
VERDICT_INCONCLUSIVE = "inconclusive"

EQUIVALENCE_PREFIXES = ("response_bytes", "count", "results", "nested.")
_HEADLINE_METRICS = (
    "total_ms_min",
    "total_ms_median",
    "total_ms_max",
    "total_ms_stdev",
    "sql_ms_capture_pass",
    "python_ms_est",
    "queries",
    "response_bytes",
    "count",
    "results",
)


def _equivalence_keys(arm: Mapping[str, Any]) -> list[str]:
    return [key for key in arm if key.startswith(EQUIVALENCE_PREFIXES)]


def equivalence_mismatches(
    base: Mapping[str, Any], branch: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Return the fields on which the two arms disagree about what they did."""
    keys = sorted(set(_equivalence_keys(base)) | set(_equivalence_keys(branch)))
    return [
        {"field": key, "base": base.get(key), "branch": branch.get(key)}
        for key in keys
        if base.get(key) != branch.get(key)
    ]


def _delta(base: Any, branch: Any) -> Any:
    if isinstance(base, (int, float)) and isinstance(branch, (int, float)):
        return round(branch - base, 3)
    return None


def _spread(arm: Mapping[str, Any]) -> float:
    """
    How much this arm varies from call to call, robustly.

    Median minus min, not max minus min: a single scheduling or garbage
    collection outlier is routine even after a warm-up, and letting one of
    them set the noise floor would make every result inconclusive. The
    distance from an arm's best call to its typical one is variability that
    actually recurs.
    """
    return float(arm.get("total_ms_median", 0)) - float(arm.get("total_ms_min", 0))


def decide(
    base: Mapping[str, Any], branch: Mapping[str, Any], mismatches: Sequence[Any]
) -> tuple[str, str]:
    """Return the verdict and the sentence explaining it."""
    if mismatches:
        fields = ", ".join(str(item["field"]) for item in mismatches)
        return VERDICT_VOID, (
            f"the arms returned different responses ({fields}); they did not do "
            f"the same work, so no delta may be quoted"
        )
    median_delta = _delta(base["total_ms_median"], branch["total_ms_median"]) or 0.0
    min_delta = _delta(base["total_ms_min"], branch["total_ms_min"]) or 0.0
    noise = max(_spread(base), _spread(branch))
    if abs(median_delta) <= noise:
        return VERDICT_INCONCLUSIVE, (
            f"the median difference ({median_delta:+.2f} ms) is within the "
            f"call-to-call variability of a single arm ({noise:.2f} ms between "
            f"its best and typical call)"
        )
    if (median_delta < 0) != (min_delta < 0):
        return VERDICT_INCONCLUSIVE, (
            f"min ({min_delta:+.2f} ms) and median ({median_delta:+.2f} ms) "
            f"disagree about which arm is faster"
        )
    direction = "faster" if median_delta < 0 else "slower"
    return VERDICT_OK, (
        f"the branch is {abs(median_delta):.2f} ms {direction} at the median, "
        f"outside the {noise:.2f} ms call-to-call variability of a single arm"
    )


def _per_query(
    base_rows: Sequence[Mapping[str, Any]],
    branch_rows: Sequence[Mapping[str, Any]],
    production: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_label_base = {row["query"]: row for row in base_rows}
    by_label_branch = {row["query"]: row for row in branch_rows}
    empty = {"sql_ms": 0.0, "gap_ms": 0.0, "total_ms": 0.0, "per_req": 0.0}
    rows = []
    labels = set(by_label_base) | set(by_label_branch) | set(production)
    for label in sorted(labels):
        left = by_label_base.get(label, empty)
        right = by_label_branch.get(label, empty)
        # None rather than zero where production has no such row: a query the
        # baseline never saw is unknown, not free.
        prod = production.get(label)
        rows.append(
            {
                "query": label,
                "production_sql_ms": prod["sql_ms"] if prod else None,
                "production_gap_ms": prod["gap_ms"] if prod else None,
                "production_total_ms": prod["total_ms"] if prod else None,
                "base_sql_ms": left["sql_ms"],
                "base_gap_ms": left["gap_ms"],
                "base_total_ms": left["total_ms"],
                "branch_sql_ms": right["sql_ms"],
                "branch_gap_ms": right["gap_ms"],
                "branch_total_ms": right["total_ms"],
                "delta_ms": round(right["total_ms"] - left["total_ms"], 3),
                "base_per_req": left["per_req"],
                "branch_per_req": right["per_req"],
            }
        )
    return sorted(rows, key=lambda row: row["delta_ms"])


def _drift(
    config: BenchmarkConfig, rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """
    Flag queries the change does not touch that do not look like production.

    This is the falsification check: a seed parameter that makes an
    *unchanged* query wildly slower than production is wrong, however good
    the story behind it was. A targeted query is excluded, because it is
    supposed to differ — that is the whole point of the change.

    Direction matters and is reported. Local faster than production is
    expected: no network round-trip, a warm cache, no contention. Local
    *slower* is the signal that the seed is the wrong shape.
    """
    targeted = {
        classifier.label for classifier in config.trace.classify if classifier.targeted
    }
    factor = config.calibration.drift_factor
    drifted = []
    for row in rows:
        production = row["production_total_ms"]
        local = row["base_total_ms"]
        if row["query"] in targeted or not production or not local:
            continue
        ratio = max(production, local) / min(production, local)
        if ratio <= factor:
            continue
        slower = local > production
        drifted.append(
            {
                "query": row["query"],
                "production_total_ms": production,
                "local_total_ms": local,
                "ratio": round(ratio, 1),
                "local_slower": slower,
                "note": (
                    "the seed makes an unchanged query slower than production; "
                    "this shape is falsified, not merely imprecise"
                    if slower
                    else "local is faster than production, which is expected "
                    "here, but this far apart suggests the seed understates "
                    "the real fan-out"
                ),
            }
        )
    return sorted(drifted, key=lambda row: -row["ratio"])


def _calibration(
    config: BenchmarkConfig, shape: Mapping[str, Any], arm: Mapping[str, Any]
) -> list[dict[str, Any]]:
    counts = shape.get("counts", {})
    rows = []
    for observable in config.calibration.observables:
        row = {
            "observable": observable.name,
            "source": observable.source,
            "production": observable.production,
            "seed": counts.get(observable.seed_step or observable.name),
            "measured": arm.get(observable.response) if observable.response else None,
            "off_by": None,
            "note": observable.note,
        }
        row["off_by"] = _relative_gap(row["production"], row["measured"])
        rows.append(row)
    return rows


def _relative_gap(production: Any, measured: Any) -> float | None:
    """
    Return |measured - production| / production, or ``None`` if not comparable.

    Non-numeric observables are common and legitimate — "one run per course",
    a prose note about tenancy — so anything that is not a pair of numbers is
    simply not scored rather than being treated as a failure.
    """
    if isinstance(production, bool) or isinstance(measured, bool):
        return None
    if not isinstance(production, (int, float)) or not isinstance(
        measured, (int, float)
    ):
        return None
    if production == 0:
        return None
    return round(abs(measured - production) / abs(production), 3)


def _calibration_mismatches(
    config: BenchmarkConfig, rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    """
    Observables whose measured response is too far from the production value.

    This is the check that catches a seed which built the right number of rows
    and still produces a response a fraction of production's size — the counts
    all agree, and only the payload says otherwise. Like drift, it questions
    the seed and never the verdict: the two arms remain comparable to each
    other whether or not either resembles production.
    """
    tolerances = {
        observable.name: observable.tolerance
        for observable in config.calibration.observables
    }
    return [
        {
            **row,
            "tolerance": tolerances.get(row["observable"], 0.25),
            "note": (
                f"the response is {row['off_by']:.0%} away from the production "
                f"value; the seed does not reproduce what this endpoint returns "
                f"in production, so per-query numbers describe a different shape"
            ),
        }
        for row in rows
        if row.get("off_by") is not None
        and row["off_by"] > tolerances.get(row["observable"], 0.25)
    ]


def compare(
    config: BenchmarkConfig,
    base: Mapping[str, Any],
    branch: Mapping[str, Any],
    *,
    traces: Mapping[str, Mapping[str, Any]] | None = None,
    shape: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the comparison payload: the primary machine-readable artifact.

    ``traces`` maps arm name to that arm's ``TRACE_RESULT`` payload; without it
    the comparison still reports wall clock, but with no attribution.
    """
    shape = shape or {}
    base_trace = (traces or {}).get("base") or {}
    branch_trace = (traces or {}).get("branch") or {}
    mismatches = equivalence_mismatches(base, branch)
    verdict, reason = decide(base, branch, mismatches)
    base_rows = aggregate(base_trace, config.trace.classify)
    branch_rows = aggregate(branch_trace, config.trace.classify)
    baseline_path = config.calibration.baseline
    baseline = load_baseline(baseline_path) if baseline_path else None
    per_query = _per_query(base_rows, branch_rows, by_label(baseline))
    calibration = _calibration(config, shape, branch)

    return {
        "benchmark": config.name,
        "description": config.description,
        "verdict": verdict,
        "reason": reason,
        "refs": {"base": base.get("ref"), "branch": branch.get("ref")},
        "equivalence_mismatches": mismatches,
        "metrics": [
            {
                "metric": metric,
                "base": base.get(metric),
                "branch": branch.get(metric),
                "delta": _delta(base.get(metric), branch.get(metric)),
            }
            for metric in _HEADLINE_METRICS
        ],
        "per_query": per_query,
        # Drift is a warning about the seed, never a change to the verdict:
        # the verdict is about whether the two arms are comparable to each
        # other, drift is about whether either resembles production.
        "calibration_drift": _drift(config, per_query),
        # Measured against the branch arm: both arms are held to the same
        # equivalence fields, so either would do, and the branch is the one
        # whose shape a reader is about to draw conclusions from.
        "calibration_mismatches": _calibration_mismatches(config, calibration),
        "production": {
            "requests": (baseline or {}).get("requests"),
            "trace_ids": (baseline or {}).get("trace_ids", []),
        },
        "classifier_collisions": sorted(
            set(collisions(base_rows)) | set(collisions(branch_rows))
        ),
        "shape": {
            "knobs": dict(config.knobs),
            "counts": shape.get("counts", {}),
            "m2m_pairs": shape.get("m2m_pairs", {}),
            "warnings": shape.get("warnings", []),
        },
        "calibration": calibration,
        "preconditions": {
            "base": base.get("preconditions", {}),
            "branch": branch.get("preconditions", {}),
        },
        "trace_warnings": sorted(
            set(base_trace.get("warnings", [])) | set(branch_trace.get("warnings", []))
        ),
        "caveat": (
            "Local Postgres has no network round-trip, a warm cache and no "
            "contention. Production has all three, and they penalise larger "
            "result sets disproportionately. This is a floor, not an estimate."
        ),
    }


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> list[str]:
    if not rows:
        return ["_(nothing to show)_", ""]
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join("" if cell is None else str(cell) for cell in row) + " |"
        for row in rows
    )
    lines.append("")
    return lines


_VERDICT_HEADLINE = {
    VERDICT_VOID: "VOID — do not quote a delta",
    VERDICT_INCONCLUSIVE: "INCONCLUSIVE",
    VERDICT_OK: "OK",
}


def _render_drift(comparison: Mapping[str, Any]) -> list[str]:
    """Render the seed-drift section, or nothing when the seed looks right."""
    drifted = comparison.get("calibration_drift")
    if not drifted:
        return []
    return [
        "## Seed drift from production",
        "",
        "These queries are **not** the target of the change, so they should "
        "look like production. They do not, which puts the seed shape in "
        "question rather than the result.",
        "",
        *_table(
            ["query", "production", "local", "ratio", "reading"],
            [
                [
                    row["query"],
                    row["production_total_ms"],
                    row["local_total_ms"],
                    f"{row['ratio']}x",
                    row["note"],
                ]
                for row in drifted
            ],
        ),
    ]


def _render_calibration_mismatches(comparison: Mapping[str, Any]) -> list[str]:
    """Render response observables that missed production, or nothing."""
    missed = comparison.get("calibration_mismatches")
    if not missed:
        return []
    return [
        "## The response does not look like production",
        "",
        "The seed built its rows, but what the endpoint returned is a "
        "different size from the production sample it was calibrated against. "
        "Row counts agreeing is not the same as the payload agreeing, and the "
        "per-query numbers below describe whatever shape this actually is.",
        "",
        *_table(
            ["observable", "production", "measured", "off by", "tolerance"],
            [
                [
                    row["observable"],
                    row["production"],
                    row["measured"],
                    f"{row['off_by']:.0%}",
                    f"{row['tolerance']:.0%}",
                ]
                for row in missed
            ],
        ),
    ]


def _render_provenance(production: Mapping[str, Any]) -> list[str]:
    """Render the trace ids the production baseline was distilled from."""
    trace_ids = production.get("trace_ids")
    if not trace_ids:
        return []
    return [
        "## Production baseline",
        "",
        f"Distilled from {production.get('requests')} request(s):",
        "",
        *[f"- `{trace_id}`" for trace_id in trace_ids],
        "",
    ]


def render_markdown(comparison: Mapping[str, Any]) -> str:
    """Render the comparison payload as a report a reviewer can read."""
    lines: list[str] = [
        f"# Benchmark: {comparison['benchmark']}",
        "",
    ]
    if comparison.get("description"):
        lines += [comparison["description"], ""]
    verdict = comparison["verdict"]
    lines += [
        f"**{_VERDICT_HEADLINE.get(verdict, verdict.upper())}** — "
        f"{comparison['reason']}",
        "",
        f"Arms: base `{comparison['refs'].get('base')}` vs "
        f"branch `{comparison['refs'].get('branch')}`",
        "",
    ]

    if comparison["equivalence_mismatches"]:
        lines += ["## The arms disagree", ""]
        lines += _table(
            ["field", "base", "branch"],
            [
                [item["field"], item["base"], item["branch"]]
                for item in comparison["equivalence_mismatches"]
            ],
        )

    lines += ["## Wall clock", ""]
    lines += _table(
        ["metric", "base", "branch", "delta"],
        [
            [row["metric"], row["base"], row["branch"], row["delta"]]
            for row in comparison["metrics"]
        ],
    )

    lines += ["## Per-query attribution (median of traced repeats)", ""]
    production = comparison.get("production", {})
    if production.get("requests"):
        lines += [
            f"The `prod tot` column is the median across "
            f"{production['requests']} production request(s). Local is "
            f"expected to be faster — no round-trip, warm cache, no "
            f"contention.",
            "",
        ]
    lines += _table(
        [
            "query",
            "prod tot",
            "base sql",
            "base gap",
            "base tot",
            "br sql",
            "br gap",
            "br tot",
            "delta",
        ],
        [
            [
                row["query"],
                row.get("production_total_ms"),
                row["base_sql_ms"],
                row["base_gap_ms"],
                row["base_total_ms"],
                row["branch_sql_ms"],
                row["branch_gap_ms"],
                row["branch_total_ms"],
                row["delta_ms"],
            ]
            for row in comparison["per_query"]
        ],
    )

    lines += _render_drift(comparison)
    if comparison["classifier_collisions"]:
        collided = ", ".join(comparison["classifier_collisions"])
        lines += [
            f"> Classifier collision on: {collided}. These labels matched a "
            f"non-whole number of statements per request, so they are mixing "
            f"two different queries. Tighten the `[[trace.classify]]` patterns.",
            "",
        ]

    shape = comparison["shape"]
    lines += ["## Shape measured", ""]
    lines += _table(
        ["knob", "value"], [[key, value] for key, value in shape["knobs"].items()]
    )
    lines += _table(
        ["step", "rows"], [[key, value] for key, value in shape["counts"].items()]
    )
    if shape["m2m_pairs"]:
        lines += _table(
            ["relation", "pairs"],
            [[key, value] for key, value in shape["m2m_pairs"].items()],
        )
    for warning in shape["warnings"]:
        lines += [f"> {warning}", ""]

    lines += _render_calibration_mismatches(comparison)

    if comparison["calibration"]:
        lines += ["## Calibration against production", ""]
        lines += _table(
            ["observable", "source", "production", "seed", "measured", "note"],
            [
                [
                    row["observable"],
                    row["source"],
                    row["production"],
                    row["seed"],
                    "—" if row["measured"] is None else row["measured"],
                    row["note"],
                ]
                for row in comparison["calibration"]
            ],
        )

    lines += _render_provenance(production)

    lines += ["## Conditions", ""]
    conditions = comparison["preconditions"]
    keys = sorted(set(conditions.get("base", {})) | set(conditions.get("branch", {})))
    lines += _table(
        ["condition", "base", "branch"],
        [
            [
                key,
                conditions.get("base", {}).get(key),
                conditions.get("branch", {}).get(key),
            ]
            for key in keys
        ],
    )
    for warning in comparison["trace_warnings"]:
        lines += [f"> {warning}", ""]
    lines += [comparison["caveat"], ""]
    return "\n".join(lines)


_MEMORY_HEADLINE = {
    "retaining": "RETAINED",
    "high-water": "HIGH-WATER",
    "stable": "STABLE",
}


def render_memory_markdown(result: Mapping[str, Any]) -> str:
    """
    Render the retention pass as a report a reviewer can read.

    Deliberately leads with the verdict and the two per-request numbers,
    because everything after them is only worth reading if those say there is
    something to chase.
    """
    verdict = result["verdict"]
    lines: list[str] = [
        f"# Retention: {result['url']}",
        "",
        f"**{_MEMORY_HEADLINE.get(verdict, verdict.upper())}** — {result['reason']}",
        "",
        *_table(
            ["", "baseline", "final", "per request"],
            [
                [
                    "RSS (MiB)",
                    result["baseline_rss_mib"],
                    result["final_rss_mib"],
                    f"{result['mib_per_request']:+}",
                ],
                [
                    "live objects",
                    result["baseline_objects"],
                    result["final_objects"],
                    f"{result['objects_per_request']:+}",
                ],
            ],
        ),
        f"Over {result['requests']} requests, after a forced collection. "
        f"Live objects are counted after collecting, so growth there is "
        f"reachable rather than merely uncollected — that is what separates "
        f"retention from an allocator holding freed arenas.",
        "",
    ]

    by_type = result.get("retained_by_type") or []
    if by_type:
        lines += ["## What is still reachable", ""]
        lines += _table(
            ["type", "count", "per request"],
            [
                [
                    row["type"],
                    row["count"],
                    round(row["count"] / max(result["requests"], 1), 1),
                ]
                for row in by_type
            ],
        )

    grown = result.get("lru_caches_grown")
    if grown:
        lines += [
            "## Caches that grew",
            "",
            "An `lru_cache` keyed on something request-scoped is the most "
            "common way a worker grows without any one place looking wrong.",
            "",
        ]
        lines += _table(
            ["cache", "entries added", "current size", "per request"],
            [
                [
                    row["cache"],
                    row["entries_added"],
                    row["current_size"],
                    row["per_request"],
                ]
                for row in grown
            ],
        )
    elif result.get("retained_objects"):
        lines += [
            "No `lru_cache` in the process grew, which rules that category "
            "out: whatever holds these objects is hand-rolled.",
            "",
        ]

    for held in result.get("holders") or []:
        lines += [f"### What holds `{held['type']}`", ""]
        if not held["chain"]:
            lines += [
                "No named holder found inside the scan budget. Raise "
                "`[memory].scan_budget` to look further.",
                "",
            ]
            continue
        lines += ["```", *_indent_chain(held["chain"]), "```", ""]

    return "\n".join(lines)


def _indent_chain(chain: Sequence[str]) -> list[str]:
    """Render a reference chain root-first, one indent per hop."""
    return [
        ("  " * depth) + ("-> " if depth else "") + step
        for depth, step in enumerate(chain)
    ]
