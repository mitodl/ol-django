from functools import cached_property  # noqa: D100
from pathlib import Path

from git import Repo


class Project:
    """Representation for the ol-django project"""

    def __init__(self):  # noqa: D107
        self.path = Path.cwd()

    @cached_property
    def repo(self) -> Repo:  # noqa: D102
        return Repo(self.path)
