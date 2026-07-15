"""Models for the payment gateway"""

from django.db import models
from mitol.common.models import TimestampedModel


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


class StripeWebhookSecretRoute(TimestampedModel):
    """Stores valid paths for webhook secrets."""

    secret = models.ForeignKey(
        StripeWebhookSecret, on_delete=models.CASCADE, related_name="routes"
    )
    url_name = models.CharField(max_length=255, help_text="The url_name for the route")
