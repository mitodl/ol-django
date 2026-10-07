"""Decide whether a diff is one app's release and nothing else.

`changelog.py check-release-only` gates an automatic pull request approval with
this, so allowing a file by PATH is not enough. Everything a release is allowed
to touch is a shipped artifact: `mitol/<app>/__init__.py` is imported by every
consumer of the package, the app's `pyproject.toml` decides its dependencies and
how it is built, and `uv.lock` decides what CI installs while CI holds the PyPI
publishing identity. So each one is checked for WHAT changed inside it.

Nothing here executes any of the content it reads. Blobs are pulled out of the
object database and parsed, never imported, and the working tree the caller runs
from is the base branch rather than the branch being judged.
"""

from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any

import tomllib
from git import Commit
from packaging.version import InvalidVersion, Version

from scripts.apps import App
from scripts.version import DUNDER_VERSION

#: The only path outside the released app a release may touch. Checked by content
#: in `_lockfile_violations`, because "uv.lock changed" and "uv.lock recorded the
#: new version" are very different diffs.
LOCKFILE = "uv.lock"


def out_of_release_scope(paths: Iterable[str], app_path: Path) -> list[str]:
    """Return the paths a release of ``app_path`` has no business touching"""
    return sorted(
        path
        for path in paths
        if path != LOCKFILE and not Path(path).is_relative_to(app_path)
    )


def _blob(commit: Commit, path: str) -> bytes | None:
    """Read a file out of the object database, or None if it is not there"""
    try:
        return (commit.tree / path).data_stream.read()
    except KeyError:
        return None


def declared_version(commit: Commit, app: App) -> str | None:
    """Read the `[project] version` an app's pyproject declares at a commit.

    Reads the commit's blob, not `app.version`, which reads the working tree --
    under `pull_request_target` that is the base branch, so it would answer with
    the old version.
    """
    raw = _blob(commit, str(app.relative_path / "pyproject.toml"))

    if raw is None:
        return None

    return tomllib.loads(raw.decode()).get("project", {}).get("version")


def _version_violations(base: Commit, target: Commit, app: App) -> list[str]:
    """Require a version present at both ends of the diff, and higher at the end"""
    path = str(app.relative_path / "pyproject.toml")
    before = declared_version(base, app)
    after = declared_version(target, app)

    if before is None or after is None:
        return [f"{path} does not declare a version at both ends of the diff."]

    if before == after:
        return [
            f"{app.relative_path}/CHANGELOG.md is rewritten but the version in "
            f"pyproject.toml is still {before}, so no release is being cut."
        ]

    try:
        went_up = Version(after) > Version(before)
    except InvalidVersion:
        return [f"{path}: {after!r} is not a version this can compare."]

    if not went_up:
        return [f"{path}: version went from {before} to {after}, which is not up."]

    return []


def _dunder_violations(base: Commit, target: Commit, app: App) -> list[str]:
    """`__init__.py` is a shipped module: only its `__version__` line may move"""
    path = str(app.relative_path / "mitol" / app.module_name / "__init__.py")
    before, after = _blob(base, path), _blob(target, path)

    if before is None or after is None:
        return [f"{path} is added or removed, which a release does not do."]

    if DUNDER_VERSION.sub("", before.decode()) != DUNDER_VERSION.sub(
        "", after.decode()
    ):
        return [
            f"{path} changes something other than its `__version__` line. "
            "That module is imported by everyone who installs the package."
        ]

    return []


def _changelogd_violations(base: Commit, target: Commit, app: App) -> list[str]:
    """`changelog.d/` may only lose fragments; everything else in it is code.

    This is the one directory inside the app that the code checks never see:
    `changes.py` excludes `*/changelog.d/*` from `source_changes`, so nothing in
    it ever counts as `code_changes`. That exclusion is right for the advisory
    `check` and wrong for an approval gate -- `scriv.ini` lives here, and scriv
    executes `command:`-prefixed config values on the next `collect`, so an
    edit to it (or any file smuggled in alongside the fragments) must be a
    violation, not a blind spot. Collecting fragments only ever deletes files,
    which is all a release is allowed to do here.
    """
    changelogd = app.relative_path / "changelog.d"
    problems = []

    for change in base.diff(target, paths=[str(changelogd)]):
        if change.change_type == "D" and Path(change.a_path).name != "scriv.ini":
            continue

        path = change.b_path or change.a_path
        problems.append(
            f"{path} is not a fragment deletion; cutting a release only ever "
            f"removes files from {changelogd}."
        )

    return sorted(problems)


def _without_version_keys(doc: dict[str, Any]) -> dict[str, Any]:
    """Copy a pyproject with the two declarations a release moves removed"""
    stripped = deepcopy(doc)
    stripped.get("project", {}).pop("version", None)
    stripped.get("tool", {}).get("bumpver", {}).pop("current_version", None)

    return stripped


def _pyproject_violations(base: Commit, target: Commit, app: App) -> list[str]:
    """Only the two version declarations may differ; dependencies may not"""
    path = str(app.relative_path / "pyproject.toml")
    before, after = _blob(base, path), _blob(target, path)

    if before is None or after is None:
        return []  # already reported by `_version_violations`

    if _without_version_keys(tomllib.loads(before.decode())) != _without_version_keys(
        tomllib.loads(after.decode())
    ):
        return [
            f"{path} changes something other than the version declarations - "
            "a dependency, a build setting, or tool configuration."
        ]

    return []


def _lock_entries(raw: bytes, released: str) -> tuple[dict[str, Any], dict, list[str]]:
    """Split a lockfile into its non-package body, its packages, and any collisions.

    Keyed on name AND version, because a lockfile legitimately carries several
    versions of one package. The released distribution is keyed on name alone,
    with its version dropped, since moving that is the whole point of the diff.

    COLLISIONS ARE REPORTED, NOT RESOLVED. Two entries sharing a key would
    otherwise overwrite each other, and only the survivor would be compared --
    so a second `django 5.0` carrying a hostile `source` could hide behind the
    legitimate one and never be looked at. uv may well reject such a lockfile
    itself, but this is not the place to assume that.
    """
    doc = tomllib.loads(raw.decode())
    packages: dict[tuple[str, ...], dict] = {}
    collisions = []

    for package in doc.pop("package", []):
        name = package.get("name")

        if name == released:
            key, entry = (name,), {k: v for k, v in package.items() if k != "version"}
        else:
            key, entry = (name, package.get("version")), package

        if key in packages:
            collisions.append(_label(key))
            continue

        packages[key] = entry

    return doc, packages, collisions


def _label(key: tuple[str, ...]) -> str:
    """Name a locked package for a message. The released one carries no version"""
    return " ".join(str(part) for part in key)


def _lockfile_violations(base: Commit, target: Commit, app: App) -> list[str]:
    """Allow the lockfile to record the new version and nothing else.

    A release moves exactly one line here. Anything else -- a repointed `source`,
    an edited hash, a package added or dropped -- would be installed by every
    later `uv sync`, including the CI jobs that publish to PyPI.
    """
    before, after = _blob(base, LOCKFILE), _blob(target, LOCKFILE)

    if before is None or after is None or before == after:
        return []

    body_before, packages_before, collisions_before = _lock_entries(before, app.name)
    body_after, packages_after, collisions_after = _lock_entries(after, app.name)

    if collisions := sorted(set(collisions_before + collisions_after)):
        return [
            f"{LOCKFILE} locks the same package more than once, which hides one "
            f"entry behind another: {', '.join(collisions)}."
        ]

    if body_before != body_after:
        return [f"{LOCKFILE} changes something outside its package list."]

    added = sorted(map(_label, packages_after.keys() - packages_before.keys()))
    dropped = sorted(map(_label, packages_before.keys() - packages_after.keys()))

    if added or dropped:
        return [
            f"{LOCKFILE} adds or drops locked packages: {', '.join(added + dropped)}."
        ]

    changed = sorted(
        key[0] for key in packages_before if packages_before[key] != packages_after[key]
    )

    if changed:
        return [
            f"{LOCKFILE} rewrites locked packages other than the version being "
            f"released: {', '.join(changed)}."
        ]

    return []


def content_violations(base: Commit, target: Commit, app: App) -> list[str]:
    """Every way this diff touches a release-allowed file it should not have"""
    return [
        *_version_violations(base, target, app),
        *_dunder_violations(base, target, app),
        *_pyproject_violations(base, target, app),
        *_lockfile_violations(base, target, app),
        *_changelogd_violations(base, target, app),
    ]
