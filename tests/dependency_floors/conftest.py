"""Shared helpers for the dependency_floors tests.

Every rule is about the relationship between three things — a floor table, a
lockfile and a set of package manifests — so the tests build a throwaway
repository under ``tmp_path`` rather than checking an inline string. The
``repo`` fixture keeps that to one call: describe the three, then ask which
rules fire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


def _quote(value: str) -> str:
    return f'"{value}"'


def _array(values: list[str]) -> str:
    return "[" + ", ".join(_quote(value) for value in values) + "]"


@dataclass
class Package:
    """One ``[[package]]`` entry to write into a synthetic lockfile."""

    version: str = "1.0"
    deps: list[str] = field(default_factory=list)
    extras: dict[str, list[str]] = field(default_factory=dict)
    #: Markers are ignored by the graph, so a test can assert that directly.
    markers: dict[str, str] = field(default_factory=dict)


def render_lock(packages: dict[str, Package | list[Package]]) -> str:
    """Render a ``uv.lock`` from a mapping of name to package entries.

    A name may map to a list, which writes repeated ``[[package]]`` entries for
    the same package — what uv does when resolution markers select different
    versions, and something the graph has to fold back together.
    """
    blocks = ["version = 1", "revision = 3", ""]

    for name, entry in packages.items():
        for package in entry if isinstance(entry, list) else [entry]:
            blocks.append("[[package]]")
            blocks.append(f"name = {_quote(name)}")
            blocks.append(f"version = {_quote(package.version)}")

            if package.deps:
                rendered = ", ".join(
                    "{ name = "
                    + _quote(dep)
                    + (
                        f", marker = {_quote(package.markers[dep])}"
                        if dep in package.markers
                        else ""
                    )
                    + " }"
                    for dep in package.deps
                )
                blocks.append(f"dependencies = [{rendered}]")

            for extra, names in package.extras.items():
                blocks.append("")
                blocks.append("[package.optional-dependencies]")
                rendered = ", ".join("{ name = " + _quote(n) + " }" for n in names)
                blocks.append(f"{extra} = [{rendered}]")

            blocks.append("")

    return "\n".join(blocks)


def render_member(name: str, deps: list[str], extras: dict[str, list[str]]) -> str:
    """Render a member's ``pyproject.toml``."""
    lines = ["[project]", f"name = {_quote(name)}", 'version = "1.0"']
    lines.append(f"dependencies = {_array(deps)}")

    if extras:
        lines.append("")
        lines.append("[project.optional-dependencies]")
        lines.extend(f"{extra} = {_array(values)}" for extra, values in extras.items())

    return "\n".join(lines) + "\n"


def render_floors(
    floors: dict[str, dict[str, Any]], options: dict[str, Any] | None
) -> str:
    """Render the ``[tool.dependency-floors]`` table."""
    lines = []

    if options:
        lines.append("[tool.dependency-floors.options]")
        for key, value in options.items():
            rendered = _array(value) if isinstance(value, list) else _quote(value)
            lines.append(f"{key} = {rendered}")
        lines.append("")

    for name, body in floors.items():
        lines.append(f"[tool.dependency-floors.floors.{name}]")
        for key, value in body.items():
            if key == "workspace":
                continue
            rendered = _array(value) if isinstance(value, list) else _quote(value)
            lines.append(f"{key} = {rendered}")

        workspace = body.get("workspace")

        if workspace is not None:
            lines.append("")
            lines.append(f"[tool.dependency-floors.floors.{name}.workspace]")
            for key, value in workspace.items():
                if key == "providers":
                    rendered = ", ".join(
                        f"{provider} = {_quote(version)}"
                        for provider, version in value.items()
                    )
                    lines.append("providers = { " + rendered + " }")
                else:
                    lines.append(f"{key} = {_quote(value)}")
        lines.append("")

    return "\n".join(lines)


@pytest.fixture
def repo(tmp_path: Path) -> Callable[..., Path]:
    """Build a synthetic repository and return the path to its manifest."""

    def build(
        *,
        floors: dict[str, dict[str, Any]],
        packages: dict[str, Package | list[Package]] | None = None,
        members: dict[str, dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
        write_lock: bool = True,
        raw_floors: str | None = None,
    ) -> Path:
        manifest = tmp_path / "pyproject.toml"
        body = ["[project]", 'name = "synthetic"', 'version = "0.0"', ""]

        if constraints is not None:
            body.append("[tool.uv]")
            body.append(f"constraint-dependencies = {_array(constraints)}")
            body.append("")

        body.append(
            raw_floors if raw_floors is not None else render_floors(floors, options)
        )
        manifest.write_text("\n".join(body))

        if write_lock:
            (tmp_path / "uv.lock").write_text(render_lock(packages or {}))

        for directory, spec in (members or {}).items():
            package_dir = tmp_path / "src" / directory
            package_dir.mkdir(parents=True, exist_ok=True)
            (package_dir / "pyproject.toml").write_text(
                render_member(
                    spec.get("name", directory),
                    spec.get("deps", []),
                    spec.get("extras", {}),
                )
            )

        return manifest

    return build
