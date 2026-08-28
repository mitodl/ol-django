"""Tests for the CLI's cross-file behaviour and its new flags."""

from __future__ import annotations

import json
from contextlib import chdir
from pathlib import Path

import pytest
from mitol.drf_lint.cli import main
from mitol.drf_lint.index.cache import DEFAULT_CACHE_NAME

from tests.drf_lint.conftest import MODELS_SOURCE, UTILS_SOURCE

_SERIALIZER = """\
from rest_framework import serializers

from myapp.models import Course


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "run_count"]

    def get_thing(self, instance):
        return instance.author.name
"""

_PREFETCH_SERIALIZER = """\
from mitol.common.serializers import BaseSerializer

from myapp.models import Course


class CourseSerializer(BaseSerializer):
    class Meta:
        model = Course
        fields = ["id"]
"""

_EXPECTED_VIOLATIONS = 2


@pytest.fixture
def repo(tmp_path: Path):
    """Build a project on disk and move the working directory into it."""
    (tmp_path / "pyproject.toml").write_text("")
    app = tmp_path / "myapp"
    app.mkdir()
    (app / "__init__.py").touch()
    (app / "utils.py").write_text(UTILS_SOURCE)
    (app / "models.py").write_text(MODELS_SOURCE)
    (app / "serializers.py").write_text(_SERIALIZER)
    with chdir(tmp_path):
        yield tmp_path


def _run(*args: str) -> int:
    return main([*args, "--no-index-cache"])


# ------------------------------------------------------------------ #
# Cross-file analysis end to end
# ------------------------------------------------------------------ #


def test_cross_file_rules_fire_by_default(repo, capsys):  # noqa: ARG001
    """No configuration is needed: the project root is discovered."""
    assert _run("--no-baseline", "myapp/serializers.py") == 1
    output = capsys.readouterr().out
    assert "ORM005" in output
    assert "ORM006" in output


def test_no_cross_file_restores_the_single_file_behaviour(repo, capsys):  # noqa: ARG001
    """The escape hatch runs exactly the rules the tool had before the index."""
    assert main(["--no-baseline", "--no-cross-file", "myapp/serializers.py"]) == 0
    assert capsys.readouterr().out == ""


def test_ignore_disables_one_rule(repo, capsys):  # noqa: ARG001
    """`--ignore` takes one value per flag so a filename cannot be swallowed."""
    assert _run("--no-baseline", "--ignore", "ORM006", "myapp/serializers.py") == 1
    output = capsys.readouterr().out
    assert "ORM005" in output
    assert "ORM006" not in output


def test_ignore_accepts_a_comma_separated_list(repo, capsys):  # noqa: ARG001
    """One token, several codes."""
    arguments = ("--no-baseline", "--ignore", "ORM005,ORM006", "myapp/serializers.py")
    assert _run(*arguments) == 0
    assert capsys.readouterr().out == ""


def test_select_restricts_to_one_rule(repo, capsys):  # noqa: ARG001
    """`--select` is the staged-rollout knob."""
    assert _run("--no-baseline", "--select", "ORM005", "myapp/serializers.py") == 1
    output = capsys.readouterr().out
    assert "ORM005" in output
    assert "ORM006" not in output


def test_model_resolution_never_disables_the_fallback(repo, capsys):  # noqa: ARG001
    """With imports intact, `never` still resolves; the flag is accepted."""
    assert (
        _run("--no-baseline", "--model-resolution", "never", "myapp/serializers.py")
        == 1
    )
    assert "ORM005" in capsys.readouterr().out


def test_warn_unresolved_reports_on_stderr(repo, capsys):
    """Diagnostics never affect the exit code."""
    (repo / "myapp" / "serializers.py").write_text(
        "from rest_framework import serializers\n\n\n"
        "class S(serializers.ModelSerializer):\n"
        "    class Meta:\n"
        "        model = Nowhere\n"
        "        fields = ['id']\n"
    )
    assert (
        _run(
            "--no-baseline",
            "--warn-unresolved",
            "--model-resolution",
            "never",
            "myapp/serializers.py",
        )
        == 0
    )
    captured = capsys.readouterr()
    assert "could not resolve Meta.model = Nowhere" in captured.err
    assert captured.out == ""


# ------------------------------------------------------------------ #
# Prefetch rules through the CLI
# ------------------------------------------------------------------ #


def test_prefetch_rules_fire_through_the_cli(repo, capsys):
    """ORM008 reaches the terminal like any other rule."""
    (repo / "myapp" / "prefetch.py").write_text(_PREFETCH_SERIALIZER)
    assert _run("--no-baseline", "myapp/prefetch.py") == 1
    assert "ORM008" in capsys.readouterr().out


def test_prefetch_base_is_configurable(repo, capsys):
    """Repos that wrap BaseSerializer can point the rules at their own base."""
    (repo / "myapp" / "prefetch.py").write_text(
        _PREFETCH_SERIALIZER.replace(
            "from mitol.common.serializers import BaseSerializer",
            "from acme.base import HouseSerializer",
        ).replace("BaseSerializer)", "HouseSerializer)")
    )
    assert _run("--no-baseline", "myapp/prefetch.py") == 0
    capsys.readouterr()
    assert (
        _run(
            "--no-baseline",
            "--prefetch-base",
            "acme.base.HouseSerializer",
            "myapp/prefetch.py",
        )
        == 1
    )
    assert "ORM008" in capsys.readouterr().out


# ------------------------------------------------------------------ #
# Configuration, caching and robustness
# ------------------------------------------------------------------ #


def test_pyproject_configuration_is_honoured(repo, capsys):
    """`[tool.drf_lint]` saves every consumer repo from stuffing args in YAML."""
    (repo / "pyproject.toml").write_text(
        '[tool.drf_lint]\nignore = ["ORM005", "ORM006"]\n'
    )
    assert _run("--no-baseline", "myapp/serializers.py") == 0
    assert capsys.readouterr().out == ""


def test_build_index_writes_the_cache_and_exits(repo, capsys):
    """A CI warm-up step should not have to check any files."""
    assert main(["--build-index"]) == 0
    assert (repo / DEFAULT_CACHE_NAME).exists()
    assert "index cache refreshed" in capsys.readouterr().out


def test_cached_run_produces_identical_output(repo, capsys):  # noqa: ARG001
    """The cache is an optimisation, never a behaviour change."""
    assert main(["--no-baseline", "myapp/serializers.py"]) == 1
    first = capsys.readouterr().out
    assert main(["--no-baseline", "myapp/serializers.py"]) == 1
    assert capsys.readouterr().out == first


def test_baseline_round_trips_cross_file_violations(repo, capsys):
    """The new codes participate in the existing gradual-rollout mechanism."""
    assert main(["--generate-baseline", "myapp/serializers.py"]) == 0
    capsys.readouterr()
    recorded = json.loads((repo / "drf_lint_baseline.json").read_text())
    assert len(recorded) == _EXPECTED_VIOLATIONS
    assert any("ORM005" in key for key in recorded)
    assert main(["myapp/serializers.py"]) == 0
    assert capsys.readouterr().out == ""


def test_missing_project_root_falls_back_to_local_rules(tmp_path, capsys):
    """No root marker must degrade gracefully, never crash."""
    serializers = tmp_path / "serializers.py"
    serializers.write_text(
        "from rest_framework import serializers\n\n\n"
        "class S(serializers.Serializer):\n"
        "    def get_x(self, instance):\n"
        "        return instance.runs.all()\n"
    )
    arguments = ["--no-baseline", "--project-root", str(tmp_path), "serializers.py"]
    with chdir(tmp_path):
        assert main(arguments) == 1
    assert "ORM002" in capsys.readouterr().out


def test_syntax_error_elsewhere_does_not_break_the_run(repo, capsys):
    """One broken file must not take the whole hook down."""
    (repo / "myapp" / "broken.py").write_text("def oops(:\n")
    assert _run("--no-baseline", "myapp/serializers.py") == 1
    assert "ORM005" in capsys.readouterr().out
