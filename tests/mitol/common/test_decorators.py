"""Tests for decorators"""
import pytest

from mitol.common.decorators import single_task


@pytest.mark.parametrize("has_lock", [False, True])
@pytest.mark.parametrize("raise_block", [False, True])
@pytest.mark.parametrize("input_arg", [None, "foo"])
@pytest.mark.parametrize("cache_name", [None, "foo"])
@pytest.mark.parametrize("lock_str", [None, "foo"])
def test_single_task(mocker, has_lock, raise_block, input_arg, cache_name, lock_str):
    """single_task should only allow 1 instance of inner task to run at same time"""
    mock_app = mocker.patch("mitol.common.decorators.get_redis_connection")
    mock_app.return_value.lock.return_value.acquire.side_effect = [True, has_lock]

    func = mocker.Mock(__name__="testfunc")
    decorated_func = single_task(
        timeout=2, raise_block=raise_block, cache_name=cache_name, lock_str=lock_str
    )
    args = [input_arg] if input_arg else []
    decorated_func(func)(*args)
    if raise_block and not has_lock:
        with pytest.raises(BlockingIOError):
            decorated_func(func)(*args)
    else:
        decorated_func(func)(*args)
    mock_app.return_value.lock.assert_any_call(
        f"{lock_str or 'testfunc'}-id-{input_arg or 'single'}", timeout=2
    )
    assert func.call_count == (2 if has_lock else 1)
