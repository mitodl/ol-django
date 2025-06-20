"""Test for transcoding app utils"""

import pytest
from mitol.transcoding.utils import (
    FileConfig,
    filter_mp4_groups,
    get_output_path,
    get_subscribe_url,
    is_thumbnail_group,
)


def test_get_subscribe_url(mocker):
    """Test get_subscribe_url to format ConfirmSubscription url correctly"""

    fake_region = "us-east-1"
    fake_account_id = "1234567890"

    mocker.patch("django.conf.settings.AWS_REGION", fake_region)
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", fake_account_id)

    assert get_subscribe_url("fake-token") == (
        f"https://sns.{fake_region}.amazonaws.com/?Action=ConfirmSubscription&"
        f"TopicArn=arn:aws:sns:{fake_region}:{fake_account_id}:"
        "MediaConvertJobAlert&Token=fake-token"
    )


def test_file_config():
    """Test FileConfig initialization with various parameters"""
    file_config = FileConfig(
        "test-video.mp4",
        source_prefix="uploads/",
        source_bucket="source-bucket",
        destination_prefix="transcodes/",
        destination_bucket="destination-bucket",
    )

    assert file_config.video_source_key == "test-video.mp4"
    assert file_config.source_prefix == "uploads/"
    assert file_config.source_bucket == "source-bucket"
    assert file_config.destination_prefix == "transcodes/"
    assert file_config.destination_bucket == "destination-bucket"
    assert file_config.group_settings == {}


def test_file_config_init_with_group_settings():
    """Test FileConfig initialization with group settings"""
    group_settings = {
        "HlsGroupSettings": {"SegmentLength": 6, "Destination": "s3://bucket/path/"}
    }

    file_config = FileConfig("test-video.mp4", group_settings=group_settings)

    assert file_config.group_settings == group_settings
    assert file_config.video_source_key == "test-video.mp4"


def test_file_config_init_with_defaults():
    """Test FileConfig initialization with default parameters"""
    file_config = FileConfig("test-video.mp4")

    assert file_config.video_source_key == "test-video.mp4"
    assert file_config.source_prefix == ""
    assert file_config.source_bucket == "test-bucket"
    assert file_config.destination_prefix == ""
    assert file_config.destination_bucket == "test-bucket"
    assert file_config.group_settings == {}


@pytest.mark.parametrize(
    ("group", "expected_result"),
    [
        (
            {
                "Outputs": [
                    {"VideoDescription": {"CodecSettings": {"Codec": "FRAME_CAPTURE"}}}
                ]
            },
            True,
        ),
        (
            {"Outputs": [{"VideoDescription": {"CodecSettings": {"Codec": "H_264"}}}]},
            False,
        ),
        ({}, False),
    ],
)
def test_is_thumbnail_group(group, expected_result):
    """Test is_thumbnail_group correctly identifies thumbnail groups"""
    assert is_thumbnail_group(group) is expected_result


@pytest.mark.parametrize(
    ("output_groups", "expected_count", "expected_container"),
    [
        (
            [
                {"Outputs": [{"ContainerSettings": {"Container": "MP4"}}]},
                {"Outputs": [{"ContainerSettings": {"Container": "HLS"}}]},
            ],
            1,
            "HLS",
        ),
        ([], 0, None),
        ([{"Outputs": [{"ContainerSettings": {"Container": "MP4"}}]}], 0, None),
        (
            [
                {"Outputs": [{"ContainerSettings": {"Container": "HLS"}}]},
                {"Outputs": [{"ContainerSettings": {"Container": "CMAF"}}]},
            ],
            2,
            None,
        ),
    ],
)
def test_filter_mp4_groups(output_groups, expected_count, expected_container):
    """Test filter_mp4_groups properly filters out MP4 groups"""
    filtered_groups = filter_mp4_groups(output_groups)

    assert len(filtered_groups) == expected_count

    if expected_container and filtered_groups:
        assert (
            filtered_groups[0]["Outputs"][0]["ContainerSettings"]["Container"]
            == expected_container
        )


@pytest.mark.parametrize(
    ("is_thumbnail_group", "expected_bucket", "expected_path_prefix"),
    [
        (False, "transcode-bucket", "transcodes/test-video"),
        (True, "thumbnail-bucket", "thumbnails/test-video"),
    ],
)
def test_get_output_path(is_thumbnail_group, expected_bucket, expected_path_prefix):
    """Test get_output_path constructs the correct paths for different group types"""

    file_config = FileConfig(
        "test-video.mp4",
        source_prefix="uploads/",
        destination_prefix="transcodes/",
        destination_bucket="transcode-bucket",
    )
    file_config.destination = "transcodes/test-video"

    output_path = get_output_path(
        file_config,
        is_thumbnail_group=is_thumbnail_group,
        thumbnail_bucket="thumbnail-bucket",
        thumbnail_prefix="thumbnails/",
    )

    expected_output_path = f"s3://{expected_bucket}/{expected_path_prefix}"
    assert output_path == expected_output_path
