from collections.abc import Iterable
from os import makedirs
from pathlib import Path
from textwrap import dedent, indent

import tomllib
from click import echo
from click_log import simple_verbosity_option
from cloup import Context, group, option, pass_context
from git import Commit
from git.diff import Diff
from scriv.collect import collect
from scriv.create import create
from scriv.scriv import Scriv

from scripts.apps import App, list_apps
from scripts.changes import Changes
from scripts.contextlibs import chdir
from scripts.decorators import app_option, pass_app, pass_project
from scripts.project import Project
from scripts.release_scope import (
    content_violations,
    out_of_release_scope,
)


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


def _report_empty_fragments(app: App) -> bool:
    """Report an app's changelog fragments that have no content"""
    with chdir(app.absolute_path):
        scriv = Scriv()
        fragments = scriv.fragments_to_combine()
        for fragment in fragments:
            fragment.read()

    empty_fragments = [
        fragment for fragment in fragments if not fragment.content.strip()
    ]

    if not empty_fragments:
        return False

    echo(f"Changelog(s) are present in {app.relative_path} but have no content:")

    for fragment in empty_fragments:
        echo(f"\t{fragment.path}")

    echo("")

    return True


def _report_mixed_release(app: App, changes: Changes) -> bool:
    """Report an app whose release is being cut in the same PR as code changes"""
    if not (changes.has_changelog_md_changes and changes.has_code_changes):
        return False

    echo(
        f"CHANGELOG.md is being rewritten in {app.relative_path} alongside "
        "code changes:"
    )

    for change in changes.code_changes:
        _echo_change(change)

    echo(
        indent(
            "Cut the release in its own PR. Code changes ship with a\n"
            "changelog.d fragment; collecting those fragments into\n"
            "CHANGELOG.md is a separate change.",
            "\t",
        )
    )
    echo("")

    return True


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
            and changes.has_new_changelogd_fragments
        ):
            echo(
                f"Changelog(s) are present in {app.relative_path} but there are no source changes:"  # noqa: E501
            )
            for change in changes.new_changelogd_fragments:
                _echo_change(change)
            is_error = True
            echo("")

        if _report_mixed_release(app, changes):
            is_error = True

        if _report_empty_fragments(app):
            is_error = True

    if is_error:
        ctx.exit(1)


def _changed_paths(changes: Iterable[Diff]) -> set[str]:
    """Collect every path a diff touches, both sides of a rename included"""
    return {
        path
        for change in changes
        for path in (change.a_path, change.b_path)
        if path is not None
    }


def _released_version(commit: Commit, app: App) -> str:
    """Read the version being released out of the diff's target commit.

    Not `app.version`, which reads the working tree -- under
    `pull_request_target` that is the base branch, so it would print the old one.
    """
    blob = commit.tree / str(app.relative_path / "pyproject.toml")

    return tomllib.loads(blob.data_stream.read().decode())["project"]["version"]


def _released_app(ctx: Context, apps: list[App], changes: dict[str, Changes]) -> App:
    """Return the single app whose release this diff cuts, or exit non-zero"""
    released = [
        app for app in apps if changes[app.module_name].has_changelog_md_changes
    ]

    if len(released) == 1:
        return released[0]

    if not released:
        echo("No app's CHANGELOG.md is rewritten here, so this is not a release.")
    else:
        names = ", ".join(app.module_name for app in released)
        echo(f"More than one app is being released at once: {names}")
        echo(indent("Cut each release in its own PR.", "\t"))

    ctx.exit(1)
    raise AssertionError  # unreachable: ctx.exit raises


@changelog.command("check-release-only")
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
def check_release_only(ctx: Context, project: Project, base: str, target: str):
    """Exit 0 only if this diff is one app's release and nothing else.

    DELIBERATELY STRICTER THAN `check`. That command asks, per app, whether a
    CHANGELOG.md rewrite is mixed with code *under that app* -- it never looks
    outside `src/<app>/`, so a release PR that also edits `.github/workflows/`,
    `scripts/` or the root pyproject passes it today. That is fine for an advisory
    check a human reads. This one decides whether a PR is approved without a human,
    so anything outside the released app is a privilege-escalation path and is
    rejected by name.

    It also will not take a file on trust because a release is allowed to touch
    it. `check` exempts the two version declarations by PATH, so arbitrary code
    appended to the shipped `mitol/<app>/__init__.py` reads as a release; here
    every allowed file is checked for what changed inside it. See
    release_scope.py.

    Diffs from the MERGE BASE rather than `base..target`. `check` takes the two-dot
    diff, which folds commits landed on main since the branch point in as reverse
    changes; an approval gate cannot be wrong in either direction.
    """
    merge_bases = project.repo.merge_base(base, target)

    if not merge_bases:
        echo(f"No merge base between {base} and {target}.")
        ctx.exit(1)

    base_commit = merge_bases[0]
    target_commit = project.repo.commit(target)

    apps = list_apps(project)
    changes = {
        app.module_name: app.get_changes(base_commit, target_commit) for app in apps
    }

    app = _released_app(ctx, apps, changes)

    problems = [
        # Files a release is allowed to touch, checked for what changed inside
        # them -- see release_scope.py for why a path allowance is not enough.
        *content_violations(base_commit, target_commit, app),
        # Files a release is not allowed to touch at all.
        *(
            f"{path} is not part of releasing {app.relative_path}."
            for path in out_of_release_scope(
                _changed_paths(base_commit.diff(target_commit)), app.relative_path
            )
        ),
    ]

    for other in apps:
        for change in changes[other.module_name].code_changes:
            problems.append(  # noqa: PERF401
                f"{change.a_path or change.b_path} is code, not a release."
            )

    if problems:
        echo(f"Not a release-only diff ({len(problems)} problems):")
        for problem in sorted(set(problems)):
            echo(indent(problem, "\t"))
        echo("")
        echo(
            "A release PR contains nothing but the release, so this one is not\n"
            "approved automatically. Split the rest out, or have it reviewed."
        )
        ctx.exit(1)

    echo(f"Release-only: {app.name} {_released_version(target_commit, app)}")


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
