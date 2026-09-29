"""
Settings the benchmark harness runs the testapp against.

Deliberately *not* ``main.settings.test``. Test settings commonly enable
coverage and N+1 profilers whose cost scales with the work under test, which
is the fastest way to manufacture a benchmark result. This module is the
nearest thing the testapp has to production settings: it supplies the values
``shared`` requires and nothing that only makes sense in a test run.
"""

from mitol.common.envs import import_settings_modules

import_settings_modules("main.settings.shared")

DEBUG = False

MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL = "http://localhost:5000/"
MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC = "main.integration.build_credential"
MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET = "abc123"  # noqa: S105  # pragma: allowlist secret

MITOL_MAIL_MESSAGE_CLASSES = ["main.messages.SampleMessage"]
MITOL_MAIL_FROM_EMAIL = "invalid@localhost"
MITOL_MAIL_REPLY_TO_ADDRESS = "invalid@localhost"

MITOL_HUBSPOT_API_PRIVATE_TOKEN = "testtoken"  # noqa: S105

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
    "durable": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "durable_cache",
    },
}

FEATURES = {}

MITOL_APIGATEWAY_LOGOUT_URL = "/logout"
MITOL_APIGATEWAY_DEFAULT_POST_LOGOUT_DEST = "/app-after-logout"
