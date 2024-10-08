"""API tests"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from mitol.mail.api import (
    build_message,
    can_email_user,
    get_connection,
    get_message_classes,
    get_message_sender,
    render_email_templates,
    safe_format_recipient,
    send_message,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("email_settings")]

User = get_user_model()


@pytest.fixture
def email_settings(settings):  # noqa: PT004
    """Default settings for email tests"""  # noqa: D401
    settings.MITOL_MAIL_RECIPIENT_OVERRIDE = None


def test_get_message_classes(mocker, settings):
    """Verify get_message_classes dynamically imports named classes"""
    imported = [mocker.Mock(), mocker.Mock()]
    mock_import_string = mocker.patch(
        "mitol.mail.api.import_string", side_effect=imported
    )
    settings.MITOL_MAIL_MESSAGE_CLASSES = ["abc.Class1", "abc.Class2"]

    assert get_message_classes() == imported

    mock_import_string.assert_any_call("abc.Class1")
    mock_import_string.assert_any_call("abc.Class2")


def test_get_message_classes_invalid(mocker, settings):
    """Verify get_message_classes maps an import error into a ImproperlyConfigured error"""  # noqa: E501
    mocker.patch(
        "mitol.mail.api.import_string",
        side_effect=[mocker.Mock(), ImportError],
    )

    settings.MITOL_MAIL_MESSAGE_CLASSES = ["abc.Class1", "abc.Class2"]

    with pytest.raises(ImproperlyConfigured):
        get_message_classes()


def test_safe_format_email_recipient():
    """Test that safe_format_recipient uses the input if it's not a user"""
    assert safe_format_recipient("test@localhost") == "test@localhost"


@pytest.mark.parametrize("use_default", [True, False])
def test_safe_format_user_recipient(mocker, settings, use_default):
    """Test that safe_format_recipient calls the configured function if the recipient is a User instance"""  # noqa: E501
    if not use_default:
        settings.MITOL_MAIL_FORMAT_RECIPIENT_FUNC = "my.custom.function"

    mock_import_string = mocker.patch("mitol.mail.api.import_string")
    configured_func = mock_import_string.return_value
    user = mocker.Mock(
        spec=User, email="test@localhost", first_name="first", last_name="last"
    )
    assert safe_format_recipient(user) == mock_import_string.return_value.return_value

    configured_func.assert_called_once_with(user)
    mock_import_string.assert_called_once_with(
        "mitol.mail.defaults.format_recipient" if use_default else "my.custom.function"
    )


@pytest.mark.parametrize("use_default", [True, False])
def test_can_email_user(settings, mocker, use_default):
    """Test that can_email_user proxies to the configured function"""
    if not use_default:
        settings.MITOL_MAIL_CAN_EMAIL_USER_FUNC = "my.custom.function"

    mock_import_string = mocker.patch("mitol.mail.api.import_string")
    configured_func = mock_import_string.return_value
    user = mocker.Mock()
    assert can_email_user(user) == configured_func.return_value
    configured_func.assert_called_once_with(user)
    mock_import_string.assert_called_once_with(
        "mitol.mail.defaults.can_email_user" if use_default else "my.custom.function"
    )


def test_safe_format_recipient_override(mocker, settings):
    """Test that the recipient override works"""
    settings.MITOL_MAIL_RECIPIENT_OVERRIDE = "admin@localhost"
    assert safe_format_recipient(mocker.Mock()) == "admin@localhost"


def test_render_email_templates(mocker):
    """Test render_email_templates"""
    tmpls = {
        "test/subject.txt": "Welcome Jane Smith",
        "test/body.html": """<html><head>
<style type="text/css" data-premailer="ignore">
p {
  color: blue;
}
</style>
<style type="text/css">
.red {
  color: red;
}
</style>
</head><body>
<a href="http://example.com" class="red">html link</a>
</body></html>""",
    }
    mocker.patch(
        "mitol.mail.api.render_to_string", side_effect=lambda path, _: tmpls[path]
    )

    context = {"empty": False}

    subject, text_body, html_body = render_email_templates("test", context)
    assert subject == "Welcome Jane Smith"
    assert text_body == "html link (http://example.com)"
    assert html_body == (
        "<html><head>\n"
        '<style type="text/css">\n'
        "p {\n"
        "  color: blue;\n"
        "}\n"
        "</style>\n"
        "</head><body>\n"
        '<a href="http://example.com" class="red" style="color:red">html link</a>\n'
        "</body></html>"
    )


@pytest.mark.parametrize("recipient_is_user", [True, False])
def test_build_message(mocker, recipient_is_user):
    """
    Tests that build_message correctly builds a message object using the Anymail APIs
    """
    template_context = {"context_key": "context_value"}
    email = "user@localhost"
    recipient = (
        mocker.Mock(spec=User, email=email, first_name="First", last_name="Last")
        if recipient_is_user
        else email
    )
    mock_message_cls = mocker.Mock()
    mock_connection = mocker.Mock()

    assert (
        build_message(
            mock_connection,
            mock_message_cls,
            recipient,
            template_context,
            kwarg1=1,
            kwarg2=2,
        )
        == mock_message_cls.create.return_value
    )

    mock_message_cls.create.assert_called_once_with(
        connection=mock_connection,
        to=[safe_format_recipient(recipient)],
        template_context={
            **template_context,
            "user": recipient if recipient_is_user else None,
        },
        kwarg1=1,
        kwarg2=2,
    )


@pytest.mark.usefixtures("mailoutbox")
def test_send_message_none(mocker):
    """Tests that send_message bails if there is no message"""
    patched_logger = mocker.patch("mitol.mail.api.log")

    send_message(None)

    patched_logger.exception.assert_not_called()


@pytest.mark.usefixtures("mailoutbox")
def test_send_message_failure(mocker):
    """Tests that send_message logs all exceptions"""
    message = mocker.Mock()
    message.send.side_effect = ConnectionError
    patched_logger = mocker.patch("mitol.mail.api.log")

    send_message(message)

    message.send.assert_called_once()
    patched_logger.exception.assert_called_once()


@pytest.mark.parametrize("use_default", [True, False])
def test_get_connection(settings, mocker, use_default):
    """Verify get_connection calls with the correct backend"""
    if not use_default:
        settings.MITOL_MAIL_CONNECTION_BACKEND = "my.custom.backend"

    mock_django_get_connection = mocker.patch("mitol.mail.api.django_get_connection")

    with get_connection() as conn:
        assert conn == mock_django_get_connection.return_value

    mock_django_get_connection.assert_called_once_with(
        "anymail.backends.mailgun.EmailBackend" if use_default else "my.custom.backend"
    )


@pytest.mark.parametrize(
    "shared_context, expected_context",  # noqa: PT006
    [({"a": 1}, {"a": 1, "b": 2}), ({}, {"b": 2}), (None, {"b": 2})],
)
def test_get_message_sender(mocker, shared_context, expected_context):
    """Test that get_message_sender configures a wrapper around sending APIs"""
    message_cls = mocker.Mock()
    recipient = mocker.Mock()
    mock_get_connection = mocker.patch("mitol.mail.api.get_connection")
    mock_build_message = mocker.patch("mitol.mail.api.build_message")
    mock_send_message = mocker.patch("mitol.mail.api.send_message")

    connection = mock_get_connection.return_value.__enter__.return_value

    with get_message_sender(message_cls, shared_context=shared_context) as sender:
        sender.build_and_send_message(recipient, {"b": 2}, tags=["tag1", "tag2"])

    mock_build_message.assert_called_once_with(
        connection, message_cls, recipient, expected_context, tags=["tag1", "tag2"]
    )
    mock_send_message.assert_called_once_with(mock_build_message.return_value)

    mock_get_connection.return_value.__enter__.assert_called_once_with()
