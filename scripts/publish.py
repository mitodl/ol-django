"""Support for the automated PyPI publish workflow"""

import json
import urllib.error
import urllib.request
from http import HTTPStatus

from click import echo
from cloup import Context, group, pass_context

from scripts.apps import App, list_apps
from scripts.project import Project

PYPI_RELEASE_URL = "https://pypi.org/pypi/{name}/{version}/json"
REQUEST_TIMEOUT = 30


def is_published(name: str, version: str) -> bool:
    """Determine whether an exact version of a package is already on PyPI"""
    request = urllib.request.Request(  # noqa: S310
        PYPI_RELEASE_URL.format(name=name, version=version),
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310
            return response.status == HTTPStatus.OK
    except urllib.error.HTTPError as error:
        if error.code == HTTPStatus.NOT_FOUND:
            return False
        # Anything else (rate limiting, an outage) is unknown rather than
        # unpublished. Raising keeps the workflow from republishing a release
        # that already exists.
        raise


def _matrix_entry(app: App) -> dict[str, str]:
    return {
        "app": app.module_name,
        "package": app.name,
        "version": app.version,
        "tag": app.version_git_tag,
    }


@group()
@pass_context
def publish(ctx: Context):
    """CLI for the publish workflow"""
    ctx.ensure_object(Project)


@publish.command()
@pass_context
def matrix(ctx: Context):
    """Emit a GitHub Actions matrix of the packages that need publishing"""
    project = ctx.ensure_object(Project)

    echo(
        json.dumps(
            {
                "include": [
                    _matrix_entry(app)
                    for app in list_apps(project)
                    if not is_published(app.name, app.version)
                ]
            }
        )
    )


if __name__ == "__main__":
    publish()
