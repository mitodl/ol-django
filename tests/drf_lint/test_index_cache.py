"""Tests for the on-disk index cache.

Timing assertions would be flaky in CI, so these measure the property that
actually matters: how many files get re-read.
"""

from __future__ import annotations

import mitol.drf_lint.index as index_pkg
from mitol.drf_lint.index import build_index
from mitol.drf_lint.index.cache import DEFAULT_CACHE_NAME, config_hash, load

_MODULE_COUNT = 12


def _seed(project, count=_MODULE_COUNT):
    for number in range(count):
        project.write(
            f"myapp/mod{number}.py",
            f"""
            class Model{number}:
                @property
                def total(self):
                    return self.rows.count()
            """,
        )
    return project.root / DEFAULT_CACHE_NAME


def _counting_scan(monkeypatch):
    """Replace the scanner with a counting wrapper and return the counter."""
    calls: list[str] = []
    original = index_pkg.scan_file

    def wrapped(path, dotted, **kwargs):
        calls.append(str(path))
        return original(path, dotted, **kwargs)

    monkeypatch.setattr(index_pkg, "scan_file", wrapped)
    return calls


def test_cache_file_is_written(project):
    """A first run leaves a cache behind."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache)
    assert cache.exists()
    assert len(load(cache)) >= _MODULE_COUNT


def test_warm_run_rescans_nothing(project, monkeypatch):
    """Every file matches on size and mtime, so none is re-read."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache)
    calls = _counting_scan(monkeypatch)
    build_index(project.root, cache_path=cache)
    assert calls == []


def test_editing_one_file_rescans_only_that_file(project, monkeypatch):
    """Invalidation is per file, not all-or-nothing."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache)
    project.write("myapp/mod3.py", "class Model3:\n    pass\n")
    calls = _counting_scan(monkeypatch)
    build_index(project.root, cache_path=cache)
    assert [call for call in calls if call.endswith("mod3.py")] == calls
    assert len(calls) == 1


def test_edited_results_are_visible(project):
    """A cached run still reflects the edit it just re-read."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache)
    project.write("myapp/mod3.py", "class Model3:\n    pass\n")
    index = build_index(project.root, cache_path=cache)
    assert "total" not in index.modules["myapp.mod3"].classes["Model3"].members


def test_corrupt_cache_rebuilds_silently(project):
    """A pre-commit hook must never fail because of its own cache."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache)
    cache.write_text("not json{")
    index = build_index(project.root, cache_path=cache)
    assert "myapp.mod0" in index.modules


def test_stale_config_hash_invalidates_everything(project):
    """A vocabulary change must not be served from an old cache."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache)
    cache.write_text(cache.read_text().replace(config_hash(), "stale"))
    assert load(cache) == {}


def test_cache_round_trips_every_field(project):
    """What comes back out of the cache must behave like a fresh scan."""
    project.with_models()
    cache = project.root / DEFAULT_CACHE_NAME
    fresh = build_index(project.root, cache_path=cache, use_cache=False)
    build_index(project.root, cache_path=cache)
    cached = build_index(project.root, cache_path=cache)

    def snapshot(index):
        return {
            (module, cls, name): (member.kind, member.queries)
            for module, info in index.modules.items()
            for cls, class_info in info.classes.items()
            for name, member in class_info.members.items()
        }

    assert snapshot(cached) == snapshot(fresh)
    course = cached.modules["myapp.models"].classes["Course"]
    assert course.relations == {"author": "Author"}
    assert course.many_relations == {"topics": "Topic"}


def test_no_cache_flag_never_writes(project):
    """`--no-index-cache` maps to a build that leaves nothing behind."""
    cache = _seed(project)
    build_index(project.root, cache_path=cache, use_cache=False)
    assert not cache.exists()
