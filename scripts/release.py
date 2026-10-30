import datetime
import subprocess
import sys
from pathlib import Path

from click import Choice, echo, option
from click import Path as ClickPath
from cloup import Context, group, pass_context

from scripts import changelog, version
from scripts.apps import App, list_apps
from scripts.decorators import app_option, pass_app, pass_project
from scripts.project import Project


@group()
@pass_context
def release(ctx: Context):
    ctx.ensure_object(Project)


@release.command()
@app_option
@option(
    "--bump",
    type=Choice(["major", "minor", "patch"]),
    help="Which part to bump. Required for, and only accepted by, semver apps.",
)
@pass_app
@pass_context
def prepare(ctx: Context, app: App, bump: str | None):
    """Bump an app's version and fold its changelog fragments into CHANGELOG.md"""
    # bumpver derives a date-based version on its own, but refuses to bump a
    # MAJOR.MINOR.PATCH one without being told which part.
    if app.is_semver and bump is None:
        echo(
            f"{app.module_name} uses semantic versioning; pass --bump major|minor|patch"
        )
        raise SystemExit(1)
    if not app.is_semver and bump is not None:
        echo(f"{app.module_name} uses date-based versioning; --bump does not apply")
        raise SystemExit(1)

    if not _fragment_paths(app):
        echo(
            f"No changelog fragments found in {app.module_name}/changelog.d.\n"
            "CI requires a changelog entry for a release, so add one with:\n"
            f"  uv run scripts/changelog.py create --app {app.module_name}"
        )
        raise SystemExit(1)

    ctx.invoke(
        version.version.get_command(ctx, "update"), **({bump: True} if bump else {})
    )
    # keep=False lets scriv delete the fragments it consumed; they are then
    # committed as ordinary deletions alongside the version bump.
    ctx.invoke(changelog.collect, version=app.version, keep=False)

    # The lockfile pins every workspace member's version, so it moves with the
    # bump and belongs in the same commit.
    subprocess.run(["uv", "lock"], check=True, cwd=app.project.path)  # noqa: S607

    echo(
        f"\nPrepared {app.version_git_tag}.\n\n"
        "Commit these changes and open a PR containing nothing else. CI rejects "
        "a release PR that also changes code.\n"
        "Publishing to PyPI and tagging happen automatically once CI passes on "
        "main."
    )


@release.command()
@option(
    "--body-file",
    type=ClickPath(dir_okay=False, writable=True, path_type=Path),
    required=True,
    help="Where to write the pull request body.",
)
@option(
    "--title-file",
    type=ClickPath(dir_okay=False, writable=True, path_type=Path),
    required=True,
    help="Where to write the pull request title.",
)
@pass_project
def weekly(project: Project, body_file: Path, title_file: Path):
    """Prepare every date-versioned app that has changelog fragments waiting

    Writes a pull request title and body describing what was cut, and writes
    neither when nothing was - so a caller can treat the files' absence as
    "nothing to release" rather than parsing output for it.
    """
    waiting = [app for app in list_apps(project) if _fragment_paths(app)]
    # A semver app needs a person to say which part to bump, because what the
    # changes mean is not something the calendar can answer. Report those and
    # cut the rest, whose versions the date decides.
    deferred = [app for app in waiting if app.is_semver]
    cutting = [app for app in waiting if not app.is_semver]

    if not cutting:
        echo("No date-versioned app has changelog fragments waiting.")
        if deferred:
            echo(f"\n{_deferred_section(deferred)}")
        return

    cut = []
    for app in cutting:
        previous = app.version
        _prepare_in_subprocess(project, app)
        cut.append((app, previous))

    title_file.write_text(f"{_title(cut)}\n")
    body_file.write_text(_body(cut, deferred))

    echo(f"\nPrepared {len(cut)} release(s):")
    for app, previous in cut:
        echo(f"\t{app.name} {previous} -> {app.version}")
    echo(f"\nWrote {title_file} and {body_file}.")


def _prepare_in_subprocess(project: Project, app: App) -> None:
    """Run ``prepare`` for one app in a process of its own

    ``prepare`` is wrapped by ``app_option``, which chdirs into the app
    directory for the life of the command and never changes back, so calling it
    in-process once per app would resolve each app relative to the previous
    one's directory. A process per app is also exactly what a person does,
    which leaves one code path to keep working instead of two.
    """
    subprocess.run(  # noqa: S603
        [
            sys.executable,
            str(project.path / "scripts" / "release.py"),
            "prepare",
            "--app",
            app.module_name,
        ],
        check=True,
        cwd=project.path,
    )


def _title(cut: list[tuple[App, str]]) -> str:
    """Build the pull request title

    A single app keeps the ``Release <package>/v<version>`` form the
    repository's release commits already use. Several do not: spelling out
    fifteen of them produces a title nothing will display in full.
    """
    if len(cut) == 1:
        app, _ = cut[0]
        return f"Release {app.version_git_tag}"

    today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()

    return f"Release {len(cut)} packages ({today})"


def _body(cut: list[tuple[App, str]], deferred: list[App]) -> str:
    """Build the pull request body from the entries scriv just collected"""
    sections = [
        "Cut by the weekly release workflow (`.github/workflows/release.yml`)."
        " Every package below has had its `changelog.d/` fragments folded into"
        " its `CHANGELOG.md` and its version bumped everywhere it is declared."
        "\n\nMerging this releases all of them: the `publish` job in `ci.yml`"
        " uploads each package whose version on `main` is not yet on PyPI, then"
        " tags it.",
    ]

    sections.extend(
        f"## {app.name} {previous} -> {app.version}\n\n{_changelog_entry(app)}"
        for app, previous in cut
    )

    if deferred:
        sections.append(_deferred_section(deferred))

    return "\n\n".join(sections) + "\n"


def _deferred_section(deferred: list[App]) -> str:
    """Report the apps left for a person, and the command that releases them"""
    lines = [
        "## Not released automatically",
        "",
        "These version semantically, so which part to bump is a judgement"
        " about what the changes mean rather than something the date settles."
        " Cut them by hand:",
        "",
    ]
    lines.extend(
        f"- `{app.name}` ({app.version}, {len(_fragment_paths(app))} waiting):"
        f" `uv run scripts/release.py prepare --app {app.module_name}"
        " --bump major|minor|patch`"
        for app in deferred
    )

    return "\n".join(lines)


def _changelog_entry(app: App) -> str:
    """Read back the CHANGELOG.md section scriv just wrote for this version

    scriv precedes each entry with an ``<a id='changelog-VERSION'></a>``
    anchor, so an entry runs from its own anchor to the next one, or to the end
    of the file for an app's first release. Reading the file back rather than
    re-reading the fragments means the pull request says exactly what the
    changelog says, including anything scriv reformatted on the way in.
    """
    changelog_md = (app.absolute_path / "CHANGELOG.md").read_text()
    anchor = f"<a id='changelog-{app.version}'></a>"

    start = changelog_md.find(anchor)
    if start < 0:
        return f"_No `{anchor}` section found in CHANGELOG.md._"

    body_start = start + len(anchor)
    next_anchor = changelog_md.find("<a id='changelog-", body_start)
    end = next_anchor if next_anchor >= 0 else len(changelog_md)

    entry = changelog_md[body_start:end].strip()
    # Drop scriv's own `## [version] - date` heading. The section heading this
    # entry sits under already names the package and both versions.
    lines = entry.splitlines()
    if lines and lines[0].startswith("## "):
        entry = "\n".join(lines[1:]).strip()

    return entry


def _fragment_paths(app: App) -> list:
    """List an app's uncollected changelog fragments"""
    changelog_dir = app.absolute_path / "changelog.d"

    return [
        path
        for path in sorted(changelog_dir.glob("*"))
        if path.is_file()
        and path.name != "scriv.ini"
        and not path.name.startswith(("README", "."))
    ]


if __name__ == "__main__":
    release()
