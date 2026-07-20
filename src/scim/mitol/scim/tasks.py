import logging

import celery
import requests
from celery.exceptions import MaxRetriesExceededError
from celery.utils.time import get_exponential_backoff_interval
from django.contrib.auth import get_user_model
from django.db.models import Q
from mitol.common.utils.celery import get_celery_app
from mitol.common.utils.collections import chunks
from mitol.scim import api

User = get_user_model()
app = get_celery_app()

RETRY_BACKOFF_MAX_SECONDS = 600

log = logging.getLogger()


@app.task(
    bind=True,
    acks_late=True,
    max_retries=5,
    autoretry_for=(requests.RequestException,),
    retry_backoff=True,
    retry_backoff_max=RETRY_BACKOFF_MAX_SECONDS,
    retry_jitter=True,
)
def sync_users_to_scim_remote_batch(self, *, user_ids: list[int]):
    """Sync a set of users to the scim remote"""
    # materialized rather than left lazy: sync_users_to_scim_remote iterates
    # its argument more than once (partitioning, then again to find missing
    # users), and a QuerySet doesn't guarantee that's a single query
    users = list(User.objects.filter(id__in=user_ids).order_by("id"))
    failed_users = api.sync_users_to_scim_remote(users)

    if not failed_users:
        return

    failed_user_ids = [user.id for user in failed_users]
    try:
        # re-queue only the users that failed (a bad chunk, a rejected bulk
        # op) instead of the previous behavior of silently dropping them
        # until the next full sweep. This is a manual retry() call rather
        # than an autoretry_for-raised exception, so the configured
        # retry_backoff isn't applied automatically - compute the same
        # exponential-backoff-with-jitter delay explicitly.
        countdown = get_exponential_backoff_interval(
            factor=1,
            retries=self.request.retries,
            maximum=RETRY_BACKOFF_MAX_SECONDS,
            full_jitter=True,
        )
        raise self.retry(kwargs={"user_ids": failed_user_ids}, countdown=countdown)
    except MaxRetriesExceededError:
        log.error(  # noqa: TRY400
            "Giving up on SCIM sync for %d user(s) after %d retries: %s",
            len(failed_user_ids),
            self.max_retries,
            failed_user_ids,
        )


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
