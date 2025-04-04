"""API for the transcoding app."""

import json
from pathlib import Path
from typing import Optional

import boto3
from django.conf import settings

from mitol.transcoding.constants import GroupSettings


def media_convert_job(  # noqa: PLR0913
    video_source_key: str,
    source_prefix: str = settings.VIDEO_S3_UPLOAD_PREFIX,
    source_bucket: str = settings.AWS_STORAGE_BUCKET_NAME,
    destination_prefix: str = settings.VIDEO_S3_TRANSCODE_PREFIX,
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

        add_group_settings(job_dict, destination, destination_bucket, group_settings)

        return client.create_job(**job_dict)


def add_group_settings(
    job_dict: dict,
    destination: str,
    destination_bucket: str,
    group_settings: dict,
) -> None:
    """
    Add group settings to the MediaConvert job dictionary.

    Args:
        job_dict (dict): MediaConvert job dictionary.
        destination (str): Destination path for the output files.
        group_settings (dict): Group settings for the job.
        destination_bucket (str, optional): S3 bucket for the transcoded output.
    """

    exclude_mp4 = group_settings.get("exclude_mp4", False)
    output_groups = job_dict["Settings"]["OutputGroups"]

    if exclude_mp4:
        # Remove the MP4 output group if not needed
        output_groups = [
            group
            for group in output_groups
            if group["OutputGroupSettings"]["Type"] != GroupSettings.FILE_GROUP_SETTINGS
        ]

    for group in output_groups:
        output_group_settings = group["OutputGroupSettings"]
        group_settings_type = group["OutputGroupSettings"]["Type"]
        if group_settings_type == GroupSettings.HLS_GROUP_SETTINGS:
            group_settings_key = GroupSettings.HLS_GROUP_SETTINGS_KEY
            output_group_settings[group_settings_key]["SegmentLength"] = (
                group_settings.get("SegmentLength", 10)
            )
            output_group_settings[group_settings_key]["AdditionalManifests"][0][
                "ManifestNameModifier"
            ] = group_settings.get("ManifestNameModifier", "__index")
        elif group_settings_type == GroupSettings.FILE_GROUP_SETTINGS:
            group_settings_key = GroupSettings.FILE_GROUP_SETTINGS_KEY
        else:
            group_type = group_settings_type
            error_msg = f"Unsupported group settings type: {group_type}"
            raise ValueError(error_msg)

        output_group_settings[group_settings_key]["Destination"] = (
            f"s3://{destination_bucket}/{destination}"
        )
