"""users utils tests"""

from unittest.mock import Mock, patch

import pytest
import re
from django.db import IntegrityError
from mitol.common.utils.user import (
    _find_available_username,
    create_user_with_generated_username,
    is_duplicate_username_error,
    usernameify,
)

EXPECTED_RETRY_COUNT = 2
MAX_ATTEMPTS_LIMIT = 10


@pytest.mark.parametrize(
    "full_name,email,expected_username",  # noqa: PT006
    [
        [" John  Doe ", None, "john-doe"],  # noqa: PT007
        ["Tabby	Tabberson", None, "tabby-tabberson"],  # noqa: PT007
        ["Àccèntèd Ñame, Ësq.", None, "àccèntèd-ñame-ësq"],  # noqa: PT007
        ["-Dashy_St._Underscores-", None, "dashy-st-underscores"],  # noqa: PT007
        ["Repeated-----Chars___Jr.", None, "repeated-chars-jr"],  # noqa: PT007
        ["Numbers123 !$!@ McStrange!!##^", None, "numbers-mcstrange"],  # noqa: PT007
        ["Кирил Френков", None, "кирил-френков"],  # noqa: PT007
        ["年號", None, "年號"],  # noqa: PT007
        ["abcdefghijklmnopqrstuvwxyz", None, "abcdefghijklmnopqrst"],  # noqa: PT007
        ["ai bi cı dI eİ fI", None, "ai-bi-ci-di-ei-fi"],  # noqa: PT007, RUF001
        ["", "some.email@example.co.uk", "someemail"],  # noqa: PT007
    ],
)
def test_usernameify(mocker, full_name, email, expected_username):
    """Usernameify should turn a user's name into a username, or use the email
    if necessary
    """
    # Change the username max length to 20 for test data simplicity's sake
    temp_username_max_len = 20
    patched_log_error = mocker.patch("mitol.common.utils.user.log.error")

    assert (
        usernameify(full_name, email=email, max_length=temp_username_max_len)
        == expected_username
    )
    assert patched_log_error.called == bool(email and not full_name)


def test_usernameify_fail():
    """Usernameify should raise an exception if the full name and email both
    fail to produce a username
    """
    with pytest.raises(ValueError):  # noqa: PT011
        assert usernameify("!!!", email="???@example.com")


@pytest.mark.parametrize(
    "exception_text,expected_value",  # noqa: PT006
    [
        ["DETAILS: (username)=(ABCDEFG) already exists", True],  # noqa: PT007
        ["DETAILS: (email)=(ABCDEFG) already exists", False],  # noqa: PT007
    ],
)
def test_is_duplicate_username_error(exception_text, expected_value):
    """
    is_duplicate_username_error should return True if the exception text
    provided indicates a duplicate username error
    """
    assert is_duplicate_username_error(exception_text) is expected_value


@pytest.fixture
def fake_user():
    """
    Fixture that returns a mock user object with a username attribute.
    Used for testing username generation and collision logic.
    """
    return Mock(username="testuser")


@patch("mitol.common.utils.user._find_available_username")
def test_create_user_first_try_success(mock_find_username, fake_user):
    """
    Test that create_user_with_generated_username succeeds on the first try
    if there is no collision.
    """
    serializer = Mock()
    serializer.save.return_value = fake_user
    result = create_user_with_generated_username(
        serializer=serializer,
        initial_username="testuser",
        username_field="username",
        max_length=30,
        model=None,
        attempts_limit=3,
    )
    assert result == fake_user
    serializer.save.assert_called_once_with(username="testuser")
    mock_find_username.assert_not_called()


@patch("mitol.common.utils.user._find_available_username")
def test_create_user_with_collision_and_retry(mock_find_username, fake_user):
    """
    Test that create_user_with_generated_username retries on username
    collision and succeeds on retry.
    """
    serializer = Mock()
    duplicate_error = IntegrityError(
        "duplicate key value violates unique constraint"
    )
    serializer.save.side_effect = [
        duplicate_error,
        fake_user,
    ]
    mock_find_username.return_value = "testuser1"
    with patch(
        "mitol.common.utils.user.is_duplicate_username_error",
        return_value=True
    ):
        result = create_user_with_generated_username(
            serializer=serializer,
            initial_username="testuser",
            username_field="username",
            max_length=30,
            model=None,
            attempts_limit=3,
        )
    assert result == fake_user
    assert serializer.save.call_count == EXPECTED_RETRY_COUNT
    assert mock_find_username.call_count == 1
    serializer.save.assert_called_with(username="testuser1")


@patch("mitol.common.utils.user._find_available_username")
def test_create_user_fails_after_max_attempts(mock_find_username):
    """
    Test that create_user_with_generated_username returns None after
    exhausting all attempts due to collisions.
    """
    serializer = Mock()
    serializer.save.side_effect = IntegrityError("duplicate")
    mock_find_username.return_value = "newusername"
    with patch(
        "mitol.common.utils.user.is_duplicate_username_error",
        return_value=True
    ):
        result = create_user_with_generated_username(
            serializer=serializer,
            initial_username="testuser",
            username_field="username",
            max_length=30,
            model=None,
            attempts_limit=MAX_ATTEMPTS_LIMIT,
        )
    assert result is None
    assert serializer.save.call_count == MAX_ATTEMPTS_LIMIT


@patch("mitol.common.utils.user._find_available_username")
def test_create_user_raises_on_unknown_integrity_error(mock_find_username):  # noqa: ARG001
    """
    Test that create_user_with_generated_username does not retry and raises
    if the error is not a username collision.
    """
    serializer = Mock()
    serializer.save.side_effect = IntegrityError("some other db error")
    with patch(
        "mitol.common.utils.user.is_duplicate_username_error",
        return_value=False
    ), pytest.raises(IntegrityError, match="some other db error"):
        create_user_with_generated_username(
            serializer=serializer,
            initial_username="testuser",
            username_field="username",
            max_length=30,
            model=None,
            attempts_limit=1,
        )


@patch("mitol.common.utils.user._find_available_username")
def test_create_user_initial_username_too_short(mock_find_username, fake_user):
    """
    Test that create_user_with_generated_username appends '11'
    if the initial username is too short.
    """
    serializer = Mock()
    serializer.save.return_value = fake_user
    result = create_user_with_generated_username(
        serializer=serializer,
        initial_username="a",
        username_field="username",
        max_length=30,
        model=None,
        attempts_limit=3,
    )
    assert result == fake_user
    serializer.save.assert_called_once_with(username="a11")
    mock_find_username.assert_not_called()


@pytest.mark.parametrize(
    ("username_base", "existing_usernames", "expected"),
    [
        (
            "someuser",
            [f"someuser{i}" for i in range(1, 6)],
            "someuser6",
        ),
        (
            "abcdefghij",
            [f"abcdefghij{i}" for i in range(1, 10)],
            "abcdefgh10",
        ),
        (
            "abcdefghi",
            ["abcdefgh97", "abcdefgh98", "abcdefgh99"],
            "abcdefg100",
        ),
    ],
)
def test_find_available_username(username_base, existing_usernames, expected):
    """
    Test that _find_available_username returns the correct
    next available username given existing usernames.
    """
    mock_model = Mock()
    mock_qs = Mock()

    mock_qs.values_list.return_value = existing_usernames
    mock_model.objects.filter.return_value = mock_qs

    result = _find_available_username(
        initial_username_base=username_base,
        model=mock_model,
        username_field="username",
        max_length=10,
    )
    assert result == expected


def test_full_username_creation():
    """
    Ensure that usernameify respects max length and
    that _find_available_username generates a suffixed username that
    also respects max length.
    """
    expected_username_max = 30
    user_full_name = "Longerton McLongernamenbergenstein"
    generated_username = usernameify(
        user_full_name, max_length=expected_username_max
    )
    assert len(generated_username) == expected_username_max

    mock_model = Mock()
    mock_qs = Mock()

    mock_qs.values_list.return_value = [f"{generated_username}1"]
    mock_model.objects.filter.return_value = mock_qs

    available_username = _find_available_username(
        initial_username_base=generated_username,
        model=mock_model,
        username_field="username",
        max_length=expected_username_max,
    )
    assert available_username == f"{generated_username[:-1]}2"
    assert len(available_username) == expected_username_max
