from mitol.common.envs import get_list_literal

# Set to the default URL the user should be sent to when logging out.
# If there's no redirect URL specified otherwise, the user gets sent here.
MITOL_DEFAULT_POST_LOGOUT_URL = "/app"

MITOL_ALLOWED_REDIRECT_HOSTS = get_list_literal(
    name="ALLOWED_REDIRECT_HOSTS", description="Allowed redirect hostnames", default=[]
)
