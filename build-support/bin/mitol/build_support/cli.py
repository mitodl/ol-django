from cloup import Context, group, pass_context

from mitol.build_support.commands.changelog import changelog
from mitol.build_support.commands.release import release
from mitol.build_support.commands.version import version
from mitol.build_support.project import Project


@group()
@pass_context
def cli(ctx: Context):
    """CLI for build tools"""
    ctx.ensure_object(Project)


cli.add_command(changelog)
cli.add_command(release)
cli.add_command(version)

if __name__ == '__main__':
    cli()
