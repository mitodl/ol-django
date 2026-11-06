"""Rule-by-rule tests for the dependency-floors checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mitol.dependency_floors.config import load
from mitol.dependency_floors.rules import check

from tests.dependency_floors.conftest import Package

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

FLOOR = {"certifi": {"specifier": ">=2.0"}}
WORKSPACE = {
    "certifi": {
        "specifier": ">=2.0",
        "workspace": {"policy": "entry-point", "providers": {"core": "5.0"}},
    }
}
OPTIONS = {"members": "src/*"}


def rules(manifest: Path) -> list[str]:
    """Rule identifiers reported for a repository, in order."""
    return [violation.rule for violation in check(load(manifest), manifest)]


def summaries(manifest: Path) -> str:
    """Every summary joined, for asserting on wording."""
    return " | ".join(v.summary for v in check(load(manifest), manifest))


# --- the lockfile honours the floor -------------------------------------


@pytest.mark.parametrize(
    ("locked", "expected"),
    [("1.0", ["lock-below-floor"]), ("2.0", []), ("3.0", [])],
)
def test_a_resolution_below_the_floor_is_reported(
    repo: Callable[..., Path], locked: str, expected: list[str]
) -> None:
    """A resolution below the floor fails; at or above it passes."""
    manifest = repo(floors=FLOOR, packages={"certifi": Package(version=locked)})

    assert rules(manifest) == expected


def test_a_floor_absent_from_the_lock_is_ignored(repo: Callable[..., Path]) -> None:
    """Nothing resolved the package, so there is nothing to be below the floor."""
    manifest = repo(floors=FLOOR, packages={"requests": Package()})

    assert rules(manifest) == []


def test_every_resolved_version_has_to_clear_the_floor(
    repo: Callable[..., Path],
) -> None:
    """A lock may carry several versions; each one has to clear the floor."""
    manifest = repo(
        floors=FLOOR,
        packages={"certifi": [Package(version="3.0"), Package(version="1.0")]},
    )

    assert rules(manifest) == ["lock-below-floor"]


# --- a resolver constraint agrees with the floor ------------------------


@pytest.mark.parametrize(
    ("constraint", "expected"),
    [
        ("certifi>=1.0", ["constraint-below-floor"]),
        ("certifi>=2.0", []),
        ("certifi>=9.0", []),
        ("requests>=1.0", []),
    ],
)
def test_a_constraint_weaker_than_the_floor_is_reported(
    repo: Callable[..., Path], constraint: str, expected: list[str]
) -> None:
    """A weaker constraint is drift; an equal or stricter one is fine."""
    manifest = repo(
        floors=FLOOR,
        packages={"certifi": Package(version="2.0")},
        constraints=[constraint],
    )

    assert rules(manifest) == expected


def test_no_constraint_table_is_not_a_violation(repo: Callable[..., Path]) -> None:
    """Not every repository uses constraints, and one is never required."""
    manifest = repo(floors=FLOOR, packages={"certifi": Package(version="2.0")})

    assert rules(manifest) == []


# --- a package that reaches the floor declares it -----------------------


def _entry_repo(repo: Callable[..., Path], deps: list[str]) -> Path:
    return repo(
        floors=WORKSPACE,
        options=OPTIONS,
        packages={
            "certifi": Package(version="2.0"),
            "requests": Package(deps=["certifi"]),
            "app": Package(deps=["requests"]),
        },
        members={"app": {"name": "app", "deps": deps}},
    )


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        (["requests"], ["floor-not-declared"]),
        (["requests", "certifi>=1.0"], ["floor-not-declared"]),
        (["requests", "certifi>=2.0"], []),
        (["requests", "certifi>=3.0"], []),
        (["requests", "certifi"], ["floor-not-declared"]),
    ],
)
def test_reaching_the_floor_requires_declaring_it_high_enough(
    repo: Callable[..., Path], deps: list[str], expected: list[str]
) -> None:
    """Reaching the floored package means declaring it, and high enough."""
    assert rules(_entry_repo(repo, deps)) == expected


def test_an_undeclared_floor_names_the_reachability_path(
    repo: Callable[..., Path],
) -> None:
    """The message has to say how the package arrives, or it is not actionable."""
    manifest = _entry_repo(repo, ["requests"])
    details = check(load(manifest), manifest)[0].details

    assert "path: requests -> certifi" in details


# --- inheritance through a workspace sibling ----------------------------


def _inherit_repo(repo: Callable[..., Path], deps: list[str]) -> Path:
    return repo(
        floors=WORKSPACE,
        options=OPTIONS,
        packages={
            "certifi": Package(version="2.0"),
            "requests": Package(deps=["certifi"]),
            "core": Package(deps=["requests"]),
            "leaf": Package(deps=["core"]),
        },
        members={
            "core": {"name": "core", "deps": ["requests", "certifi>=2.0"]},
            "leaf": {"name": "leaf", "deps": deps},
        },
    )


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        (["core"], ["inherited-floor-unpinned"]),
        (["core>=4.0"], ["inherited-floor-unpinned"]),
        (["core>=5.0"], []),
        (["core>=6.0"], []),
    ],
)
def test_inheriting_a_floor_requires_pinning_the_sibling(
    repo: Callable[..., Path], deps: list[str], expected: list[str]
) -> None:
    """An unpinned sibling can be satisfied by a release predating the floor."""
    assert rules(_inherit_repo(repo, deps)) == expected


def test_declaring_a_floor_already_inherited_is_reported(
    repo: Callable[..., Path],
) -> None:
    """Declaring the floor where it is inherited is what the policy avoids."""
    manifest = _inherit_repo(repo, ["core>=5.0", "certifi>=2.0"])

    assert rules(manifest) == ["floor-declared-redundantly"]
    assert "declares certifi directly" in summaries(manifest)


def test_inheritance_with_no_recorded_provider_explains_itself(
    repo: Callable[..., Path],
) -> None:
    """Inheritance with no recorded provider version cannot be satisfied."""
    floors = {
        "certifi": {
            "specifier": ">=2.0",
            "workspace": {"policy": "entry-point"},
        }
    }
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
            "leaf": {"name": "leaf", "deps": ["core"]},
        },
    )

    assert rules(manifest) == ["inherited-floor-unpinned"]
    assert "record the first core release" in str(
        check(load(manifest), manifest)[0].details
    )


# --- a declaration nothing justifies ------------------------------------


def test_a_floor_nothing_reaches_is_reported(repo: Callable[..., Path]) -> None:
    """A floor that stops being needed has to be shed, not left behind."""
    manifest = repo(
        floors=WORKSPACE,
        options=OPTIONS,
        packages={"certifi": Package(version="2.0"), "app": Package()},
        members={"app": {"name": "app", "deps": ["certifi>=2.0"]}},
    )

    assert rules(manifest) == ["floor-not-needed"]


def test_a_declaration_does_not_justify_itself(
    repo: Callable[..., Path],
) -> None:
    """Declaring the floor must not be what makes the floor look reachable.

    Without excluding a requirement on the floored package from the search,
    every declaration justifies itself and nothing is ever found unnecessary.
    """
    manifest = repo(
        floors=WORKSPACE,
        options=OPTIONS,
        packages={
            "certifi": Package(version="2.0"),
            "app": Package(deps=["certifi"]),
        },
        members={"app": {"name": "app", "deps": ["certifi>=2.0"]}},
    )

    assert rules(manifest) == ["floor-not-needed"]


def test_a_base_declaration_covers_an_extra_that_needs_it(
    repo: Callable[..., Path],
) -> None:
    """A base declaration covers the extra that needs it; it is not redundant."""
    manifest = repo(
        floors=WORKSPACE,
        options=OPTIONS,
        packages={
            "certifi": Package(version="2.0"),
            "requests": Package(deps=["certifi"]),
            "app": Package(extras={"net": ["requests"]}),
        },
        members={
            "app": {
                "name": "app",
                "deps": ["certifi>=2.0"],
                "extras": {"net": ["requests"]},
            }
        },
    )

    assert rules(manifest) == []


# --- `direct`: a package that uses the floored dependency itself --------


def _direct_repo(repo: Callable[..., Path], deps: list[str]) -> Path:
    """Build a member whose only route to certifi is its own declaration."""
    return repo(
        floors={
            "certifi": {
                "specifier": ">=2.0",
                "direct": ["helper"],
                "workspace": {"policy": "entry-point"},
            }
        },
        options=OPTIONS,
        packages={
            "certifi": Package(version="2.0"),
            "helper": Package(deps=["certifi"]),
        },
        members={"helper": {"name": "helper", "deps": deps}},
    )


@pytest.mark.parametrize(
    ("deps", "expected"),
    [
        (["certifi>=2.0"], []),
        (["certifi>=1.0"], ["floor-not-declared"]),
        ([], ["floor-not-declared"]),
    ],
)
def test_direct_members_are_held_to_the_floor_without_reachability(
    repo: Callable[..., Path], deps: list[str], expected: list[str]
) -> None:
    """A package that imports the dependency declares it, and is never pruned.

    Reachability cannot see an import. Without this, the only thing pulling
    certifi in is the declaration itself, which the search deliberately
    ignores — so the check would tell the package to drop a floor it needs.
    """
    assert rules(_direct_repo(repo, deps)) == expected
