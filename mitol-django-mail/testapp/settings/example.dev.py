"""
Dev-only settings

Copy this file to testapp/settings/dev.py. DO NOT RENAME!

You can then modify the copied file, testapp/settings/dev.py is gitignored.
"""
from testapp.settings.shared import *


# mail app settings, customize for local development
MITOL_MAIL_MESSAGE_CLASSES = ["testapp.messages.SampleMessage"]

MITOL_MAIL_FROM_EMAIL = "invalid@localhost"
MITOL_MAIL_REPLY_TO_ADDRESS = "invalid@localhost"
# MITOL_MAIL_RECIPIENT_OVERRIDE = "invalid@localhost"
MITOL_MAIL_ENABLE_EMAIL_DEBUGGER = True
# MITOL_MAIL_FORMAT_RECIPIENT_FUNC = "mitol.mail.defaults.format_recipient"
# MITOL_MAIL_CAN_EMAIL_USER_FUNC = "mitol.mail.defaults.can_email_user"
# MITOL_MAIL_CONNECTION_BACKEND = "anymail.backends.mailgun.EmailBackend"
