"""Tests for baseline management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mitol.drf_lint import baseline as baseline_mod
from mitol.drf_lint.rules.base import Violation


@pytest.fixture
def tmp_baseline(tmp_path: Path) -> Path:
    """Return a path to a temporary baseline file that does not yet exist."""
    return tmp_path / "baseline.json"


def test_load_nonexistent_returns_empty(tmp_baseline: Path):
    """Loading a baseline that does not exist returns an empty set."""
    assert baseline_mod.load(tmp_baseline) == set()


def test_save_creates_file(tmp_baseline: Path):
    """Saving violations to a new path creates the baseline file."""
    violations = [Violation(rule="ORM001", message="test", line=5, col=0)]
    baseline_mod.save(tmp_baseline, violations, "serializers.py")
    assert tmp_baseline.exists()


def test_save_and_load_roundtrip(tmp_baseline: Path):
    """Violations saved to a baseline can be loaded back as keys."""
    violations = [Violation(rule="ORM001", message="test", line=5, col=0)]
    baseline_mod.save(tmp_baseline, violations, "serializers.py")
    loaded = baseline_mod.load(tmp_baseline)
    assert "serializers.py:5:0:ORM001" in loaded


def test_save_merges_with_existing(tmp_baseline: Path):
    """Saving twice merges both sets of violations into the baseline."""
    v1 = Violation(rule="ORM001", message="test", line=5, col=0)
    v2 = Violation(rule="ORM002", message="test", line=10, col=4)
    baseline_mod.save(tmp_baseline, [v1], "serializers.py")
    baseline_mod.save(tmp_baseline, [v2], "serializers.py")
    loaded = baseline_mod.load(tmp_baseline)
    assert "serializers.py:5:0:ORM001" in loaded
    assert "serializers.py:10:4:ORM002" in loaded


def test_save_is_idempotent(tmp_baseline: Path):
    """Saving the same violation twice does not duplicate its baseline entry."""
    violations = [Violation(rule="ORM001", message="test", line=5, col=0)]
    baseline_mod.save(tmp_baseline, violations, "serializers.py")
    baseline_mod.save(tmp_baseline, violations, "serializers.py")
    keys = json.loads(tmp_baseline.read_text())
    assert keys.count("serializers.py:5:0:ORM001") == 1


def test_filter_new_removes_known():
    """filter_new returns only violations whose key is absent from the baseline."""
    v_known = Violation(rule="ORM001", message="test", line=5, col=0)
    v_new = Violation(rule="ORM001", message="test", line=10, col=0)
    baseline = {"serializers.py:5:0:ORM001"}
    result = baseline_mod.filter_new([v_known, v_new], "serializers.py", baseline)
    assert result == [v_new]


def test_filter_new_empty_baseline_returns_all():
    """filter_new with an empty baseline returns all violations unchanged."""
    violations = [
        Violation(rule="ORM001", message="test", line=5, col=0),
        Violation(rule="ORM002", message="test", line=10, col=0),
    ]
    result = baseline_mod.filter_new(violations, "serializers.py", set())
    assert result == violations
