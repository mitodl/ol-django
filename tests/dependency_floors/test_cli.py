"""Tests for the CLI entry point."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from mitol.dependency_floors.cli import EXIT_CONFIG, EXIT_OK, EXIT_VIOLATIONS, main

from tests.dependency_floors.conftest import Package, render_lock

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FLOOR = {"certifi": {"specifier": ">=2.0"}}


@pytest.fixture
def clean(repo: Callable[..., Path]) -> Path:
    """Build a repository whose single floor holds."""
    return repo(floors=FLOOR, packages={"certifi": Package(version="2.0")})


@pytest.fixture
def dirty(repo: Callable[..., Path]) -> Path:
    """Build a repository whose lockfile has fallen under its floor."""
    return repo(floors=FLOOR, packages={"certifi": Package(version="1.0")})


def test_a_holding_floor_exits_zero(clean: Path) -> None:
    """Nothing to report means a green build."""
    assert main(["--config", str(clean), "check"]) == EXIT_OK


def test_a_violation_exits_one(dirty: Path) -> None:
    """The exit code is what gates CI, so it has to be distinct from a crash."""
    assert main(["--config", str(dirty), "check"]) == EXIT_VIOLATIONS


def test_unreadable_configuration_exits_two(tmp_path: Path) -> None:
    """A broken config must not be mistaken for a clean run or a violation."""
    assert main(["--config", str(tmp_path / "nope.toml"), "check"]) == EXIT_CONFIG


def test_a_missing_lockfile_exits_two(repo: Callable[..., Path]) -> None:
    """An absent lock cannot be read as 'no packages, therefore no problems'."""
    manifest = repo(floors=FLOOR, write_lock=False)

    assert main(["--config", str(manifest), "check"]) == EXIT_CONFIG


def test_json_output_carries_every_field(
    dirty: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The machine-readable form is what another tool would consume."""
    main(["--config", str(dirty), "check", "--format", "json"])
    payload = json.loads(capsys.readouterr().out)

    assert [entry["rule"] for entry in payload] == ["lock-below-floor"]
    assert payload[0]["path"] == "uv.lock"
    assert payload[0]["summary"]
    assert payload[0]["details"]


def test_lock_can_be_overridden(repo: Callable[..., Path], tmp_path: Path) -> None:
    """Pointing at another lockfile is how a repository checks a built artefact."""
    manifest = repo(floors=FLOOR, packages={"certifi": Package(version="2.0")})
    elsewhere = tmp_path / "other.lock"
    elsewhere.write_text(render_lock({"certifi": Package(version="1.0")}))

    assert main(["--config", str(manifest), "--lock", str(elsewhere), "check"]) == (
        EXIT_VIOLATIONS
    )


def test_explain_names_the_classification(
    repo: Callable[..., Path], capsys: pytest.CaptureFixture[str]
) -> None:
    """Explain exists so a classification never has to be reconstructed by hand."""
    manifest = repo(
        floors={
            "certifi": {
                "specifier": ">=2.0",
                "workspace": {"policy": "entry-point"},
            }
        },
        options={"members": "src/*"},
        packages={
            "certifi": Package(version="2.0"),
            "requests": Package(deps=["certifi"]),
            "app": Package(deps=["requests"]),
        },
        members={"app": {"name": "app", "deps": ["requests", "certifi>=2.0"]}},
    )

    assert main(["--config", str(manifest), "explain", "certifi"]) == EXIT_OK

    out = capsys.readouterr().out

    assert "certifi>=2.0" in out
    assert "locked:  2.0" in out
    assert "requests -> certifi" in out


def test_explain_rejects_an_undeclared_floor(clean: Path) -> None:
    """Asking about a floor that is not configured is a user error, not a pass."""
    assert main(["--config", str(clean), "explain", "requests"]) == EXIT_CONFIG
