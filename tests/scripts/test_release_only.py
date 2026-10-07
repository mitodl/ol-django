"""Tests for `scripts/changelog.py check-release-only`.

That command is what decides whether a pull request is approved without a human
reading it (`.github/workflows/release-auto-approve.yml`), so the cases that must
NOT pass matter more here than the one that must.
"""

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from git import Actor, Repo

from scripts import apps
from scripts.changelog import changelog, out_of_release_scope

RELEASED_APP = Path("src/widget")

AUTHOR = Actor("Test", "test@example.com")


@pytest.mark.parametrize(
    "path",
    [
        "src/widget/CHANGELOG.md",
        "src/widget/changelog.d/20260101_fragment.md",
        "src/widget/pyproject.toml",
        "src/widget/mitol/widget/__init__.py",
        # The lockfile pins every workspace member's version, so it moves with the
        # bump and is part of the release commit by construction.
        "uv.lock",
    ],
)
def test_in_release_scope(path):
    """Paths a release legitimately touches are not reported"""
    assert out_of_release_scope([path], RELEASED_APP) == []


@pytest.mark.parametrize(
    "path",
    [
        # The three `changelog.py check` would let through: it only ever looks
        # under `src/<app>/`.
        ".github/workflows/ci.yml",
        "scripts/release.py",
        "pyproject.toml",
        # Another app's release, or its code, is somebody else's PR.
        "src/gadget/pyproject.toml",
        # `src/widget2` starts with `src/widget` as a string but is a different
        # app. Prefix matching would wave it through.
        "src/widget2/mitol/widget2/views.py",
    ],
)
def test_out_of_release_scope(path):
    """Everything else is reported, including the near-misses"""
    assert out_of_release_scope([path], RELEASED_APP) == [path]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content).lstrip())


def _app(root: Path, name: str, version: str) -> None:
    """Lay down one workspace app at `version`"""
    _write(
        root / "src" / name / "pyproject.toml",
        f"""
        [project]
        name = "mitol-django-{name}"
        version = "{version}"

        [tool.bumpver]
        current_version = "{version}"
        """,
    )
    _write(
        root / "src" / name / "mitol" / name / "__init__.py",
        f'__version__ = "{version}"\n',
    )
    _write(root / "src" / name / "CHANGELOG.md", "# Changelog\n")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Build a two-app git workspace at the commit a release branches from.

    `scripts.apps.get_source_dir` resolves against the real checkout's `src/`, so
    it is redirected here; `Project` reads the working directory, so the test runs
    from inside the fixture.
    """
    repo = Repo.init(tmp_path, initial_branch="main")

    _app(tmp_path, "widget", "1.0.0")
    _app(tmp_path, "gadget", "1.0.0")
    _write(
        tmp_path / "src" / "widget" / "changelog.d" / "20260101_change.md", "- A fix\n"
    )
    _write(tmp_path / "uv.lock", "version = 1\n")
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\n")

    repo.git.add(A=True)
    base = repo.index.commit("Base", author=AUTHOR, committer=AUTHOR)

    monkeypatch.setattr(apps, "get_source_dir", lambda: tmp_path / "src")
    monkeypatch.chdir(tmp_path)

    return repo, base


def _cut_release(tmp_path: Path, version: str = "1.1.0") -> None:
    """Do to `widget` what `scripts/release.py prepare` would"""
    _app(tmp_path, "widget", version)
    _write(
        tmp_path / "src" / "widget" / "CHANGELOG.md",
        f"# Changelog\n\n## {version}\n\n- A fix\n",
    )
    (tmp_path / "src" / "widget" / "changelog.d" / "20260101_change.md").unlink()
    _write(tmp_path / "uv.lock", "version = 1\n# bumped\n")


def _run(repo: Repo, base) -> object:
    repo.git.add(A=True)
    repo.index.commit("Release", author=AUTHOR, committer=AUTHOR)

    return CliRunner().invoke(
        changelog, ["check-release-only", "--base", base.hexsha, "--target", "HEAD"]
    )


def test_release_only_passes(workspace, tmp_path):
    """A release and nothing else is approved"""
    repo, base = workspace
    _cut_release(tmp_path)

    result = _run(repo, base)

    assert result.exit_code == 0, result.output
    assert "mitol-django-widget/v1.1.0" in result.output


def test_release_plus_a_workflow_edit_is_rejected(workspace, tmp_path):
    """One extra file outside the app is enough to withhold the approval"""
    repo, base = workspace
    _cut_release(tmp_path)
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\n# sneak\n")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert ".github/workflows/ci.yml" in result.output


def test_release_plus_code_in_the_same_app_is_rejected(workspace, tmp_path):
    """The case `changelog.py check` already catches still has to fail here"""
    repo, base = workspace
    _cut_release(tmp_path)
    _write(tmp_path / "src" / "widget" / "mitol" / "widget" / "views.py", "x = 1\n")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "Code is changing in src/widget" in result.output


def test_changelog_rewrite_without_a_version_bump_is_rejected(workspace, tmp_path):
    """Rewriting CHANGELOG.md is not a release unless the version moves"""
    repo, base = workspace
    _cut_release(tmp_path, version="1.0.0")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "version in pyproject.toml is unchanged" in result.output


def test_two_releases_at_once_are_rejected(workspace, tmp_path):
    """Releasing two apps in one PR is a human's call"""
    repo, base = workspace
    _cut_release(tmp_path)
    _app(tmp_path, "gadget", "2.0.0")
    _write(tmp_path / "src" / "gadget" / "CHANGELOG.md", "# Changelog\n\n## 2.0.0\n")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "More than one app is being released at once" in result.output


def test_a_plain_code_pr_is_not_a_release(workspace, tmp_path):
    """An ordinary PR exits non-zero without claiming anything is wrong with it"""
    repo, base = workspace
    _write(tmp_path / "src" / "widget" / "mitol" / "widget" / "views.py", "x = 1\n")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "not a release" in result.output
