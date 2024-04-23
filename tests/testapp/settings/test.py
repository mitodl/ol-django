"""Test-only settings"""

from mitol.common.envs import import_settings_modules

import_settings_modules("testapp.settings.shared")

MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = "http://localhost:5000/"
MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC = "testapp.integration.build_credential"
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = "abc123"

# mail app settings
MITOL_MAIL_MESSAGE_CLASSES = ["testapp.messages.SampleMessage"]

MITOL_MAIL_FROM_EMAIL = "invalid@localhost"
MITOL_MAIL_REPLY_TO_ADDRESS = "invalid@localhost"
MITOL_MAIL_ENABLE_EMAIL_DEBUGGER = True

# hubspot settings
MITOL_HUBSPOT_API_PRIVATE_TOKEN = "testtoken"

CACHES = {
    # general durable cache (redis should be considered ephemeral)
    "durable": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "durable_cache",
    },
}
