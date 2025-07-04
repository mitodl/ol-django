"""Utils tests"""

from mitol.common.utils.helpers import max_or_none


def test_max_or_none():
    """
    Assert that max_or_none returns the max of some iterable, or None if the iterable has no items
    """
    assert max_or_none(i for i in [5, 4, 3, 2, 1]) == 5
    assert max_or_none([1, 3, 5, 4, 2]) == 5
    assert max_or_none([]) is None
