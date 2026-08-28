"""Shared helpers for the drf_lint tests.

Cross-file rules need more than one file, so most tests build a throwaway
package under ``tmp_path`` rather than checking an inline string.  The
``project`` fixture keeps that close to the existing inline style: write a few
sources, then ask which rules fire.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from mitol.drf_lint.checker import CheckContext, check_file
from mitol.drf_lint.index import ProjectIndex, build_index, module_for_path
from mitol.drf_lint.rules.base import Violation

#: A model exercising every shape the index needs to understand.
MODELS_SOURCE = """
from functools import cached_property

from django.db import models

from myapp.utils import compute_stats


class AbstractTimestamped(models.Model):
    @property
    def revision_count(self):
        return self.revisions.count()


class Author(models.Model):
    name = models.CharField(max_length=255)


class Course(AbstractTimestamped):
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    topics = models.ManyToManyField("Topic")
    name = models.CharField(max_length=255)

    @property
    def run_count(self):
        return self.runs.count()

    @property
    def run_list(self):
        return self.runs.all()

    @property
    def plain_name(self):
        return self.name.upper()

    @property
    def author_name(self):
        return self.author.name

    @property
    def summary(self):
        return self.get_price()

    @cached_property
    def cached_runs(self):
        return self.runs.all()

    def get_price(self):
        return compute_stats(self)

    def cheap(self):
        return 42

    @property
    def loop_a(self):
        return self.loop_b

    @property
    def loop_b(self):
        return self.loop_a

    @property
    def marked_clean(self):  # drf-lint: no-query
        return self.runs.all()

    @property
    def calls_marked_clean(self):
        return self.marked_clean


class Track(Course):
    @property
    def run_count(self):
        return 0
"""

UTILS_SOURCE = """
def compute_stats(obj):
    return obj.prices.all()


def pure_helper(value):
    return value * 2
"""


class Project:
    """A disposable Python package tree the index can be built over."""

    def __init__(self, root: Path) -> None:
        """Mark *root* as a project root and start with an empty tree."""
        self.root = root
        (root / "pyproject.toml").write_text("")
        self._index: ProjectIndex | None = None

    def write(self, relative: str, source: str) -> Path:
        """Write *source* to *relative*, creating packages along the way."""
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        directory = path.parent
        while directory != self.root:
            marker = directory / "__init__.py"
            if not marker.exists():
                # Only create it once; touching an existing one would bump its
                # mtime and invalidate it in the cache tests.
                marker.touch()
            directory = directory.parent
        path.write_text(dedent(source).lstrip())
        self._index = None
        return path

    def with_models(self) -> Project:
        """Add the standard ``myapp.models`` / ``myapp.utils`` pair."""
        self.write("myapp/utils.py", UTILS_SOURCE)
        self.write("myapp/models.py", MODELS_SOURCE)
        return self

    def index(self, **kwargs) -> ProjectIndex:
        """Build (and memoise) the project index."""
        if self._index is None:
            self._index = build_index(self.root, use_cache=False, **kwargs)
        return self._index

    def context(self, relative: str, **kwargs) -> CheckContext:
        """Build a :class:`CheckContext` wired to this project for *relative*."""
        module, _ = module_for_path(self.root / relative, self.root)
        return CheckContext(index=self.index(), module=module, **kwargs)

    def check(self, relative: str, **kwargs) -> list[Violation]:
        """Run the checker over *relative* with cross-file analysis enabled."""
        return check_file(self.root / relative, self.context(relative, **kwargs))

    def rules(self, relative: str, **kwargs) -> list[str]:
        """Just the rule codes reported for *relative*, in report order."""
        return [v.rule for v in self.check(relative, **kwargs)]

    def serializer(self, source: str, name: str = "myapp/serializers.py") -> str:
        """Write a serializer module and return its relative path."""
        self.write(name, source)
        return name


@pytest.fixture
def project(tmp_path: Path) -> Project:
    """Return an empty disposable project rooted at ``tmp_path``."""
    return Project(tmp_path)


@pytest.fixture
def modelled(project: Project) -> Project:
    """Return a project already carrying the standard models and helpers."""
    return project.with_models()
