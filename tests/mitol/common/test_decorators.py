"""Tests for decorators"""

from typing import List

import pytest
from mitol.common.decorators import single_task


def task_obj_lock(
    func_name: str, args: List[object], kwargs: dict  # noqa: FA100, ARG001
) -> str:  # @pylint:unused-argument
    """
    Determine a task lock name for a specific task function and object id
    """
    return f"{func_name}_{args[0] if args else 'single'}"


@pytest.mark.parametrize("has_lock", [False, True])
@pytest.mark.parametrize("raise_block", [False, True])
@pytest.mark.parametrize("input_arg", [None, "foo"])
@pytest.mark.parametrize("cache_name", [None, "foo"])
@pytest.mark.parametrize("key", [None, "foo", task_obj_lock])
def test_single_task(mocker, has_lock, raise_block, input_arg, cache_name, key):  # noqa: PLR0913
    """single_task should only allow 1 instance of inner task to run at same time"""
    mock_app = mocker.patch("mitol.common.decorators.get_redis_connection")
    mock_app.return_value.lock.return_value.acquire.side_effect = [True, has_lock]

    func = mocker.Mock(__name__="testfunc")
    decorated_func = single_task(
        timeout=2, raise_block=raise_block, cache_name=cache_name, key=key
    )
    args = [input_arg] if input_arg else []
    decorated_func(func)(*args)
    if raise_block and not has_lock:
        with pytest.raises(BlockingIOError):
            decorated_func(func)(*args)
    else:
        decorated_func(func)(*args)
    if key is None:
        expected_lock_name = func.__name__
    if isinstance(key, str):
        expected_lock_name = key
    elif callable(key):
        expected_lock_name = key(func.__name__, args, [])
    mock_app.return_value.lock.assert_any_call(
        f"task-lock:{expected_lock_name}", timeout=2
    )
    assert func.call_count == (2 if has_lock else 1)
