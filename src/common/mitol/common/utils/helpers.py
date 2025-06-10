"""helper functions for utilities"""


def max_or_none(iterable):
    """Return the max of some iterable, or None if the iterable has no items

    Args:
        iterable (iterable): Some iterable
    Returns:
        max item or None
    """
    try:
        return max(iterable)
    except ValueError:
        return None
