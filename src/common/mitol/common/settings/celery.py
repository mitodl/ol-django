"""Celery settings"""

from mitol.common.envs import get_string

MITOL_CELERY_APP_INSTANCE_PATH = get_string(
    name="MITOL_CELERY_APP_INSTANCE_PATH",
    default="main.celery.app",
    description="Path to the celery app instance",
    required=True,
)
