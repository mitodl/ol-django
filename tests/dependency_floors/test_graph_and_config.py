"""Tests for lockfile parsing, reachability and configuration loading."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from mitol.dependency_floors.config import ConfigError, load, lower_bound
from mitol.dependency_floors.graph import DependencyGraph, LockError
from mitol.dependency_floors.rules import check
from packaging.specifiers import SpecifierSet

from tests.dependency_floors.conftest import Package, render_lock

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FLOOR = {"certifi": {"specifier": ">=2.0"}}
OPTIONS = {"members": "src/*"}


# --- the graph ----------------------------------------------------------


def test_marker_gated_edges_still_count(tmp_path: Path) -> None:
    """An edge that exists only on one platform is still one a consumer can get.

    Over-reporting reachability costs a floor declared where it was not needed;
    under-reporting costs a floor silently missing.
    """
    lock = tmp_path / "uv.lock"
    lock.write_text(
        render_lock(
            {
                "app": Package(
                    deps=["winonly"], markers={"winonly": "sys_platform == 'win32'"}
                ),
                "winonly": Package(deps=["certifi"]),
                "certifi": Package(version="2.0"),
            }
        )
    )

    graph = DependencyGraph.from_uv_lock(lock)

    assert graph.path_to("app", "certifi") == ("app", "winonly", "certifi")


def test_repeated_package_entries_union_their_edges(tmp_path: Path) -> None:
    """Uv writes a package once per resolution marker; the edges fold together."""
    lock = tmp_path / "uv.lock"
    lock.write_text(
        render_lock(
            {
                "app": [
                    Package(version="1.0", deps=["old"]),
                    Package(version="2.0", deps=["new"]),
                ],
                "old": Package(),
                "new": Package(deps=["certifi"]),
                "certifi": Package(version="2.0"),
            }
        )
    )

    graph = DependencyGraph.from_uv_lock(lock)

    assert graph.path_to("app", "certifi") == ("app", "new", "certifi")
    assert [str(version) for version in graph.versions("app")] == ["1.0", "2.0"]


def test_optional_dependencies_are_edges_and_dev_ones_are_not(
    tmp_path: Path,
) -> None:
    """Extras are something a consumer can ask for; dev groups are not."""
    lock = tmp_path / "uv.lock"
    lock.write_text(
        "\n".join(
            [
                render_lock(
                    {
                        "app": Package(extras={"net": ["requests"]}),
                        "requests": Package(deps=["certifi"]),
                        "certifi": Package(version="2.0"),
                    }
                ),
                "[[package]]",
                'name = "root"',
                'version = "0.1"',
                "",
                "[package.dev-dependencies]",
                'dev = [{ name = "certifi" }]',
                "",
            ]
        )
    )

    graph = DependencyGraph.from_uv_lock(lock)

    assert graph.path_to("app", "certifi") == ("app", "requests", "certifi")
    assert graph.path_to("root", "certifi") is None


def test_an_absent_requirement_is_unreachable(tmp_path: Path) -> None:
    """A marker-excluded dependency never appears in the lock at all."""
    lock = tmp_path / "uv.lock"
    lock.write_text(render_lock({"certifi": Package(version="2.0")}))

    assert DependencyGraph.from_uv_lock(lock).path_to("absent", "certifi") is None


def test_a_missing_lockfile_is_an_error(tmp_path: Path) -> None:
    """Silently treating a missing lock as empty would pass everything."""
    with pytest.raises(LockError, match="no such lockfile"):
        DependencyGraph.from_uv_lock(tmp_path / "uv.lock")


# --- lower bounds -------------------------------------------------------


@pytest.mark.parametrize(
    ("specifier", "expected"),
    [
        (">=2.0", "2.0"),
        ("==2.0", "2.0"),
        ("~=2.0", "2.0"),
        (">2.0", "2.0"),
        (">=1.0,<3.0", "1.0"),
        (">=1.0,>=2.0", "2.0"),
        ("<3.0", None),
        ("!=2.0", None),
        ("", None),
    ],
)
def test_lower_bound(specifier: str, expected: str | None) -> None:
    """The highest lower bound a specifier places, or nothing."""
    found = lower_bound(SpecifierSet(specifier))

    assert (str(found) if found else None) == expected


# --- configuration ------------------------------------------------------


def test_closure_policy_declares_everywhere_it_reaches(
    repo: Callable[..., Path],
) -> None:
    """Under 'closure' there is no inheritance; the leaf declares the floor."""
    floors = {"certifi": {"specifier": ">=2.0", "workspace": {"policy": "closure"}}}
    manifest = repo(
        floors=floors,
        options=OPTIONS,
        packages={
            "certifi": Package(version="2.0"),
            "requests": Package(deps=["certifi"]),
            "core": Package(deps=["requests"]),
            "leaf": Package(deps=["core"]),
        },
        members={
            "core": {"name": "core", "deps": ["requests", "certifi>=2.0"]},
            "leaf": {"name": "leaf", "deps": ["core>=5.0"]},
        },
    )

    assert [v.rule for v in check(load(manifest), manifest)] == ["floor-not-declared"]


def test_members_unset_runs_only_the_repo_rules(repo: Callable[..., Path]) -> None:
    """An application publishes no metadata, so only the lockfile checks apply."""
    manifest = repo(
        floors={"certifi": {"specifier": ">=2.0"}},
        packages={
            "certifi": Package(version="2.0"),
            "requests": Package(deps=["certifi"]),
            "app": Package(deps=["requests"]),
        },
        members={"app": {"name": "app", "deps": ["requests"]}},
    )

    assert check(load(manifest), manifest) == []


def test_exclude_drops_a_member(repo: Callable[..., Path]) -> None:
    """A test-only package in src/ is not something anyone installs."""
    packages = {
        "certifi": Package(version="2.0"),
        "requests": Package(deps=["certifi"]),
        "app": Package(deps=["requests"]),
    }
    members = {"app": {"name": "app", "deps": ["requests"]}}

    included = repo(floors=FLOOR, options=OPTIONS, packages=packages, members=members)

    assert [v.rule for v in check(load(included), included)] == ["floor-not-declared"]

    excluded = repo(
        floors=FLOOR,
        options={**OPTIONS, "exclude": ["src/app"]},
        packages=packages,
        members=members,
    )

    assert check(load(excluded), excluded) == []


@pytest.mark.parametrize(
    ("table", "message"),
    [
        ("", "declares no [tool.dependency-floors] table"),
        ("[tool.dependency-floors]\n", "declares no floors"),
        (
            '[tool.dependency-floors.floors.certifi]\nspecifier = "<3.0"\n',
            "places no lower bound",
        ),
        (
            '[tool.dependency-floors.floors.certifi]\nspecifier = "not a specifier"\n',
            "not a valid specifier",
        ),
        (
            "[tool.dependency-floors.floors.certifi]\n"
            'specifier = ">=2.0"\n\n'
            "[tool.dependency-floors.floors.certifi.workspace]\n"
            'policy = "whatever"\n',
            "policy must be one of",
        ),
        (
            "[tool.dependency-floors.floors.certifi]\n"
            'specifier = ">=2.0"\n\n'
            "[tool.dependency-floors.floors.certifi.workspace]\n"
            'policy = "closure"\n'
            'providers = { core = "5.0" }\n',
            "meaningless under the 'closure' policy",
        ),
        (
            "[tool.dependency-floors.floors.certifi]\n"
            'specifier = ">=2.0"\n\n'
            "[tool.dependency-floors.floors.certifi.workspace]\n"
            'providers = { core = "not a version" }\n',
            "not a valid version",
        ),
    ],
)
def test_configuration_errors_say_what_is_wrong(
    repo: Callable[..., Path], table: str, message: str
) -> None:
    """A bad table has to fail loudly rather than check nothing."""
    manifest = repo(floors={}, raw_floors=table)

    with pytest.raises(ConfigError, match=re.escape(message)):
        load(manifest)
