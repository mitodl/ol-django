from ast import TypeAlias
from dataclasses import dataclass
from fnmatch import fnmatch
from functools import cached_property
from typing import TYPE_CHECKING

from git import Commit, Diff

if TYPE_CHECKING:
    from scripts.apps import App
else:
    App: TypeAlias = None


@dataclass(frozen=True)
class Changes:
    """
    Representation for various categories of changes in git.
    """

    all_changes: list[Diff]
    top_level_dependency_changes: list[Diff]
    source_changes: list[Diff]
    changelogd_changes: list[Diff]

    @cached_property
    def has_top_level_dependency_changes(self) -> bool:
        return len(self.top_level_dependency_changes) > 0

    def has_source_changes(self) -> bool:
        return len(self.source_changes) > 0

    def has_changelogd_changes(self) -> bool:
        return len(self.changelogd_changes) > 0

    @classmethod
    def from_app_commits(cls, *, app: App, base_commit: Commit, target_commit: Commit):
        """Create the Changes object from an app and commit range"""
        all_changes = base_commit.diff(target_commit)
        # we count these towards a changelog being present
        # but not against the absence of one
        top_level_dependency_changes = base_commit.diff(
            target_commit, paths=["uv.lock"]
        )

        source_changes = [
            change
            for change in base_commit.diff(target_commit, paths=[app.relative_path])
            if not _is_source_excluded(change.a_path)
            and not _is_source_excluded(change.b_path)
        ]

        changelogd_changes = [
            change
            for change in base_commit.diff(
                target_commit, paths=[app.relative_path / "changelog.d"]
            )
            if not _is_changelog_excluded(change.a_path)
            and not _is_changelog_excluded(change.b_path)
        ]

        return cls(
            all_changes,
            top_level_dependency_changes,
            source_changes,
            changelogd_changes,
        )


def _is_source_excluded(path: str | None) -> bool:
    """Return True if the source path is excluded"""
    if path is None:
        return False

    excluded_paths = ["*/changelog.d/*", "*/CHANGELOG.md"]

    return any(fnmatch(path, exclude) for exclude in excluded_paths)


def _is_changelog_excluded(path: str | None) -> bool:
    """Return True if the changelog path is excluded"""
    if path is None:
        return False

    excluded_paths = ["*/scriv.ini"]

    return any(fnmatch(path, exclude) for exclude in excluded_paths)
