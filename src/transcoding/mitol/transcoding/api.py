"""API for the transcoding app."""

import json
from pathlib import Path
from typing import Optional

import boto3
from django.conf import settings


def media_convert_job(  # noqa: PLR0913
    video_source_key: str,
    source_prefix: str = settings.VIDEO_S3_UPLOAD_PREFIX,
    source_bucket: str = settings.AWS_STORAGE_BUCKET_NAME,
    destination_prefix: str = settings.VIDEO_S3_TRANSCODE_PREFIX,
    destination_bucket: str = (
        settings.AWS_TRANSCODE_BUCKET_NAME or settings.AWS_STORAGE_BUCKET_NAME
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
        group_settings (dict, optional): Settings for output groups. Defaults to None.

    Returns:
        dict: MediaConvert job details.
    """

    if group_settings is None:
        group_settings = {}

    client = boto3.client(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
    )
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

        if source_prefix:
            destination_path = Path(
                video_source_key.replace(
                    source_prefix,
                    destination_prefix,
                )
            )
        else:
            destination_path = Path(destination_prefix, video_source_key)
        destination = str(destination_path.parent / destination_path.stem)

        job_dict["Settings"]["Inputs"][0]["FileInput"] = (
            f"s3://{source_bucket}/{video_source_key}"
        )

        add_group_settings(job_dict, destination, group_settings, destination_bucket)

        return client.create_job(**job_dict)


def add_group_settings(
    job_dict: dict,
    destination: str,
    group_settings: dict,
    destination_bucket: Optional[str] = None,
) -> None:
    """
    Add group settings to the MediaConvert job dictionary.

    Args:
        job_dict (dict): MediaConvert job dictionary.
        destination (str): Destination path for the output files.
        group_settings (dict): Group settings for the job.
        destination_bucket (str, optional): S3 bucket for the transcoded output.
    """

    for group in job_dict["Settings"]["OutputGroups"]:
        group_settings = group["OutputGroupSettings"]
        group_settings_type = group["OutputGroupSettings"]["Type"]
        if group_settings_type == GroupSettings.HLS_GROUP_SETTINGS:
            group_settings_key = GroupSettings.HLS_GROUP_SETTINGS_KEY
            group_settings[group_settings_key]["SegmentLength"] = group_settings.get(
                "SegmentLength", 10
            )
        elif group_settings_type == GroupSettings.FILE_GROUP_SETTINGS:
            # This is the default group settings
            group_settings_key = GroupSettings.FILE_GROUP_SETTINGS_KEY
        else:
            group_type = group_settings_type
            error_msg = f"Unsupported group settings type: {group_type}"
            raise ValueError(error_msg)

        group_settings[group_settings_key]["Destination"] = (
            f"s3://{destination_bucket}/{destination}"
        )


class GroupSettings:
    """
    Constants for AWS MediaConvert group settings types used in job configuration.
    """

    HLS_GROUP_SETTINGS = "HLS_GROUP_SETTINGS"
    HLS_GROUP_SETTINGS_KEY = "HlsGroupSettings"

    FILE_GROUP_SETTINGS = "FILE_GROUP_SETTINGS"
    FILE_GROUP_SETTINGS_KEY = "FileGroupSettings"
