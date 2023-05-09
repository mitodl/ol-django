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

from mitol.build_support.apps import App, Apps
from mitol.build_support.contextlib import chdir
from mitol.build_support.decorators import apps_option, pass_apps, pass_project, apps_option_no_default
from mitol.build_support.project import Project


@group("changelog")
@pass_context
def changelog(ctx):
    """Manage application changelogs"""

    makedirs("changelog.d", exist_ok=True)


changelog.add_command(apps_option_no_default(create))
changelog.add_command(apps_option_no_default(collect))


@changelog.command("list")
@apps_option()
@pass_apps
@pass_context
def list_all(ctx: Context, apps: Apps):
    """Print out the current set of changes"""
    for app in apps:
        with app.with_app_dir:
            scriv = Scriv()
            fragments = scriv.fragments_to_combine()

            echo(f"Changes for '{app.module_name}':")

            if not fragments:
                echo(indent("No changelog fragments present.", "\t"))

            echo(indent(f"Changelog fragments for {app.name}", "\t"))
            for fragment in fragments:
                echo(fragment.path)


def _echo_change(change: Diff):
    """Echo the change to stdout"""
    line = [change.change_type, change.a_path]

    if change.renamed:
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
@pass_apps
@pass_project
@pass_context
def check(ctx: Context, project: Project, apps: Apps, base: str, target: str):
    """Check for missing changelogs"""
    base_commit = project.repo.commit(base)
    target_commit = project.repo.commit(target)

    is_error = False

    for app in apps:
        app_rel_path = app.app_dir.relative_to(project.path)

        excluded_paths = [app_rel_path / "changelog.d/*", app_rel_path / "CHANGELOG.md"]

        def _is_excluded(path):
            return any([fnmatch(path, exclude) for exclude in excluded_paths])

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
                f"Changelog(s) are present in {app_rel_path} but there are no source changes:"
            )
            for change in changelogd_changes:
                _echo_change(change)
            is_error = True
            echo("")

        # verify the fragments aren't empty
        with app.with_app_dir:
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
