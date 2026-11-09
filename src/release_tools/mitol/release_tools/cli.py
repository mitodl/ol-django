"""The `ol-release` entry point"""

from cloup import Context, group, pass_context
from mitol.release_tools.changelog import changelog
from mitol.release_tools.init import init
from mitol.release_tools.project import Project
from mitol.release_tools.publish import publish
from mitol.release_tools.release import prepare
from mitol.release_tools.version import version


@group()
@pass_context
def cli(ctx: Context):
    """Manage changelogs, versions and PyPI releases for the packages in this repo"""
    ctx.ensure_object(Project)


cli.add_command(init)
cli.add_command(changelog)
cli.add_command(version)
cli.add_command(publish)
# `prepare` sits at the top level rather than under a `release` group of its
# own, which would hold nothing else.
cli.add_command(prepare)
