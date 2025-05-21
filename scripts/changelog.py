from os import makedirs
from pathlib import Path
from textwrap import dedent, indent

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
def list_all(_ctx: Context, app: App):
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
        line.extend(["->", change.b_path])

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
def check(ctx: Context, project: Project, base: str, target: str):
    """Check for missing changelogs"""
    base_commit = project.repo.commit(base)
    target_commit = project.repo.commit(target)

    is_error = False

    for app in list_apps(project):
        changes = app.get_changes(base_commit=base_commit, target_commit=target_commit)

        if changes.has_source_changes and not changes.has_changelogd_changes:
            echo(f"Changelog(s) are missing in {app.relative_path} for these changes:")
            for change in changes.source_changes:
                _echo_change(change)
            is_error = True
            echo("")
        elif (
            not changes.has_source_changes
            and not changes.has_top_level_dependency_changes
            and changes.has_changelogd_changes
        ):
            echo(
                f"Changelog(s) are present in {app.relative_path} but there are no source changes:"  # noqa: E501
            )
            for change in changes.changelogd_changes:
                _echo_change(change)
            is_error = True
            echo("")

        # verify the fragments aren't empty
        with chdir(app.absolute_path):
            scriv = Scriv()
            fragments = scriv.fragments_to_combine()
            for fragment in fragments:
                fragment.read()

        empty_fragments = list(filter(lambda frag: not frag.content.strip(), fragments))

        if empty_fragments:
            echo(
                f"Changelog(s) are present in {app.relative_path} but have no content:"
            )
            for fragment in empty_fragments:
                echo(f"\t{fragment.path}")
            is_error = True
            echo("")

    if is_error:
        ctx.exit(1)


@changelog.command("create-renovate")
@option(
    "-m",
    "--message",
    help="The message for the changelog line",
    required=True,
)
@pass_project
def create_renovate(project: Project, message: str):
    """Create a changelog for renovate"""
    for changed in project.repo.head.commit.diff(None):
        if not changed.a_path.endswith("pyproject.toml"):
            continue

        echo(f"Adding changelog for: {changed.a_path}")

        with chdir(Path(changed.a_path).parent):
            scriv = Scriv()
            frag = scriv.new_fragment()

            frag.content = dedent(
                f"""
                ### Changed

                - {message}"""
            )
            frag.write()


if __name__ == "__main__":
    changelog()
