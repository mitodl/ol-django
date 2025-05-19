"""API for the transcoding app."""

import json
from pathlib import Path
from typing import Optional

import boto3
from django.conf import settings

from mitol.transcoding.constants import GroupSettings
from mitol.transcoding.utils import (
    FileConfig,
    filter_mp4_groups,
    get_output_path,
    is_thumbnail_group,
)


def media_convert_job(  # noqa: PLR0913
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
) -> dict:
    """
    Create a MediaConvert job for a Video

    Args:
        video_source_key (str): S3 key for the video source.
        source_prefix (str): Prefix for the source video.
        source_bucket (str, optional): S3 bucket for the source video.
        destination_prefix (str): Prefix for the destination video.
        destination_bucket (str): S3 bucket for the transcoded output
        group_settings (dict, optional): Settings for output groups.

    Returns:
        dict: MediaConvert job details.
    """

    file_config = FileConfig(
        video_source_key,
        source_prefix,
        source_bucket,
        destination_prefix,
        destination_bucket,
        group_settings,
    )

    # Make MediaConvert job
    job_dict = make_media_convert_job(file_config)

    client = boto3.client(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
    )
    return client.create_job(**job_dict)


def make_media_convert_job(file_config: FileConfig) -> dict:
    """
    Create a MediaConvert job config.

    Args:
        file_config (FileConfig): Configuration for file paths and settings.

    Returns:
        dict: MediaConvert job details.
    """

    with Path(Path.cwd() / settings.TRANSCODE_JOB_TEMPLATE).open(
        encoding="utf-8",
    ) as job_template:
        job_dict = json.loads(job_template.read())
        job_dict["UserMetadata"]["filter"] = settings.VIDEO_TRANSCODE_QUEUE
        job_dict["Queue"] = (
            f"arn:aws:mediaconvert:{settings.AWS_REGION}:"
            f"{settings.AWS_ACCOUNT_ID}:queues/{settings.VIDEO_TRANSCODE_QUEUE}"
        )
        job_dict["Role"] = (
            f"arn:aws:iam::{settings.AWS_ACCOUNT_ID}:role/{settings.AWS_ROLE_NAME}"
        )

        file_config.destination = get_destination_path(file_config)

        job_dict["Settings"]["Inputs"][0]["FileInput"] = (
            f"s3://{file_config.source_bucket}/{file_config.video_source_key}"
        )

        add_group_settings(job_dict, file_config)

    return job_dict


def get_destination_path(file_config: FileConfig) -> str:
    """
    Calculate the destination path for transcoded files.

    Args:
        file_config (FileConfig): Configuration for file paths and settings.


    Returns:
        str: Destination path for the transcoded files.
    """
    if file_config.source_prefix:
        destination_path = Path(
            file_config.video_source_key.replace(
                file_config.source_prefix,
                file_config.destination_prefix,
            )
        )
    else:
        destination_path = Path(
            file_config.destination_prefix, file_config.video_source_key
        )

    return str(destination_path.parent / destination_path.stem)


def add_group_settings(job_dict: dict, file_config: FileConfig) -> None:
    """
    Add group settings to the MediaConvert job dictionary.

    Args:
        job_dict (dict): MediaConvert job dictionary.
        file_config (FileConfig): Configuration for file paths and settings.
    """
    output_groups = job_dict["Settings"]["OutputGroups"]
    exclude_mp4 = file_config.group_settings.get("exclude_mp4", False)
    exclude_thumbnail = file_config.group_settings.get("exclude_thumbnail", False)

    # Apply all filters sequentially
    if exclude_mp4:
        output_groups = filter_mp4_groups(output_groups)

    if exclude_thumbnail:
        output_groups = [
            group for group in output_groups if not is_thumbnail_group(group)
        ]

    job_dict["Settings"]["OutputGroups"] = output_groups

    for group in output_groups:
        output_group_settings = group["OutputGroupSettings"]
        group_settings_type = output_group_settings["Type"]

        _is_thumbnail_group = is_thumbnail_group(group)

        if group_settings_type == GroupSettings.HLS_GROUP_SETTINGS:
            group_settings_key = GroupSettings.HLS_GROUP_SETTINGS_KEY
            output_group_settings[group_settings_key]["SegmentLength"] = (
                file_config.group_settings.get("SegmentLength", 10)
            )
            output_group_settings[group_settings_key]["AdditionalManifests"][0][
                "ManifestNameModifier"
            ] = file_config.group_settings.get("ManifestNameModifier", "__index")
        elif group_settings_type == GroupSettings.FILE_GROUP_SETTINGS:
            group_settings_key = GroupSettings.FILE_GROUP_SETTINGS_KEY
        else:
            group_type = group_settings_type
            error_msg = f"Unsupported group settings type: {group_type}"
            raise ValueError(error_msg)
        output_path = get_output_path(
            file_config, is_thumbnail_group=_is_thumbnail_group
        )
        output_group_settings[group_settings_key]["Destination"] = output_path
