from click import echo, pass_context
from cloup import Context, group, option

from mitol.build_support.apps import Apps
from mitol.build_support.commands import changelog, version
from mitol.build_support.decorators import (
    apps_option,
    no_require_main,
    pass_apps,
    pass_project,
    require_no_changes,
)
from mitol.build_support.project import Project


@group()
def release():
    pass


@release.command()
@require_no_changes
@no_require_main
@apps_option()
@option(
    "--push",
    help="Push the release commit and tag.",
    flag_value=True,
    default=False,
)
@pass_apps
@pass_project
@pass_context
def create(ctx: Context, project: Project, apps: Apps, push: bool):
    """Create a new release"""
    for app in apps:
        args = [f"--app={app.module_name}"]
        ctx.invoke(changelog.check, args=args)
        ctx.invoke(version.update, args=args)
        ctx.invoke(changelog.collect, version=app.version)

        # copy and remove irrelevant params
        params = ctx.params.copy()
        params.pop("push", None)

        ctx.invoke(commit_and_tag, **params)

        if push:
            ctx.invoke(push_to_remote, **params)


@release.command()
@apps_option()
@pass_apps
@pass_project
def commit_and_tag(project: Project, apps: Apps):
    """Commit outstanding changes and tag them as a release"""
    for app in apps:
        repo = project.repo
        tag_name = app.version_git_tag

        repo.index.add(
            [
                app.app_dir / "__init__.py",
                app.app_dir / "pyproject.toml",
                app.app_dir / "CHANGELOG.md",
            ]
        )
        repo.index.commit(f"Release {tag_name}")

        echo(f"Tagging {tag_name}")
        repo.create_tag(tag_name)


@release.command()
@apps_option()
@pass_apps
@pass_project
def push_to_remote(project: Project, apps: Apps):
    """Push the latest release commit and tag to the remote"""
    for app in apps:
        # git push origin --follow-tags {tag} HEAD
        project.repo.remote("origin").push(
            [app.version_git_tag, "HEAD"],
            follow_tags=True,
        )
