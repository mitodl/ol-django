from mitol.common.utils.celery import get_celery_app
from django.contrib.auth import get_user_model

User = get_user_model()
app = get_celery_app()


@app.task(acks_late=True)
def sync_users_to_scim_remote_batch(*, user_ids: list[int], create: bool = True, update: bool = False):
    """Sync a set of users to the scim remote"""
    # TODO: search for the users by email
    # TODO: create users if they don't exist
    # TODO: otherwise update scim_* fields to match existing user


@app.task()
def sync_all_users_to_scim_remote():
