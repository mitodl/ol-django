import subprocess

from click import echo
from cloup import Context, group, pass_context

from scripts import changelog, version
from scripts.apps import App
from scripts.decorators import app_option, pass_app
from scripts.project import Project


@group()
@pass_context
def release(ctx: Context):
    ctx.ensure_object(Project)


@release.command()
@app_option
@pass_app
@pass_context
def prepare(ctx: Context, app: App):
    """Bump an app's version and fold its changelog fragments into CHANGELOG.md"""
    if not _fragment_paths(app):
        echo(
            f"No changelog fragments found in {app.module_name}/changelog.d.\n"
            "CI requires a changelog entry for a release, so add one with:\n"
            f"  uv run scripts/changelog.py create --app {app.module_name}"
        )
        raise SystemExit(1)

    ctx.invoke(version.version.get_command(ctx, "update"))
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
