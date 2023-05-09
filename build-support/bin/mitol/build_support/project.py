from functools import cached_property
from pathlib import Path
from typing import List

from git import Repo

from mitol.build_support.apps import App, get_source_dir, list_app_dirs



class Project:
    """Representation for the ol-django project"""

    def __init__(self):
        self.path = Path.cwd()
        self.source_dir = get_source_dir(Path.cwd())

    @cached_property
    def repo(self) -> Repo:
        return Repo(self.path)
    
    @cached_property
    def apps(self):
        return {
            App(dir_path.stem, dir_path.absolute())
            for dir_path in list_app_dirs(self.path)
        }
    
    @cached_property
    def get_app(self, name: str) -> App:
        return self.apps[name]

    def app_paths(self) -> List[Path]:
        """List the apps in the repo"""
        return map(lambda app: app.path, self.apps.values())