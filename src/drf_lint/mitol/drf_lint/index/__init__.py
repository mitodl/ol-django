"""Project-wide index of which class members perform database queries.

The single-file checker can only see the serializer in front of it.  This
package supplies the other half: a coarse map of every model, helper and
serializer in the project, closed over the call graph, so that touching a
model property in a serializer can be recognised as the query it really is.
"""

from __future__ import annotations

from pathlib import Path

from mitol.drf_lint.index import cache as cache_mod
from mitol.drf_lint.index.discovery import (
    DEFAULT_EXCLUDES,
    DEFAULT_SKIP_DIRS,
    find_project_root,
    iter_project_files,
    load_config,
    module_for_path,
)
from mitol.drf_lint.index.model import (
    ClassInfo,
    Member,
    MemberId,
    ModuleInfo,
    ProjectIndex,
    QueryHit,
)
from mitol.drf_lint.index.propagate import explain, propagate, transitive_hits
from mitol.drf_lint.index.scan import scan_file, scan_source

__all__ = [
    "DEFAULT_EXCLUDES",
    "DEFAULT_SKIP_DIRS",
    "ClassInfo",
    "Member",
    "MemberId",
    "ModuleInfo",
    "ProjectIndex",
    "QueryHit",
    "build_index",
    "explain",
    "find_project_root",
    "iter_project_files",
    "load_config",
    "module_for_path",
    "overlay_source",
    "transitive_hits",
]


def build_index(
    root: Path,
    *,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
    cache_path: Path | None = None,
    use_cache: bool = True,
    fallback: str = "unique",
) -> ProjectIndex:
    """Scan every Python file under *root* and close the call graph over it.

    Files whose size and mtime match the cache are not re-read.  Anything that
    fails to read or parse is skipped rather than raising -- a syntax error in
    an unrelated file must never block a commit.
    """
    index = ProjectIndex(root=root)
    cached = cache_mod.load(cache_path) if use_cache and cache_path else {}
    fresh: dict[str, ModuleInfo] = {}

    for path in iter_project_files(root, excludes):
        key = str(path)
        try:
            stat = path.stat()
        except OSError:
            continue
        previous = cached.get(key)
        if (
            previous is not None
            and previous.mtime_ns == stat.st_mtime_ns
            and previous.size == stat.st_size
        ):
            module = previous
        else:
            dotted, is_package = module_for_path(path, root)
            module = scan_file(path, dotted, is_package=is_package)
            if module is None:
                continue
        fresh[key] = module
        index.add(module)

    index.reindex_names()
    propagate(index, fallback=fallback)

    if use_cache and cache_path:
        cache_mod.save(cache_path, fresh)
    return index


def overlay_source(index: ProjectIndex, source: str, path: Path) -> str | None:
    """Scan *source* into the index in place of whatever is on disk at *path*.

    pre-commit hands us the staged content of a file, which may differ from
    what the index read.  Overlaying keeps ``self.<helper>()`` resolution
    honest for the file actually being checked.  Returns its dotted name.
    """
    dotted, is_package = module_for_path(path, index.root)
    module = scan_source(source, dotted, str(path), is_package=is_package)
    if module is None:
        return index.by_path.get(str(path))
    index.add(module)
    index.reindex_names()
    propagate(index)
    return dotted
