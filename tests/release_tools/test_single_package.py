"""A repository whose root pyproject.toml is the package"""

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from git import Repo
from mitol.release_tools import apps, config
from mitol.release_tools import project as project_module
from mitol.release_tools.apps import App, list_app_names
from mitol.release_tools.cli import cli
from mitol.release_tools.init import _version_module
from mitol.release_tools.project import Project

from tests.release_tools.conftest import (
    clear_caches,
    make_single_package,
    refresh_app_choices,
    write,
)


def run(*args):
    return CliRunner().invoke(cli, list(args), obj=Project())


def test_the_root_is_the_one_package(single_package_repo):
    assert list_app_names() == ["my-package"]

    app = App.create(Project(), "my-package")

    assert app.absolute_path == single_package_repo
    assert app.relative_path.parts == ()


def test_the_key_is_the_distribution_not_the_checkout_directory(tmp_path, monkeypatch):
    """Otherwise `--app` depends on what the clone happens to be called

    A CI runner checking out to a temp directory would need a different
    `--app` value from a developer's machine.
    """
    for directory in ("checkout-a", "checkout-b"):
        root = tmp_path / directory
        root.mkdir()
        Repo.init(root)
        monkeypatch.setattr(project_module, "PROJECT_ROOT", root)
        monkeypatch.setattr(apps, "PROJECT_ROOT", root)
        monkeypatch.setattr(config, "PROJECT_ROOT", root)
        make_single_package(root, dist_name="my-package", version="1.2.3")

        assert list_app_names() == ["my-package"]


@pytest.mark.usefixtures("single_package_repo")
def test_the_tag_drops_the_package_prefix():
    """`v1.2.3`, not `my-package/v1.2.3`"""
    assert App.create(Project(), "my-package").version_git_tag == "v1.2.3"


def test_tag_format_overrides_the_layout_default(repo_root):
    make_single_package(repo_root, dist_name="my-package", version="1.2.3")
    pyproject = repo_root / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            'layout = "single"', 'layout = "single"\ntag-format = "release-{version}"'
        )
    )
    clear_caches()

    assert App.create(Project(), "my-package").version_git_tag == "release-1.2.3"


def test_app_may_be_omitted(single_package_repo):
    write(
        single_package_repo / "changelog.d" / "20260101_note.md", "### Added\n\n- x\n"
    )
    refresh_app_choices()

    assert run("changelog", "list").exit_code == 0


@patch("mitol.release_tools.publish.is_published", new=lambda *_: False)
@pytest.mark.usefixtures("single_package_repo")
def test_the_matrix_carries_the_bare_tag():
    entries = json.loads(run("publish", "matrix").stdout)["include"]

    assert entries == [{"package": "my-package", "version": "1.2.3", "tag": "v1.2.3"}]


@pytest.mark.usefixtures("single_package_repo")
def test_the_version_module_is_found_by_name():
    """The distribution name matches the module here, so the scan is skipped"""
    app = App.create(Project(), "my-package")

    assert str(_version_module(app)) == "src/my_package/__init__.py"


@pytest.mark.usefixtures("single_package_repo")
def test_version_check_reports_the_single_package():
    result = run("version", "check")

    assert result.exit_code == 0, result.output
    assert "for 1 package." in result.output


@pytest.mark.usefixtures("repo_root")
def test_version_check_fails_when_nothing_is_discovered():
    """A gate that loops zero times must not report success"""
    result = run("version", "check")

    assert result.exit_code == 1
    assert "No packages found" in result.output


@pytest.fixture
def committed(single_package_repo):
    """Commit everything, so later commits have something to diff against"""
    repo = Repo(single_package_repo)
    repo.git.add(A=True)
    repo.index.commit("base")

    return single_package_repo


def changes_after(write_files):
    """Commit a change to the single package and return how it was classified"""
    app = App.create(Project(), "my-package")
    repo = app.project.repo
    base = repo.head.commit
    write_files()
    repo.git.add(A=True)

    return app.get_changes(base_commit=base, target_commit=repo.index.commit("change"))


def test_a_release_commit_is_not_a_mixed_release(committed):
    """The case that made single-package repos unusable

    `relative_path` is `.` for a root package, and git reads a `.` pathspec as
    an empty one matching the whole repo. The root's own `CHANGELOG.md` then
    counted as a code change, so `_report_mixed_release` fired on every
    release and no release PR could ever pass CI.
    """

    def cut_release():
        pyproject = committed / "pyproject.toml"
        pyproject.write_text(pyproject.read_text().replace("1.2.3", "1.2.4"))
        write(
            committed / "src" / "my_package" / "__init__.py",
            '__version__ = "1.2.4"\n',
        )
        write(committed / "CHANGELOG.md", "# Changelog\n\n## [1.2.4]\n\n- A thing\n")
        (committed / "changelog.d" / "20260101_note.md").unlink(missing_ok=True)

    write(committed / "changelog.d" / "20260101_note.md", "### Added\n\n- A thing\n")
    Repo(committed).git.add(A=True)
    Repo(committed).index.commit("fragment")

    changes = changes_after(cut_release)

    assert changes.has_changelog_md_changes
    assert not changes.has_code_changes


def test_a_lockfile_bump_needs_no_fragment(committed):
    """`uv.lock` counts towards a changelog, never against its absence"""
    changes = changes_after(lambda: write(committed / "uv.lock", "version = 2\n"))

    assert changes.has_top_level_dependency_changes
    assert not changes.has_source_changes


def test_a_code_change_is_still_a_source_change(committed):
    changes = changes_after(
        lambda: write(committed / "src" / "my_package" / "api.py", "x = 1\n")
    )

    assert changes.has_source_changes
    assert changes.has_code_changes


def test_repo_level_files_are_the_packages_source(committed):
    """The repo is the package, so a workflow edit is a change to it

    Recorded rather than incidental: `.` is an empty pathspec, so everything
    at the root lands here. If that ever becomes too noisy - a CI tweak
    demanding a changelog fragment - this is the test that should change.
    """
    changes = changes_after(
        lambda: write(committed / ".github" / "workflows" / "ci.yml", "on: push\n")
    )

    assert changes.has_source_changes


@pytest.mark.usefixtures("repo_root")
@pytest.mark.parametrize("command", [("version", "check"), ("publish", "matrix")])
def test_every_gate_refuses_to_pass_with_no_packages(command):
    """A gate that iterates nothing must not report success

    This is how a misconfigured repo silently never releases: the commands
    looked at zero packages and exited 0.
    """
    result = run(*command)

    assert result.exit_code == 1
    # On stderr, so `publish matrix`'s stdout stays pipeable to jq.
    assert "No packages found" in result.stderr


def test_changelog_check_refuses_to_pass_with_no_packages(repo_root):
    """Checked with real refs, since this command resolves them first"""
    write(repo_root / "README.md", "# nothing\n")
    repo = Repo(repo_root)
    repo.git.add(A=True)
    first = repo.index.commit("one")
    write(repo_root / "README.md", "# still nothing\n")
    repo.git.add(A=True)
    repo.index.commit("two")

    result = run("changelog", "check", "-b", first.hexsha, "-t", "HEAD")

    assert result.exit_code == 1
    assert "No packages found" in result.stderr


def test_a_misspelled_layout_is_reported(repo_root):
    """Loading cannot raise, so the complaint surfaces when a command runs"""
    write(repo_root / "pyproject.toml", '[tool.ol-release]\nlayout = "signle"\n')
    clear_caches()

    result = run("version", "check")

    assert 'Ignoring [tool.ol-release] layout = "signle"' in result.stderr
    assert "expected one of single, workspace" in result.stderr


def test_the_no_packages_message_fits_the_layout(repo_root):
    """Telling someone to set `layout = "single"` when they already did is noise"""
    write(
        repo_root / "pyproject.toml",
        '[tool.ol-release]\nlayout = "single"\n',
    )
    clear_caches()

    result = run("version", "check")

    assert result.exit_code == 1
    assert "no [project] name" in result.stderr


def test_a_malformed_root_pyproject_does_not_break_the_cli(repo_root):
    """Discovery runs at import, so it has to degrade rather than traceback"""
    write(
        repo_root / "pyproject.toml",
        'project = "notatable"\n[tool.ol-release]\nlayout = "single"\n',
    )
    clear_caches()

    assert list_app_names() == []
    assert run("--help").exit_code == 0


def test_a_non_string_name_is_not_a_package(repo_root):
    write(
        repo_root / "pyproject.toml",
        '[project]\nname = 123\n[tool.ol-release]\nlayout = "single"\n',
    )
    clear_caches()

    assert list_app_names() == []
