"""Utilities around library django apps"""
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import List, Dict

import toml

from mitol.build_support.contextlib import chdir

SOURCE_PATH = "src/mitol/"


def get_source_dir(root_dir: str) -> Path:
    """Get the source directory"""
    return root_dir / SOURCE_PATH


def get_app_dir(root_dir: str, path: str) -> Path:
    """Get a directory path to a specific app"""
    return get_source_dir(root_dir) / path


def list_app_dirs(root_dir: str) -> List[Path]:
    """List the apps in the repo"""
    return sorted(
        dir_path
        for dir_path in get_source_dir(root_dir).iterdir()
        if dir_path.is_dir() and (dir_path / "__init__.py").exists()
    )

def list_app_names(root_dir: str) -> List[str]:
    """List the app names"""
    return [name.stem for name in list_app_dirs(root_dir)]


class App:
    module_name: str
    app_dir: str

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

    @contextmanager
    def with_app_dir(self):
        with chdir(self.app_dir):
            yield



class Apps(Dict[str, App]): pass