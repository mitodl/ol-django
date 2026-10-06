"""Shared behavior for the SCIM views"""

import functools

from django.db import transaction
from mitol.scim.adapters import lock_free_adapter


def _atomic_handler(handler):
    """Wrap a view handler so its body runs inside a transaction"""

    @functools.wraps(handler)
    def wrapper(self, request, *args, **kwargs):
        with transaction.atomic():
            return handler(self, request, *args, **kwargs)

    wrapper._scim_atomic = True  # noqa: SLF001
    return wrapper


class ScimLockingMixin:
    """
    Take the adapter's row lock, in a transaction, on exactly one set of methods.

    `UserAdapter` takes a `SELECT ... FOR UPDATE` when it is constructed, and
    Django rejects that outside a transaction. The methods that lock and the
    methods that open a transaction therefore have to be the same set: a method
    that locks without a transaction raises `TransactionManagementError`, and a
    method that opens a transaction without locking pays for one it has no use
    for. `LOCKING_METHODS` is that single set, and it drives both behaviors --
    splitting them across two mixins would let either half be applied on its
    own, and each half alone is broken.

    Every other method gets a lock-free adapter and no transaction. That is
    what keeps reads cheap: `django_scim` builds one adapter per serialized
    object (`GetView.get_single`, `FilterMixin._build_response`), so locking
    reads would re-fetch and lock every already-loaded row of a list or
    `/.search` page.

    The transaction is applied to each handler rather than around `dispatch()`
    because `django_scim.views.SCIMView.dispatch` catches every exception and
    renders it as a SCIM error response -- a block wrapping dispatch would see
    a clean return and commit the partial write rather than roll it back. For
    the same reason these views cannot rely on `ATOMIC_REQUESTS`.
    """

    #: Methods that modify the resource, so need the adapter's row lock and a
    #: transaction to hold it in. Declared rather than inferred from the verb
    #: because `/.search` is a POST that only reads.
    LOCKING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

    def __init_subclass__(cls, **kwargs):
        """Wrap the locking handlers this subclass resolves in a transaction.

        Done here rather than by overriding `post`/`put`/`patch`/`delete` so a
        subclass that defines its own handler still gets wrapped -- an
        inherited override would be silently shadowed by it, which is the
        failure mode this mixin exists to remove.
        """
        super().__init_subclass__(**kwargs)
        for method in cls.LOCKING_METHODS:
            name = method.lower()
            handler = getattr(cls, name, None)
            if handler is not None and not getattr(handler, "_scim_atomic", False):
                setattr(cls, name, _atomic_handler(handler))

    @property
    def scim_adapter(self):
        """Return the adapter class to serialize this request with"""
        adapter_cls = super().scim_adapter
        if self.request.method in self.LOCKING_METHODS:
            return adapter_cls
        return lock_free_adapter(adapter_cls)
