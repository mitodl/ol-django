from bumpver import cli
from cloup import Context, group, pass_context

from scripts.decorators import app_option
from scripts.project import Project


@group()
@pass_context
def version(ctx: Context):
    """CLI for build tools"""
    ctx.ensure_object(Project)
    ctx.invoke(cli.cli, **ctx.params)


version.add_command(app_option(cli.grep))
version.add_command(app_option(cli.init))
version.add_command(app_option(cli.show))
version.add_command(cli.test)  # this doesn't require config so doesn't require --app
version.add_command(app_option(cli.update))


if __name__ == "__main__":
    version()
