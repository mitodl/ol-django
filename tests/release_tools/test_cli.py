"""The command tree, and that the shared context object survives its nesting"""

import json
from unittest.mock import patch

from click.testing import CliRunner
from mitol.release_tools.cli import cli
from mitol.release_tools.project import Project

from tests.release_tools.conftest import add_package, refresh_app_choices, write


def run(*args):
    return CliRunner().invoke(cli, list(args), obj=Project())


def test_every_command_is_reachable_from_the_root():
    result = run("--help")

    for name in ("init", "changelog", "version", "publish", "prepare"):
        assert name in result.output


@patch("mitol.release_tools.publish.is_published", new=lambda *_: False)
def test_publish_matrix_emits_a_github_actions_matrix(repo_root):
    add_package(
        repo_root, "alpha", dist_name="mitol-alpha", version="2026.1.1", module="alpha"
    )

    result = run("publish", "matrix")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "include": [
            {
                "package": "mitol-alpha",
                "version": "2026.1.1",
                "tag": "mitol-alpha/v2026.1.1",
            }
        ]
    }


@patch("mitol.release_tools.publish.is_published", new=lambda *_: True)
def test_nothing_to_publish_is_an_empty_matrix(repo_root):
    add_package(
        repo_root, "alpha", dist_name="mitol-alpha", version="2026.1.1", module="alpha"
    )

    assert json.loads(run("publish", "matrix").output) == {"include": []}


def test_prepare_refuses_a_release_with_no_fragments(repo_root):
    """The guidance has to survive the extra nesting, not a traceback

    `prepare` reaches sideways into the version and changelog groups, so this
    exercises the context object being found up the chain rather than rebuilt.
    """
    add_package(
        repo_root, "alpha", dist_name="mitol-alpha", version="2026.1.1", module="alpha"
    )
    write(repo_root / "src" / "alpha" / "changelog.d" / "scriv.ini", "[scriv]\n")

    refresh_app_choices()

    result = run("prepare", "--app", "alpha")

    assert result.exit_code == 1
    assert "No changelog fragments found" in result.output
    assert "ol-release changelog create --app alpha" in result.output


def test_prepare_requires_a_bump_for_a_semver_app(repo_root):
    add_package(repo_root, "alpha", dist_name="alpha", version="1.2.3", module="alpha")
    refresh_app_choices()

    result = run("prepare", "--app", "alpha")

    assert result.exit_code == 1
    assert "pass --bump major|minor|patch" in result.output


def test_prepare_rejects_a_bump_for_a_date_based_app(repo_root):
    add_package(
        repo_root, "alpha", dist_name="alpha", version="2026.1.1", module="alpha"
    )
    refresh_app_choices()

    result = run("prepare", "--app", "alpha", "--bump", "minor")

    assert result.exit_code == 1
    assert "--bump does not apply" in result.output
