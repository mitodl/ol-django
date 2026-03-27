"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path

from mitol.drf_lint.cli import main

_CLEAN_SERIALIZER = """\
from rest_framework import serializers

class GoodSerializer(serializers.Serializer):
    def get_name(self, instance):
        return instance.name
"""

_BAD_SERIALIZER = """\
from rest_framework import serializers

class BadSerializer(serializers.Serializer):
    def get_email(self, instance):
        return User.objects.filter(pk=instance.pk).first()
"""

_BAD_SERIALIZER_ORM002 = """\
from rest_framework import serializers

class AnotherSerializer(serializers.Serializer):
    def get_prices(self, instance):
        return list(instance.resource_prices.all())
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_cli_no_files():
    """CLI with no file arguments returns exit code 0."""
    assert main([]) == 0


def test_cli_clean_file(tmp_path: Path):
    """CLI against a clean serializer file returns exit code 0."""
    f = _write(tmp_path / "serializers.py", _CLEAN_SERIALIZER)
    assert main([str(f), "--no-baseline"]) == 0


def test_cli_violations_exit_1(tmp_path: Path):
    """CLI against a file with violations returns exit code 1."""
    f = _write(tmp_path / "serializers.py", _BAD_SERIALIZER)
    assert main([str(f), "--no-baseline"]) == 1


def test_cli_nonexistent_file(tmp_path: Path, capsys):
    """CLI with a nonexistent file path prints an error and returns exit code 0."""
    result = main([str(tmp_path / "missing.py"), "--no-baseline"])
    assert result == 0
    captured = capsys.readouterr()
    assert "file not found" in captured.err


def test_cli_generate_baseline(tmp_path: Path):
    """--generate-baseline writes violations to baseline.json and exits with 0."""
    f = _write(tmp_path / "serializers.py", _BAD_SERIALIZER)
    baseline_path = tmp_path / "baseline.json"
    result = main([str(f), "--generate-baseline", "--baseline", str(baseline_path)])
    assert result == 0
    assert baseline_path.exists()
    keys = json.loads(baseline_path.read_text())
    assert len(keys) > 0


def test_cli_baseline_suppresses_known_violations(tmp_path: Path):
    """After generating a baseline, re-running the same file exits with 0."""
    f = _write(tmp_path / "serializers.py", _BAD_SERIALIZER)
    baseline_path = tmp_path / "baseline.json"
    main([str(f), "--generate-baseline", "--baseline", str(baseline_path)])
    assert main([str(f), "--baseline", str(baseline_path)]) == 0


def test_cli_no_baseline_flag_reports_all(tmp_path: Path):
    """--no-baseline ignores an existing baseline file and reports all violations."""
    f = _write(tmp_path / "serializers.py", _BAD_SERIALIZER)
    baseline_path = tmp_path / "baseline.json"
    main([str(f), "--generate-baseline", "--baseline", str(baseline_path)])
    assert main([str(f), "--no-baseline"]) == 1


def test_cli_new_violation_after_baseline(tmp_path: Path):
    """A violation added after baseline generation is reported as a new violation."""
    f = _write(tmp_path / "serializers.py", _BAD_SERIALIZER)
    baseline_path = tmp_path / "baseline.json"
    main([str(f), "--generate-baseline", "--baseline", str(baseline_path)])

    f.write_text(_BAD_SERIALIZER + _BAD_SERIALIZER_ORM002, encoding="utf-8")
    assert main([str(f), "--baseline", str(baseline_path)]) == 1


def test_cli_prints_violations(tmp_path: Path, capsys):
    """Violations are printed to stdout with rule code and filename."""
    f = _write(tmp_path / "serializers.py", _BAD_SERIALIZER)
    main([str(f), "--no-baseline"])
    captured = capsys.readouterr()
    assert "ORM001" in captured.out
