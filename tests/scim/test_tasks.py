import pytest
from django.contrib.auth import get_user_model
from mitol.common.factories import UserFactory
from mitol.common.factories.defaults import ScimUserFactory, SsoUserFactory
from mitol.scim import tasks
from more_itertools import flatten

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.mark.parametrize("never_synced_only", [True, False])
def test_sync_all_users_to_scim_remote(mocker, never_synced_only):
    existing_user_ids = {user.id for user in User.objects.all()}

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

    assert (set(user_ids) - existing_user_ids) == {user.id for user in expected_users}


def test_sync_users_to_scim_remote_batch_drains_the_generator(mocker):
    """sync_users_to_scim_remote is a generator - it does nothing until
    iterated. sync_users_to_scim_remote_batch must actually drain it, not
    just call it and discard the (unexecuted) generator object, or the
    sync silently never runs.
    """
    users = UserFactory.create_batch(3)
    consumed_ids = []

    def _fake_sync(synced_users):
        for user in synced_users:
            consumed_ids.append(user.id)
            yield mocker.Mock(user=user)

    mocker.patch(
        "mitol.scim.tasks.api.sync_users_to_scim_remote", side_effect=_fake_sync
    )

    tasks.sync_users_to_scim_remote_batch(user_ids=[user.id for user in users])

    assert consumed_ids == [user.id for user in users]
