"""Transcoding utilities"""

from django.conf import settings

from mitol.transcoding.constants import TRANSCODE_JOB_SUBSCRIPTION_URL


def get_subscribe_url(token: str) -> str:
    """Get a SNS subscribe url"""

    return TRANSCODE_JOB_SUBSCRIPTION_URL.format(
        AWS_REGION=settings.AWS_REGION,
        AWS_ACCOUNT_ID=settings.AWS_ACCOUNT_ID,
        TOKEN=token,
    )
