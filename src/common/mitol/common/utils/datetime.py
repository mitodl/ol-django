"""Datetime utilities"""
from datetime import datetime, timedelta

import pytz


def now_in_utc() -> datetime:
    """
    Get the current time in UTC
    Returns:
        datetime.datetime: A datetime object for the current time
    """
    return datetime.now(tz=pytz.UTC)


def is_near_now(time: datetime, epsilon: timedelta = timedelta(seconds=5)) -> bool:
    """
    Returns true if time is within five seconds or so of now
    Args:
        time (datetime.datetime):
            The time to test
        epsilon (datetime.timedelta):
            The allowed delta in time
    Returns:
        bool:
            True if near now, false otherwise
    """
    now = now_in_utc()
    return now - epsilon < time < now + epsilon
