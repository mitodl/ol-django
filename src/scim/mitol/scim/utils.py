"""Utils"""


def is_authenticated_predicate(user):
    """Verify that the user is active and staff"""
    return user.is_authenticated and user.is_active and user.is_staff
