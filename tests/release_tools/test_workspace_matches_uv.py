"""Discovery must agree with uv about what the workspace contains

Discovery parses `[tool.uv.workspace]` itself rather than shelling out, because
`uv workspace metadata` resolves the dependency graph before answering and so
fails outright when resolution does - the wrong failure for a CI gate. The cost
is that `Path.glob` is not uv's glob engine. This test spends one subprocess to
keep uv the oracle anyway: if the two ever disagree about which directories are
members, it fails here rather than silently releasing the wrong set.
"""

import shutil
import subprocess
from pathlib import Path

import pytest
import tomllib
from mitol.release_tools.apps import list_app_names
from mitol.release_tools.config import load

REPO = Path(__file__).parents[2]

pytestmark = pytest.mark.skipif(
    shutil.which("uv") is None, reason="needs the uv binary"
)


def uv_member_names() -> set[str]:
    """Directory names of every workspace member, according to uv"""
    listed = subprocess.run(  # noqa: S603
        [shutil.which("uv"), "workspace", "list"],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    ).stdout.split()

    # `uv workspace list` prints distribution names; map them back to
    # directories through the pyproject each member declares.
    by_dist = {}
    for member in _member_dirs():
        with (member / "pyproject.toml").open("rb") as handle:
            by_dist[tomllib.load(handle)["project"]["name"]] = member.name

    return {by_dist[name] for name in listed if name in by_dist}


def _member_dirs() -> list[Path]:
    """Every directory the configured member globs match, unfiltered"""
    return [
        path
        for pattern in load(REPO).members
        for path in REPO.glob(pattern)
        if path.is_dir() and (path / "pyproject.toml").exists()
    ]


def test_discovery_is_uv_members_minus_our_exclusions():
    """The only thing we drop that uv keeps is `[tool.ol-release] exclude`"""
    expected = uv_member_names() - load(REPO).exclude

    assert set(list_app_names()) == expected


def test_the_exclusions_actually_exclude_something():
    """A guard on the guard: an empty exclude would make the above vacuous"""
    excluded = load(REPO).exclude

    assert excluded
    assert excluded <= uv_member_names()
    assert not (excluded & set(list_app_names()))
