"""Test factories for Payment Gateway."""

import faker
from factory import LazyAttribute, SubFactory
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
