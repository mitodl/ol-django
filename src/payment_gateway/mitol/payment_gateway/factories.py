"""Test factories for Payment Gateway."""

import faker
import pytz
from django.conf import settings
from factory import Factory, LazyAttribute, SubFactory, Trait
from factory.django import DjangoModelFactory
from mitol.payment_gateway import constants, fixtures
from mitol.payment_gateway.models import (
    StripePaymentMethodType,
    StripeWebhookSecret,
    StripeWebhookSecretRoute,
)

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


class StripePaymentMethodTypeFactory(DjangoModelFactory):
    """Factory for Stripe payment method types (custom by default)"""

    name = LazyAttribute(lambda _: f"{FAKE.word()} {FAKE.uuid4()}")
    gateway = constants.MITOL_PAYMENT_GATEWAY_STRIPE
    is_default = True
    gateway_data = LazyAttribute(
        lambda _: {
            "type": constants.STRIPE_PAYMENT_METHOD_TYPE_CUSTOM,
            "id": f"cpmt_{FAKE.pystr(min_chars=24, max_chars=24)}",
        }
    )

    class Meta:
        """Factory meta opts"""

        model = StripePaymentMethodType

    class Params:
        """Allow creating builtin payment methods."""

        builtin = Trait(
            gateway_data=LazyAttribute(
                lambda _: {
                    "type": constants.STRIPE_PAYMENT_METHOD_TYPE_BUILTIN,
                    "id": FAKE.word(),
                }
            )
        )


class StripeAbstractEventFactory(Factory):
    """Abstract factory to set some defaults for Stripe events."""

    created = FAKE.past_datetime("-1y", pytz.timezone(settings.TIME_ZONE))
    id = FAKE.pystr(min_chars=24, max_chars=24, prefix="evt_")

    class Meta:
        """Factory meta opts"""

        abstract = True


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

        model = fixtures.stripe_checkout_session

    class Params:
        """Allow the PaymentIntent to be "expanded"."""

        expanded = Trait(
            payment_intent=LazyAttribute(
                lambda o: StripePaymentIntentFactory.create(
                    created=FAKE.date_time_between(
                        start_date=o.created, tzinfo=pytz.timezone(settings.TIME_ZONE)
                    )
                )
            )
        )


class StripePaymentIntentFactory(Factory):
    """Factory for payment intents."""

    class Meta:
        """Meta opts for the factory"""

        model = fixtures.stripe_payment_intent


class StripeCheckoutSessionEventFactory(StripeAbstractEventFactory):
    """Factory that returns a faked CheckoutSession event"""

    data = LazyAttribute(
        lambda _: {"object": StripeSimpleCheckoutSessionFactory.create()}
    )
    type = "checkout.session.completed"

    class Meta:
        """Factory meta opts"""

        model = fixtures.stripe_event


class StripeCheckoutSessionWithPIEventFactory(StripeAbstractEventFactory):
    """Factory that returns a faked CheckoutSession event w/ a PaymentIntent"""

    data = LazyAttribute(
        lambda _: {"object": StripeSimpleCheckoutSessionFactory.create(expanded=True)}
    )
    type = "checkout.session.completed"

    class Meta:
        """Factory meta opts"""

        model = fixtures.stripe_event
