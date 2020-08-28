"""Test-only settings"""
from testapp.settings.shared import *


# mail app settings
MITOL_MAIL_MESSAGE_CLASSES = ["testapp.messages.SampleMessage"]

MITOL_MAIL_FROM_EMAIL = "invalid@localhost"
MITOL_MAIL_REPLY_TO_ADDRESS = "invalid@localhost"
MITOL_MAIL_ENABLE_EMAIL_DEBUGGER = True
