import re

from bumpver import cli
from click import echo
from cloup import Context, group, pass_context

from scripts.apps import App, list_apps
from scripts.decorators import app_option
from scripts.project import Project

DUNDER_VERSION = re.compile(r'^__version__\s*=\s*"(?P<version>[^"]+)"', re.MULTILINE)


@group()
@pass_context
def version(ctx: Context):
    """CLI for build tools"""
    ctx.ensure_object(Project)
    ctx.invoke(cli.cli, **ctx.params)


def _declared_versions(app: App) -> dict[str, str | None]:
    """Map each place an app declares its version to the value found there"""
    pyproject = app.pyproject
    init_path = app.absolute_path / "mitol" / app.module_name / "__init__.py"
    match = DUNDER_VERSION.search(init_path.read_text())

    return {
        "pyproject.toml [project] version": pyproject["project"]["version"],
        "pyproject.toml [tool.bumpver] current_version": pyproject["tool"]["bumpver"][
            "current_version"
        ],
        f"mitol/{app.module_name}/__init__.py __version__": (
            match.group("version") if match else None
        ),
    }


@version.command("check")
@pass_context
def check(ctx: Context):
    """Verify each app declares the same version in every place it records one"""
    project = ctx.ensure_object(Project)
    is_error = False

    for app in list_apps(project):
        declared = _declared_versions(app)

        if len(set(declared.values())) > 1:
            is_error = True
            echo(f"{app.module_name}: version declarations disagree")
            for location, value in declared.items():
                echo(f"  {value} in {location}")

    if is_error:
        echo(
            "\nBump versions with `uv run scripts/release.py prepare --app APPNAME`, "
            "which updates every declaration at once."
        )
        raise SystemExit(1)

    echo(f"Version declarations agree for all {len(list_apps(project))} apps.")


version.add_command(app_option(cli.grep))
version.add_command(app_option(cli.init))
version.add_command(app_option(cli.show))
version.add_command(cli.test)  # this doesn't require config so doesn't require --app
version.add_command(app_option(cli.update))


if __name__ == "__main__":
    version()
