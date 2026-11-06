import subprocess

from click import Choice, echo, option
from cloup import Context, command, pass_context
from mitol.release_tools import changelog, version
from mitol.release_tools.apps import App
from mitol.release_tools.changes import LOCKFILE
from mitol.release_tools.decorators import app_option, pass_app


@command()
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
            f"No changelog fragments found in {app.relative_path / 'changelog.d'}.\n"
            "CI requires a changelog entry for a release, so add one with:\n"
            f"  ol-release changelog create --app {app.module_name}"
        )
        raise SystemExit(1)

    ctx.invoke(
        version.version.get_command(ctx, "update"), **({bump: True} if bump else {})
    )
    # keep=False lets scriv delete the fragments it consumed; they are then
    # committed as ordinary deletions alongside the version bump.
    ctx.invoke(changelog.collect, version=app.version, keep=False)

    # The lockfile pins every workspace member's version, so it moves with the
    # bump and belongs in the same commit. A repo without one is not
    # necessarily a uv repo at all, and failing here would leave the version
    # bumped and the fragments already collected.
    if (app.project.path / LOCKFILE).exists():
        subprocess.run(["uv", "lock"], check=True, cwd=app.project.path)  # noqa: S607
    else:
        echo(f"No {LOCKFILE}; skipping the lockfile refresh.")

    echo(
        f"\nPrepared {app.version_git_tag}.\n\n"
        "Commit these changes and open a PR containing nothing else. CI rejects "
        "a release PR that also changes code.\n"
        "Publishing to PyPI and tagging happen automatically once CI passes on "
        "main."
    )


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
