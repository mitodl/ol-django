from bumpver import cli

from mitol.build_support.decorators import apps_option_no_default

version = cli.cli
version.name = "version"

grep = apps_option_no_default(cli.grep)
init = apps_option_no_default(cli.init)
show = apps_option_no_default(cli.show)
test = cli.test  # this doesn't require config so doesn't require --app
update = apps_option_no_default(cli.update)
