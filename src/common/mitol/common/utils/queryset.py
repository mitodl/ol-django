from django.core.exceptions import FieldDoesNotExist
from django.db.models import Model


def is_prefetched(instance: Model, prefetch_name: str) -> bool:
    """
    Return True if the designated field was prefetched.

    This checks usages of select_related(), prefetch_related(), and prefetch().

    Args:
        instance (Model): any model instance
        prefetch_name (str): the field to check
    Returns:
        bool: True if the field was prefetched
    """
    try:
        field = instance._meta.get_field(prefetch_name)  # noqa: SLF001
        field_is_cached = field.is_cached(instance)
    except FieldDoesNotExist:
        field_is_cached = False

    return (
        # django's builtin select_related()
        field_is_cached
        or
        # django's builtin prefetch_related()
        prefetch_name in getattr(instance, "_prefetched_objects_cache", {})
        or
        # django-prefetch's prefetch()
        prefetch_name in instance.__dict__
    )
