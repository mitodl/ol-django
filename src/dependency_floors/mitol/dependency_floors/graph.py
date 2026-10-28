"""Build a dependency reachability graph from a lockfile."""

from __future__ import annotations

import contextlib
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


class LockError(Exception):
    """The lockfile is missing or cannot be read."""


@dataclass(frozen=True)
class LockedPackage:
    """One package in a resolution, with every version the lock records."""

    name: str
    versions: tuple[Version, ...]
    dependencies: frozenset[str]


def _edge_names(entries: Any) -> set[str]:
    """Canonical names on one side of a ``dependencies``-shaped array.

    Markers are deliberately ignored. An edge that only exists on one platform
    or Python version is still an edge a consumer can end up resolving, and
    over-reporting reachability is the safe direction here: the cost is a floor
    declared where it was not strictly needed, not a floor silently missing.
    """
    if not isinstance(entries, list):
        return set()

    return {
        canonicalize_name(entry["name"])
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }


class DependencyGraph:
    """Which packages can reach which, under a single resolution."""

    def __init__(self, packages: dict[str, LockedPackage]) -> None:
        """Wrap an already-indexed mapping of canonical name to package."""
        self._packages = packages

    def __contains__(self, name: str) -> bool:
        """Whether the lockfile resolved a package at all."""
        return canonicalize_name(name) in self._packages

    @classmethod
    def from_uv_lock(cls, path: Path) -> DependencyGraph:
        """Read a ``uv.lock`` into a graph.

        ``dependencies`` and every group under ``optional-dependencies`` become
        edges. ``dev-dependencies`` deliberately do not: those hang off the root
        project and describe what the repository needs to test itself, not what
        a consumer installing one of its packages would resolve.

        A lock may carry more than one version of a package, when different
        resolution markers pick different ones. Their edges are unioned under a
        single node, which again over-reports rather than under-reports.
        """
        if not path.is_file():
            message = f"no such lockfile: {path}"
            raise LockError(message)

        with path.open("rb") as handle:
            document = tomllib.load(handle)

        versions: dict[str, set[Version]] = {}
        edges: dict[str, set[str]] = {}

        for entry in document.get("package", []):
            raw_name = entry.get("name")

            if not isinstance(raw_name, str):
                continue

            name = canonicalize_name(raw_name)
            edges.setdefault(name, set())
            versions.setdefault(name, set())

            # A package with no usable version still contributes its edges,
            # so reachability survives a lock entry this parser cannot read.
            with contextlib.suppress(KeyError, InvalidVersion):
                versions[name].add(Version(entry["version"]))

            edges[name] |= _edge_names(entry.get("dependencies"))

            optional = entry.get("optional-dependencies")
            if isinstance(optional, dict):
                for group in optional.values():
                    edges[name] |= _edge_names(group)

        return cls(
            {
                name: LockedPackage(
                    name=name,
                    versions=tuple(sorted(versions[name])),
                    dependencies=frozenset(group),
                )
                for name, group in edges.items()
            }
        )

    def versions(self, name: str) -> tuple[Version, ...]:
        """Every version of a package the lock resolved."""
        package = self._packages.get(canonicalize_name(name))
        return package.versions if package else ()

    def path_to(self, start: str, target: str) -> tuple[str, ...] | None:
        """Shortest dependency path from ``start`` to ``target``, if one exists.

        Returns ``None`` when ``start`` is absent from the lock, which is how a
        requirement excluded by a marker — or a lock that predates it — reads.
        """
        origin = canonicalize_name(start)
        goal = canonicalize_name(target)

        if origin not in self._packages:
            return None

        if origin == goal:
            return (origin,)

        came_from: dict[str, str] = {origin: ""}
        queue = deque([origin])

        while queue:
            current = queue.popleft()

            for neighbour in sorted(self._packages[current].dependencies):
                if neighbour in came_from:
                    continue

                came_from[neighbour] = current

                if neighbour == goal:
                    return _retrace(came_from, neighbour)

                if neighbour in self._packages:
                    queue.append(neighbour)

        return None


def _retrace(came_from: dict[str, str], node: str) -> tuple[str, ...]:
    """Walk the breadth-first parents back to the origin."""
    chain = [node]

    while came_from[chain[-1]]:
        chain.append(came_from[chain[-1]])

    return tuple(reversed(chain))
