"""Models for the payment gateway"""

import logging

from django.db import models
from mitol.common.models import TimestampedModel

log = logging.getLogger(__name__)


class ActiveUndeleteManager(models.Manager):
    """Query manager for active objects"""

    # This can be used generally, for the models that have `is_active` field
    def get_queryset(self):
        """Default filter out inactive records."""
        return super().get_queryset().filter(is_active=True)


class StripeWebhookSecret(TimestampedModel):
    """Stores secrets for configured webhooks."""

    objects = ActiveUndeleteManager()
    all_objects = models.Manager()

    is_active = models.BooleanField(default=True, blank=True)
    secret_name = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="A human-readable name for this secret.",
    )
    webhook_secret = models.CharField(
        max_length=255, unique=True, help_text="The secret provided by Stripe."
    )

    @classmethod
    def get_secret_from_request_queryset(cls, request):
        """
        Return a queryset that pulls the secret for the requested route.

        This matches on URL name if it can and falls back to path_info if it can't.
        """

        if request.resolver_match and request.resolver_match.url_name:
            route = request.resolver_match.url_name
        else:
            log.warning(
                "StripePaymentGateway: could not get the route from the request,"
                " using path_info instead"
            )
            route = request.path_info

        return StripeWebhookSecret.objects.filter(routes__url_name=route)


class StripeWebhookSecretRoute(TimestampedModel):
    """Stores valid paths for webhook secrets."""

    secret = models.ForeignKey(
        StripeWebhookSecret, on_delete=models.CASCADE, related_name="routes"
    )
    url_name = models.CharField(max_length=255, help_text="The url_name for the route")
