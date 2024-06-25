from bumpver import cli  # noqa: D100

from mitol.build_support.decorators import app_option

version = cli.cli
version.name = "version"

grep = app_option(cli.grep)
init = app_option(cli.init)
show = app_option(cli.show)
test = cli.test  # this doesn't require config so doesn't require --app
update = app_option(cli.update)
