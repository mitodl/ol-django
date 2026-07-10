"""Tests for the Stripe Payment Gateway"""

from dataclasses import asdict
from decimal import Decimal

import faker
import pytest
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import path, resolve
from main.factories import CartItemFactory, OrderFactory
from mitol.payment_gateway import api
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_STRIPE

from tests.payment_gateway.factories import (
    StripeWebhookSecretRouteFactory,
)

FAKE = faker.Factory.create()
pytestmark = [pytest.mark.django_db]


class MockCheckoutSession:
    """A mocked checkout session."""

    url = FAKE.url()


class MockStripeEventData:
    """Stores the "object" for the event below."""

    object = {"type": "some-sort-of-stripe-data"}


class MockStripeEvent:
    """A mocked out Stripe event."""

    id = ""
    data = None

    def __init__(self):
        """Make the data"""

        self.data = MockStripeEventData()


@pytest.fixture(autouse=True)
def stripe_settings_factory(settings):
    """Set the app to use the Stripe gateway."""

    settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY = MITOL_PAYMENT_GATEWAY_STRIPE
    settings.MITOL_PAYMENT_GATEWAY_STRIPE_API_KEY = (
        f"sk_test_{FAKE.random_letters(length=32)}"
    )


def test_start_payment(mocker):
    """
    Test that calling start_payment generates the proper payload for Stripe.

    This should exercise the order payload generation code, ensure the gateway
    API is calling the proper Stripe API, and check to make sure the returned
    data has the correct return type.
    """

    receipt_url = FAKE.url()
    cancel_url = FAKE.url()

    order = OrderFactory.create()
    item = CartItemFactory.create()
    order.items.append(item)

    stripe_session_data = {
        "client_reference_id": order.reference,
        "customer_email": order.email,
        "line_items": [
            {
                "quantity": item.quantity,
                "price_data": {
                    "currency": "USD",
                    "unit_amount_decimal": (
                        Decimal(item.unitprice + item.taxable).quantize(Decimal("1.00"))
                        * 100
                    ),
                    "tax_behavior": "inclusive",
                    "product_data": {
                        "name": item.name,
                        "description": item.name,
                        "metadata": asdict(item),
                    },
                },
            },
        ],
        "mode": "payment",
        "ui_mode": "hosted_page",
        "success_url": receipt_url,
        "cancel_url": cancel_url,
        "metadata": {},
    }

    mocked_stripe_session_create = mocker.patch(
        "stripe.checkout._session_service.SessionService.create",
        side_effect=lambda *_, **__: MockCheckoutSession(),
    )

    result = api.PaymentGateway.start_payment(
        MITOL_PAYMENT_GATEWAY_STRIPE, order, receipt_url, cancel_url
    )

    assert "method" in result
    assert result["method"] == "GET"
    mocked_stripe_session_create.assert_called_with(stripe_session_data)


def test_webhook_validation(mocker):
    """
    Test that the webhook validation works as expected.

    Webhook data is submitted with a signature that is encrypted with a shared
    key. Keys are generated per configured webhook target, so there may be
    multiple keys; Stripe allows multiple webhooks to be configured with the same
    target, so the same app endpoint may receive messages signed with different
    valid keys.

    The top-level get_formatted_response calls decode_processor_response, which
    in turn is a wrapper for perform_processor_response_validation in the Stripe
    gateway, so we just need to call that.
    """
    route_match = StripeWebhookSecretRouteFactory.create()
    url_name = route_match.url_name

    event = MockStripeEvent()
    event.id = "ev_test1234"

    class TestUrlconf:
        urlpatterns = [
            path("", lambda _: HttpResponse("OK"), name=url_name),
        ]

    mocked_construct_event = mocker.patch(
        "stripe._stripe_client.StripeClient.construct_event",
        return_value=event,
    )

    request = RequestFactory().post(
        "/",
        {"id": event.id},
        content_type="application/json",
        headers={"Stripe-Signature": "test1234"},
    )

    with override_settings(ROOT_URLCONF=TestUrlconf):
        request.resolver_match = resolve("/")

    assert request.resolver_match
    assert request.resolver_match.url_name == url_name

    result = api.PaymentGateway.validate_processor_response(
        MITOL_PAYMENT_GATEWAY_STRIPE, request
    )

    mocked_construct_event.assert_called()
    assert result == event
