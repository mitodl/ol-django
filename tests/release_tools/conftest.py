"""Fixtures building throwaway repositories for the release tooling to read"""

import textwrap
from pathlib import Path

import pytest
from click import Choice
from git import Repo
from mitol.release_tools import apps, project
from mitol.release_tools.cli import cli

NAMESPACED = "namespaced"
FLAT = "flat"


def write(path: Path, content: str) -> Path:
    """Write dedented content, creating parent directories as needed"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content))

    return path


def add_package(  # noqa: PLR0913
    root: Path,
    directory: str,
    *,
    dist_name: str,
    version: str,
    module: str,
    bumpver: bool = True,
    extra: str = "",
) -> Path:
    """Create one package under `root/src/`, optionally already configured"""
    package = root / "src" / directory
    # A version starting with the current millennium is date-based; anything
    # else is semver. Crude, but it keeps the fixtures to one argument.
    is_dated = version.startswith("2026.")
    pattern = "YYYY.MM.DD[.INC0]" if is_dated else "MAJOR.MINOR.PATCH"
    bumpver_tables = (
        f"""
        [tool.bumpver]
        current_version = "{version}"
        version_pattern = "{pattern}"

        [tool.bumpver.file_patterns]
        "pyproject.toml" = ['version = "{{version}}"']
        "{module}/__init__.py" = ['__version__ = "{{version}}"']
        """
        if bumpver
        else ""
    )

    write(
        package / "pyproject.toml",
        f"""\
        [project]
        name = "{dist_name}"
        version = "{version}"
        {textwrap.dedent(bumpver_tables)}{extra}""",
    )
    write(package / module / "__init__.py", "")

    return package


def refresh_app_choices():
    """Rebuild the --app choices against the packages that exist now

    `decorators.app_option` freezes them when the module is imported, which is
    right for a real invocation and wrong for a test, where the repository is
    built afterwards. This does what that import would have done.
    """
    commands = [cli, *cli.commands.values()]

    for command in commands:
        for sub in getattr(command, "commands", {}).values():
            commands.append(sub)  # noqa: PERF402

    for command in commands:
        for param in command.params:
            if "--app" in param.opts and isinstance(param.type, Choice):
                param.type.choices = apps.list_app_names()


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    """Build an empty git repo and point the tooling at it as its root

    `PROJECT_ROOT` is module state resolved at import, so it is patched rather
    than relying on the cwd, which commands change while they run.
    """
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    Repo.init(root)

    monkeypatch.setattr(project, "PROJECT_ROOT", root)
    monkeypatch.setattr(apps, "PROJECT_ROOT", root)
    monkeypatch.chdir(root)

    return root
