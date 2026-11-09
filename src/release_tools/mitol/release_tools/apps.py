"""Utilities around library django apps"""

from contextlib import chdir, contextmanager
from fnmatch import fnmatch
from functools import cache, cached_property
from pathlib import Path

import tomllib
from git import Commit
from mitol.release_tools import config
from mitol.release_tools.changes import Changes
from mitol.release_tools.project import PROJECT_ROOT, Project

#: The standard marker for a distribution that must never reach an index.
PRIVATE_CLASSIFIER = "Private :: Do Not Upload"


class NoPackagesError(Exception):
    """Raised when a command needs packages and discovery found none"""


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
        with (self.absolute_path / "pyproject.toml").open("rb") as f:
            return tomllib.load(f)

    @property
    def name(self) -> str:
        return self.pyproject["project"]["name"]

    @property
    def version(self) -> str:
        return self.pyproject["project"]["version"]

    @property
    def version_git_tag(self):
        """The git tag for this app's current version

        A monorepo has to say which package a tag belongs to; a
        single-package repo conventionally does not. Either default can be
        overridden with ``[tool.ol-release] tag-format``.
        """
        settings = config.load()
        template = settings.tag_format or config.TAG_FORMATS[settings.layout]

        return template.format(name=self.name, version=self.version)

    @property
    def is_private(self) -> bool:
        """Whether the distribution is marked as never to be uploaded

        ``Private :: Do Not Upload`` is the standard classifier for a package
        that must not reach PyPI. It says nothing about whether the changelog
        and version are managed, so it gates publishing only.
        """
        classifiers = self.pyproject.get("project", {}).get("classifiers", [])

        return PRIVATE_CLASSIFIER in classifiers

    @property
    def bumpver(self) -> dict:
        """The app's ``[tool.bumpver]`` table, empty when it has none

        Discovery follows the uv workspace, which says nothing about whether a
        member is set up for release, so an app without this table is a shape
        the tool has to survive rather than crash on.
        """
        return self.pyproject.get("tool", {}).get("bumpver", {})

    @property
    def version_files(self) -> list[str]:
        """App-relative paths of the files bumpver rewrites when the version changes

        Read from ``[tool.bumpver.file_patterns]`` rather than assumed, because not
        every app keeps its code under ``mitol/<appname>/`` (edx-api-client's is
        ``edx_api/``). Falls back to the pyproject alone for an app with no
        bumpver table, which still declares its version there.
        """
        return list(self.bumpver.get("file_patterns", ["pyproject.toml"]))

    @property
    def is_semver(self) -> bool:
        """Whether the app versions with MAJOR.MINOR.PATCH instead of a date"""
        return "MAJOR" in self.bumpver.get("version_pattern", "")

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
    """Get the source directory

    Retained for the common single-root layout; discovery itself goes through
    the workspace members, which need not all sit under one directory.
    """
    return PROJECT_ROOT / "src"


def _is_excluded(path: Path, patterns: tuple[str, ...]) -> bool:
    """Whether a root-relative path matches any uv workspace exclude pattern"""
    return any(fnmatch(str(path), pattern) for pattern in patterns)


def _discover() -> tuple[dict[str, Path], dict[str, list[Path]]]:
    """Map each package's directory name to its path, from the uv workspace"""
    return _discover_in(PROJECT_ROOT)


@cache
def _discover_in(root: Path) -> tuple[dict[str, Path], dict[str, list[Path]]]:
    """Discover the packages under one repository root

    Keyed on the root rather than cached bare, so that the memo cannot outlive
    the root it was computed for.

    Returns the mapping and, separately, any name claimed by more than one
    member. Members may sit at different depths, so two can share a basename;
    that is reported at lookup rather than raised here, because the ``--app``
    choices are built at import and a raise would take ``--help`` with it.
    """
    settings = config.load(root)

    if settings.layout is config.Layout.SINGLE:
        return _discover_single(root), {}

    found: dict[str, Path] = {}
    clashes: dict[str, list[Path]] = {}

    for pattern in settings.members:
        for path in sorted(root.glob(pattern)):
            relative = path.relative_to(root)

            # uv tolerates a member glob matching a file, or a directory with
            # no pyproject.toml; neither is a package this tool can manage.
            if (
                not path.is_dir()
                or not (path / "pyproject.toml").exists()
                or _is_excluded(relative, settings.workspace_exclude)
                or path.name in settings.exclude
            ):
                continue

            if path.name in found and found[path.name] != path:
                clashes.setdefault(path.name, [found[path.name]]).append(path)
                continue

            found[path.name] = path

    return found, clashes


def _discover_single(root: Path) -> dict[str, Path]:
    """Treat the repo root as the one package

    Keyed on the distribution name rather than the directory name: the
    directory is whatever the checkout happens to be called, which differs
    between machines and CI runners and would make ``--app`` unreproducible.
    """
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError, ValueError):
        return {}

    project = data.get("project")
    name = project.get("name") if isinstance(project, dict) else None

    # Same discipline as the config loader: this runs while `decorators` is
    # being imported to build the --app choices, so anything unexpected has to
    # mean "no packages" rather than take `ol-release --help` down with it.
    return {name: root} if isinstance(name, str) and name else {}


def get_app_dir(name: str) -> Path:
    """Get the directory of a specific app"""
    found, clashes = _discover()

    if name in clashes:
        listed = ", ".join(str(path) for path in clashes[name])
        message = f"{name} matches more than one workspace member: {listed}"
        raise ValueError(message)

    if name not in found:
        known = ", ".join(sorted(found)) or "none"
        message = f"No such package: {name}. Found: {known}"
        raise ValueError(message)

    return found[name]


def list_app_paths() -> list[Path]:
    """List the packages in the repo

    Empty rather than an error when nothing matches: the ``--app`` choices are
    built at import time, so a repo root that declares no workspace - or no
    repo root at all - would otherwise make ``--help`` unavailable.
    """
    found, _ = _discover()

    return sorted(found.values())


def list_app_names() -> list[str]:
    """List the app names"""
    return sorted(_discover()[0])


def list_apps(project: Project) -> list[App]:
    """Get a list of App instances"""
    return [App.create(project, name) for name in list_app_names()]


def require_apps(project: Project) -> list[App]:
    """List the repo's packages, refusing to carry on when there are none

    A gate that iterates nothing and reports success is indistinguishable
    from one that passed, which is how a misconfigured repo silently never
    releases. Every command that checks or publishes goes through here.
    """
    apps = list_apps(project)

    if apps:
        return apps

    settings = config.load()

    if settings.layout is config.Layout.SINGLE:
        detail = "the root pyproject.toml declares no [project] name"
    else:
        detail = (
            "check [tool.uv.workspace] members, or set\n"
            '[tool.ol-release] layout = "single" if this repo is one package'
        )

    message = f"No packages found: {detail}."
    raise NoPackagesError(message)
