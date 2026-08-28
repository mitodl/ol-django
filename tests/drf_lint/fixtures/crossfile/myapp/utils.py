"""Fixture helpers living outside models.py, to exercise ORM004."""


def compute_stats(obj):
    """Queries through a plain function."""
    return obj.prices.all()


def pure_helper(value):
    """No query."""
    return value * 2
