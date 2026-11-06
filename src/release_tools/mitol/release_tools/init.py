"""Bootstrap a repository so the rest of `ol-release` has something to read

The other commands assume a shape the tool itself never creates: a per-package
``changelog.d/`` holding scriv's config, a ``CHANGELOG.md`` carrying scriv's
insert marker, a ``[tool.bumpver]`` table, and a ``__version__`` for bumpver to
rewrite. ``init`` creates whatever is missing and leaves everything else alone.
"""

import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from textwrap import dedent

import tomlkit
from click import Choice, echo, option
from cloup import Context, command, pass_context
from mitol.release_tools.apps import App, list_apps
from mitol.release_tools.project import Project
from mitol.release_tools.version import DUNDER_VERSION

#: Where the shared scriv entry-title template lives, relative to the repo root.
TEMPLATE_DIR = ".scriv"
TEMPLATE_NAME = "entry_title.md.j2"

#: Fragments are markdown in every repo, so that one template and one set of
#: scriv settings cover every repository the tool manages.
CHANGELOG_FORMAT = "md"
CHANGELOG_NAME = f"CHANGELOG.{CHANGELOG_FORMAT}"
INSERT_MARKER = "<!-- scriv-insert-here -->"

#: What the start of a released entry looks like: scriv writes an HTML anchor
#: above each one, and a hand-written changelog has only the heading.
ENTRY_START = ("<a id='changelog-", '<a id="changelog-', "## ")

#: Directories that hold `__init__.py` files which are never the package's own.
NOT_THE_PACKAGE = frozenset({"tests", "test", "docs", "migrations"})

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

VERSION_PATTERNS = {
    "semver": "MAJOR.MINOR.PATCH",
    "date": "YYYY.MM.DD[.INC0]",
}

CHANGELOG_HEADER = """\
# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

{marker}
"""

#: Appended when the package already has a hand-maintained changelog in a
#: format scriv will not append to. Collecting markdown fragments into a
#: reStructuredText file would produce a broken document, so that history stays
#: where it is and is linked from here instead.
LEGACY_POINTER = "Releases before this file begins are recorded in [{name}]({name}).\n"

NEXT_STEPS = """\
Still to do, none of which `init` can do for you:

  1. Call the tool from CI. The three steps that matter are:
       ol-release changelog check
       ol-release version check
       ol-release publish matrix
     The first two gate a PR; the third emits the publish matrix on main.
  2. Give the publish job `id-token: write` and an environment, conventionally
     named `pypi`, so PyPI Trusted Publishing can mint a token for it.
  3. Register a PyPI Trusted Publisher for every package, matching the owner,
     repository, workflow filename and environment the publish job actually
     uses. A package not yet on PyPI needs a *pending* publisher.
"""


@dataclass(frozen=True)
class Action:
    """One file `init` would write, with the content to write into it"""

    path: Path
    summary: str
    content: str


def _template_source() -> str:
    """Read the entry-title template shipped inside this package"""
    return (
        files("mitol.release_tools")
        .joinpath("templates", TEMPLATE_NAME)
        .read_text(encoding="utf-8")
    )


def _version_module(app: App) -> Path:
    """Find the importable package that should own the app's ``__version__``

    Identified structurally rather than by name: the outermost directories
    holding an ``__init__.py``, with test and docs trees discarded. That
    resolves ``mitol/common/`` under a PEP 420 namespace, ``edx_api/`` where
    the module shares nothing with the distribution name, and a flat
    ``ol_openedx_chat/`` alike. Ambiguity is an error rather than a guess:
    naming the wrong module means bumpver silently rewrites nothing.
    """
    # Filter on the path *within* the package. Matching against the absolute
    # path would discard every candidate in a checkout that happens to live
    # under a directory called `docs` or `tests`.
    inside = (
        path.relative_to(app.absolute_path)
        for path in app.absolute_path.rglob("__init__.py")
    )
    found = sorted(
        path.parent for path in inside if not NOT_THE_PACKAGE.intersection(path.parts)
    )
    outermost = [
        candidate
        for candidate in found
        if not any(other in candidate.parents for other in found)
    ]

    if len(outermost) == 1:
        return outermost[0] / "__init__.py"

    listed = ", ".join(str(path / "__init__.py") for path in outermost) or "none"
    message = (
        f"Cannot tell which module holds {app.name}'s version "
        f"(candidates: {listed}). Pass --version-file with a path relative to "
        f"{app.relative_path}."
    )
    raise ValueError(message)


def _versioning_scheme(app: App, override: str | None) -> str:
    """Resolve which version pattern to configure for an app"""
    if override:
        return override

    return "semver" if SEMVER.match(app.version) else "date"


def _scriv_ini(app: App, version_module: Path) -> str:
    """Render the scriv config for one package

    The ``file:`` path is relative to the **package** directory, not to the
    ``changelog.d`` the config sits in: scriv rejects the fragment directory as
    a base for any path starting ``../`` and falls back to the process's
    working directory, which every command has already chdir'd to the package.
    """
    up = "../" * len(app.relative_path.parts)
    template = f"{up}{TEMPLATE_DIR}/entry_title.${{config:format}}.j2"

    return dedent(
        f"""\
        [scriv]
        format = {CHANGELOG_FORMAT}
        md_header_level = 2
        entry_title_template = file: {template}
        version = literal: {version_module}: __version__
        """
    )


def _bumpver_tables(app: App, scheme: str, version_module: Path) -> str:
    """Render the bumpver tables for one package"""
    return dedent(
        f"""\

        [tool.bumpver]
        current_version = "{app.version}"
        version_pattern = "{VERSION_PATTERNS[scheme]}"

        [tool.bumpver.file_patterns]
        "pyproject.toml" = [
            'version = "{{version}}"',
        ]
        "{version_module}" = [
            '__version__ = "{{version}}"',
        ]
        """
    )


def _legacy_changelogs(app: App) -> list[Path]:
    """Hand-maintained changelogs in a format scriv will not append to"""
    return sorted(
        path
        for path in app.absolute_path.glob("CHANGELOG.*")
        if path.name != CHANGELOG_NAME
    )


def _new_changelog(app: App) -> str:
    """Render a fresh CHANGELOG.md, linking any history it does not contain"""
    body = CHANGELOG_HEADER.format(marker=INSERT_MARKER)
    pointers = "".join(
        LEGACY_POINTER.format(name=path.name) for path in _legacy_changelogs(app)
    )

    return f"{body}\n{pointers}" if pointers else body


def _with_insert_marker(existing: str) -> str:
    """Add scriv's insert marker to a changelog that lacks one

    It goes above the newest existing entry, so that collected entries land
    newest-first the way scriv expects. An entry starts at its anchor where
    scriv wrote one, and at its heading otherwise - putting the marker between
    the two would orphan the anchor onto the entry above it.
    """
    lines = existing.splitlines(keepends=True)

    for index, line in enumerate(lines):
        if line.startswith(ENTRY_START):
            head, tail = "".join(lines[:index]), "".join(lines[index:])
            return f"{head}{INSERT_MARKER}\n\n{tail}"

    separator = "" if existing.endswith("\n") else "\n"

    return f"{existing}{separator}\n{INSERT_MARKER}\n"


def _plan_repo(project: Project) -> list[Action]:
    """Work out which repo-level files are missing"""
    template = project.path / TEMPLATE_DIR / TEMPLATE_NAME

    if template.exists():
        return []

    return [
        Action(
            template,
            "shared scriv entry title template",
            _template_source(),
        )
    ]


def _plan_scriv(app: App, version_module: Path) -> list[Action]:
    """Plan the scriv config for one package"""
    scriv_ini = app.absolute_path / "changelog.d" / "scriv.ini"

    if scriv_ini.exists():
        return []

    return [Action(scriv_ini, "scriv config", _scriv_ini(app, version_module))]


def _plan_changelog(app: App) -> list[Action]:
    """Plan the changelog for one package"""
    changelog = app.absolute_path / CHANGELOG_NAME

    if not changelog.exists():
        return [
            Action(changelog, "changelog with scriv insert marker", _new_changelog(app))
        ]

    existing = changelog.read_text()

    if INSERT_MARKER in existing:
        return []

    return [
        Action(changelog, "add the scriv insert marker", _with_insert_marker(existing))
    ]


def _plan_bumpver(app: App, scheme: str, version_module: Path) -> list[Action]:
    """Plan the bumpver configuration for one package"""
    if "bumpver" in app.pyproject.get("tool", {}):
        return []

    pyproject = app.absolute_path / "pyproject.toml"
    # tomlkit rather than the toml used for reading: round-tripping through
    # toml would strip every comment in the file it rewrites.
    document = tomlkit.parse(pyproject.read_text())
    added = tomlkit.parse(_bumpver_tables(app, scheme, version_module))
    # Assign the two sub-tables one at a time. `document.update()` would take
    # the whole `[tool]` table from `added` and overwrite the existing one,
    # deleting every sibling `[tool.*]` section - hatch's build config among
    # them - while leaving the comments the choice of tomlkit was meant to
    # protect perfectly intact.
    tool = document.setdefault("tool", tomlkit.table(is_super_table=True))

    for name, table in added["tool"].items():
        tool[name] = table

    return [
        Action(
            pyproject,
            f"[tool.bumpver], {VERSION_PATTERNS[scheme]}",
            tomlkit.dumps(document),
        )
    ]


def _plan_dunder_version(app: App, version_module: Path) -> list[Action]:
    """Plan the ``__version__`` declaration bumpver needs something to rewrite"""
    module = app.absolute_path / version_module
    existing = module.read_text() if module.exists() else ""

    if DUNDER_VERSION.search(existing):
        return []

    # A blank line separates the declaration from existing code, but a new
    # module should not open with one.
    separator = "" if not existing else "\n" if existing.endswith("\n") else "\n\n"

    return [
        Action(
            module,
            f'__version__ = "{app.version}"',
            f'{existing}{separator}__version__ = "{app.version}"\n',
        )
    ]


def _plan_app(app: App, scheme: str, version_module: Path) -> list[Action]:
    """Work out which of one package's files are missing"""
    return [
        *_plan_scriv(app, version_module),
        *_plan_changelog(app),
        *_plan_bumpver(app, scheme, version_module),
        *_plan_dunder_version(app, version_module),
    ]


def _resolve_module(app: App, version_file: str | None) -> Path:
    """Resolve the version module, reusing bumpver's answer when it has one"""
    if version_file:
        # Keep the override inside the package it names. Without this a path
        # with enough `../` in it writes a module outside the repository, and
        # every bumpver pattern and scriv config then points at it.
        candidate = (app.absolute_path / version_file).resolve()

        if not candidate.is_relative_to(app.absolute_path.resolve()):
            message = (
                f"--version-file must stay inside {app.relative_path}; "
                f"{version_file} escapes it."
            )
            raise ValueError(message)

        return Path(version_file)

    configured = [
        path
        for path in app.pyproject.get("tool", {})
        .get("bumpver", {})
        .get("file_patterns", {})
        if path != "pyproject.toml"
    ]

    if len(configured) == 1:
        return Path(configured[0])

    return _version_module(app)


def _select_apps(
    project: Project, app_names: tuple[str, ...], *, version_file: str | None
) -> list[App]:
    """Resolve which packages to configure, rejecting a selection that cannot work"""
    discovered = list_apps(project)

    if not discovered:
        echo("No packages found. Run this from the root of the repository.")
        raise SystemExit(1)

    unknown = sorted(set(app_names) - {app.module_name for app in discovered})

    if unknown:
        known = ", ".join(sorted(app.module_name for app in discovered))
        echo(f"No such package: {', '.join(unknown)}. Found: {known}")
        raise SystemExit(1)

    apps = [app for app in discovered if not app_names or app.module_name in app_names]

    # The override names a path inside one package, so it cannot describe more
    # than one. Applied across a repo it would create that same path under
    # every package and point their configs at the wrong module.
    if version_file and len(apps) > 1:
        echo("--version-file applies to a single package; pass one --app with it.")
        raise SystemExit(1)

    return apps


def _explain(app: App, error: Exception) -> str:
    """Turn a failure on one package into a message naming that package

    A `KeyError` here is a `pyproject.toml` without a static `[project]
    version` - a Poetry layout, or `dynamic = ["version"]`. The tool has
    nothing to seed bumpver from, and saying so beats a bare traceback.
    """
    if isinstance(error, KeyError):
        return (
            f"{app.module_name}: no static version in [project]. "
            f"{app.relative_path}/pyproject.toml must declare one before "
            "its version can be managed."
        )

    return str(error)


def _describe(path: Path, project: Project) -> str:
    """Render a path relative to the repo root, for display"""
    try:
        return str(path.relative_to(project.path))
    except ValueError:
        return str(path)


@command()
@option(
    "-a",
    "--app",
    "app_names",
    multiple=True,
    # A free string rather than a Choice: the other commands build their
    # choices when this module is imported, which is fine for a repo the tool
    # already manages but wrong here, where the packages are discovered on the
    # filesystem as `init` runs. Validated against the live list below.
    help="Only configure these packages. Repeatable. Defaults to all of them.",
)
@option(
    "--versioning",
    type=Choice(sorted(VERSION_PATTERNS)),
    help="Version scheme to configure. Inferred per package when omitted.",
)
@option(
    "--version-file",
    help=(
        "Path to the module holding __version__, relative to the package "
        "directory. Only needed when it cannot be inferred."
    ),
)
@option(
    "--check",
    is_flag=True,
    help="Report what is missing and exit non-zero. Writes nothing.",
)
@option("--dry-run", is_flag=True, help="Show what would be written. Writes nothing.")
@pass_context
def init(  # noqa: PLR0913, PLR0917
    ctx: Context,
    app_names: tuple[str, ...],
    versioning: str | None,
    version_file: str | None,
    check: bool,  # noqa: FBT001
    dry_run: bool,  # noqa: FBT001
):
    """Create the changelog and version files the other commands expect"""
    project = ctx.ensure_object(Project)
    apps = _select_apps(project, app_names, version_file=version_file)
    planned = _plan_repo(project)

    for app in apps:
        try:
            module = _resolve_module(app, version_file)
            scheme = _versioning_scheme(app, versioning)
        except (KeyError, ValueError) as error:
            echo(_explain(app, error))
            raise SystemExit(1) from error

        planned.extend(_plan_app(app, scheme, module))

    if not planned:
        echo(f"Already configured: {len(apps)} package(s), nothing to do.")
        return

    for action in planned:
        echo(f"{_describe(action.path, project)} - {action.summary}")

    if check:
        echo(f"\n{len(planned)} item(s) missing. Run `ol-release init` to create them.")
        ctx.exit(1)

    if dry_run:
        echo(f"\n{len(planned)} item(s) would be written. Nothing was.")
        return

    for action in planned:
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_text(action.content)

    echo(f"\nConfigured {len(apps)} package(s).\n")
    echo(NEXT_STEPS)
