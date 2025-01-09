from fnmatch import fnmatch
from os import makedirs
from textwrap import indent

from click import echo
from click_log import simple_verbosity_option
from cloup import Context, group, option, pass_context
from git.diff import Diff
from scriv.collect import collect
from scriv.create import create
from scriv.scriv import Scriv

from scripts.apps import App, list_apps
from scripts.contextlibs import chdir
from scripts.decorators import app_option, pass_app, pass_project
from scripts.project import Project


@group("changelog")
@pass_context
def changelog(ctx):
    """Manage application changelogs"""
    ctx.ensure_object(Project)

    makedirs("changelog.d", exist_ok=True)  # noqa: PTH103


changelog.add_command(app_option(create))
changelog.add_command(app_option(collect))


@changelog.command("list")
@app_option
@pass_app
@pass_context
def list_all(ctx: Context, app: App):  # noqa: ARG001
    """Print out the current set of changes"""
    scriv = Scriv()
    fragments = scriv.fragments_to_combine()

    if not fragments:
        echo("No changelog fragments present.")

    echo(f"Changelog fragments for {app.name}")
    for fragment in fragments:
        echo(fragment.path)


def _echo_change(change: Diff):
    """Echo the change to stdout"""
    line = [change.change_type, change.a_path]

    if change.renamed_file:
        line.extend(["->", changelog.b_path])

    echo(indent(" ".join(line), "\t"))


@changelog.command()
@option(
    "-b",
    "--base",
    help="The base ref to diff against for changes.",
    default="origin/main",
)
@option(
    "-t",
    "--target",
    help="The target ref to diff against the base.",
    default="HEAD",
)
@simple_verbosity_option()
@pass_project
@pass_context
def check(ctx: Context, project: Project, base: str, target: str):  # noqa: C901
    """Check for missing changelogs"""
    base_commit = project.repo.commit(base)
    target_commit = project.repo.commit(target)

    is_error = False

    for app_abs_path in list_apps():
        app_rel_path = app_abs_path.relative_to(project.path)

        excluded_paths = [app_rel_path / "changelog.d/*", app_rel_path / "CHANGELOG.md"]

        def _is_excluded(path):
            return any([fnmatch(path, exclude) for exclude in excluded_paths])  # noqa: B023, C419

        source_changes = [
            change
            for change in base_commit.diff(target_commit, paths=[app_rel_path])
            if not _is_excluded(change.a_path) and not _is_excluded(change.b_path)
        ]
        has_source_changes = len(source_changes) > 0

        changelogd_changes = base_commit.diff(
            target_commit, paths=[app_rel_path / "changelog.d"]
        )
        has_changelogd_changes = len(changelogd_changes) > 0

        if has_source_changes and not has_changelogd_changes:
            echo(f"Changelog(s) are missing in {app_rel_path} for these changes:")
            for change in source_changes:
                _echo_change(change)
            is_error = True
            echo("")
        elif not has_source_changes and has_changelogd_changes:
            echo(
                f"Changelog(s) are present in {app_rel_path} but there are no source changes:"  # noqa: E501
            )
            for change in changelogd_changes:
                _echo_change(change)
            is_error = True
            echo("")

        # verify the fragments aren't empty
        with chdir(app_abs_path):
            scriv = Scriv()
            fragments = scriv.fragments_to_combine()
            for fragment in fragments:
                fragment.read()

        empty_fragments = list(filter(lambda frag: not frag.content.strip(), fragments))

        if empty_fragments:
            echo(f"Changelog(s) are present in {app_rel_path} but have no content:")
            for fragment in empty_fragments:
                echo(f"\t{fragment.path}")
            is_error = True
            echo("")

    if is_error:
        ctx.exit(1)


if __name__ == "__main__":
    changelog()
