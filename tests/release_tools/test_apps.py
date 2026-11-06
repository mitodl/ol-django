"""Package discovery and the metadata read off each pyproject.toml"""

import pytest
from mitol.release_tools.apps import (
    App,
    get_app_dir,
    list_app_names,
    list_app_paths,
    list_apps,
)
from mitol.release_tools.project import Project

from tests.release_tools.conftest import (
    add_package,
    clear_caches,
    write,
    write_workspace,
)


def test_no_source_dir_lists_nothing(repo_root, monkeypatch):
    """A missing src/ is empty, not an error

    The --app choices are built when the module is imported, so raising here
    would make even `--help` unavailable outside a checkout.
    """
    monkeypatch.setattr("mitol.release_tools.apps.PROJECT_ROOT", repo_root / "nowhere")

    assert list_app_paths() == []


def test_lists_only_directories_holding_a_pyproject(repo_root):
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    (repo_root / "src" / "not_a_package").mkdir()
    write(repo_root / "src" / "__init__.py", "")

    assert list_app_names() == ["alpha"]


def test_tool_ol_release_exclude_drops_a_member(repo_root):
    """A workspace member can be real and still not be ours to manage

    `src/uvtestapp` is a genuine uv member here - it is in `[tool.uv.sources]`
    and the root dependencies - so the workspace config cannot express that it
    is never released. That is what this table is for.
    """
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    add_package(repo_root, "skipme", dist_name="s", version="1.0.0", module="s")
    write_workspace(repo_root, ["src/*"])

    assert list_app_names() == ["alpha", "skipme"]

    write(
        repo_root / "pyproject.toml",
        """\
        [project]
        name = "root"
        version = "0.0.0"

        [tool.uv.workspace]
        members = ["src/*"]

        [tool.ol-release]
        exclude = ["skipme"]
        """,
    )
    clear_caches()

    assert list_app_names() == ["alpha"]


@pytest.mark.parametrize(
    ("version", "is_semver"),
    [("1.15.1", True), ("2026.10.30", False)],
)
def test_reads_version_scheme_from_bumpver(repo_root, version, is_semver):
    add_package(repo_root, "alpha", dist_name="a", version=version, module="a")
    app = App.create(Project(), "alpha")

    assert app.version == version
    assert app.is_semver is is_semver


def test_tag_and_version_files_come_from_pyproject(repo_root):
    """Metadata is read, never derived from the directory name

    edx-api-client keeps its code in edx_api/, so a tool that assumed
    mitol/<dir>/ would rewrite the wrong file.
    """
    add_package(
        repo_root,
        "edx_api_client",
        dist_name="edx-api-client",
        version="1.15.1",
        module="edx_api",
    )
    app = App.create(Project(), "edx_api_client")

    assert app.name == "edx-api-client"
    assert app.version_git_tag == "edx-api-client/v1.15.1"
    assert app.version_files == ["pyproject.toml", "edx_api/__init__.py"]


def test_list_apps_is_sorted_and_bound_to_the_project(repo_root):
    add_package(repo_root, "zulu", dist_name="z", version="1.0.0", module="z")
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    project = Project()

    assert [app.module_name for app in list_apps(project)] == ["alpha", "zulu"]
    assert all(app.project is project for app in list_apps(project))


def test_a_member_outside_src_is_discovered_and_resolves(repo_root):
    """`members = ["src/*", "testapp"]` is ol-django's real shape

    Scanning `src/` could not see such a member at all, and rebuilding its
    path as `src/<name>` pointed at a directory that does not exist.
    """
    add_package(
        repo_root, "toplevel", dist_name="t", version="1.0.0", module="t", under=""
    )
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    write_workspace(repo_root, ["src/*", "toplevel"])

    assert list_app_names() == ["alpha", "toplevel"]

    app = App.create(Project(), "toplevel")

    assert app.absolute_path == repo_root / "toplevel"
    assert str(app.relative_path) == "toplevel"
    assert app.name == "t"


def test_a_workspace_exclude_pattern_drops_a_member(repo_root):
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    add_package(repo_root, "beta", dist_name="b", version="1.0.0", module="b")
    write_workspace(repo_root, ["src/*"], exclude=["src/beta"])

    assert list_app_names() == ["alpha"]


def test_a_glob_match_without_a_pyproject_is_not_a_package(repo_root):
    """Uv tolerates these; ol-django's `src/dependency_floors` is one"""
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    (repo_root / "src" / "not_a_package").mkdir()
    write_workspace(repo_root, ["src/*"])

    assert list_app_names() == ["alpha"]


def test_a_file_matched_by_the_glob_is_skipped(repo_root):
    """open-edx-plugins has a `src/__init__.py` that `src/*` matches"""
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    write(repo_root / "src" / "__init__.py", "")
    write_workspace(repo_root, ["src/*"])

    assert list_app_names() == ["alpha"]


def test_no_workspace_table_falls_back_to_src(repo_root):
    """Keeps the tool usable in a repo that is not a uv workspace"""
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")

    assert list_app_names() == ["alpha"]


def test_a_basename_claimed_twice_fails_at_lookup_not_discovery(repo_root):
    """Listing must keep working: the --app choices are built at import"""
    add_package(repo_root, "dupe", dist_name="a", version="1.0.0", module="a")
    add_package(
        repo_root, "dupe", dist_name="b", version="1.0.0", module="b", under="plugins"
    )
    write_workspace(repo_root, ["src/*", "plugins/*"])

    assert list_app_names() == ["dupe"]

    with pytest.raises(ValueError, match="more than one workspace member"):
        get_app_dir("dupe")


def test_an_unknown_app_names_the_known_ones(repo_root):
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    write_workspace(repo_root, ["src/*"])

    with pytest.raises(ValueError, match=r"No such package: nope\. Found: alpha"):
        get_app_dir("nope")


def test_the_private_classifier_is_read(repo_root):
    add_package(
        repo_root,
        "alpha",
        dist_name="a",
        version="1.0.0",
        module="a",
        bumpver=False,
        extra='classifiers = ["Private :: Do Not Upload"]\n',
    )
    add_package(
        repo_root, "beta", dist_name="b", version="1.0.0", module="b", bumpver=False
    )
    write_workspace(repo_root, ["src/*"])
    project = Project()

    assert App.create(project, "alpha").is_private is True
    assert App.create(project, "beta").is_private is False
