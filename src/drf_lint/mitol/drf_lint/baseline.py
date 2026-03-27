"""Baseline management for drf_lint.

A baseline file records pre-existing violations so they are not re-reported
until fixed. This allows gradual rollout without blocking CI on accumulated
technical debt.

Usage::

    # Generate baseline from existing violations:
    drf-lint --generate-baseline --baseline drf_lint_baseline.json serializers.py

    # Subsequent runs skip violations present in the baseline:
    drf-lint --baseline drf_lint_baseline.json serializers.py
"""

from __future__ import annotations

import json
from pathlib import Path

from mitol.drf_lint.rules.base import Violation


def load(path: Path) -> set[str]:
    """Load a baseline file and return the set of violation keys."""
    if not path.exists():
        return set()
    return set(json.loads(path.read_text(encoding="utf-8")))


def save(path: Path, violations: list[Violation], filename: str) -> None:
    """Append violations from *filename* to the baseline file at *path*."""
    new_keys = {v.baseline_key(filename) for v in violations}
    existing = load(path)
    merged = sorted(existing | new_keys)
    path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")


def filter_new(
    violations: list[Violation],
    filename: str,
    baseline: set[str],
) -> list[Violation]:
    """Return only violations whose baseline key is not in *baseline*."""
    return [v for v in violations if v.baseline_key(filename) not in baseline]
