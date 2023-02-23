"""Utilities around library django apps"""
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import List

import toml

from mitol.build_support.contextlib import chdir

SOURCE_PATH = "src/mitol/"


def get_source_dir() -> Path:
    """Get the source directory"""
    return Path.cwd() / SOURCE_PATH


def get_app_dir(path: str) -> Path:
    """Get a directory path to a specific app"""
    return get_source_dir() / path


def list_apps() -> List[Path]:
    """List the apps in the repo"""
    return sorted(
        dir_path
        for dir_path in get_source_dir().iterdir()
        if dir_path.is_dir() and (dir_path / "__init__.py").exists()
    )


def list_app_names() -> List[str]:
    """List the app names"""
    return [name.stem for name in list_apps()]


class App:
    module_name: str

    @property
    def pyproject(self):
        with open(self.app_dir / "pyproject.toml", "r") as f:
            return toml.loads(f.read())

    @property
    def name(self):
        return self.pyproject["project"]["name"]

    @property
    def version(self):
        return self.pyproject["project"]["version"]

    @property
    def version_git_tag(self):
        return f"{self.name}/v{self.version}"

    @cached_property
    def app_dir(self) -> Path:
        return get_app_dir(self.module_name).absolute()

    @contextmanager
    def with_app_dir(self):
        with chdir(self.app_dir):
            yield
