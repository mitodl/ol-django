"""Reading the repo's configuration out of the root pyproject.toml"""

from mitol.release_tools import config
from mitol.release_tools.config import DEFAULT_MEMBERS, Config, load

from tests.release_tools.conftest import clear_caches, write


def test_an_unconfigured_repo_gets_the_defaults(repo_root):
    """No root pyproject.toml at all still has to work

    The --app choices are built when `decorators` is imported, so raising here
    would make `ol-release --help` unavailable outside a checkout.
    """
    assert load(repo_root) == Config()
    assert load(repo_root).members == DEFAULT_MEMBERS


def test_a_pyproject_without_either_table_gets_the_defaults(repo_root):
    write(repo_root / "pyproject.toml", '[project]\nname = "root"\n')
    clear_caches()

    assert load(repo_root).members == DEFAULT_MEMBERS
    assert load(repo_root).exclude == frozenset()


def test_malformed_toml_falls_back_rather_than_crashing(repo_root):
    write(repo_root / "pyproject.toml", "[project\nthis is not toml")
    clear_caches()

    assert load(repo_root) == Config()


def test_both_tables_are_read(repo_root):
    write(
        repo_root / "pyproject.toml",
        """\
        [tool.uv.workspace]
        members = ["src/*", "testapp"]
        exclude = ["src/__pycache__"]

        [tool.ol-release]
        exclude = ["uvtestapp"]
        """,
    )
    clear_caches()
    settings = load(repo_root)

    assert settings.members == ("src/*", "testapp")
    assert settings.workspace_exclude == ("src/__pycache__",)
    assert settings.exclude == frozenset({"uvtestapp"})


def test_wrong_types_fall_back_rather_than_crashing(repo_root):
    write(
        repo_root / "pyproject.toml",
        """\
        [tool.uv.workspace]
        members = "src/*"

        [tool.ol-release]
        exclude = 3
        """,
    )
    clear_caches()
    settings = load(repo_root)

    assert settings.members == DEFAULT_MEMBERS
    assert settings.exclude == frozenset()


def test_an_empty_members_list_falls_back(repo_root):
    """An empty list would discover nothing, which is never what is meant"""
    write(repo_root / "pyproject.toml", "[tool.uv.workspace]\nmembers = []\n")
    clear_caches()

    assert load(repo_root).members == DEFAULT_MEMBERS


def test_the_cache_does_not_serve_one_root_for_another(repo_root, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    write(other / "pyproject.toml", '[tool.ol-release]\nexclude = ["beta"]\n')

    assert load(repo_root).exclude == frozenset()
    assert load(other).exclude == frozenset({"beta"})


def test_root_is_resolved_at_call_time(repo_root, monkeypatch):
    """Not as a default argument, which would bind PROJECT_ROOT at import"""
    write(repo_root / "pyproject.toml", '[tool.ol-release]\nexclude = ["gamma"]\n')
    monkeypatch.setattr(config, "PROJECT_ROOT", repo_root)
    clear_caches()

    assert load().exclude == frozenset({"gamma"})
