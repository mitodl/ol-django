"""How a git diff is sorted into source, changelog and release changes"""

import pytest
from git import Repo
from mitol.release_tools.apps import App
from mitol.release_tools.project import Project

from tests.release_tools.conftest import add_package, write


@pytest.fixture
def app(repo_root):
    """Commit a package, so that later commits have something to diff against"""
    add_package(
        repo_root, "alpha", dist_name="mitol-alpha", version="2026.1.1", module="alpha"
    )
    write(repo_root / "src" / "alpha" / "changelog.d" / "scriv.ini", "[scriv]\n")
    write(repo_root / "uv.lock", "version = 1\n")

    repo = Repo(repo_root)
    repo.git.add(A=True)
    repo.index.commit("base")

    return App.create(Project(), "alpha")


def changes_after(app, write_files):
    """Commit a change and return how it was classified"""
    repo = app.project.repo
    base = repo.head.commit
    write_files()
    repo.git.add(A=True)

    return app.get_changes(base_commit=base, target_commit=repo.index.commit("change"))


def test_code_change_is_a_source_change(app, repo_root):
    changes = changes_after(
        app, lambda: write(repo_root / "src" / "alpha" / "alpha" / "api.py", "x = 1\n")
    )

    assert changes.has_source_changes
    assert changes.has_code_changes
    assert not changes.has_changelogd_changes


def test_changelog_files_are_not_source_changes(app, repo_root):
    """A fragment must not satisfy the check that demands a fragment"""
    changes = changes_after(
        app,
        lambda: write(
            repo_root / "src" / "alpha" / "changelog.d" / "20260101_a.md", "x"
        ),
    )

    assert not changes.has_source_changes
    assert changes.has_changelogd_changes
    assert changes.has_new_changelogd_fragments


def test_scriv_ini_is_not_a_fragment(app, repo_root):
    """Editing scriv's config is neither a fragment nor a source change"""
    changes = changes_after(
        app,
        lambda: write(
            repo_root / "src" / "alpha" / "changelog.d" / "scriv.ini",
            "[scriv]\nformat = md\n",
        ),
    )

    assert not changes.has_source_changes
    assert not changes.has_changelogd_changes


def test_version_declarations_alone_are_not_code(app, repo_root):
    """A release touches only the files that declare the version

    That is what lets `changelog check` tell a release apart from a code
    change that happens to rewrite CHANGELOG.md.
    """

    def bump():
        pyproject = repo_root / "src" / "alpha" / "pyproject.toml"
        pyproject.write_text(pyproject.read_text().replace("2026.1.1", "2026.1.2"))
        write(
            repo_root / "src" / "alpha" / "alpha" / "__init__.py",
            '__version__ = "2026.1.2"\n',
        )
        write(repo_root / "src" / "alpha" / "CHANGELOG.md", "# Changelog\n")

    changes = changes_after(app, bump)

    assert changes.has_source_changes
    assert changes.has_changelog_md_changes
    assert not changes.has_code_changes


def test_renaming_a_fragment_is_not_a_new_fragment(app, repo_root):
    """Migrating a fragment's format must not require a source change to go with it"""
    changelog_d = repo_root / "src" / "alpha" / "changelog.d"
    write(changelog_d / "20260101_a.rst", "x")
    repo = app.project.repo
    repo.git.add(A=True)
    repo.index.commit("fragment")

    base = repo.head.commit
    (changelog_d / "20260101_a.rst").unlink()
    write(changelog_d / "20260101_a.md", "x")
    repo.git.add(A=True)
    changes = app.get_changes(
        base_commit=base, target_commit=repo.index.commit("migrate")
    )

    assert changes.has_changelogd_changes
    assert not changes.has_new_changelogd_fragments


def test_lockfile_changes_are_tracked_separately(app, repo_root):
    changes = changes_after(app, lambda: write(repo_root / "uv.lock", "version = 2\n"))

    assert changes.has_top_level_dependency_changes
    assert not changes.has_source_changes
