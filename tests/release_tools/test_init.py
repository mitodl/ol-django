"""Bootstrapping a repository that the other commands could not otherwise read"""

from pathlib import Path

import pytest
from click.testing import CliRunner
from git import Repo
from mitol.release_tools import apps, config
from mitol.release_tools import project as project_module
from mitol.release_tools.apps import App
from mitol.release_tools.init import (
    INSERT_MARKER,
    TEMPLATE_DIR,
    TEMPLATE_NAME,
    _template_source,
    _version_module,
    init,
)
from mitol.release_tools.project import Project

from tests.release_tools.conftest import add_package, clear_caches, write

#: click's exit code for a usage error, such as a missing required option.
USAGE_ERROR = 2

LEGACY_RST = """\
Change Log
----------

[0.6.1] - 2026-10-06
~~~~~~~~~~~~~~~~~~~~
- Something that happened before any of this.
"""


@pytest.fixture
def plugin(repo_root):
    """Build a package shaped like open-edx-plugins': flat, semver, unconfigured"""
    package = add_package(
        repo_root,
        "ol_openedx_chat",
        dist_name="ol-openedx-chat",
        version="0.6.1",
        module="ol_openedx_chat",
        bumpver=False,
        extra='description = "chat"\n',
    )
    write(package / "CHANGELOG.rst", LEGACY_RST)
    write(package / "tests" / "__init__.py", "")

    return package


def run(*args):
    """Invoke `init`, supplying the required scheme unless the test sets one"""
    if "--versioning" not in args:
        args = ("--versioning", "semver", *args)

    return CliRunner().invoke(init, list(args), obj=Project())


def run_bare(*args):
    """Invoke `init` exactly as given, with nothing added"""
    return CliRunner().invoke(init, list(args), obj=Project())


def test_creates_everything_a_bare_package_lacks(repo_root, plugin):
    result = run()

    assert result.exit_code == 0, result.output
    assert (repo_root / ".scriv" / "entry_title.md.j2").exists()
    assert (plugin / "changelog.d" / "scriv.ini").exists()
    assert (plugin / "CHANGELOG.md").exists()
    assert (
        '__version__ = "0.6.1"'
        in (plugin / "ol_openedx_chat" / "__init__.py").read_text()
    )
    assert "[tool.bumpver]" in (plugin / "pyproject.toml").read_text()


def test_infers_semver_from_the_existing_version(plugin):
    """A package on 0.6.1 must not be handed a date-based pattern

    bumpver would then invent a version that sorts below the one already on
    PyPI, and consumers pinning >=0.6,<1 would never see the release.
    """
    run()

    assert (
        'version_pattern = "MAJOR.MINOR.PATCH"'
        in (plugin / "pyproject.toml").read_text()
    )


def test_versioning_flag_overrides_the_inference(plugin):
    run("--versioning", "date")

    assert (
        'version_pattern = "YYYY.MM.DD[.INC0]"'
        in (plugin / "pyproject.toml").read_text()
    )


def test_existing_changelog_history_is_left_alone(plugin):
    """A hand-written .rst is linked, never rewritten or converted

    Collecting markdown fragments into reStructuredText would produce a broken
    document, and the history is not ours to reformat.
    """
    run()

    assert (plugin / "CHANGELOG.rst").read_text() == LEGACY_RST
    assert "CHANGELOG.rst" in (plugin / "CHANGELOG.md").read_text()
    assert INSERT_MARKER in (plugin / "CHANGELOG.md").read_text()


def test_scriv_config_points_at_the_shared_template(plugin):
    run()
    config = (plugin / "changelog.d" / "scriv.ini").read_text()

    assert "file: ../../.scriv/entry_title.${config:format}.j2" in config
    assert "version = literal: ol_openedx_chat/__init__.py: __version__" in config


def test_existing_tool_tables_survive(repo_root):
    """Adding [tool.bumpver] must not take the rest of [tool] with it

    Every package in the first target repo configures hatch under [tool], so
    replacing the table wholesale would leave 24 of 25 unable to build a
    correct wheel - and silently, since nothing reads it until release time.
    """
    package = add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="alpha",
        bumpver=False,
        extra=(
            "\n[tool.hatch.build.targets.wheel]\n"
            'packages = ["alpha"]\n'
            "\n[tool.pytest.ini_options]\n"
            'testpaths = ["tests"]\n'
        ),
    )

    assert run().exit_code == 0

    written = (package / "pyproject.toml").read_text()

    assert "[tool.hatch.build.targets.wheel]" in written
    assert 'packages = ["alpha"]' in written
    assert "[tool.pytest.ini_options]" in written
    assert "[tool.bumpver]" in written


def test_scriv_template_path_resolves_from_the_package_dir(repo_root):
    """Scriv reads `file:` relative to the cwd, which commands set to the package

    A path computed from `changelog.d` instead is one level too deep, and
    nothing notices until the first `prepare` tries to collect fragments.
    """
    package = add_package(
        repo_root, "alpha", dist_name="alpha", version="1.0.0", module="alpha"
    )

    assert run().exit_code == 0

    config = (package / "changelog.d" / "scriv.ini").read_text()
    template_line = next(
        line for line in config.splitlines() if "entry_title_template" in line
    )
    relative = template_line.split("file: ", 1)[1].replace("${config:format}", "md")

    assert (package / relative).resolve() == (
        repo_root / ".scriv" / "entry_title.md.j2"
    )


def test_comments_in_pyproject_survive(repo_root):
    """Bumpver is inserted with tomlkit so the file is edited, not regenerated"""
    package = add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="alpha",
        bumpver=False,
        extra='# load-bearing comment\ndescription = "a"\n',
    )
    run()

    assert "# load-bearing comment" in (package / "pyproject.toml").read_text()


@pytest.mark.usefixtures("plugin")
def test_running_twice_writes_nothing(repo_root):
    run()
    before = {
        path: path.read_bytes() for path in repo_root.rglob("*") if path.is_file()
    }

    result = run()

    assert "nothing to do" in result.output
    assert {
        path: path.read_bytes() for path in repo_root.rglob("*") if path.is_file()
    } == before


def test_check_reports_without_writing(plugin):
    result = run("--check")

    assert result.exit_code == 1
    assert "missing" in result.output
    assert not (plugin / "changelog.d").exists()

    run()

    assert run("--check").exit_code == 0


def test_dry_run_reports_without_writing(plugin):
    result = run("--dry-run")

    assert result.exit_code == 0
    assert "Nothing was" in result.output
    assert not (plugin / "changelog.d").exists()


def test_app_option_narrows_the_work(repo_root, plugin):
    add_package(
        repo_root,
        "beta",
        dist_name="beta",
        version="1.0.0",
        module="beta",
        bumpver=False,
    )

    assert run("--app", "beta").exit_code == 0

    assert not (plugin / "changelog.d").exists()
    assert (repo_root / "src" / "beta" / "changelog.d").exists()


@pytest.mark.usefixtures("plugin")
def test_unknown_app_names_what_was_found():
    result = run("--app", "nope")

    assert result.exit_code == 1
    assert "ol_openedx_chat" in result.output


@pytest.mark.parametrize(
    ("directory", "dist_name", "module"),
    [
        # mitol/ is a PEP 420 namespace, so the version lives a level down
        ("common", "mitol-django-common", "mitol/common"),
        # edx-api-client's module shares nothing with its distribution name
        ("edx_api_client", "edx-api-client", "edx_api"),
        # and the flat case, where they happen to agree
        ("ol_openedx_chat", "ol-openedx-chat", "ol_openedx_chat"),
    ],
)
def test_version_module_is_found_structurally(repo_root, directory, dist_name, module):
    """The owning module is never derived from the distribution name

    Three real layouts disagree about the relationship between the two, so
    matching on the name would rewrite the wrong file in two of them.
    """
    add_package(
        repo_root,
        directory,
        dist_name=dist_name,
        version="1.0.0",
        module=module,
        bumpver=False,
    )
    app = App.create(Project(), directory)

    assert str(_version_module(app)) == f"{module}/__init__.py"


def test_ambiguous_version_module_is_an_error_not_a_guess(repo_root):
    """Naming the wrong module means bumpver silently rewrites nothing"""
    package = add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="one",
        bumpver=False,
    )
    write(package / "two" / "__init__.py", "")

    result = run()

    assert result.exit_code == 1
    assert "one/__init__.py" in result.output
    assert "two/__init__.py" in result.output


def test_configured_bumpver_names_the_version_module(repo_root):
    """Where bumpver already answers the question, do not re-derive it"""
    add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="weird_name",
    )
    package = repo_root / "src" / "alpha"
    write(package / "extra" / "__init__.py", "")

    assert run().exit_code == 0
    assert (
        "weird_name/__init__.py" in (package / "changelog.d" / "scriv.ini").read_text()
    )


def test_shipped_template_matches_this_repos_copy():
    """The package ships the template and this repo also commits one

    Nothing else keeps the two in step, so a change to either alone would
    give ol-django a different changelog heading from every repo `init`
    configures.
    """
    shipped = _template_source()
    committed = Path(__file__).parents[2] / TEMPLATE_DIR / TEMPLATE_NAME

    assert committed.read_text() == shipped


def test_a_checkout_under_a_docs_directory_still_resolves(tmp_path, monkeypatch):
    """The test/docs filter applies within the package, not to the whole path

    Matching on absolute path components discards every candidate for a
    checkout that happens to live under `~/docs/` or `~/tests/`.
    """

    root = tmp_path / "docs" / "repo"
    (root / "src").mkdir(parents=True)
    Repo.init(root)
    monkeypatch.setattr(project_module, "PROJECT_ROOT", root)
    monkeypatch.setattr(apps, "PROJECT_ROOT", root)
    monkeypatch.setattr(config, "PROJECT_ROOT", root)
    clear_caches()
    monkeypatch.chdir(root)

    add_package(
        root, "alpha", dist_name="alpha", version="1.0.0", module="alpha", bumpver=False
    )

    assert str(_version_module(App.create(Project(), "alpha"))) == "alpha/__init__.py"


def test_a_package_with_no_static_version_is_named_not_a_traceback(repo_root):
    """`dynamic = ["version"]` is legal PEP 621 and has nothing to seed bumpver"""
    write(
        repo_root / "src" / "beta" / "pyproject.toml",
        """\
        [project]
        name = "beta"
        dynamic = ["version"]
        """,
    )
    write(repo_root / "src" / "beta" / "beta" / "__init__.py", "")

    result = run()

    assert result.exit_code == 1
    assert "beta: no static version" in result.output


@pytest.mark.usefixtures("plugin")
def test_version_file_needs_a_single_app(repo_root):
    """The override names a path inside one package, so it cannot describe two"""
    add_package(
        repo_root,
        "beta",
        dist_name="beta",
        version="1.0.0",
        module="beta",
        bumpver=False,
    )

    result = run("--version-file", "ol_openedx_chat/__init__.py")

    assert result.exit_code == 1
    assert "single package" in result.output
    assert not (repo_root / "src" / "beta" / "ol_openedx_chat").exists()


@pytest.mark.usefixtures("plugin")
def test_version_file_cannot_escape_the_package(repo_root):
    """A path with enough `../` would write a module outside the repository"""
    result = run(
        "--app", "ol_openedx_chat", "--version-file", "../../../escaped/__init__.py"
    )

    assert result.exit_code == 1
    assert "escapes it" in result.output
    assert not (repo_root.parent / "escaped").exists()


def test_a_new_version_module_does_not_open_with_a_blank_line(repo_root):
    package = add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="alpha",
        bumpver=False,
    )

    run()

    assert (package / "alpha" / "__init__.py").read_text() == '__version__ = "1.0.0"\n'


def test_an_existing_module_keeps_its_code(repo_root):
    package = add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version="1.0.0",
        module="alpha",
        bumpver=False,
    )
    write(package / "alpha" / "__init__.py", "FOO = 1\n")

    run()

    assert (package / "alpha" / "__init__.py").read_text() == (
        'FOO = 1\n\n__version__ = "1.0.0"\n'
    )


@pytest.mark.parametrize(
    "version",
    ["2026.11.6", "2024.10.24", "2026.11.6.1", "1.0", "0.1.0a1"],
)
def test_the_versioning_scheme_is_never_guessed(repo_root, version):
    """A version string does not say which scheme produced it

    `2024.10.24` and `2026.11.6` are valid X.Y.Z and valid dates both, so the
    old regex called them semver and `--bump patch` would have advanced
    `2024.10.24` to the invented date `2024.10.25`. `1.0` and `0.1.0a1` went
    the other way and got a date pattern bumpver rejects outright - at the
    first release, long after `init` exited 0.
    """
    add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version=version,
        module="alpha",
        bumpver=False,
    )

    result = run_bare()

    assert result.exit_code == USAGE_ERROR
    assert "--versioning" in result.output


@pytest.mark.parametrize(
    ("scheme", "version", "pattern"),
    [
        ("date", "2024.10.24", "YYYY.MM.DD[.INC0]"),
        ("semver", "1.0", "MAJOR.MINOR.PATCH"),
    ],
)
def test_the_stated_scheme_is_what_gets_written(repo_root, scheme, version, pattern):
    """Both of these are mis-classified by a regex over the version string"""
    package = add_package(
        repo_root,
        "alpha",
        dist_name="alpha",
        version=version,
        module="alpha",
        bumpver=False,
    )

    assert run("--versioning", scheme).exit_code == 0
    assert f'version_pattern = "{pattern}"' in (package / "pyproject.toml").read_text()


@pytest.mark.parametrize("quoted", ["'1.0.0'", '"1.0.0"'])
def test_the_version_matches_the_pattern_written_beside_it(repo_root, quoted):
    """Tomlkit keeps the file's own quoting, but the pattern always uses `"`

    A single-quoted version left as-is means bumpver's `version = "{version}"`
    pattern never matches, so `prepare` bumps every other declaration and
    leaves [project] version behind - silently, since bumpver does not treat
    a non-matching pattern as an error.
    """
    package = repo_root / "src" / "alpha"
    write(
        package / "pyproject.toml",
        f'[project]\nname = "alpha"\nversion = {quoted}\n',
    )
    write(package / "alpha" / "__init__.py", "")
    clear_caches()

    assert run("--versioning", "semver").exit_code == 0

    lines = (package / "pyproject.toml").read_text().splitlines()
    rendered = 'version = "{version}"'.replace("{version}", "1.0.0")

    # Whole line, not a substring: `current_version = "1.0.0"` in the bumpver
    # table ends with the same text and would match either way.
    assert rendered in lines


def test_an_already_configured_repo_needs_no_scheme(repo_root):
    """`[tool.bumpver]` already says which scheme the package uses

    Demanding the flag here would mean typing an answer that is then ignored,
    which is the common case on a repo that has been managed for a while.
    """
    add_package(repo_root, "alpha", dist_name="alpha", version="1.0.0", module="alpha")

    assert run_bare().exit_code == 0


def test_the_error_names_the_packages_that_need_a_scheme(repo_root):
    add_package(repo_root, "configured", dist_name="c", version="1.0.0", module="c")
    add_package(
        repo_root, "bare", dist_name="b", version="1.0.0", module="b", bumpver=False
    )

    result = run_bare()

    assert result.exit_code == USAGE_ERROR
    assert "bare" in result.output
    assert "configured" not in result.output
