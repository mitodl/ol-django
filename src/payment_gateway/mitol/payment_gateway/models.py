"""Models for the payment gateway"""

import logging

from django.core.exceptions import ValidationError
from django.db import models
from mitol.common.models import TimestampedModel, TimestampedModelQuerySet
from mitol.payment_gateway.constants import (
    MITOL_PAYMENT_GATEWAY_CHOICES,
    MITOL_PAYMENT_GATEWAY_STRIPE,
    STRIPE_CUSTOM_PAYMENT_METHOD_ID_PREFIX,
    STRIPE_PAYMENT_METHOD_TYPE_CUSTOM,
    STRIPE_PAYMENT_METHOD_TYPES,
)

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


class PaymentMethodType(TimestampedModel):
    """
    A payment method that a gateway should offer during checkout.

    Most payment methods are configured in the processor itself. This is for the
    ones that have to be requested explicitly when the checkout is set up. The
    format of `gateway_data` depends on the gateway; see the gateway-specific
    proxy models (e.g. `StripePaymentMethodType`).
    """

    name = models.CharField(
        max_length=255, help_text="A human-readable name for this payment method."
    )
    gateway = models.CharField(
        max_length=50,
        choices=MITOL_PAYMENT_GATEWAY_CHOICES,
        help_text="The payment gateway this payment method applies to.",
    )
    gateway_data = models.JSONField(
        blank=True,
        default=dict,
        help_text="Gateway-specific data for this payment method.",
    )
    is_default = models.BooleanField(
        default=False,
        blank=True,
        help_text=(
            "Use this payment method when checkout is started without an explicit"
            " list of payment methods."
        ),
    )

    class Meta:
        """Meta opts for the model"""

        constraints = [
            models.UniqueConstraint(
                fields=["gateway", "name"],
                name="payment_gateway_unique_payment_method_type_name",
            ),
        ]

    def __str__(self):
        """Return a readable representation"""

        return f"{self.gateway}: {self.name}"


class StripePaymentMethodTypeManager(
    models.Manager.from_queryset(TimestampedModelQuerySet)
):
    """Manager that only returns Stripe payment method types."""

    def get_queryset(self):
        """Filter to the Stripe gateway."""

        return super().get_queryset().filter(gateway=MITOL_PAYMENT_GATEWAY_STRIPE)


class StripePaymentMethodType(PaymentMethodType):
    """
    Payment method types for the Stripe gateway.

    `gateway_data` is stored as `{"type": <type>, "id": <id>}`:
    - `type` is "custom" for a custom payment method (sent in
      `custom_payment_method_types`) or "builtin" for one of Stripe's own payment
      methods (sent in `payment_method_types`).
    - `id` is the custom payment method type ID (e.g. `cpmt_123`) for custom
      methods, or the Stripe payment method type (e.g. `card`) for builtin ones.
    """

    objects = StripePaymentMethodTypeManager()

    class Meta:
        """Meta opts for the model"""

        proxy = True

    @property
    def _gateway_data_dict(self) -> dict:
        """Return the gateway data, or an empty dict if it isn't a dict."""

        if not isinstance(self.gateway_data, dict):
            msg = f"Invalid gateway data for StripePaymentMethodType {self.id}"
            raise TypeError(msg)

        return self.gateway_data

    @property
    def stripe_type(self) -> str | None:
        """Return the Stripe payment method type (custom or builtin)."""

        return self._gateway_data_dict.get("type")

    @stripe_type.setter
    def stripe_type(self, value: str):
        """Set the Stripe payment method type."""

        self.gateway_data = {**self._gateway_data_dict, "type": value}

    @property
    def stripe_id(self) -> str | None:
        """Return the Stripe ID for the payment method."""

        return self._gateway_data_dict.get("id")

    @stripe_id.setter
    def stripe_id(self, value: str):
        """Set the Stripe ID for the payment method."""

        self.gateway_data = {**self._gateway_data_dict, "id": value}

    @property
    def is_custom(self) -> bool:
        """Return True if this is a custom payment method."""

        return self.stripe_type == STRIPE_PAYMENT_METHOD_TYPE_CUSTOM

    def get_validation_errors(self) -> list[str]:
        """Return a list of problems with the Stripe-specific data."""

        if not isinstance(self.gateway_data, dict):
            return ["gateway_data must be a JSON object."]

        errors = []
        if self.stripe_type not in STRIPE_PAYMENT_METHOD_TYPES:
            errors.append(
                f"gateway_data type must be one of {STRIPE_PAYMENT_METHOD_TYPES}."
            )
        if not isinstance(self.stripe_id, str) or not self.stripe_id:
            errors.append("gateway_data id must be a non-empty string.")
        elif self.is_custom and not self.stripe_id.startswith(
            STRIPE_CUSTOM_PAYMENT_METHOD_ID_PREFIX
        ):
            errors.append(
                "Custom payment method IDs must start with "
                f"{STRIPE_CUSTOM_PAYMENT_METHOD_ID_PREFIX}."
            )
        elif not self.is_custom and self.stripe_id.startswith(
            STRIPE_CUSTOM_PAYMENT_METHOD_ID_PREFIX
        ):
            errors.append(
                "Built-in method IDs must not start with "
                f"{STRIPE_CUSTOM_PAYMENT_METHOD_ID_PREFIX}."
            )

        return errors

    def clean(self):
        """Validate the Stripe-specific data."""

        super().clean()

        errors = self.get_validation_errors()
        if errors:
            raise ValidationError({"gateway_data": errors})

    def save(self, *args, **kwargs):
        """Make sure the gateway is always set to Stripe."""

        self.gateway = MITOL_PAYMENT_GATEWAY_STRIPE
        super().save(*args, **kwargs)
