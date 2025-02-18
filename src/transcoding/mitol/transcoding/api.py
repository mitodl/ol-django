"""API for the transcoding app."""

import json
import os

import boto3
from django.conf import settings


def create_media_convert_job(video_source_key):
    """Create a MediaConvert job for a Video"""
    source_prefix = settings.DRIVE_S3_UPLOAD_PREFIX
    client = boto3.client(
        "mediaconvert",
        region_name=settings.AWS_REGION,
        endpoint_url=settings.VIDEO_S3_TRANSCODE_ENDPOINT,
    )
    with open(  # noqa: PTH123
        os.path.join(  # noqa: PTH118
            os.getcwd(),  # noqa: PTH109
            "config/mediaconvert.json",
        ),
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
        destination = os.path.splitext(  # noqa: PTH122
            video_source_key.replace(
                source_prefix,
                settings.VIDEO_S3_TRANSCODE_PREFIX,
            )
        )[0]
        job_dict["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
            "FileGroupSettings"
        ]["Destination"] = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{destination}"
        job_dict["Settings"]["Inputs"][0]["FileInput"] = (
            f"s3://{settings.AWS_STORAGE_BUCKET_NAME}/{video_source_key}"
        )
        return client.create_job(**job_dict)


def update_video_job(video_job: VideoJob, results: dict):
    """Update a VideoJob and associated Video, VideoFiles based on MediaConvert results"""  # noqa: E501
    video_job.job_output = results
    status = results.get("status")
    video = video_job.video
    if status == "COMPLETE":
        video_job.status = VideoJobStatus.COMPLETE
        try:
            process_video_outputs(video, results.get("outputGroupDetails"))
        except:  # pylint:disable=bare-except  # noqa: E722
            log.exception("Error processing video outputs for job %s", video_job.job_id)
    elif status == "ERROR":
        video.status = VideoStatus.FAILED
        video_job.status = VideoJobStatus.FAILED
        log.error(
            "Transcode failure for %s, error code %s: %s",
            video.source_key,
            results.get("errorCode"),
            results.get("errorMessage"),
        )
        video_job.error_code = str(results.get("errorCode"))
        video_job.error_message = results.get("errorMessage")
    video_job.save()
    video.save()