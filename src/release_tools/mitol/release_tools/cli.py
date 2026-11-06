"""The `ol-release` entry point"""

from click import echo
from cloup import Context, Group, group, pass_context
from mitol.release_tools import config
from mitol.release_tools.apps import NoPackagesError
from mitol.release_tools.changelog import changelog
from mitol.release_tools.init import init
from mitol.release_tools.project import Project
from mitol.release_tools.publish import publish
from mitol.release_tools.release import prepare
from mitol.release_tools.version import version


class ReleaseGroup(Group):
    """Reports a missing-packages error as a message, not a traceback"""

    def invoke(self, ctx: Context):
        try:
            return super().invoke(ctx)
        except NoPackagesError as error:
            echo(str(error), err=True)
            raise SystemExit(1) from error


@group(cls=ReleaseGroup)
@pass_context
def cli(ctx: Context):
    """Manage changelogs, versions and PyPI releases for the packages in this repo"""
    ctx.ensure_object(Project)
    settings = config.load()

    if settings.unknown_tag_format is not None:
        echo(
            f'Ignoring [tool.ol-release] tag-format = "{settings.unknown_tag_format}": '
            "it must render with {name} and {version} only.",
            err=True,
        )

    declared = settings.unknown_layout

    if declared is not None:
        # Loading cannot raise - it happens while `decorators` is imported -
        # so the only place to say this is here, before any command runs.
        # Left unsaid, a typo means zero packages and every gate passing.
        known = ", ".join(sorted(member.value for member in config.Layout))
        echo(
            f'Ignoring [tool.ol-release] layout = "{declared}": '
            f"expected one of {known}.",
            err=True,
        )


cli.add_command(init)
cli.add_command(changelog)
cli.add_command(version)
cli.add_command(publish)
# `prepare` sits at the top level rather than under a `release` group of its
# own, which would hold nothing else.
cli.add_command(prepare)
