"""Digital credentials app AppConfigs"""

import os

from mitol.common.apps import BaseApp


class DigitalCredentialsApp(BaseApp):
    """Default configuration for the digital credentials app"""

    name = "mitol.digitalcredentials"
    label = "digitalcredentials"
    verbose_name = "Digital Credentials"

    required_settings = [  # noqa: RUF012
        "MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL",
        "MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC",
        "MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET",
    ]

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
