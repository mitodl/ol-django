from typing import Dict

import pytest
from django.conf import settings
from testapp.factories import CartItemFactory, OrderFactory

from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.api import CyberSourcePaymentGateway, PaymentGateway
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_CYBERSOURCE

ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture()
def order():
    return OrderFactory()


@pytest.fixture()
def cartitems():
    return CartItemFactory.create_batch(5)


def generate_test_cybersource_payload(order, cartitems, transaction_uuid):
    """
    Generates a test payload based on the order and cart items passed in, ready
    for signing.
    """
    receipt_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"

    test_line_items = {}
    test_total = 0

    for idx, line in enumerate(cartitems):
        test_total += line.quantity * line.unitprice

        test_line_items[f"item_{idx}_code"] = str(line.code)
        test_line_items[f"item_{idx}_name"] = str(line.name)[:254]
        test_line_items[f"item_{idx}_quantity"] = line.quantity
        test_line_items[f"item_{idx}_sku"] = line.sku
        test_line_items[f"item_{idx}_tax_amount"] = str(line.taxable)
        test_line_items[f"item_{idx}_unit_price"] = str(line.unitprice)

    test_payload = {
        "access_key": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY,
        "amount": str(test_total),
        "consumer_id": order.username,
        "currency": "USD",
        "locale": "en-us",
        **test_line_items,
        "line_item_count": len(cartitems),
        "reference_number": order.reference,
        "profile_id": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID,
        "signed_date_time": now_in_utc().strftime(ISO_8601_FORMAT),
        "override_custom_receipt_page": receipt_url,
        "override_custom_cancel_page": cancel_url,
        "transaction_type": "sale",
        "transaction_uuid": transaction_uuid,
        "unsigned_field_names": "",
        "customer_ip_address": order.ip_address if order.ip_address else None,
    }

    return {"payload": test_payload, "items": test_line_items}


def test_invalid_payload_generation(order, cartitems):
    """
    Tests to make sure something sane happens when an invalid payment gateway
    is specified.
    """
    receipt_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"
    order.items = cartitems

    checkout_data = PaymentGateway.start_payment(
        "Invalid Payment Gateway",
        order,
        receipt_url,
        cancel_url,
        merchant_fields=None,
    )

    assert isinstance(checkout_data, TypeError)


def test_cybersource_payload_generation(order, cartitems):
    """
    Starts a payment through the payment gateway, and then checks to make sure
    there's stuff in the payload that it generates. The transaction is not sent
    through CyberSource itself.
    """
    receipt_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"
    order.items = cartitems

    checkout_data = PaymentGateway.start_payment(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
        order,
        receipt_url,
        cancel_url,
        merchant_fields=None,
    )

    test_payload = generate_test_cybersource_payload(
        order, cartitems, checkout_data["payload"]["transaction_uuid"]
    )
    test_payload = test_payload["payload"]

    gateway = CyberSourcePaymentGateway()

    signed_test_payload = gateway._sign_cybersource_payload(test_payload)

    assert signed_test_payload == checkout_data["payload"]

    assert "payload" in checkout_data
    assert "url" in checkout_data
    assert (
        checkout_data["url"]
        == settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_SECURE_ACCEPTANCE_URL
    )
    assert checkout_data["method"] == "POST"


def test_cybersource_response_auth(order, cartitems):
    """
    Generates a test payload, then uses it to generate a fake request that is
    run through the validate_processor_response method.
    """

    class FakeRequest:
        """
        This implements just the stuff that the validator method needs to check
        the response.
        """

        data: Dict
        method: str

        def __init__(self, data, method):
            self.data = data
            self.method = method

    receipt_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"
    order.items = cartitems

    checkout_data = PaymentGateway.start_payment(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
        order,
        receipt_url,
        cancel_url,
        merchant_fields=None,
    )

    test_payload = generate_test_cybersource_payload(
        order, cartitems, checkout_data["payload"]["transaction_uuid"]
    )
    test_payload = test_payload["payload"]

    gateway = CyberSourcePaymentGateway()

    signed_test_payload = gateway._sign_cybersource_payload(test_payload)

    fake_request = FakeRequest(signed_test_payload, "POST")

    assert PaymentGateway.validate_processor_response(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE, fake_request
    )