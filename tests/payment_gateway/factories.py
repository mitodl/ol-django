# ruff: noqa: CPY001
"""Test factories for Payment Gateway."""

import dataclasses
from datetime import datetime

import faker
import pytz
from django.conf import settings
from factory import Factory, LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from mitol.payment_gateway.models import StripeWebhookSecret, StripeWebhookSecretRoute

FAKE = faker.Factory.create()


class StripeWebhookSecretFactory(DjangoModelFactory):
    """Factory for Stripe webhooks"""

    is_active = True
    secret_name = FAKE.words(5)
    webhook_secret = LazyAttribute(
        lambda _: f"whsec_fake_{FAKE.random_letters(length=32)}"
    )

    class Meta:
        """Factory meta opts"""

        model = StripeWebhookSecret


class StripeWebhookSecretRouteFactory(DjangoModelFactory):
    """Factory for matched routes for webhook secrets"""

    secret = SubFactory(StripeWebhookSecretFactory)
    url_name = LazyAttribute(lambda _: f"{FAKE.word()}-{FAKE.word()}")

    class Meta:
        """Factory meta opts"""

        model = StripeWebhookSecretRoute


@dataclasses.dataclass
class SimpleStripeEvent:
    """A very basic representation of a Stripe event, suitable for testing."""

    id: str | None = None
    created: datetime | None = None
    type: str | None = None
    object: str = "event"
    data: dict = dataclasses.field(default_factory=dict)
    request: dict = dataclasses.field(default_factory=dict)
    livemode: bool = False
    api_version: str = "2026-06-24.dahlia"
    pending_webhooks: int = 0

    def to_dict(self, *, for_json: bool = False):
        """Return the event as a dict"""

        return {
            "id": self.id,
            "created": self.created.isoformat()
            if self.created and for_json
            else self.created,
            "type": self.type,
            "object": self.object,
            "data": self.data,
            "request": self.request,
            "livemode": self.livemode,
            "api_version": self.api_version,
            "pending_webhooks": self.pending_webhooks,
        }

    def get(self, field):
        """Get the value for the field"""

        return getattr(self, field)


@dataclasses.dataclass
class SimpleStripeCheckoutSession:
    """A basic representation of a Stripe checkout session, suitable for testing."""

    id: str | None = None
    created: datetime | None = None
    object: str = "checkout.session"
    payment_intent: str | dict = ""
    mode: str = "payment"
    ui_mode: str = "hosted_page"
    payment_status: str = "paid"
    status: str = ""
    amount_total: int = 0
    amount_subtotal: int = 0
    client_reference_id: str = ""
    success_url: str = ""
    cancel_url: str = ""
    currency: str = "usd"

    def to_dict(self, *, for_json: bool = False):
        """Return the session as a dict"""

        return {
            "id": self.id,
            "created": self.created.isoformat()
            if self.created and for_json
            else self.created,
            "object": self.object,
            "payment_intent": self.payment_intent,
            "mode": self.mode,
            "ui_mode": self.ui_mode,
            "payment_status": self.payment_status,
            "status": self.status,
            "amount_total": self.amount_total,
            "amount_subtotal": self.amount_subtotal,
            "client_reference_id": self.client_reference_id,
            "success_url": self.success_url,
            "cancel_url": self.cancel_url,
            "currency": self.currency,
        }

    def get(self, field, default=None):
        """Get the value for the field"""

        return getattr(self, field, default)


class StripeAbstractEventFactory(Factory):
    """Abstract factory to set some defaults for Stripe events."""

    created = FAKE.past_datetime("-1y", pytz.timezone(settings.TIME_ZONE))
    id = FAKE.pystr(min_chars=24, max_chars=24, prefix="evt_")
    object = "event"

    class Meta:
        """Factory meta opts"""

        abstract = True
        model = SimpleStripeEvent


class StripeSimpleCheckoutSessionFactory(Factory):
    """Factory for CheckoutSessions, with a minimal amount of data"""

    created = FAKE.past_datetime("-1y", pytz.timezone(settings.TIME_ZONE))
    id = FAKE.pystr(min_chars=58, max_chars=58, prefix="cs_test_")
    payment_intent = FAKE.pystr(min_chars=24, max_chars=24, prefix="pi_")
    ui_mode = "hosted_page"
    payment_status = "paid"
    status = "complete"
    # Stripe won't allow a transaction in USD under 50c.
    amount_total = FAKE.pyint(min_value=50, max_value=9999)
    amount_subtotal = LazyAttribute(lambda o: o.amount_total)
    client_reference_id = LazyAttribute(lambda _: f"payment-gateway-{FAKE.uuid4()}")
    success_url = FAKE.uri(
        [
            "https",
        ]
    )
    cancel_url = FAKE.uri(
        [
            "https",
        ]
    )

    class Meta:
        """Factory meta opts"""

        model = SimpleStripeCheckoutSession


class StripeCheckoutSessionEventFactory(StripeAbstractEventFactory):
    """Factory that returns a faked CheckoutSession event"""

    data = LazyAttribute(
        lambda _: {"object": StripeSimpleCheckoutSessionFactory.create()}
    )
    type = "checkout.session.completed"

    class Meta:
        """Factory meta opts"""

        model = SimpleStripeEvent
