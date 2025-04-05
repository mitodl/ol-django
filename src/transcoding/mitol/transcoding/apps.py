"""transcoding app AppConfig"""

import os

from django.apps import AppConfig


class Transcoding(AppConfig):
    """Default configuration for the transcoding app"""

    name = "mitol.transcoding"
    label = "transcoding"
    verbose_name = "Transcoding App"

    required_settings = [
        "VIDEO_TRANSCODE_QUEUE",
        "VIDEO_S3_TRANSCODE_ENDPOINT",
        "VIDEO_S3_TRANSCODE_PREFIX",
        "VIDEO_S3_UPLOAD_PREFIX",
        "AWS_STORAGE_BUCKET_NAME",
        "VIDEO_S3_TRANSCODE_BUCKET",
        "AWS_REGION",
        "AWS_ACCOUNT_ID",
        "AWS_ROLE_NAME",
        "POST_TRANSCODE_ACTIONS",
        "TRANSCODE_JOB_TEMPLATE",
    ]

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
