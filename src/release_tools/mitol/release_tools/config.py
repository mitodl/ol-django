"""Repository configuration, read from the root ``pyproject.toml``

Two tables matter. ``[tool.uv.workspace]`` says where the packages are, and is
read rather than duplicated because every repository this manages is already a
uv workspace. ``[tool.ol-release]`` says what the workspace config cannot:
which members the tool should leave alone, how releases are tagged, and
whether the repo is a workspace at all.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from pathlib import Path

import tomllib
from mitol.release_tools.project import PROJECT_ROOT

#: Where packages live when the repo declares no uv workspace. Load-bearing:
#: it keeps the tool usable in a repo that is not a uv workspace at all.
DEFAULT_MEMBERS = ("src/*",)


class Layout(StrEnum):
    """How a repository arranges the packages this tool manages"""

    #: Many packages, found through the uv workspace. The default, so that a
    #: repo which says nothing keeps behaving as it always has.
    WORKSPACE = "workspace"
    #: One package, and the repo root is it.
    SINGLE = "single"


#: How a release is tagged, per layout. A single-package repo conventionally
#: tags `v1.2.3`; a monorepo has to say which package the tag belongs to.
TAG_FORMATS = {
    Layout.WORKSPACE: "{name}/v{version}",
    Layout.SINGLE: "v{version}",
}


@dataclass(frozen=True)
class Config:
    """What the root pyproject.toml says about this repo's packages"""

    #: ``[tool.ol-release] layout`` - stated, never inferred.
    layout: Layout = Layout.WORKSPACE
    #: ``[tool.ol-release] tag-format``; ``None`` means the layout's default.
    tag_format: str | None = None
    #: A ``layout`` value that was set but not understood, kept so commands
    #: can say so rather than behaving as though nothing was declared.
    unknown_layout: str | None = None
    #: Likewise for a ``tag-format`` that does not render.
    unknown_tag_format: str | None = None
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


def _unknown_layout(value: object) -> str | None:
    """Report the declared layout when it is not one this tool knows"""
    if value is None:
        return None

    try:
        Layout(value)
    except ValueError:
        return str(value)

    return None


def _tag_format(value: object) -> str | None:
    """Accept a tag template only if it renders

    An unrenderable template would otherwise raise from `version_git_tag`,
    which `prepare` reaches *after* bumping the version, collecting the
    fragments and refreshing the lockfile - leaving a half-cut release.
    """
    if not isinstance(value, str):
        return None

    try:
        value.format(name="name", version="0.0.0")
    except (KeyError, IndexError, ValueError):
        return None

    return value


def _unknown_tag_format(value: object) -> str | None:
    """Report a tag template that was set but cannot render"""
    if value is None:
        return None

    return None if _tag_format(value) is not None else str(value)


def _layout(value: object) -> Layout:
    """Read the declared layout, falling back rather than raising

    An unrecognised value lands on the default for the same reason nothing
    else here raises: this is read during module import.
    """
    try:
        return Layout(value)
    except ValueError:
        return Layout.WORKSPACE


@cache
def _load(root: Path) -> Config:
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return Config()

    workspace = _table(data, "tool", "uv", "workspace")
    members = _strings(workspace.get("members"))
    ours = _table(data, "tool", "ol-release")

    declared = ours.get("layout")

    return Config(
        layout=_layout(declared),
        unknown_layout=_unknown_layout(declared),
        tag_format=_tag_format(ours.get("tag-format")),
        unknown_tag_format=_unknown_tag_format(ours.get("tag-format")),
        members=members or DEFAULT_MEMBERS,
        workspace_exclude=_strings(workspace.get("exclude")),
        exclude=frozenset(_strings(ours.get("exclude"))),
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
