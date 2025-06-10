import logging

import celery
from django.contrib.auth import get_user_model
from django.db.models import Q

from mitol.common.utils.celery import get_celery_app
from mitol.common.utils.collections import chunks
from mitol.scim import api

User = get_user_model()
app = get_celery_app()


log = logging.getLogger()


@app.task(acks_late=True)
def sync_users_to_scim_remote_batch(*, user_ids: list[int]):
    """Sync a set of users to the scim remote"""
    users = User.objects.filter(id__in=user_ids).order_by("id")
    api.sync_users_to_scim_remote(users)


@app.task(bind=True, acks_late=True)
def sync_all_users_to_scim_remote(self, *, never_synced_only: bool = False):
    user_q = (
        User.objects.values_list("id", flat=True).filter(is_active=True).order_by("id")
    )

    if never_synced_only:
        user_q = user_q.filter(Q(global_id="") | Q(scim_external_id=None))

    msg = f"Syncing {user_q.count()} users to SCIM remote"
    log.info(msg)

    return self.replace(
        celery.group(
            sync_users_to_scim_remote_batch.si(user_ids=user_ids)
            for user_ids in chunks(
                user_q,
                chunk_size=1000,
            )
        )
    )
