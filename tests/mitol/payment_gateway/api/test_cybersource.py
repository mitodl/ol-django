import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict

import pytest
from CyberSource.rest import ApiException
from django.conf import settings
from testapp.factories import CartItemFactory, OrderFactory, RefundFactory
from urllib3.response import HTTPResponse

from mitol.common.utils.datetime import now_in_utc
from mitol.payment_gateway.api import (
    CyberSourcePaymentGateway,
    PaymentGateway,
    ProcessorResponse,
)
from mitol.payment_gateway.constants import MITOL_PAYMENT_GATEWAY_CYBERSOURCE
from mitol.payment_gateway.exceptions import (
    InvalidTransactionException,
    RefundDuplicateException,
)

ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture()
def order():
    return OrderFactory()


@pytest.fixture()
def refund():
    return RefundFactory()


@pytest.fixture()
def cartitems():
    return CartItemFactory.create_batch(5)


@pytest.fixture
def response_payload(request):
    """Fixture to return dictionary of a specific JSON file with provided name in request param"""

    with open(
        os.path.join(
            os.getcwd(), "tests/mitol/payment_gateway/api", f"{request.param}.json"
        ),
        mode="r",
    ) as f:
        response_txt = f.read()
        response_json = json.loads(response_txt)
        yield response_json


@dataclass
class FakeRequest:
    """
    This implements just the stuff that the validator method needs to check
    the response.
    """

    data: Dict
    method: str


def generate_test_cybersource_payload(order, cartitems, transaction_uuid):
    """
    Generates a test payload based on the order and cart items passed in, ready
    for signing.
    """
    backoffice_post_url = "https://www.google.com"
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

    consumer_id = hashlib.sha256(order.username.encode("ascii")).hexdigest()

    test_payload = {
        "access_key": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_ACCESS_KEY,
        "amount": str(test_total),
        "consumer_id": consumer_id,
        "currency": "USD",
        "locale": "en-us",
        **test_line_items,
        "line_item_count": len(cartitems),
        "reference_number": order.reference,
        "profile_id": settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_PROFILE_ID,
        "signed_date_time": now_in_utc().strftime(ISO_8601_FORMAT),
        "override_backoffice_post_url": backoffice_post_url,
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
    backoffice_post_url = "https://www.google.com"
    receipt_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"
    order.items = cartitems

    checkout_data = PaymentGateway.start_payment(
        "Invalid Payment Gateway",
        order,
        receipt_url,
        cancel_url,
        backoffice_post_url,
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
    backoffice_post_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"
    order.items = cartitems

    checkout_data = PaymentGateway.start_payment(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
        order,
        receipt_url,
        cancel_url,
        backoffice_post_url,
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
    receipt_url = "https://www.google.com"
    backoffice_post_url = "https://www.google.com"
    cancel_url = "https://duckduckgo.com"
    order.items = cartitems

    checkout_data = PaymentGateway.start_payment(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
        order,
        receipt_url,
        cancel_url,
        backoffice_post_url,
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


@pytest.mark.parametrize(
    "response_payload, expected_response_code",
    [
        ("test_success_payload", ProcessorResponse.STATE_ACCEPTED),
        ("test_cancel_payload", ProcessorResponse.STATE_CANCELLED),
    ],
    indirect=["response_payload"],
)
def test_cybersource_payment_response(
    response_payload, expected_response_code, order, cartitems
):
    """
    Testing this really requires a payload from CyberSource, which also means
    having an profile and keys set up. So, instead, this has a set of payloads
    from test payments. (These have fake keys in them and won't pass the
    signaure validation, so this test doesn't validate them.)
    """
    payment_response_json = response_payload

    # sanity check - make sure the payloads are actually valid JSON
    assert "req_amount" in payment_response_json

    fake_request = FakeRequest(payment_response_json, "POST")

    response = PaymentGateway.get_formatted_response(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE, fake_request
    )

    assert response.state == expected_response_code


def test_cybersource_client_configuration_url(settings):
    """
    Tests that get_client_configuration generates the right configuration url for CyberSource Payment processor
    """
    settings.CYBERSOURCE_REST_API_ENVIRONMENT = "apitest.cybersource.com"
    gateway = CyberSourcePaymentGateway()
    configuration = gateway.get_client_configuration()
    assert (
        configuration["run_environment"]
        == settings.MITOL_PAYMENT_GATEWAY_CYBERSOURCE_REST_API_ENVIRONMENT
    )


def test_generate_refund_payload(refund):
    """
    Tests that generate_refund_payload function generates correct readable formatted JSON for the request to
    CyberSource refund API calls.
    """

    cybersource_gateway = CyberSourcePaymentGateway()
    refund_payload = json.loads(cybersource_gateway.generate_refund_payload(refund))
    assert "_client_reference_information" in refund_payload
    assert "_order_information" in refund_payload

    client_reference_information = refund_payload["_client_reference_information"]

    # Passing transaction_id in reference information is important because the refund API won't send a duplicate
    # request response if there is no transaction_id in the request payload
    assert client_reference_information["_transaction_id"] == refund.transaction_id

    order_information = refund_payload["_order_information"]
    assert "_amount_details" in order_information
    assert order_information["_amount_details"] == {
        "_total_amount": refund.refund_amount,
        "_currency": refund.refund_currency,
    }


@pytest.mark.parametrize("response_payload", ["test_refund_success"], indirect=True)
def test_cybersource_refund_response_success(response_payload, refund, mocker):
    """
    Tests that the perform_refund method returns the expected response to the calling application.
    This test uses a sample request JSON to as API response from CyberSource since we won't be hitting the
    real API in tests. Instead, We will mock it for this case
    """

    success_response_json = response_payload

    assert "orderInformation" in success_response_json
    assert "refundAmountDetails" in success_response_json
    assert "status" in success_response_json

    mocker.patch(
        "CyberSource.RefundApi.refund_payment",
        return_value=["", "", json.dumps(success_response_json)],
    )
    cybersource_gateway = CyberSourcePaymentGateway()
    response = cybersource_gateway.perform_refund(refund)

    assert response.state == ProcessorResponse.STATE_PENDING
    assert response.transaction_id == refund.transaction_id


@pytest.mark.parametrize("response_payload", ["test_refund_duplicate"], indirect=True)
def test_cybersource_refund_response_failure_duplicate(
    response_payload, refund, mocker
):
    """
    Tests that the perform_refund method raises RefundDuplicateException when the API errors out with a
    "DUPLICATE_REQUEST" reason.
    """

    duplicate_response_json = response_payload

    sample_response = HTTPResponse(
        status=400,
        reason="Bad Request",
        body=json.dumps(duplicate_response_json),
        headers={},
    )

    expected_exception = ApiException(http_resp=sample_response)

    mocker.patch("CyberSource.RefundApi.refund_payment", side_effect=expected_exception)

    cybersource_gateway = CyberSourcePaymentGateway()

    # A RefundDuplicateException should be raised if request fails with DUPLICATE_REQUEST reason
    with pytest.raises(RefundDuplicateException) as ex:
        cybersource_gateway.perform_refund(refund)

    # Response data assertions
    assert ex.value.reason_code == duplicate_response_json["reason"]
    assert ex.value.transaction_id == refund.transaction_id
    assert ex.value.amount == refund.refund_amount
    assert ex.value.body == duplicate_response_json


@pytest.mark.parametrize("response_payload", ["test_refund_duplicate"], indirect=True)
def test_cybersource_refund_response_failure_general(response_payload, refund, mocker):
    """
    Tests that the perform_refund method passes on the incoming exception as it is when there is API error reason is
    other then DUPLICATE_REQUEST.
    """
    duplicate_response_json = response_payload

    duplicate_response_json["reason"] = "dummy"

    sample_response = HTTPResponse(
        status=400,
        reason="Bad Request",
        body=json.dumps(duplicate_response_json),
        headers={},
    )

    expected_exception = ApiException(http_resp=sample_response)

    mocker.patch("CyberSource.RefundApi.refund_payment", side_effect=expected_exception)

    cybersource_gateway = CyberSourcePaymentGateway()

    # An ApiException should be raised if request fails without DUPLICATE_REQUEST reason
    with pytest.raises(ApiException):
        cybersource_gateway.perform_refund(refund)


@pytest.mark.parametrize(
    "response_payload", ["test_success_payload"], indirect=["response_payload"]
)
def test_create_refund_request(response_payload):
    """Tests that create_refund_request creates the correct Refund Request object out of provided
    payment transaction dictionary"""

    payment_response_json = response_payload
    refund_request = PaymentGateway.create_refund_request(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
        payment_response_json,
    )

    assert refund_request.transaction_id == payment_response_json["transaction_id"]
    assert refund_request.refund_amount == payment_response_json["req_amount"]
    assert refund_request.refund_currency == payment_response_json["req_currency"]


@pytest.mark.parametrize(
    "transaction_data",
    [
        {},
        {"transaction_id": 11},
        {"req_amount": 100},
        {"req_currency": "USD"},
        {"transaction_id": 11, "req_amount": 100},
        {"req_amount": 100, "req_currency": "USD"},
        {"transaction_id": 100, "req_currency": "USD"},
    ],
)
def test_create_refund_request_invalid_data_exception(transaction_data):
    """
    Test that create_refund_request throws InvalidTransactionException if the payment transaction dictionary is invalid
    """
    cybersource_gateway = CyberSourcePaymentGateway()

    # A RefundDuplicateException should be raised if request fails with DUPLICATE_REQUEST reason
    with pytest.raises(InvalidTransactionException):
        cybersource_gateway.create_refund_request(
            MITOL_PAYMENT_GATEWAY_CYBERSOURCE, transaction_data
        )
