"""Django settings for transcoding app."""

from mitol.common.envs import get_delimited_list, get_string

VIDEO_S3_TRANSCODE_ENDPOINT = get_string(
    name="VIDEO_S3_TRANSCODE_ENDPOINT",
    default="aws_mediaconvert_transcodes",
    description=("Endpoint to be used for AWS MediaConvert"),
)
VIDEO_TRANSCODE_QUEUE = get_string(
    name="VIDEO_TRANSCODE_QUEUE",
    default="Default",
    description=("Name of MediaConvert queue to use for transcoding"),
)
VIDEO_S3_TRANSCODE_BUCKET = get_string(
    name="VIDEO_S3_TRANSCODE_BUCKET",
    default="",
    description=("Bucket to be used for transcoding"),
)
VIDEO_S3_TRANSCODE_PREFIX = get_string(
    name="VIDEO_S3_TRANSCODE_PREFIX",
    default="",
    description=("Prefix for the transcoded video"),
)
VIDEO_S3_UPLOAD_PREFIX = get_string(
    name="VIDEO_S3_UPLOAD_PREFIX",
    default="",
    description=("Prefix for the source video"),
)
POST_TRANSCODE_ACTIONS = get_delimited_list(
    name="POST_TRANSCODE_ACTIONS",
    default=[],
    description="Actions to perform before publish",
)
TRANSCODE_JOB_TEMPLATE = get_string(
    name="TRANSCODE_JOB_TEMPLATE",
    default="",
    description="Path to the transcoding job template",
)
