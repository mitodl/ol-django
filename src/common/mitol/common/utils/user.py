"""User utilities."""

import logging
import re

from django.contrib.auth import get_user_model
from django.db import IntegrityError

from mitol.common.constants import (
    USERNAME_COLLISION_ATTEMPTS,
    USERNAME_INVALID_CHAR_PATTERN,
    USERNAME_MAX_LEN,
    USERNAME_SEPARATOR,
    USERNAME_SEPARATOR_REPLACE_PATTERN,
    USERNAME_TURKISH_I_CHARS,
    USERNAME_TURKISH_I_CHARS_REPLACEMENT,
)

from .helpers import max_or_none

log = logging.getLogger(__name__)


def _reformat_for_username(string):
    """Removes/substitutes characters in a string to make it suitable as a
    username value.

    Args:
        string (str): A string
    Returns:
        str: A version of the string with username-appropriate characters
    """
    cleaned_string = re.sub(USERNAME_INVALID_CHAR_PATTERN, "", string)
    cleaned_string = re.sub(
        USERNAME_TURKISH_I_CHARS,
        USERNAME_TURKISH_I_CHARS_REPLACEMENT,
        cleaned_string,
    )
    return (
        re.sub(USERNAME_SEPARATOR_REPLACE_PATTERN, USERNAME_SEPARATOR, cleaned_string)
        .lower()
        .strip(USERNAME_SEPARATOR)
    )


def is_duplicate_username_error(exc):
    """Return True if the given exception indicates that there was an attempt
    to save a User record with an already-existing username.

    Args:
        exc (Exception): An exception

    Returns:
        bool: Whether or not the exception indicates a duplicate username error
    """
    return re.search(r"\(username\)=\([^\s]+\) already exists", str(exc)) is not None


def _find_available_username(  # noqa: RET503
    initial_username_base,
    model=None,
    username_field="username",
    max_length=USERNAME_MAX_LEN,
):
    """Return a username with the lowest possible suffix given some
    base username. If the applied suffix makes the username longer than the
    username max length, characters are removed from the right of the username
    to make room.

    EXAMPLES:
    initial_username_base = "johndoe"
        Existing usernames = "johndoe"
        Return value = "johndoe1"
    initial_username_base = "johndoe"
        Existing usernames = "johndoe", "johndoe1" through "johndoe5"
        Return value = "johndoe6"
    initial_username_base = "abcdefghijklmnopqrstuvwxyz"  (26 characters,
        assuming 26 character max)
        Existing usernames = "abcdefghijklmnopqrstuvwxyz"
        Return value = "abcdefghijklmnopqrstuvwxy1"  # pragma: allowlist secret
    initial_username_base = "abcdefghijklmnopqrstuvwxy"
        (25 characters long, assuming 26 character max)
        Existing usernames = "abc...y", "abc...y1" through "abc...y9"
        Return value = "abcdefghijklmnopqrstuvwx10"  # pragma: allowlist secret

    Args:
         initial_username_base (str): Base username to start with
         model: The model class to query (defaults to User model)
         username_field (str): The field name to use for username queries
            (defaults to 'username')
         max_length (int): The maximum allowed username length
            (defaults to USERNAME_MAX_LEN)
    Returns:
        str: An available username
    """
    if model is None:
        model = get_user_model()

    # Keeps track of the number of characters that must be cut from the
    # username to be less than the username max length when the
    # suffix is applied.
    letters_to_truncate = 0 if len(initial_username_base) < max_length else 1
    # Any query for suffixed usernames could come up empty. The minimum suffix
    # will be added to the username in that case.
    current_min_suffix = 1
    while letters_to_truncate < len(initial_username_base):
        username_base = initial_username_base[
            0 : len(initial_username_base) - letters_to_truncate
        ]
        # Find usernames that match the username base and have a numerical
        # suffix, then find the max suffix
        filter_kwargs = {f"{username_field}__regex": rf"^{username_base}\d+$"}
        existing_usernames = model.objects.filter(**filter_kwargs).values_list(
            username_field, flat=True
        )

        suffixes = []
        for username in existing_usernames:
            match = re.search(r"\d+$", username)
            if match is not None:
                try:
                    suffixes.append(int(match.group()))
                except (ValueError, AttributeError):
                    continue

        max_suffix = max_or_none(suffixes) if suffixes else None

        if max_suffix is None:
            return "".join([username_base, str(current_min_suffix)])
        else:
            next_suffix = max_suffix + 1
            candidate_username = "".join([username_base, str(next_suffix)])
            # If the next suffix adds a digit and causes the username to
            # exceed the character limit, keep searching.
            if len(candidate_username) <= max_length:
                return candidate_username
        # At this point, we know there are no suffixes left to add to this
        # username base that was tried,
        # so we will need to remove letters from the end of that username base
        # to make room for a longer suffix.
        letters_to_truncate = letters_to_truncate + 1
        available_suffix_digits = max_length - (
            len(initial_username_base) - letters_to_truncate
        )
        # If there is space for 4 digits for the suffix, the minimum value it
        # could be is 1000, or 10^3
        current_min_suffix = 10 ** (available_suffix_digits - 1)


def usernameify(full_name, email="", max_length=USERNAME_MAX_LEN):
    """Public API for username generation Generate a username based on a
    full name, or an email address as a fallback.

    Args:
        full_name (str): A full name (i.e.: User.name)
        email (str): An email address to use as a fallback if the full name
            produces a blank username
        max_length (int): The maximum allowed username length
            (defaults to USERNAME_MAX_LEN)
    Returns:
        str: A generated username
    Raises:
        ValueError: Raised if generated username was blank after trying both
            the full name and email
    """
    username = _reformat_for_username(full_name)

    if not username and email:
        log.error(
            "User's full name could not be used to generate a username "
            "(full name: '%s'). "
            "Trying email instead...",
            full_name,
        )
        username = _reformat_for_username(email.split("@")[0])
    if not username:
        raise ValueError(
            "Username could not be generated (full_name: '{}', email: '{}')".format(  # noqa: EM103, UP032
                full_name, email
            )
        )
    return username[0:max_length]


def create_user_with_generated_username(  # noqa: PLR0913
    serializer,
    initial_username,
    username_field,
    max_length,
    model=None,
    attempts_limit=USERNAME_COLLISION_ATTEMPTS,
):
    """Public API for user creation with auto-generated username
    Creates a User with a given username, and if there is a User that already
    has that username, finds an available username and
    reattempts the User creation.

    Args:
        serializer: A serializer instance that has been instantiated
            with user data and has passed initial validation
        initial_username (str): The initial username to attempt to
            save the User with
        username_field (str): The field name to use for the username
        max_length (int): The maximum allowed username length
        model: The model class to pass to find_username_func (defaults to None)
        attempts_limit (int): Maximum number of attempts to create user

    Returns:
        User or None: The created User (or None if the User could not be
        created in the number of retries allowed)
    """
    created_user = None
    username = initial_username
    attempts = 0

    if len(username) < 2:  # noqa: PLR2004
        username = username + "11"

    while created_user is None and attempts < attempts_limit:
        try:
            created_user = serializer.save(username=username)
        except IntegrityError as exc:  # noqa: PERF203
            if not is_duplicate_username_error(exc):
                raise
            username = _find_available_username(
                initial_username,
                model=model,
                username_field=username_field,
                max_length=max_length,
            )
        finally:
            attempts += 1
    return created_user
