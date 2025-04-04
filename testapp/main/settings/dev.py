"""
Dev-only settings

Copy this file to main/settings/dev.py. DO NOT RENAME!

You can then modify the copied file, main/settings/dev.py is gitignored.
"""

from mitol.common.envs import import_settings_modules

import_settings_modules("main.settings.shared")

MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = "http://localhost:5000/"
MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC = (
    "mitol.digitalcredentials.main.integration.build_credential"
)
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = "abc123"  # noqa: S105
