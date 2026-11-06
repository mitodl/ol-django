from functools import wraps

from click import Choice, Command, UsageError, make_pass_decorator, option
from cloup import Context, pass_context
from mitol.release_tools import config
from mitol.release_tools.apps import App, list_app_names
from mitol.release_tools.project import Project

pass_project = make_pass_decorator(Project)
pass_app = make_pass_decorator(App)


def _apply_app_option(func):
    """
    Adds an option -a/--app for the application directory
    """  # noqa: D401

    def _sole_app() -> str | None:
        """Pick the package to use when --app is omitted

        Resolved when the command runs, not when this decorator is applied:
        the layout comes from the repo being operated on, and the decorator
        is evaluated at import, before there is one.
        """
        if config.load().layout is not config.Layout.SINGLE:
            return None

        names = list_app_names()

        return names[0] if len(names) == 1 else None

    def _app_option(ctx: Context, param: str, value: str | None) -> str | None:  # noqa: ARG001
        if value is None:
            # Not `required=True`: whether an app must be named depends on the
            # repo, and click settles `required` before it ever sees one. The
            # package list has to be restored by hand, because click only adds
            # it for options it knows are required.
            known = ", ".join(list_app_names()) or "none found"
            message = f"Missing option '-a' / '--app'. Choose from: {known}."
            raise UsageError(message, ctx=ctx)

        app = ctx.ensure_object(App)
        app.module_name = value
        app.project = ctx.ensure_object(Project)
        return value

    return option(
        "-a",
        "--app",
        required=False,
        default=_sole_app,
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
