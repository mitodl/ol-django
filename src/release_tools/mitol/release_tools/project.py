from functools import cached_property
from pathlib import Path

from git import Repo

# Resolved once, at import, rather than per call: commands chdir into an app
# directory while they run, so anything re-reading the cwd later would resolve
# the project root to whichever app happened to be current.
PROJECT_ROOT = Path.cwd()


class Project:
    """Representation for the project being released"""

    def __init__(self):
        self.path = PROJECT_ROOT

    @cached_property
    def repo(self) -> Repo:
        return Repo(self.path)
