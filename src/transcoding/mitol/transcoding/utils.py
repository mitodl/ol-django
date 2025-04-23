"""Transcoding utilities"""

from typing import Optional

from django.conf import settings

from mitol.transcoding.constants import TRANSCODE_JOB_SUBSCRIPTION_URL


class FileConfig:
    """
    Configuration for file path settings used in MediaConvert job creation.
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
        group_settings: Optional[dict] = None,
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


def get_subscribe_url(token: str) -> str:
    """Get a SNS subscribe url"""

    return TRANSCODE_JOB_SUBSCRIPTION_URL.format(
        AWS_REGION=settings.AWS_REGION,
        AWS_ACCOUNT_ID=settings.AWS_ACCOUNT_ID,
        TOKEN=token,
    )


def is_thumbnail_group(group: dict) -> bool:
    """
    Determine if the group is for thumbnails by checking for FRAME_CAPTURE codec.
    Args:
        group (dict): Output group from the MediaConvert job.
    Returns:
        bool: True if the group adds thumbnails, False otherwise.
    """
    for output in group.get("Outputs", []):
        video_description = output.get("VideoDescription", {})
        codec_settings = video_description.get("CodecSettings", {})
        if codec_settings.get("Codec") == "FRAME_CAPTURE":
            return True
    return False


def filter_mp4_groups(output_groups: list) -> list:
    """
    Filter out MP4 output groups.
    Args:
        output_groups (list): List of output groups from the MediaConvert job.
    Returns:
        filtered_groups (list): Filtered list of output groups without MP4 outputs.
    """
    filtered_groups = []
    for group in output_groups:
        # Check if this group contains MP4 outputs
        is_mp4_group = False
        for output in group.get("Outputs", []):
            container_settings = output.get("ContainerSettings", {})
            if container_settings.get("Container") == "MP4":
                is_mp4_group = True
                break

        # Keep the group if it's not an MP4 group
        if not is_mp4_group:
            filtered_groups.append(group)
    return filtered_groups


def get_output_path(
    file_config: FileConfig,
    *,
    is_thumbnail_group: bool,
    thumbnail_bucket: Optional[str] = (
        settings.VIDEO_S3_THUMBNAIL_BUCKET or settings.AWS_STORAGE_BUCKET_NAME
    ),
    thumbnail_prefix: Optional[str] = (
        settings.VIDEO_S3_THUMBNAIL_PREFIX or settings.VIDEO_S3_UPLOAD_PREFIX
    ),
) -> str:
    """
    Get the appropriate output path based on group type and settings.
    Args:
        file_config (FileConfig): Configuration for file paths and settings.
    Kwargs:
        is_thumbnail_group (bool): Flag indicating if the group is for thumbnails.
        thumbnail_bucket (str, optional): S3 bucket for thumbnail generation.
        thumbnail_prefix (str, optional): Prefix for the thumbnail video.
    Returns:
        str: Output path for the MediaConvert job.
    """

    # Use Django settings for thumbnail bucket/prefix, with fallbacks
    destination_bucket = (
        thumbnail_bucket if is_thumbnail_group else file_config.destination_bucket
    )
    destination = (
        file_config.destination.replace(
            file_config.destination_prefix, thumbnail_prefix
        )
        if is_thumbnail_group and thumbnail_prefix
        else file_config.destination
    )

    return f"s3://{destination_bucket}/{destination}"
