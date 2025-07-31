import functools
import random
from collections.abc import Callable
from functools import wraps

from django.utils.cache import get_max_age, patch_cache_control
from django_redis import get_redis_connection
from typing_extensions import ParamSpec

P = ParamSpec("P")


def cache_control_max_age_jitter(*args, **kwargs):  # noqa: ARG001
    def _cache_controller(viewfunc):
        @wraps(viewfunc)
        def _cache_controlled(request, *args, **kw):
            # Ensure argument looks like a request.
            if not hasattr(request, "META"):
                raise TypeError(  # noqa: TRY003
                    "cache_control_max_age_jitter didn't receive an HttpRequest. If you are "  # noqa: EM101, E501
                    "decorating a classmethod, be sure to use "
                    "@method_decorator."
                )
            response = viewfunc(request, *args, **kw)
            max_age = get_max_age(response)
            if not max_age:
                max_age = kwargs["max_age"]
            # add random delay upto 5 minutes
            kwargs["max_age"] = max_age + random.randint(1, 600)  # noqa: S311
            patch_cache_control(response, **kwargs)
            return response

        return _cache_controlled

    return _cache_controller


def single_task(
    timeout: int,
    raise_block: bool | None = True,  # noqa: FBT002, FBT001
    key: (str or Callable[[str, P.args, P.kwargs], str]) | None = None,
    cache_name: str | None = "redis",
) -> Callable:
    """
    Only allow one instance of a celery task to run concurrently
    Based on https://bit.ly/2RO2aav

    Args:
        timeout(int): Time in seconds to wait before relinquishing a lock
        raise_block(bool): If true, raise a BlockingIOError when locked
        key(str | Callable): Custom lock name or function to generate one
        cache_name(str): The name of the celery redis cache (default is "redis")

    Returns:
        Callable: wrapped function (typically a celery task)
    """

    def task_run(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            has_lock = False
            client = get_redis_connection(cache_name)
            if isinstance(key, str):
                lock_id = key
            elif callable(key):
                lock_id = key(func.__name__, args, kwargs)
            else:
                lock_id = func.__name__
            lock = client.lock(f"task-lock:{lock_id}", timeout=timeout)
            try:
                has_lock = lock.acquire(blocking=False)
                if has_lock:
                    return_value = func(*args, **kwargs)
                else:
                    if raise_block:
                        raise BlockingIOError
                    return_value = None
            finally:
                if has_lock and lock.locked():
                    lock.release()
            return return_value

        return wrapper

    return task_run
