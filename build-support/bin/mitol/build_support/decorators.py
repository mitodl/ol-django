from functools import wraps

from click import Choice, Command, make_pass_decorator, option
from cloup import Context, pass_context

from mitol.build_support.apps import App, list_app_names
from mitol.build_support.project import Project

pass_project = make_pass_decorator(Project)
pass_app = make_pass_decorator(App)


def _apply_app_option(func):
    """
    Adds an option -a/--app for the application directory
    """  # noqa: D401

    def _app_option(ctx: Context, param: str, value: str) -> str:  # noqa: ARG001
        app = ctx.ensure_object(App)
        app.module_name = value
        return value

    return option(
        "-a",
        "--app",
        required=True,
        callback=_app_option,
        expose_value=False,
        type=Choice(list_app_names(), case_sensitive=True),
    )(func)


def with_app(func):
    """Contextualizes a command in an application directory"""

    if isinstance(func, Command):
        # we're trying to decorate a command/group, so decorate its callback instead
        func.callback = with_app(func.callback)
        return func

    @wraps(func)
    @pass_app
    @pass_context
    def _with_app(ctx, app, *args, **kwargs):
        ctx.with_resource(app.with_app_dir())
        return ctx.invoke(func, *args, **kwargs)

    return _with_app


def app_option(func):
    """Configures a command with a contextual app"""  # noqa: D401
    return with_app(_apply_app_option(func))


def _no_require_main_callback(ctx: Context, param: str, value: bool) -> bool:  # noqa: FBT001, ARG001
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
                "Cannot proceed with local git changes present.\n\nCommit or remove them and try again."  # noqa: E501
            )

        return ctx.invoke(func, *args, **kwargs)

    return wrapper
