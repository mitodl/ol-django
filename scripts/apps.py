"""Utilities around library django apps"""

from contextlib import contextmanager
from functools import cached_property
from pathlib import Path

import toml
from git import Commit

from scripts.changes import Changes
from scripts.contextlibs import chdir
from scripts.project import Project


class App:
    module_name: str | None = None
    project: Project | None = None

    @classmethod
    def create(cls, project: Project, module_name: str):
        app = App()
        app.project = project
        app.module_name = module_name
        return app

    @property
    def pyproject(self):
        with open(self.absolute_path / "pyproject.toml") as f:  # noqa: PTH123
            return toml.loads(f.read())

    @property
    def name(self) -> str:
        return self.pyproject["project"]["name"]

    @property
    def version(self) -> str:
        return self.pyproject["project"]["version"]

    @property
    def version_git_tag(self):
        return f"{self.name}/v{self.version}"

    @cached_property
    def absolute_path(self) -> Path:
        return get_app_dir(self.module_name).absolute()

    @cached_property
    def relative_path(self):
        return self.absolute_path.relative_to(self.project.path)

    @contextmanager
    def with_app_dir(self):
        with chdir(self.absolute_path):
            yield

    def get_changes(self, base_commit: Commit, target_commit: Commit) -> Changes:
        return Changes.from_app_commits(
            app=self, base_commit=base_commit, target_commit=target_commit
        )


def get_source_dir() -> Path:
    """Get the source directory"""
    return Path(__file__).parent.parent / "src"


def get_app_dir(path: str) -> Path:
    """Get a directory path to a specific app"""
    return get_source_dir() / path


def list_app_paths() -> list[Path]:
    """List the apps in the repo"""
    return sorted(
        dir_path
        for dir_path in get_source_dir().iterdir()
        if dir_path.is_dir()
        and (dir_path / "pyproject.toml").exists()
        and dir_path.stem != "uvtestapp"
    )


def list_app_names() -> list[str]:
    """List the app names"""
    return [name.stem for name in list_app_paths()]


def list_apps(project: Project) -> list[App]:
    """Get a list of App instances"""
    return [App.create(project, name) for name in list_app_names()]
