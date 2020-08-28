"""Testing mail defaults"""

from mitol.mail.defaults import can_email_user, format_recipient


def test_format_recipient(mocker):
    """Test that format_recipient formats a user's email and name"""
    user = mocker.Mock(email="user@localhost", first_name="Sally", last_name="Ride")
    assert format_recipient(user) == "Sally Ride <user@localhost>"


def test_can_email_user(mocker):
    """Test that can_email_user returns True only if the user has an email"""
    assert can_email_user(mocker.Mock(email="user@localhost")) == True
    assert can_email_user(mocker.Mock(email="")) == False
    assert can_email_user(mocker.Mock(email=None)) == False
