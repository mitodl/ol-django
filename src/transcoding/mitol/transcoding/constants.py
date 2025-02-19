"""This module contains constants used in the transcoding app."""

BAD_REQUEST_MSG = "Token cannot be empty!"
TRANSCODE_JOB_SUBSCRIPTION_URL = (
    "https://sns.{AWS_REGION}.amazonaws.com/?Action=ConfirmSubscription&"
    "TopicArn=arn:aws:sns:{AWS_REGION}:{AWS_ACCOUNT_ID}:"
    "MediaConvertJobAlert&Token={TOKEN}"
)
