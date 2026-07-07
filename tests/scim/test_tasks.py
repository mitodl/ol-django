import pytest
from celery.exceptions import MaxRetriesExceededError, Retry
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


def test_sync_users_to_scim_remote_batch_requeues_failed_users(mocker):
    """A partial sync failure should be re-queued for just the failed users"""
    users = UserFactory.create_batch(3)
    failed_users = users[:2]

    mocker.patch(
        "mitol.scim.tasks.api.sync_users_to_scim_remote",
        return_value=failed_users,
    )
    mock_retry = mocker.patch.object(
        tasks.sync_users_to_scim_remote_batch, "retry", side_effect=Retry
    )

    with pytest.raises(Retry):
        tasks.sync_users_to_scim_remote_batch(user_ids=[user.id for user in users])

    mock_retry.assert_called_once()
    call_kwargs = mock_retry.call_args.kwargs
    assert call_kwargs["kwargs"] == {"user_ids": [user.id for user in failed_users]}
    # a manual retry() call doesn't get retry_backoff applied automatically -
    # the task computes and passes its own countdown
    assert call_kwargs["countdown"] >= 0


def test_sync_users_to_scim_remote_batch_gives_up_after_max_retries(mocker, caplog):
    """Once retries are exhausted the failed users are logged, not raised"""
    users = UserFactory.create_batch(2)

    mocker.patch(
        "mitol.scim.tasks.api.sync_users_to_scim_remote",
        return_value=users,
    )
    mocker.patch.object(
        tasks.sync_users_to_scim_remote_batch,
        "retry",
        side_effect=MaxRetriesExceededError,
    )

    tasks.sync_users_to_scim_remote_batch(user_ids=[user.id for user in users])

    assert "Giving up on SCIM sync" in caplog.text


def test_sync_users_to_scim_remote_batch_no_op_on_full_success(mocker):
    """No retry is attempted when every user synced successfully"""
    users = UserFactory.create_batch(2)

    mocker.patch(
        "mitol.scim.tasks.api.sync_users_to_scim_remote",
        return_value=[],
    )
    mock_retry = mocker.patch.object(tasks.sync_users_to_scim_remote_batch, "retry")

    tasks.sync_users_to_scim_remote_batch(user_ids=[user.id for user in users])

    mock_retry.assert_not_called()
