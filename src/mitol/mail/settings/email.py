"""
Email settings for django builtin email functionality

Note: this does not cover anymail, mailgun, etc configuration.
Those are covered by the mitol-django-mail app.
"""

from mitol.common.envs import app_namespaced, get_bool, get_int, get_string

MAILGUN_RECIPIENT_OVERRIDE = get_string(
    name="MAILGUN_RECIPIENT_OVERRIDE",
    default=None,
    dev_only=True,
    description="Override the recipient for outgoing email, development only",
)
EMAIL_RECIPIENT_OVERRIDE = get_string(
    name="EMAIL_RECIPIENT_OVERRIDE",
    default=MAILGUN_RECIPIENT_OVERRIDE,
    dev_only=True,
    description="Override the recipient for outgoing email, development only",
)
EMAIL_BACKEND = get_string(
    name=app_namespaced("EMAIL_BACKEND"),
    default="django.core.mail.backends.smtp.EmailBackend",
    description="The default email backend to use for outgoing email. This is used in some places by django itself. See `NOTIFICATION_EMAIL_BACKEND` for the backend used for most application emails.",
)
EMAIL_HOST = get_string(
    name=app_namespaced("EMAIL_HOST"),
    default="localhost",
    description="Outgoing e-mail hostname",
)
EMAIL_PORT = get_int(
    name=app_namespaced("EMAIL_PORT"), default=25, description="Outgoing e-mail port"
)
EMAIL_HOST_USER = get_string(
    name=app_namespaced("EMAIL_USER"),
    default="",
    description="Outgoing e-mail auth username",
)
EMAIL_HOST_PASSWORD = get_string(
    name=app_namespaced("EMAIL_PASSWORD"),
    default="",
    description="Outgoing e-mail auth password",
)
EMAIL_USE_TLS = get_bool(
    name=app_namespaced("EMAIL_TLS"),
    default=False,
    description="Outgoing e-mail TLS setting",
)
EMAIL_SUPPORT = get_string(
    name=app_namespaced("SUPPORT_EMAIL"),
    default=EMAIL_RECIPIENT_OVERRIDE or "support@localhost",
    description="Email address listed for customer support",
)
DEFAULT_FROM_EMAIL = get_string(
    name=app_namespaced("FROM_EMAIL"),
    default="webmaster@localhost",
    description="E-mail to use for the from field",
)
