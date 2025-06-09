import pytest
from mitol.common.factories import UserFactory
from mitol.common.factories.defaults import ScimUserFactory, SsoUserFactory
from mitol.scim import tasks
from more_itertools import flatten

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("never_synced_only", [True, False])
def test_sync_all_users_to_scim_remote(mocker, never_synced_only):
    synced_users = ScimUserFactory.create_batch(10)
    unsynced_users = UserFactory.create_batch(10)
    sso_users = SsoUserFactory.create_batch(10)

    expected_users = [
        *sso_users,
        *unsynced_users,
    ]

    if not never_synced_only:
        expected_users.extend(synced_users)

    mock_replace = mocker.patch(
        "mitol.scim.tasks.sync_all_users_to_scim_remote.replace", autospec=True
    )

    tasks.sync_all_users_to_scim_remote(never_synced_only=never_synced_only)

    mock_replace.assert_called_once()

    group = mock_replace.call_args[0][0]

    user_ids = flatten([task.kwargs["user_ids"] for task in group.tasks])

    assert set(user_ids) == {user.id for user in expected_users}
