"""
Dev-only settings

Copy this file to testapp/settings/dev.py. DO NOT RENAME!

You can then modify the copied file, testapp/settings/dev.py is gitignored.
"""

from mitol.common.envs import import_settings_modules

import_settings_modules("testapp.settings.shared")
MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = "http://localhost:5000/"
MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC = "testapp.integration.build_credential"
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = "abc123"


# mail app settings, customize for local development
MITOL_MAIL_MESSAGE_CLASSES = ["testapp.messages.SampleMessage"]

MITOL_MAIL_FROM_EMAIL = "invalid@localhost"
MITOL_MAIL_REPLY_TO_ADDRESS = "invalid@localhost"
# MITOL_MAIL_RECIPIENT_OVERRIDE = "invalid@localhost"  # noqa: ERA001
MITOL_MAIL_ENABLE_EMAIL_DEBUGGER = True
# MITOL_MAIL_FORMAT_RECIPIENT_FUNC = "mitol.mail.defaults.format_recipient"  # noqa: ERA001
# MITOL_MAIL_CAN_EMAIL_USER_FUNC = "mitol.mail.defaults.can_email_user"  # noqa: ERA001
# MITOL_MAIL_CONNECTION_BACKEND = "anymail.backends.mailgun.EmailBackend"  # noqa: ERA001
