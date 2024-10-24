
from click import echo, pass_context
from cloup import Context, group, option

from mitol.build_support.apps import App
from mitol.build_support.commands import changelog, version
from mitol.build_support.decorators import (
    app_option,
    no_require_main,
    pass_app,
    pass_project,
)
from mitol.build_support.project import Project


@group()
def release():
    pass


@release.command()
# @require_no_changes
@no_require_main
@app_option
@option(
    "--push",
    help="Push the release commit and tag.",
    flag_value=True,
    default=False,
)
@pass_app
@pass_project
@pass_context
def create(ctx: Context, project: Project, app: App, push: bool):  # noqa: FBT001, ARG001
    """Create a new release"""

    ctx.invoke(changelog.check)
    ctx.invoke(version.update)
    # keep=True so we can remove these properly (i.e. in Git) later
    ctx.invoke(changelog.collect, version=app.version, keep=True)

    # copy and remove irrelevant params
    params = ctx.params.copy()
    params.pop("push", None)

    ctx.invoke(commit_and_tag, **params)

    if push:
        ctx.invoke(push_to_remote, **params)


@release.command()
@app_option
@pass_app
@pass_project
def commit_and_tag(project: Project, app: App):
    """Commit outstanding changes and tag them as a release"""
    repo = project.repo
    tag_name = app.version_git_tag

    repo.index.add(
        [
            app.app_dir / "mitol" / app.module_name / "__init__.py",
            app.app_dir / "pyproject.toml",
            app.app_dir / "CHANGELOG.md",
        ]
    )

    repo.index.remove(
        [
            app.app_dir / "changelog.d" / "*.md",
        ]
    )

    repo.index.commit(f"Release {tag_name}")

    echo(f"Tagging {tag_name}")
    repo.create_tag(tag_name)


@release.command()
@app_option
@pass_app
@pass_project
def push_to_remote(project: Project, app: App):
    """Push the latest release commit and tag to the remote"""
    # git push origin --follow-tags {tag} HEAD
    project.repo.remote("origin").push(
        [app.version_git_tag, "HEAD"],
        follow_tags=True,
    )
