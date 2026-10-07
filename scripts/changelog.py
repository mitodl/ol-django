from collections.abc import Iterable
from os import makedirs
from pathlib import Path
from textwrap import dedent, indent

import toml
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


#: Paths a release PR may touch outside the app being released. The lockfile pins
#: every workspace member's version, so it moves with the bump (see release.py).
_RELEASE_SCOPE_EXEMPT = frozenset({"uv.lock"})


def _changed_paths(changes: Iterable[Diff]) -> set[str]:
    """Collect every path a diff touches, both sides of a rename included"""
    return {
        path
        for change in changes
        for path in (change.a_path, change.b_path)
        if path is not None
    }


def out_of_release_scope(paths: Iterable[str], app_path: Path) -> list[str]:
    """Return the paths a release of ``app_path`` has no business touching.

    Deliberately a pure function over paths: it is the whole security boundary of
    ``check-release-only`` and is unit-tested without a git fixture.
    """
    return sorted(
        path
        for path in paths
        if path not in _RELEASE_SCOPE_EXEMPT and not Path(path).is_relative_to(app_path)
    )


def _version_at(commit: Commit, app: App) -> str | None:
    """Read an app's declared version as of ``commit``, or None if it did not exist"""
    try:
        blob = commit.tree / str(app.relative_path / "pyproject.toml")
    except KeyError:
        return None

    return (
        toml.loads(blob.data_stream.read().decode()).get("project", {}).get("version")
    )


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
    is_error = False

    if _version_at(base_commit, app) == _version_at(target_commit, app):
        echo(
            f"{app.relative_path}/CHANGELOG.md is rewritten but the version in "
            "pyproject.toml is unchanged, so no release is being cut."
        )
        is_error = True

    for other in apps:
        if changes[other.module_name].has_code_changes:
            echo(f"Code is changing in {other.relative_path} alongside the release:")
            for change in changes[other.module_name].code_changes:
                _echo_change(change)
            is_error = True

    out_of_scope = out_of_release_scope(
        _changed_paths(base_commit.diff(target_commit)), app.relative_path
    )

    if out_of_scope:
        echo(f"Files outside {app.relative_path} are changing alongside the release:")
        for path in out_of_scope:
            echo(indent(path, "\t"))
        is_error = True

    if is_error:
        echo("")
        echo(
            "A release PR contains nothing but the release, so this one is not\n"
            "approved automatically. Split the rest out, or have it reviewed."
        )
        ctx.exit(1)

    echo(f"Release-only: {app.version_git_tag}")


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
