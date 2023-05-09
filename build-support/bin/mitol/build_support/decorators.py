from functools import wraps
from pathlib import Path

from click import Choice, make_pass_decorator, option
from cloup import Context, pass_context

from mitol.build_support.apps import Apps, list_app_names
from mitol.build_support.project import Project

pass_project = make_pass_decorator(Project)
pass_apps = make_pass_decorator(Apps)

AllApps = object()


def apps_option(*, default=AllApps):
    """
    Adds an option -a/--app for the application directory
    """
    all_apps = list_app_names(Path.cwd())

    def _apps_option(func):
        def _callback(ctx: Context, param: str, value: str) -> str:
            project: Project = ctx.find_object(Project)
            ctx.obj = Apps(
                (app.module_name, app)
                for app in project.apps
                if app.module_name in value
            )
            return value

        return option(
            "-a",
            "--app",
            "apps",
            required=True,
            callback=_callback,
            expose_value=False,
            multiple=True,
            default=(all_apps if default is AllApps else default) or [],
            type=Choice(all_apps, case_sensitive=True),
        )(func)

    return _apps_option


apps_option_no_default = apps_option(default=None)


def _no_require_main_callback(ctx: Context, param: str, value: bool) -> bool:
    if not value:
        project = ctx.find_object(Project)
        if project.repo.active_branch.name != "main":
            ctx.fail("Must be on main branch.")

    return value


no_require_main = option(
    "--no-require-main",
    help="Don't require the main branch to be checked out.",
    callback=_no_require_main_callback,
    flag_value=True,
    default=False,
    expose_value=False,
)


def require_no_changes(func):
    @wraps(func)
    @pass_project
    @pass_context
    def wrapper(ctx: Context, project: Project, *args, **kwargs):
        if project.repo.is_dirty():
            ctx.fail(
                "Cannot proceed with local git changes present.\n\nCommit or remove them and try again."
            )

        return ctx.invoke(func, *args, **kwargs)

    return wrapper
