import typing  # noqa: D100

import pluggy
from django.conf import settings
from django.utils.module_loading import import_string

from mitol.google_sheets_refunds.utils import RefundRequestRow


class RefundResult(typing.NamedTuple):  # noqa: D101
    result_type: str
    message: str = None


APP_NAME = "mitol.google_sheets_refunds"

hookimpl = pluggy.HookimplMarker(APP_NAME)
hookspec = pluggy.HookspecMarker(APP_NAME)


def get_plugin_manager():  # noqa: D103
    pm = pluggy.PluginManager(APP_NAME)

    for module_path in settings.MITOL_GOOGLE_SHEETS_REFUNDS_PLUGINS:
        plugin_cls = import_string(module_path)
        pm.register(plugin_cls())

    return pm


class RefundHooks:  # noqa: D101
    @hookspec
    def refunds_process_request(self, refund_request: RefundRequestRow) -> RefundResult:
        """Hook for processing refund requests"""  # noqa: D401
