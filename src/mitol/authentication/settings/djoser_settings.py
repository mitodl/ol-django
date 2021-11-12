from mitol.common.envs import get_string

# Relative URL to be used by Djoser for the link in the password reset email
# (see: http://djoser.readthedocs.io/en/stable/settings.html#password-reset-confirm-url)
PASSWORD_RESET_CONFIRM_URL = "password_reset/confirm/{uid}/{token}/"

# Djoser library settings (see: http://djoser.readthedocs.io/en/stable/settings.html)
MITOL_AUTHENTICATION_FROM_EMAIL = get_string(
    default="webmaster@localhost",
    name="MITOL_AUTHENTICATION_FROM_EMAIL",
    description="E-mail to use for the from field",
)

MITOL_AUTHENTICATION_REPLY_TO_ADDRESS = get_string(
    name="MITOL_AUTHENTICATION_REPLY_TO_ADDRESS",
    default="webmaster@localhost",
    description="E-mail to use for reply-to address of emails",
)

DJOSER = {
    "PASSWORD_RESET_CONFIRM_URL": PASSWORD_RESET_CONFIRM_URL,
    "SET_PASSWORD_RETYPE": False,
    "LOGOUT_ON_PASSWORD_CHANGE": False,
    "PASSWORD_RESET_CONFIRM_RETYPE": True,
    "PASSWORD_RESET_SHOW_EMAIL_NOT_FOUND": False,
    "EMAIL": {
        "password_reset": "mitol.authentication.views.djoser_views.CustomPasswordResetEmail"
    },
    "SERIALIZERS": {
        "password_reset": "mitol.authentication.serializers.djoser_serializers.CustomSendEmailResetSerializer"
    },
}
