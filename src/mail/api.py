"""
Email APIs

Example usage:

# get recipients
recipients = User.objects.all()[:10]

with get_message_sender(TestMessage) as sender:
    sender.build_and_send_message(user=user)
"""
import contextlib
import logging
import re
from collections import namedtuple
from copy import deepcopy
from os import path
from typing import Generator, Iterable, Optional, Tuple, Type, Union

import premailer
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection as django_get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.template.loader import render_to_string
from django.utils.module_loading import import_string
from toolz import compose, partial

from mitol.mail.messages import TemplatedMessage

log = logging.getLogger(__name__)


MessageSenderAPI = namedtuple(
    "MessageSenderAPI",
    [
        "connection",
        "build_message",
        "send_message",
        "can_email_user",
        "build_and_send_message",
    ],
)


def get_message_classes() -> Iterable[Type[TemplatedMessage]]:
    """Get the message classes that are configured"""
    classes = []
    for message_cls in getattr(settings, "MITOL_MAIL_MESSAGE_CLASSES", []):
        try:
            classes.append(import_string(message_cls))
        except ImportError as exc:
            raise ImproperlyConfigured(
                f"MITOL_MAIL_MESSAGE_CLASSES is invalid, could not import: {message_cls}"
            ) from exc
    return classes


def safe_format_recipient(
    recipient_or_user: Union[AbstractBaseUser, str]
) -> Optional[str]:
    """
    Returns a "safe"formatted recipient
    This means if MAILGUN_RECIPIENT_OVERRIDE is set, we only use that

    Args:
        recipient_or_user (str or AbstractBaseUser): recipient user or email str

    Returns:
        str or None: the formatted email str
    """
    override_recipient = getattr(settings, "MITOL_MAIL_RECIPIENT_OVERRIDE", None)
    format_func_name = getattr(
        settings,
        "MITOL_MAIL_FORMAT_RECIPIENT_FUNC",
        "mitol.mail.defaults.format_recipient",
    )
    format_func = import_string(format_func_name)

    # we set this for local development so we don't actually email someone
    if override_recipient is not None:
        return override_recipient

    if isinstance(recipient_or_user, AbstractBaseUser):
        return format_func(recipient_or_user)

    return recipient_or_user


def can_email_user(user: AbstractBaseUser) -> bool:
    """
    Proxies to a configurable predicate, defaults to `mitol.mail.defaults.can_email_user`

    Args:
        user (AbstractBaseUser): user to check

    Returns:
        bool: True if we can email this user
    """
    can_email_user_func_name = getattr(
        settings, "MITOL_MAIL_CAN_EMAIL_USER_FUNC", "mitol.mail.defaults.can_email_user"
    )
    can_email_user_func = import_string(can_email_user_func_name)
    return can_email_user_func(user)


def render_email_templates(template_name: str, context: dict) -> Tuple[str, str, str]:
    """
    Renders the email templates for the email

    Args:
        template_name (str): name of the template, this should match a directory in mail/templates
        context (dict): context data for the email

    Returns:
        (str, str, str): tuple of the templates for subject, text_body, html_body
    """
    subject_text = render_to_string(
        path.join(template_name, "subject.txt"), context
    ).rstrip()

    context.update({"subject": subject_text})
    html_text = render_to_string(path.join(template_name, "body.html"), context)

    # inline css styles
    html_text = premailer.transform(html_text)

    # pynliner internally uses bs4, which we can now modify the inlined version into a plaintext version
    # this avoids parsing the body twice in bs4
    soup = BeautifulSoup(html_text, "html5lib")

    # remove newlines within text tags
    for text in soup.find_all(
        ["p", "h1", "h2", "h3", "h4", "h5", "h6", "span", "a", "b", "i"]
    ):
        if text.string:  # pragma: no branch
            text.string = text.string.replace("\n", " ")

    # anchor tags get the value of their href added
    for link in soup.find_all("a"):
        link.replace_with("{} ({})".format(link.string, link.attrs["href"]))

    # clear any surviving style and title tags, so their contents don't get printed
    for style in soup.find_all(["style", "title"]):
        style.clear()  # clear contents, just removing the tag isn't enough

    fallback_text = soup.get_text().strip()
    # truncate more than 3 consecutive newlines
    fallback_text = re.sub(r"\n\s*\n", "\n\n\n", fallback_text)
    # ltrim the left side of all lines
    fallback_text = re.sub(
        r"^([ ]+)([\s\\X])", r"\2", fallback_text, flags=re.MULTILINE
    )
    # trim each line
    fallback_text = "\n".join([line.strip() for line in fallback_text.splitlines()])

    return subject_text, fallback_text, html_text


@contextlib.contextmanager
def get_connection() -> Generator:
    """Conext manager for the backend connection"""
    backend_name = getattr(
        settings,
        "MITOL_MAIL_CONNECTION_BACKEND",
        "anymail.backends.mailgun.EmailBackend",
    )
    yield django_get_connection(backend_name)


def build_message(
    connection: BaseEmailBackend,
    message_cls: Type[TemplatedMessage],
    recipient_or_user: Union[str, AbstractBaseUser],
    template_context: dict,
    **kwargs,
) -> TemplatedMessage:
    """
    Creates message objects for a set of recipients with the same context in each message.

    Args:
        connection (django.core.mail.backends.base.BaseEmailBackend): the connection to send this message with
        message_cls (class): TemplatedMessage subclass
        recipient_or_user (str or AbstractBaseUser): Iterable of user email addresses
        template_context (dict or None): A dict of context variables to pass into the template (in addition
            to the base context variables)

    Returns:
        mitol.mail.messages.TemplatedMessage: email message with rendered content
    """
    user = (
        recipient_or_user if isinstance(recipient_or_user, AbstractBaseUser) else None
    )
    to = [safe_format_recipient(recipient_or_user)]
    template_context = {**template_context, "user": user}
    return message_cls.create(
        connection=connection,
        to=to,
        template_context=template_context,
        **kwargs,
    )


def send_message(message: TemplatedMessage):
    """
    Convenience method for sending one message

    Args:
        message (mitol.mail.messages.TemplatedMessage): message to send
    """
    if message is None:
        return

    try:
        message.send()
    except Exception:
        log.exception("Error sending email '%s' to %s", message.subject, message.to)


@contextlib.contextmanager
def get_message_sender(
    message_cls: Type[TemplatedMessage], *, shared_context: Optional[dict] = None
) -> Generator:
    """
    Context manager to provide a unified interface to the mail APIs, also providing some extra functionality around shared contexts

    Args:
        message_cls (class): TemplatedMessage subclass
        shared_context (dict or None): optional shared context

    Yields:
        MessageSenderAPI:
            API context object
    """
    shared_context = shared_context or {}

    with get_connection() as connection:
        build_message_for_sender = partial(build_message, connection, message_cls)

        def _build_message(
            recipient_or_user: Union[str, AbstractBaseUser],
            template_context: dict,
            **kwargs,
        ):
            template_context = {
                **deepcopy(shared_context),  # type: ignore[arg-type]
                **template_context,
            }
            return build_message_for_sender(
                recipient_or_user, template_context, **kwargs
            )

        build_and_send_message = compose(send_message, _build_message)

        yield MessageSenderAPI(
            connection,
            _build_message,
            send_message,
            can_email_user,
            build_and_send_message,
        )
