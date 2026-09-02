"""Settings for login/logout redirect handling."""

from mitol.common.envs import get_list_literal, get_string

# Set to the default URL the user should be sent to when logging out.
# If there's no redirect URL specified otherwise, the user gets sent here.
MITOL_DEFAULT_POST_LOGOUT_URL = get_string(
    name="MITOL_DEFAULT_POST_LOGOUT_URL",
    description="Default URL to send users to after logging out",
    default="/app",
)

# Set to the list of hosts the app is allowed to redirect to.
MITOL_ALLOWED_REDIRECT_HOSTS = get_list_literal(
    name="MITOL_ALLOWED_REDIRECT_HOSTS",
    description="Allowed redirect hostnames",
    default=[],
)

# Set to the URL for the new-user onboarding flow. If empty, first-time logins
# are not redirected to onboarding.
MITOL_NEW_USER_LOGIN_URL = get_string(
    name="MITOL_NEW_USER_LOGIN_URL",
    description="URL to redirect new users to on first login",
    default="",
)
