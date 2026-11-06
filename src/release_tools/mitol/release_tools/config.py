"""Repository configuration, read from the root ``pyproject.toml``

Two tables matter. ``[tool.uv.workspace]`` says where the packages are, and is
read rather than duplicated because every repository this manages is already a
uv workspace. ``[tool.ol-release]`` says which of those the tool should leave
alone, which the workspace config has no way to express.
"""

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import tomllib
from mitol.release_tools.project import PROJECT_ROOT

#: Where packages live when the repo declares no uv workspace. Load-bearing:
#: it keeps the tool usable in a repo that is not a uv workspace at all.
DEFAULT_MEMBERS = ("src/*",)


@dataclass(frozen=True)
class Config:
    """What the root pyproject.toml says about this repo's packages"""

    #: ``[tool.uv.workspace] members`` - globs, relative to the repo root.
    members: tuple[str, ...] = DEFAULT_MEMBERS
    #: ``[tool.uv.workspace] exclude`` - globs removed from the above.
    workspace_exclude: tuple[str, ...] = ()
    #: ``[tool.ol-release] exclude`` - directory names the tool ignores.
    exclude: frozenset[str] = field(default_factory=frozenset)


def _table(data: dict, *path: str) -> dict:
    """Walk to a nested table, giving an empty one if any step is missing"""
    for key in path:
        if not isinstance(data, dict):
            return {}
        data = data.get(key, {})

    return data if isinstance(data, dict) else {}


def _strings(value: object) -> tuple[str, ...]:
    """Coerce a config value to a tuple of strings, or nothing"""
    if not isinstance(value, list):
        return ()

    return tuple(item for item in value if isinstance(item, str))


@cache
def _load(root: Path) -> Config:
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return Config()

    workspace = _table(data, "tool", "uv", "workspace")
    members = _strings(workspace.get("members"))

    return Config(
        members=members or DEFAULT_MEMBERS,
        workspace_exclude=_strings(workspace.get("exclude")),
        exclude=frozenset(_strings(_table(data, "tool", "ol-release").get("exclude"))),
    )


def load(root: Path | None = None) -> Config:
    """Read the configuration for a repository root

    Nothing raises. The ``--app`` choices are built when `decorators` is
    imported, so an unreadable or malformed root ``pyproject.toml`` has to
    degrade to defaults rather than take `ol-release --help` down with it.

    ``root`` is resolved in the body rather than as a default argument, which
    would bind ``PROJECT_ROOT`` once at import and ignore the tests' patching.
    """
    return _load(PROJECT_ROOT if root is None else root)
