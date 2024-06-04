"""MIT Open feature flags"""

import hashlib
import json
import logging
from typing import Optional

import posthog
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import caches

log = logging.getLogger()
User = get_user_model()
durable_cache = caches["durable"]


class Features:
    """Enum for feature flags"""


def configure():
    """
    Configure the posthog default_client.

    The posthog library normally takes care of this but it doesn't
    expose all the client config options.
    """
    posthog.default_client = posthog.Client(
        api_key=getattr(settings, "POSTHOG_PROJECT_API_KEY", None),
        host=getattr(settings, "POSTHOG_API_HOST", None),
        debug=settings.DEBUG,
        on_error=None,
        send=None,
        sync_mode=False,
        poll_interval=30,
        disable_geoip=True,
        feature_flags_request_timeout_seconds=settings.POSTHOG_FEATURE_FLAG_REQUEST_TIMEOUT_MS
        / 1000,
        max_retries=settings.POSTHOG_MAX_RETRIES,
    )


def default_unique_id() -> str:
    """Get the default unique_id if it's not provided"""
    return settings.HOSTNAME


def _get_person_properties(unique_id: str) -> dict:
    """
    Get posthog person_properties based on unique_id
    """
    return {
        "environment": settings.ENVIRONMENT,
        "user_id": unique_id,
    }


def _generate_cache_key(key: str, unique_id: str, person_properties: dict) -> str:
    """
    Generate a cache key for the feature flag.

    To prevent collisions, we take the unique_id and person_properties that get
    passed to the feature flag functions below, combine them, and hash them.
    Append the flag key to this to store the value in the cache.
    """

    return "{}_{}".format(
        str(
            hashlib.sha256(
                json.dumps((unique_id, person_properties)).encode("utf-8")
            ).hexdigest()
        ),
        key,
    )


def get_all_feature_flags(opt_unique_id: Optional[str] = None):
    """
    Get the set of all feature flags
    """
    unique_id = opt_unique_id or default_unique_id()
    person_properties = _get_person_properties(unique_id)

    flag_data = posthog.get_all_flags(
        unique_id,
        person_properties=person_properties,
    )

    [
        durable_cache.set(_generate_cache_key(k, unique_id, person_properties), v)
        for k, v in flag_data.items()
    ]

    return flag_data


def is_enabled(
    name: str,
    default: Optional[bool] = None,
    opt_unique_id: Optional[str] = None,
) -> bool:
    """
    Return True if the feature flag is enabled

    Args:
        name (str): feature flag name
        default (bool): default value if not set in settings
        opt_unique_id (str):
            person identifier passed back to posthog which is the display value for
            person. I recommend this be user.id for logged-in users to allow for
            more readable user flags as well as more clear troubleshooting. For
            anonymous users, a persistent ID will help with troubleshooting and tracking
            efforts.

    Returns:
        bool: True if the feature flag is enabled
    """
    unique_id = opt_unique_id or default_unique_id()
    person_properties = _get_person_properties(unique_id)

    cache_key = _generate_cache_key(name, unique_id, person_properties)
    cached_value = durable_cache.get(cache_key)

    if cached_value is not None:
        log.debug("Retrieved %s from the cache", name)
        return cached_value
    else:
        log.debug("Retrieving %s from Posthog", name)

    # value will be None if either there is no value or we can't get a response back
    value = (
        posthog.get_feature_flag(
            name,
            unique_id,
            person_properties=person_properties,
        )
        if getattr(settings, "POSTHOG_ENABLED", False)
        else None
    )

    durable_cache.set(cache_key, value) if value is not None else None

    return value if value is not None else settings.FEATURES.get(name, default or False)
