"""Common settings"""
from mitol.common.envs import app_namespaced, get_string

SITE_BASE_URL = get_string(
    name=app_namespaced("BASE_URL"),
    default=None,
    description="Base url for the application in the format PROTOCOL://HOSTNAME[:PORT]",
    required=True,
)
