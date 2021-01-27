"""Utils tests"""
from datetime import datetime, timedelta

import pytest
import pytz

from mitol.common.utils.datetime import is_near_now, now_in_utc


def test_now_in_utc():
    """now_in_utc() should return the current time set to the UTC time zone"""
    now = now_in_utc()
    assert is_near_now(now)
    assert now.tzinfo == pytz.UTC


def test_is_near_now():
    """Test is_near_now for now"""
    now = datetime.now(tz=pytz.UTC)
    assert is_near_now(now) is True
    later = now + timedelta(seconds=6)
    assert is_near_now(later) is False
    earlier = now - timedelta(seconds=6)
    assert is_near_now(earlier) is False
    # with an epsilon specified
    assert is_near_now(now, timedelta(seconds=30)) is True
    later = now + timedelta(seconds=35)
    assert is_near_now(later, timedelta(seconds=30)) is False
    earlier = now - timedelta(seconds=35)
    assert is_near_now(earlier, timedelta(seconds=30)) is False
