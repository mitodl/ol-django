"""API for the transcoding app."""

import json
from pathlib import Path
from typing import Optional

import boto3
from django.conf import settings

from mitol.transcoding.constants import GroupSettings


def get_destination_path(
    video_source_key: str,
    source_prefix: str = "",
    destination_prefix: str = "",
) -> str:
    """
    Calculate the destination path for transcoded files.

    Args:
        video_source_key (str): S3 key for the video source.
        source_prefix (str): Prefix for the source video.
        destination_prefix (str): Prefix for the destination video.

    Returns:
        str: Destination path for the transcoded files.
    """
    if source_prefix:
        destination_path = Path(
            video_source_key.replace(
                source_prefix,
                destination_prefix,
            )
        )
    else:
        destination_path = Path(destination_prefix, video_source_key)

    return str(destination_path.parent / destination_path.stem)


def make_media_convert_job(  # noqa: PLR0913
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
        group_settings (dict, optional): Settings for output groups. Defaults to None.

    Returns:
        dict: MediaConvert job details.
    """

    if group_settings is None:
        group_settings = {}

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

        destination = get_destination_path(
            video_source_key=video_source_key,
            source_prefix=source_prefix,
            destination_prefix=destination_prefix,
        )

        job_dict["Settings"]["Inputs"][0]["FileInput"] = (
            f"s3://{source_bucket}/{video_source_key}"
        )

        add_group_settings(job_dict, destination, destination_bucket, group_settings)

    return job_dict


def media_convert_job(video_source_key: str) -> dict:
    """
    Create a MediaConvert job.
    Args:
        video_source_key (str): S3 key for the video source.
    Returns:
        dict: Response from MediaConvert job creation.
    """
    job_dict = make_media_convert_job(video_source_key)

    try:
        client = boto3.client(
            "mediaconvert",
            region_name=settings.AWS_REGION,
            endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
        )
        return client.create_job(**job_dict)

    except Exception as e:
        err_msg = f"Failed to create MediaConvert client: {e}"
        raise ValueError(err_msg) from e


def _filter_mp4_groups(output_groups: list) -> list:
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


def _is_thumbnail_group(group: dict) -> bool:
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


def _get_output_path(
    destination: str,
    destination_bucket: str,
    *,  # keyword-only arguments
    is_thumbnail_group: bool = False,
    thumbnail_bucket: Optional[str] = settings.VIDEO_S3_THUMBNAIL_BUCKET,
    thumbnail_prefix: Optional[str] = settings.VIDEO_S3_THUMBNAIL_PREFIX,
) -> str:
    """
    Get the appropriate output path based on group type and settings.
    Args:
        is_thumbnail_group (bool): Flag indicating if the group is for thumbnails.
        destination (str): Destination path for the output files.
        destination_bucket (str): S3 bucket for the transcoded output.
        thumbnail_bucket (str, optional): S3 bucket for thumbnail generation.
        thumbnail_prefix (str, optional): Prefix for the thumbnail video.
    Returns:
        str: Output path for the MediaConvert job.
    """

    # Use Django settings for thumbnail bucket/prefix, with fallbacks
    if is_thumbnail_group:
        # Create the thumbnail destination path from the video source path
        thumbnail_destination = get_destination_path(
            video_source_key=str(Path(destination).parent),
            destination_prefix=(thumbnail_prefix or settings.VIDEO_S3_TRANSCODE_PREFIX),
        )
        return f"s3://{thumbnail_bucket or destination_bucket}/{thumbnail_destination}"
    return f"s3://{destination_bucket}/{destination}"


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
        destination_bucket (str): S3 bucket for the transcoded output.
        group_settings (dict): Group settings for the job.
    """
    exclude_mp4 = group_settings.get("exclude_mp4", False)
    output_groups = job_dict["Settings"]["OutputGroups"]

    if exclude_mp4:
        filtered_groups = _filter_mp4_groups(output_groups)
        job_dict["Settings"]["OutputGroups"] = filtered_groups
        output_groups = filtered_groups

    for group in output_groups:
        output_group_settings = group["OutputGroupSettings"]
        group_settings_type = output_group_settings["Type"]

        is_thumbnail_group = _is_thumbnail_group(group)

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
        output_path = _get_output_path(
            destination,
            destination_bucket,
            is_thumbnail_group=is_thumbnail_group,
        )
        output_group_settings[group_settings_key]["Destination"] = output_path
