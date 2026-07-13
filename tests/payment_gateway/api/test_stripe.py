"""Tests for the Stripe Payment Gateway"""

import logging
from dataclasses import asdict
from decimal import Decimal

import faker
import pytest
import stripe
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import path, resolve
from main.factories import CartItemFactory, OrderFactory
from mitol.payment_gateway import api
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_STRIPE
from mitol.payment_gateway.exceptions import (
    BadStripeWebhookSecretError,
    ImproperStripeWebhookRequestError,
    NoStripeWebhookSecretError,
)

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


def _setup_webhook_test(mocker):
    """Set up the data for a webhook test."""

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

    return (route_match, event, mocked_construct_event, request)


@pytest.mark.parametrize(
    "multimatch",
    [
        False,
        True,
    ],
)
def test_webhook_validation(mocker, multimatch):
    """
    Test that the webhook validation works as expected in normal circumstances.

    Webhook data is submitted with a signature that is encrypted with a shared
    key. Keys are generated per configured webhook target, so there may be
    multiple keys; Stripe allows multiple webhooks to be configured with the same
    target, so the same app endpoint may receive messages signed with different
    valid keys.

    The top-level get_formatted_response calls decode_processor_response, which
    in turn is a wrapper for perform_processor_response_validation in the Stripe
    gateway, so we just need to call that.

    This tests the case where everything matches - there's a webhook key set up
    for the current request - and where there's multiple positive matches.
    """

    route_match, event, mocked_construct_event, request = _setup_webhook_test(mocker)

    match_secrets = [route_match.secret.webhook_secret]

    if multimatch:
        # We can have multiple routes match for a given key.
        second_route_match = StripeWebhookSecretRouteFactory.create(
            url_name=route_match.url_name
        )
        match_secrets.append(second_route_match.secret.webhook_secret)

    def _construct_event_key_matcher(secret):
        """Check that the secret is one of the ones we're supposed to find."""

        assert secret in match_secrets
        return event

    mocked_construct_event.side_effect = lambda _, __, secret: (
        _construct_event_key_matcher(secret)
    )

    result = api.PaymentGateway.validate_processor_response(
        MITOL_PAYMENT_GATEWAY_STRIPE, request
    )

    mocked_construct_event.assert_called()
    assert result == event


@pytest.mark.parametrize(
    "error_type",
    [
        "bad_payload",
        "bad_json",
        "bad_id",
    ],
)
def test_webhook_validation_setup_errors(mocker, error_type):
    """
    Test that the webhook validation works as expected when the request payload is bad.

    The payload must exist, be proper JSON, and have an "id" prop or we won't be
    able to process it further.
    """

    _setup_webhook_test(mocker)

    exc_msg = "Empty payload received."
    request_body = ""
    if error_type == "bad_json":
        exc_msg = "Improper JSON payload found."
        request_body = "this is just a bare string"
    elif error_type == "bad_id":
        exc_msg = "Improper JSON payload found (no 'id' prop)."
        request_body = {
            "some_other_field": "test1234",
        }

    request = RequestFactory().post(
        "/",
        request_body,
        content_type="application/json",
        headers={"Stripe-Signature": "test1234"},
    )

    with pytest.raises(ImproperStripeWebhookRequestError) as exc:
        api.PaymentGateway.validate_processor_response(
            MITOL_PAYMENT_GATEWAY_STRIPE, request
        )

    assert exc_msg in str(exc.value)


def test_webhook_validation_bad_url_name(mocker, caplog):
    """
    Test that the webhook validation works as expected when the URL name is bad.

    Not sure why this would happen but if the resolver in the request can't figure
    out what the URL route is, then it should use the path_info instead.
    """

    route_match, _, _, request = _setup_webhook_test(mocker)

    route_match.url_name = "/"
    route_match.save()

    request.resolver_match.url_name = None

    with caplog.at_level(logging.WARNING):
        api.PaymentGateway.validate_processor_response(
            MITOL_PAYMENT_GATEWAY_STRIPE, request
        )

    assert "using path_info" in caplog.text


def test_webhook_validation_no_route_match(mocker):
    """
    Test that the webhook validation works as expected when there is no route match.

    If there's no match for the requested URL, then our API should raise an
    exception.
    """

    route_match, _, _, request = _setup_webhook_test(mocker)

    route_match.url_name = FAKE.url()
    route_match.save()

    with pytest.raises(NoStripeWebhookSecretError):
        api.PaymentGateway.validate_processor_response(
            MITOL_PAYMENT_GATEWAY_STRIPE, request
        )


def test_webhook_validation_no_secret_match(mocker):
    """
    Test that the webhook validation works as expected when there is no secret match.

    If the secret we supply isn't valid, the Stripe SDK raises an exception, and
    we move on to the next secret to try. If none of them match, we should raise
    an exception and stop.
    """

    route_match, _, mocked_construct_event, request = _setup_webhook_test(mocker)
    StripeWebhookSecretRouteFactory.create(url_name=route_match.url_name)

    mocked_construct_event.side_effect = stripe.error.SignatureVerificationError(
        "bad times", "header"
    )

    with pytest.raises(BadStripeWebhookSecretError):
        api.PaymentGateway.validate_processor_response(
            MITOL_PAYMENT_GATEWAY_STRIPE, request
        )


def test_webhook_validation_stripe_payload_error(mocker):
    """
    Test that the webhook validation works when there is a Stripe payload error.

    construct_event will raise a ValueError if it finds some sort of issue beyond
    the signature or secret being invalid.
    """

    route_match, _, mocked_construct_event, request = _setup_webhook_test(mocker)
    StripeWebhookSecretRouteFactory.create(url_name=route_match.url_name)

    mocked_construct_event.side_effect = ValueError("something went wrong")

    with pytest.raises(ImproperStripeWebhookRequestError):
        api.PaymentGateway.validate_processor_response(
            MITOL_PAYMENT_GATEWAY_STRIPE, request
        )


def test_webhook_validation_some_secret_match(mocker):
    """
    Test that the webhook validation works as expected when there is no secret match.

    If the secret we supply isn't valid, the Stripe SDK raises an exception, and
    we move on to the next secret to try. We should get a valid return value back
    if one matches, though.
    """

    route_match, event, mocked_construct_event, request = _setup_webhook_test(mocker)
    second_route_match = StripeWebhookSecretRouteFactory.create(
        url_name=route_match.url_name
    )

    def _raise_if_not_second(secret, sig_header):
        """Raise SignatureVerificationError if the secret isn't the second one."""

        if secret != second_route_match.secret.webhook_secret:
            raise stripe.error.SignatureVerificationError("bad times", sig_header)  # noqa: EM101,TRY003

        return event

    mocked_construct_event.side_effect = lambda _, sig_header, secret: (
        _raise_if_not_second(secret, sig_header)
    )

    result = api.PaymentGateway.validate_processor_response(
        MITOL_PAYMENT_GATEWAY_STRIPE, request
    )

    mocked_construct_event.assert_called()
    assert result == event
