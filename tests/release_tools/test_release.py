"""Cutting a release: bump the version, then collect against the bumped version"""

from unittest.mock import patch

from click.testing import CliRunner
from mitol.release_tools import changelog, version
from mitol.release_tools.apps import App
from mitol.release_tools.cli import cli
from mitol.release_tools.project import Project

from tests.release_tools.conftest import add_package, refresh_app_choices, write


def test_app_rereads_pyproject_after_it_changes(repo_root):
    """`App.pyproject` must stay a plain property, not a cached_property

    `prepare` invokes bumpver and then passes `app.version` to scriv. Caching
    the parsed pyproject would hand scriv the pre-bump version, so the
    collected entry would be titled with the version before the release.
    """
    package = add_package(
        repo_root, "alpha", dist_name="alpha", version="2026.1.1", module="alpha"
    )
    app = App.create(Project(), "alpha")

    assert app.version == "2026.1.1"

    pyproject = package / "pyproject.toml"
    pyproject.write_text(pyproject.read_text().replace("2026.1.1", "2026.1.2"))

    assert app.version == "2026.1.2"


@patch("subprocess.run")
def test_prepare_collects_against_the_bumped_version(
    run_subprocess, repo_root, monkeypatch
):
    """The changelog entry is titled with the version the release produced

    `prepare` bumps first and collects second, reading `app.version` in
    between. Collecting against a stale read would title the entry with the
    version the release replaced.
    """
    package = add_package(
        repo_root, "alpha", dist_name="alpha", version="2026.1.1", module="alpha"
    )
    write(package / "changelog.d" / "scriv.ini", "[scriv]\nformat = md\n")
    write(package / "changelog.d" / "20260101_note.md", "### Added\n\n- A thing\n")
    refresh_app_choices()

    collected = {}

    def fake_bump(**_kwargs):
        pyproject = package / "pyproject.toml"
        pyproject.write_text(pyproject.read_text().replace("2026.1.1", "2026.1.2"))

    def fake_collect(**kwargs):
        collected.update(kwargs)

    update = version.version.commands["update"]
    monkeypatch.setattr(update, "callback", fake_bump)
    monkeypatch.setattr(changelog.collect, "callback", fake_collect)

    result = CliRunner().invoke(cli, ["prepare", "--app", "alpha"], obj=Project())

    assert result.exit_code == 0, result.output
    assert collected["version"] == "2026.1.2"
    assert collected["keep"] is False
    # The lockfile pins every workspace member's version, so it moves with the
    # bump and belongs in the same commit.
    assert run_subprocess.call_args.args[0] == ["uv", "lock"]
    assert "Prepared alpha/v2026.1.2" in result.output
