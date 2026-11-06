"""Package discovery and the metadata read off each pyproject.toml"""

import pytest
from mitol.release_tools.apps import App, list_app_names, list_app_paths, list_apps
from mitol.release_tools.project import Project

from tests.release_tools.conftest import add_package, write


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


def test_uvtestapp_is_never_listed(repo_root):
    add_package(repo_root, "alpha", dist_name="a", version="1.0.0", module="a")
    add_package(repo_root, "uvtestapp", dist_name="u", version="1.0.0", module="u")

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
