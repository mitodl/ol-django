"""Test for transcoding API"""

import json
from pathlib import Path

import boto3
import pytest
from mitol.transcoding.api import (
    add_group_settings,
    get_destination_path,
    make_media_convert_job,
    media_convert_job,
)
from mitol.transcoding.constants import GroupSettings
from mitol.transcoding.utils import FileConfig


@pytest.fixture
def mock_file_config():
    """Create a mock file config instance"""
    return FileConfig(
        "uploads/test-video.mp4",
        source_prefix="uploads/",
        source_bucket="source-bucket",
        destination_prefix="transcodes/",
        destination_bucket="destination-bucket",
    )


@pytest.fixture
def mock_job_dict():
    """Create a mock MediaConvert job dictionary"""
    return {
        "UserMetadata": {"filter": "default"},
        "Queue": "",
        "Role": "",
        "Settings": {
            "Inputs": [{"FileInput": ""}],
            "OutputGroups": [
                {
                    "OutputGroupSettings": {
                        "Type": GroupSettings.HLS_GROUP_SETTINGS,
                        GroupSettings.HLS_GROUP_SETTINGS_KEY: {
                            "SegmentLength": 6,
                            "AdditionalManifests": [{"ManifestNameModifier": ""}],
                        },
                        "Destination": "",
                    },
                    "Outputs": [
                        {"VideoDescription": {"CodecSettings": {"Codec": "H_264"}}}
                    ],
                },
                {
                    "OutputGroupSettings": {
                        "Type": GroupSettings.FILE_GROUP_SETTINGS,
                        GroupSettings.FILE_GROUP_SETTINGS_KEY: {"Destination": ""},
                    },
                    "Outputs": [
                        {
                            "VideoDescription": {
                                "CodecSettings": {"Codec": "FRAME_CAPTURE"}
                            },
                            "ContainerSettings": {"Container": "RAW"},
                        }
                    ],
                },
                {
                    "OutputGroupSettings": {
                        "Type": GroupSettings.FILE_GROUP_SETTINGS,
                        GroupSettings.FILE_GROUP_SETTINGS_KEY: {"Destination": ""},
                    },
                    "Outputs": [{"ContainerSettings": {"Container": "MP4"}}],
                },
            ],
        },
    }


@pytest.mark.parametrize(
    ("source_prefix", "expected_destination"),
    [
        ("uploads/", "transcodes/test-video"),
        ("", "transcodes/uploads/test-video"),
        ("other-prefix/", "uploads/test-video"),
    ],
)
def test_get_destination_path(mock_file_config, source_prefix, expected_destination):
    """Test get_destination_path with various source prefixes"""
    mock_file_config.video_source_key = "uploads/test-video.mp4"
    mock_file_config.source_prefix = source_prefix
    mock_file_config.destination_prefix = "transcodes/"

    destination_path = get_destination_path(mock_file_config)
    assert destination_path == expected_destination


def test_add_group_settings_basic(mock_file_config, mock_job_dict):
    """Test add_group_settings with basic settings"""
    mock_file_config.destination = "transcodes/test-video"

    add_group_settings(mock_job_dict, mock_file_config)

    output_groups = mock_job_dict["Settings"]["OutputGroups"]
    assert len(output_groups) == 3  # noqa: PLR2004

    hls_settings = output_groups[0]["OutputGroupSettings"][
        GroupSettings.HLS_GROUP_SETTINGS_KEY
    ]
    assert hls_settings["SegmentLength"] == 10  # noqa: PLR2004
    assert hls_settings["AdditionalManifests"][0]["ManifestNameModifier"] == "__index"

    assert output_groups[0]["OutputGroupSettings"][
        GroupSettings.HLS_GROUP_SETTINGS_KEY
    ]["Destination"].startswith("s3://destination-bucket/transcodes/test-video")
    assert output_groups[1]["OutputGroupSettings"][
        GroupSettings.FILE_GROUP_SETTINGS_KEY
    ]["Destination"].startswith("s3://test-bucket/transcodes/test-video")
    assert output_groups[2]["OutputGroupSettings"][
        GroupSettings.FILE_GROUP_SETTINGS_KEY
    ]["Destination"].startswith("s3://destination-bucket/transcodes/test-video")


def test_add_group_settings_with_filters(mock_file_config, mock_job_dict):
    """Test add_group_settings with filters"""
    mock_file_config.destination = "transcodes/test-video"
    mock_file_config.group_settings = {"exclude_mp4": True, "exclude_thumbnail": True}

    add_group_settings(mock_job_dict, mock_file_config)

    output_groups = mock_job_dict["Settings"]["OutputGroups"]
    assert len(output_groups) == 1
    assert (
        output_groups[0]["OutputGroupSettings"]["Type"]
        == GroupSettings.HLS_GROUP_SETTINGS
    )


def test_add_group_settings_with_custom_settings(mock_file_config, mock_job_dict):
    """Test add_group_settings with custom settings"""
    mock_file_config.destination = "transcodes/test-video"
    mock_file_config.group_settings = {
        "SegmentLength": 15,
        "ManifestNameModifier": "__custom",
    }

    add_group_settings(mock_job_dict, mock_file_config)

    hls_settings = mock_job_dict["Settings"]["OutputGroups"][0]["OutputGroupSettings"][
        GroupSettings.HLS_GROUP_SETTINGS_KEY
    ]
    assert hls_settings["SegmentLength"] == 15  # noqa: PLR2004
    assert hls_settings["AdditionalManifests"][0]["ManifestNameModifier"] == "__custom"


def test_add_group_settings_invalid_type(mock_file_config, mock_job_dict):
    """Test add_group_settings with invalid group type"""
    mock_file_config.destination = "transcodes/test-video"

    mock_job_dict["Settings"]["OutputGroups"][0]["OutputGroupSettings"]["Type"] = (
        "INVALID_TYPE"
    )

    with pytest.raises(ValueError, match="Unsupported group settings type"):
        add_group_settings(mock_job_dict, mock_file_config)


def test_make_media_convert_job(mock_file_config, mocker):
    """Test make_media_convert_job"""
    mocker.patch("django.conf.settings.TRANSCODE_JOB_TEMPLATE", "mock_template.json")
    mocker.patch("django.conf.settings.VIDEO_TRANSCODE_QUEUE", "default")
    mocker.patch("django.conf.settings.AWS_REGION", "us-east-1")
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", "123456789012")
    mocker.patch("django.conf.settings.AWS_ROLE_NAME", "MediaConvertRole")

    mock_template = {
        "UserMetadata": {"filter": ""},
        "Queue": "",
        "Role": "",
        "Settings": {
            "Inputs": [{"FileInput": ""}],
            "OutputGroups": [
                {
                    "OutputGroupSettings": {
                        "Type": GroupSettings.HLS_GROUP_SETTINGS,
                        GroupSettings.HLS_GROUP_SETTINGS_KEY: {
                            "SegmentLength": 6,
                            "AdditionalManifests": [{"ManifestNameModifier": ""}],
                        },
                        "Destination": "",
                    },
                    "Outputs": [
                        {"VideoDescription": {"CodecSettings": {"Codec": "H_264"}}}
                    ],
                },
            ],
        },
    }

    mock_open = mocker.mock_open(read_data=json.dumps(mock_template))
    mocker.patch("pathlib.Path.open", mock_open)
    mocker.patch("pathlib.Path.cwd", return_value=Path("/"))

    job_dict = make_media_convert_job(mock_file_config)

    assert job_dict["UserMetadata"]["filter"] == "default"
    assert (
        job_dict["Queue"]
        == "arn:aws:mediaconvert:us-east-1:123456789012:queues/default"
    )
    assert job_dict["Role"] == "arn:aws:iam::123456789012:role/MediaConvertRole"
    assert (
        job_dict["Settings"]["Inputs"][0]["FileInput"]
        == "s3://source-bucket/uploads/test-video.mp4"
    )


@pytest.mark.parametrize(
    ("exclude_mp4", "exclude_thumbnail"),
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_media_convert_job(mocker, exclude_mp4, exclude_thumbnail):
    """Test media_convert_job function with different filter combinations"""
    mock_client = mocker.MagicMock()
    mocker.patch("boto3.client", return_value=mock_client)

    mock_job_dict = {"job": "config"}
    mocker.patch(
        "mitol.transcoding.api.make_media_convert_job", return_value=mock_job_dict
    )

    mocker.patch(
        "django.conf.settings.VIDEO_S3_TRANSCODE_ENDPOINT",
        "https://mediaconvert.us-east-1.amazonaws.com",
    )
    mocker.patch("django.conf.settings.AWS_REGION", "us-east-1")

    group_settings = {}
    if exclude_mp4:
        group_settings["exclude_mp4"] = True
    if exclude_thumbnail:
        group_settings["exclude_thumbnail"] = True

    media_convert_job(
        "uploads/test-video.mp4",
        group_settings=group_settings,
    )

    boto3.client.assert_called_once_with(
        "mediaconvert",
        region_name="us-east-1",
        endpoint_url="https://mediaconvert.us-east-1.amazonaws.com",
    )

    mock_client.create_job.assert_called_once_with(**mock_job_dict)
