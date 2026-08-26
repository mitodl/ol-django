"""Find the project root, enumerate its Python files, and read its config."""

from __future__ import annotations

import os
from collections.abc import Iterator
from fnmatch import fnmatch
from pathlib import Path

import tomllib

#: Directory names pruned during the walk.  Pruning by name is what keeps the
#: scan proportional to the project rather than to everything installed
#: beneath it -- globbing the whole tree and filtering afterwards spends most
#: of its time inside ``.venv`` and ``.tox``.
DEFAULT_SKIP_DIRS: frozenset[str] = frozenset(
    {
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "migrations",
        "node_modules",
        "site-packages",
        "venv",
    }
)

#: Extra user-supplied globs, matched against the files that survive pruning.
DEFAULT_EXCLUDES: tuple[str, ...] = ()

#: Markers that identify a project root, most authoritative first.
_ROOT_MARKERS = (".git", "pyproject.toml", "manage.py", "setup.cfg")


def find_project_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a project root marker."""
    start = start.resolve()
    candidates = [start, *start.parents] if start.is_dir() else list(start.parents)
    for marker in _ROOT_MARKERS:
        for directory in candidates:
            if (directory / marker).exists():
                return directory
    return None


def module_for_path(path: Path, root: Path) -> tuple[str, bool]:
    """Dotted module name for *path*, plus whether it is a package ``__init__``.

    The package boundary is where ``__init__.py`` stops, which handles a flat
    Django app layout and a ``src/`` layout identically without configuration.
    The walk never climbs above *root*, so a project nested inside a larger
    package tree still gets the module names its own imports use.
    """
    path = path.resolve()
    root = root.resolve()
    is_package = path.name == "__init__.py"
    parts = [] if is_package else [path.stem]
    directory = path.parent
    while directory != root and (directory / "__init__.py").exists():
        parts.append(directory.name)
        if directory.parent == directory:
            break
        directory = directory.parent
    parts.reverse()
    if not parts:
        parts = [path.stem]
    return ".".join(parts), is_package


def iter_project_files(
    root: Path,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
    skip_dirs: frozenset[str] = DEFAULT_SKIP_DIRS,
) -> Iterator[Path]:
    """Yield every indexable ``.py`` file under *root*, in a stable order.

    Directories are pruned as the walk proceeds; hidden directories are
    skipped wholesale, which covers ``.venv``, ``.tox``, ``.git`` and the
    various tool caches without enumerating them.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name
            for name in dirnames
            if name not in skip_dirs and not name.startswith(".")
        )
        directory = Path(dirpath)
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = directory / filename
            if excludes and any(fnmatch(str(path), pattern) for pattern in excludes):
                continue
            yield path


def load_config(root: Path) -> dict:
    """Read ``[tool.drf_lint]`` from the project's ``pyproject.toml``."""
    pyproject = root / "pyproject.toml"
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return {}
    config = tool.get("drf_lint")
    return config if isinstance(config, dict) else {}
