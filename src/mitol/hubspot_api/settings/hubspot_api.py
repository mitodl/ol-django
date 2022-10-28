"""
Hubspot settings
"""

from mitol.common.envs import get_int, get_string

MITOL_HUBSPOT_API_PRIVATE_TOKEN = get_string(
    name="MITOL_HUBSPOT_API_PRIVATE_TOKEN",
    default=None,
    description="Private token for Hubspot",
)
MITOL_HUBSPOT_API_ID_PREFIX = get_string(
    name="MITOL_HUBSPOT_API_ID_PREFIX",
    default="app",
    description="Prefix for generating custom hubspot_api ids",
)
MITOL_HUBSPOT_API_RETRIES = get_int(
    name="MITOL_HUBSPOT_API_RETRIES",
    default=3,
    description="Number of times to retry failed API requests",
)
