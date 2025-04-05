"""This module contains constants used in the transcoding app."""

BAD_REQUEST_MSG = "Token cannot be empty!"
TRANSCODE_JOB_SUBSCRIPTION_URL = (
    "https://sns.{AWS_REGION}.amazonaws.com/?Action=ConfirmSubscription&"
    "TopicArn=arn:aws:sns:{AWS_REGION}:{AWS_ACCOUNT_ID}:"
    "MediaConvertJobAlert&Token={TOKEN}"
)


class GroupSettings:
    """
    Constants for AWS MediaConvert group settings types used in job configuration.
    """

    HLS_GROUP_SETTINGS = "HLS_GROUP_SETTINGS"
    HLS_GROUP_SETTINGS_KEY = "HlsGroupSettings"

    FILE_GROUP_SETTINGS = "FILE_GROUP_SETTINGS"
    FILE_GROUP_SETTINGS_KEY = "FileGroupSettings"
