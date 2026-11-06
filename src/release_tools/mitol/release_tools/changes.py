from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from git import Commit, Diff

#: Names that are changelog bookkeeping rather than a package's source.
CHANGELOG_DIR = "changelog.d"
CHANGELOG_FILE = "CHANGELOG.md"
SCRIV_CONFIG = "scriv.ini"
#: Counted towards a changelog being present, never against its absence.
LOCKFILE = "uv.lock"
#: Where `init` puts the shared changelog template. In a single-package repo
#: that lands inside the distribution's own tree, so it needs the same
#: treatment as `changelog.d`.
TEMPLATE_DIR = ".scriv"

if TYPE_CHECKING:
    from mitol.release_tools.apps import App
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
    changelog_md_changes: list[Diff]
    code_changes: list[Diff]

    @cached_property
    def has_top_level_dependency_changes(self) -> bool:
        return len(self.top_level_dependency_changes) > 0

    @cached_property
    def has_source_changes(self) -> bool:
        return len(self.source_changes) > 0

    @cached_property
    def has_changelogd_changes(self) -> bool:
        return len(self.changelogd_changes) > 0

    @cached_property
    def has_changelog_md_changes(self) -> bool:
        return len(self.changelog_md_changes) > 0

    @cached_property
    def has_code_changes(self) -> bool:
        return len(self.code_changes) > 0

    @cached_property
    def new_changelogd_fragments(self) -> list[Diff]:
        """
        Changelog fragments that introduce genuinely new content.

        Deletions and format migrations (e.g. renaming a ``.rst`` fragment to
        ``.md``) are excluded, so that changelog maintenance does not require
        an accompanying source change. A fragment is only considered "new" if
        it is added and no fragment sharing its slug (filename without
        extension) is removed in the same diff.
        """
        removed_slugs = {
            Path(change.a_path).stem
            for change in self.changelogd_changes
            if change.change_type == "D" and change.a_path
        }

        return [
            change
            for change in self.changelogd_changes
            if change.change_type == "A"
            and change.b_path
            and Path(change.b_path).stem not in removed_slugs
        ]

    @cached_property
    def has_new_changelogd_fragments(self) -> bool:
        return len(self.new_changelogd_fragments) > 0

    @classmethod
    def from_app_commits(cls, *, app: App, base_commit: Commit, target_commit: Commit):
        """Create the Changes object from an app and commit range"""
        all_changes = base_commit.diff(target_commit)
        # we count these towards a changelog being present
        # but not against the absence of one
        top_level_dependency_changes = base_commit.diff(target_commit, paths=[LOCKFILE])

        # For a single-package repo `relative_path` is `.`, which git reads as
        # an empty pathspec matching the whole repository - correct here,
        # since the repo is the package, but it does mean every root-level
        # file is that package's source. `_is_source_excluded` is what keeps
        # the changelog and the lockfile out of it.
        source_changes = [
            change
            for change in base_commit.diff(target_commit, paths=[app.relative_path])
            if not _is_source_excluded(change.a_path)
            and not _is_source_excluded(change.b_path)
        ]

        changelogd_changes = [
            change
            for change in base_commit.diff(
                target_commit, paths=[app.relative_path / CHANGELOG_DIR]
            )
            if not _is_changelog_excluded(change.a_path)
            and not _is_changelog_excluded(change.b_path)
        ]

        changelog_md_changes = base_commit.diff(
            target_commit, paths=[app.relative_path / CHANGELOG_FILE]
        )

        # Collecting fragments into CHANGELOG.md is what cutting a release
        # means, and a release may only touch the files that declare the
        # version. Everything else under the app is code, and code ships in its
        # own PR with its own changelog fragment.
        version_declarations = {
            str(app.relative_path / path) for path in app.version_files
        }

        code_changes = [
            change
            for change in source_changes
            if not _is_version_declaration(change, version_declarations)
        ]

        return cls(
            all_changes,
            top_level_dependency_changes,
            source_changes,
            changelogd_changes,
            changelog_md_changes,
            code_changes,
        )


def _is_version_declaration(change: Diff, version_declarations: set[str]) -> bool:
    """Return True if a change only touches files that declare the version"""
    paths = {path for path in (change.a_path, change.b_path) if path is not None}

    return bool(paths) and paths <= version_declarations


def _is_source_excluded(path: str | None) -> bool:
    """Return True if the source path is excluded

    Matched on path components rather than globs: ``*/CHANGELOG.md`` needs a
    leading directory, so it silently fails to match the root package's own
    ``CHANGELOG.md`` and every release then looks like a code change. Comparing
    components is also what stops a directory named ``mychangelog.d`` matching.
    """
    if path is None:
        return False

    parts = Path(path).parts

    return (
        CHANGELOG_DIR in parts
        or TEMPLATE_DIR in parts
        or parts[-1:] == (CHANGELOG_FILE,)
        # Only the root lockfile. A nested one is a real dependency change
        # that `top_level_dependency_changes` does not see either, so
        # exempting it by name would hide it from the gate entirely.
        or path == LOCKFILE
    )


def _is_changelog_excluded(path: str | None) -> bool:
    """Return True if the changelog path is excluded"""
    if path is None:
        return False

    return Path(path).name == SCRIV_CONFIG
