"""Hooks for the API gateway user sync process."""

from django.conf import settings
from django.utils.module_loading import import_string


def run_user_sync_hooks(request, user, decoded_headers, *, created):
    """
    Invoke the MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS callables in order.

    Hooks are dotted import paths, resolved at call time. Each is called with
    keyword arguments (request, user, decoded_headers, created) and should do
    its own dirty-checking before writing. Exceptions propagate to the caller,
    rolling back the sync transaction.
    """
    for hook_path in settings.MITOL_APIGATEWAY_USERINFO_SYNC_HOOKS:
        import_string(hook_path)(
            request=request,
            user=user,
            decoded_headers=decoded_headers,
            created=created,
        )
