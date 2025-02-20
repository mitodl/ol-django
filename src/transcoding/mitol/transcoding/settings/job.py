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
