from functools import cached_property
from pathlib import Path

from git import Repo


class Project:
    """Representation for the ol-django project"""

    def __init__(self):
        self.path = Path.cwd()

    @cached_property
    def repo(self) -> Repo:
        return Repo(self.path)
