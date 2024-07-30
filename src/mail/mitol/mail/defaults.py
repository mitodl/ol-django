"""Mail utils"""
from email.utils import formataddr

from django.contrib.auth import get_user_model

User = get_user_model()


def format_recipient(user: User):
    """
    Format a user as a recipient

    Args:
        user (User): the user

    Returns:
        str:
            the formatted recipient
    """
    # first_name last_name is the safest default since it follows django's default User model
    return formataddr((f"{user.first_name} {user.last_name}", user.email))


def can_email_user(user: User):
    """
    Returns True if the user has an email address

    Args:
        user (User): user to check

    Returns:
        bool: True if we can email this user
    """
    return bool(user.email)
