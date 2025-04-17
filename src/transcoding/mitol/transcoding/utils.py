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


class FileConfig:
    """
    Configuration for file path settings
    used in MediaConvert job creation.
    """

    def __init__(  # noqa: PLR0913
        self,
        video_source_key: str,
        source_prefix: str = settings.VIDEO_S3_UPLOAD_PREFIX,
        source_bucket: str = settings.AWS_STORAGE_BUCKET_NAME,
        destination_prefix: str = (
            settings.VIDEO_S3_TRANSCODE_PREFIX or settings.VIDEO_S3_UPLOAD_PREFIX
        ),
        destination_bucket: str = (
            settings.VIDEO_S3_TRANSCODE_BUCKET or settings.AWS_STORAGE_BUCKET_NAME
        ),
        group_settings: dict | None = None,
    ):
        """
        Initialize the FilePathConfig with the given parameters.
        Args:
            video_source_key (str): S3 key for the video source.
            source_prefix (str): Prefix for the source video.
            source_bucket (str): S3 bucket for the source video.
            destination_prefix (str): Prefix for the destination video.
            destination_bucket (str): S3 bucket for the transcoded output
            group_settings (dict, optional): Settings for output groups.
        """

        if group_settings is None:
            group_settings = {}

        self.video_source_key = video_source_key
        self.source_prefix = source_prefix
        self.source_bucket = source_bucket
        self.destination_prefix = destination_prefix
        self.destination_bucket = destination_bucket
        self.group_settings = group_settings
