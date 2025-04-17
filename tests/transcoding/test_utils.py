"""Test for transcoding app"""

import pytest
from django.conf import settings


# Import the function directly instead of the whole module
@pytest.fixture()
def _mock_settings(mocker):
    """Mock AWS settings for tests"""
    mocker.patch("django.conf.settings.AWS_STORAGE_BUCKET_NAME", "test-bucket")
    mocker.patch("django.conf.settings.AWS_REGION", "us-east-1")
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", "1234567890")


@pytest.mark.usefixtures("_mock_settings")
def test_file_config():
    """Test FileConfig to ensure it sets the correct attributes"""
    from mitol.transcoding.utils import FileConfig

    file_config = FileConfig(
        video_source_key="test-key",
        source_prefix="source-prefix",
        source_bucket="source-bucket",
        destination_prefix="dest-prefix",
        destination_bucket="dest-bucket",
        group_settings={"key": "value"},
    )

    assert file_config.video_source_key == "test-key"
    assert file_config.source_prefix == "source-prefix"
    assert file_config.source_bucket == "source-bucket"
    assert file_config.destination_prefix == "dest-prefix"
    assert file_config.destination_bucket == "dest-bucket"
    assert file_config.group_settings == {"key": "value"}


@pytest.mark.usefixtures("_mock_settings")
def test_get_subscribe_url():
    """Test get_subscribe_url to format ConfirmSubscription url correctly"""
    from mitol.transcoding.utils import get_subscribe_url

    assert get_subscribe_url("fake-token") == (
        f"https://sns.{settings.AWS_REGION}.amazonaws.com/?Action=ConfirmSubscription&"
        f"TopicArn=arn:aws:sns:{settings.AWS_REGION}:{settings.AWS_ACCOUNT_ID}:"
        "MediaConvertJobAlert&Token=fake-token"
    )
