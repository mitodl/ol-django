"""Test for transcoding views"""

import json

import pytest
from mitol.transcoding.constants import BAD_REQUEST_MSG
from mitol.transcoding.views import TranscodeJobView
from rest_framework import status
from rest_framework.test import APIRequestFactory


@pytest.fixture
def api_factory():
    """Create an APIRequestFactory"""
    return APIRequestFactory()


@pytest.fixture
def transcode_job_view():
    """Create an instance of TranscodeJobView"""
    return TranscodeJobView.as_view()


@pytest.mark.parametrize(
    "token_provided",
    [
        True,
        False,
    ],
)
def test_subscription_confirmation_token_validation(
    mocker, api_factory, transcode_job_view, token_provided
):
    """Test subscription confirmation token validation"""
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", "123456789012")

    if token_provided:
        subscribe_url = "https://example.com/confirm"
        mocker.patch(
            "mitol.transcoding.views.get_subscribe_url", return_value=subscribe_url
        )
        mock_get = mocker.patch("requests.get")

    request_body = {
        "Type": "SubscriptionConfirmation",
        "TopicArn": "arn:aws:sns:us-east-1:123456789012:MediaConvertJobAlert",
        "SubscribeURL": "https://example.com/subscribe",
    }

    if token_provided:
        request_body["Token"] = "valid-token"  # noqa: S105

    request = api_factory.post(
        "/webhook/", json.dumps(request_body), content_type="application/json"
    )

    response = transcode_job_view(request)
    if not token_provided:
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"detail": BAD_REQUEST_MSG}
    else:
        assert response.status_code == status.HTTP_200_OK
        mock_get.assert_called_once_with(subscribe_url, timeout=60)


@pytest.mark.parametrize(
    ("message_type", "account_id_matches"),
    [
        ("SubscriptionConfirmation", True),
        ("SubscriptionConfirmation", False),
        ("Notification", True),
        ("Notification", False),
    ],
)
def test_account_validation(
    mocker, api_factory, transcode_job_view, message_type, account_id_matches
):
    """Test AWS account validation for different message types"""
    real_account_id = "123456789012"
    wrong_account_id = "999999999999"
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", real_account_id)

    if message_type == "SubscriptionConfirmation":
        mocker.patch(
            "mitol.transcoding.views.get_subscribe_url",
            return_value="https://example.com/confirm",
        )
        mocker.patch("requests.get")

        request_body = {
            "Type": message_type,
            "SubscribeURL": "https://example.com/subscribe",
            "Token": "valid-token",
        }

        account_id = real_account_id if account_id_matches else wrong_account_id
        request_body["TopicArn"] = (
            f"arn:aws:sns:us-east-1:{account_id}:MediaConvertJobAlert"
        )
    else:
        if account_id_matches:
            mocker.patch("django.conf.settings.POST_TRANSCODE_ACTIONS", [])

        account_id = real_account_id if account_id_matches else wrong_account_id
        request_body = {
            "Type": message_type,
            "account": account_id,
            "detail": {"jobId": "job-123"},
        }

    request = api_factory.post(
        "/webhook/", json.dumps(request_body), content_type="application/json"
    )
    response = transcode_job_view(request)
    if not account_id_matches:
        assert response.status_code == status.HTTP_403_FORBIDDEN
    else:
        assert response.status_code == status.HTTP_200_OK


def test_notification_with_multiple_actions(mocker, api_factory, transcode_job_view):
    """Test notification with multiple post-transcode actions"""
    mocker.patch("django.conf.settings.AWS_ACCOUNT_ID", "123456789012")
    mocker.patch(
        "django.conf.settings.POST_TRANSCODE_ACTIONS",
        [
            "tests.transcoding.test_views.mock_action1",
            "tests.transcoding.test_views.mock_action2",
        ],
    )

    mock_action1 = mocker.MagicMock()
    mock_action2 = mocker.MagicMock()
    mocker.patch("tests.transcoding.test_views.mock_action1", mock_action1)
    mocker.patch("tests.transcoding.test_views.mock_action2", mock_action2)

    request_body = {
        "Type": "Notification",
        "account": "123456789012",
        "detail": {"jobId": "job-123", "status": "COMPLETE"},
    }
    request = api_factory.post(
        "/webhook/", json.dumps(request_body), content_type="application/json"
    )

    response = transcode_job_view(request)
    assert response.status_code == status.HTTP_200_OK

    mock_action1.assert_called_once_with(request_body["detail"])
    mock_action2.assert_called_once_with(request_body["detail"])


def mock_action1(detail):
    """Mock action 1 for testing"""


def mock_action2(detail):
    """Mock action 2 for testing"""
