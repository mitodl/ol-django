import pytest
from mitol.common.factories import UserFactory
from mitol.scim import tasks

pytestmark = pytest.mark.django_db


def test_sync_all_users_to_sicm_remote(settings, mocker):
    settings.MITOL_SCIM_SYNC_TASK_SIZE = 5
    mock_api = mocker.patch("mitol.scim.tasks.api")

    users = UserFactory.create_batch(12)
    UserFactory.create_batch(10, is_active=False)

    tasks.sync_all_users_to_scim_remote.delay()

    assert mock_api.sync_users_to_scim_remote.call_count == 3

    mock_api.sync_users_to_scim_remote.assert_called_with(users[:5])
    mock_api.sync_users_to_scim_remote.assert_called_with(users[5:10])
    mock_api.sync_users_to_scim_remote.assert_called_with(users[10:])
