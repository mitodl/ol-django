"""Test for transcoding app"""

from mitol.transcoding.utils import get_subscribe_url


def test_get_subscribe_url(mocker):
    """Test get_subscribe_url to format ConfirmSubscription url correctly"""

    fake_region = "us-east-1"
    fake_account_id = "1234567890"

    mocker.patch("django.conf.settings.AWS_REGION", fake_region)
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", fake_account_id)

    assert (
        get_subscribe_url("fake-token")
        == (f"https://sns.{fake_region}.amazonaws.com/?Action=ConfirmSubscription&"
        f"TopicArn=arn:aws:sns:{fake_region}:{fake_account_id}:"
        "MediaConvertJobAlert&Token=fake-token")
    )
