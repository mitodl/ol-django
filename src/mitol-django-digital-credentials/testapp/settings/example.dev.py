"""
Dev-only settings

Copy this file to testapp/settings/dev.py. DO NOT RENAME!

You can then modify the copied file, testapp/settings/dev.py is gitignored.
"""
from testapp.settings.shared import *


MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = "http://localhost:5000/"
MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC = "testapp.integration.build_credential"
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = "abc123"
