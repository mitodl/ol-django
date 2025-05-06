"""Test Cases for Djoser Views"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response

pytestmark = pytest.mark.django_db
EMAIL = "email@example.com"


@pytest.fixture
def user():
    from mitol.common.factories import UserFactory

    return UserFactory.create(email=EMAIL)


class TestDjoserView:
    """Tests for views that modify Djoser views"""

    @pytest.mark.parametrize(
        "response_status,expected_session_update",  # noqa: PT006
        [
            [status.HTTP_200_OK, True],  # noqa: PT007
            [status.HTTP_204_NO_CONTENT, True],  # noqa: PT007
            [status.HTTP_400_BAD_REQUEST, False],  # noqa: PT007
        ],
    )
    def test_password_change_session_update(
        self, mocker, response_status, expected_session_update, client, user
    ):
        """
        Tests that the password change view updates the Django session when the
        request succeeds.
        """
        mocker.patch(
            "mitol.authentication.views.djoser_views.UserViewSet.set_password",
            return_value=Response(data={}, status=response_status),
        )
        update_session_patch = mocker.patch(
            "mitol.authentication.views.djoser_views.update_session_auth_hash",
            return_value=mocker.Mock(),
        )
        client.force_login(user)
        client.post(reverse("set-password-api"), {})
        assert update_session_patch.called is expected_session_update
