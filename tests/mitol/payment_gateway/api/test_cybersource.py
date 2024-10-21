import hashlib  # noqa: INP001
import json
import os
import random
from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime
from typing import Dict

import pytest
from CyberSource import models as cs_models
from CyberSource.rest import ApiException
from django.conf import settings
from factory import fuzzy
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
from testapp.factories import CartItemFactory, OrderFactory, RefundFactory
from urllib3.response import HTTPResponse

ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@pytest.fixture
def order():
    return OrderFactory()


@pytest.fixture
def refund():
    return RefundFactory()


@pytest.fixture
def cartitems():
    return CartItemFactory.create_batch(5)


@pytest.fixture
def response_payload(request):
    """Fixture to return dictionary of a specific JSON file with provided name in request param"""  # noqa: E501

    with open(  # noqa: PTH123
        os.path.join(  # noqa: PTH118
            os.getcwd(),  # noqa: PTH109
            "tests/data/payment_gateway/api",
            f"{request.param}.json",
        ),
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

    data: Dict  # noqa: FA100
    method: str


def generate_test_cybersource_payload(order, cartitems, transaction_uuid):
    """
    Generates a test payload based on the order and cart items passed in, ready
    for signing.
    """  # noqa: D401
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

    consumer_id = hashlib.sha256(order.username.encode("utf-8")).hexdigest()

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
        "override_custom_receipt_page": receipt_url,
        "override_custom_cancel_page": cancel_url,
        "transaction_type": "sale",
        "transaction_uuid": transaction_uuid,
        "unsigned_field_names": "",
        "customer_ip_address": order.ip_address if order.ip_address else None,
        "override_backoffice_post_url": backoffice_post_url,
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

    signed_test_payload = gateway._sign_cybersource_payload(test_payload)  # noqa: SLF001

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

    signed_test_payload = gateway._sign_cybersource_payload(test_payload)  # noqa: SLF001

    fake_request = FakeRequest(signed_test_payload, "POST")

    assert PaymentGateway.validate_processor_response(
        MITOL_PAYMENT_GATEWAY_CYBERSOURCE, fake_request
    )


@pytest.mark.parametrize(
    "response_payload, expected_response_code",  # noqa: PT006
    [
        ("test_success_payload", ProcessorResponse.STATE_ACCEPTED),
        ("test_cancel_payload", ProcessorResponse.STATE_CANCELLED),
    ],
    indirect=["response_payload"],
)
def test_cybersource_payment_response(
    response_payload,
    expected_response_code,
    order,  # noqa: ARG001
    cartitems,  # noqa: ARG001
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
    """  # noqa: E501
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
    """  # noqa: E501

    cybersource_gateway = CyberSourcePaymentGateway()
    refund_payload = json.loads(cybersource_gateway.generate_refund_payload(refund))
    assert "_client_reference_information" in refund_payload
    assert "_order_information" in refund_payload

    client_reference_information = refund_payload["_client_reference_information"]

    # Passing transaction_id in reference information is important because the refund API won't send a duplicate  # noqa: E501
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
    """  # noqa: E501

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
    """  # noqa: E501

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

    # A RefundDuplicateException should be raised if request fails with DUPLICATE_REQUEST reason  # noqa: E501
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
    """  # noqa: E501
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
    payment transaction dictionary
    """  # noqa: E501

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
    """  # noqa: E501
    cybersource_gateway = CyberSourcePaymentGateway()

    # A RefundDuplicateException should be raised if request fails with DUPLICATE_REQUEST reason  # noqa: E501
    with pytest.raises(InvalidTransactionException):
        cybersource_gateway.create_refund_request(
            MITOL_PAYMENT_GATEWAY_CYBERSOURCE, transaction_data
        )


def create_transaction_search_results():
    """Mocks a transaction search result. This only mocks up the things the find_transactions call actually uses."""  # noqa: E501, D401

    class fake_reference:  # noqa: N801
        code = "mitxonline-test-12345"

    class fake_summary:  # noqa: N801
        def __init__(self):
            self.id = 123456789
            self.client_reference_information = fake_reference
            self.submit_time_utc = datetime.today()  # noqa: DTZ002

    class fake_response:  # noqa: N801
        def __init__(self):
            self.total_count = 1
            self._embedded = namedtuple("embedded", "transaction_summaries")(  # noqa: PYI024
                **{"transaction_summaries": [fake_summary()]}
            )

    return fake_response()


@pytest.mark.parametrize("test_failure", [True, False])
def test_find_transactions(test_failure, mocker):
    fake_ids = ["mitxonline-test-12345", "mitxonline-test-54321"]

    faked_responses = create_transaction_search_results()

    expected_exception = Exception("CyberSource API returned HTTP status 500: Error")

    if test_failure:
        mocker.patch(
            "CyberSource.SearchTransactionsApi.create_search",
            side_effect=expected_exception,
        )
    else:
        mocker.patch(
            "CyberSource.SearchTransactionsApi.create_search",
            return_value=(faked_responses, 200, {}),
        )

    cybersource_gateway = CyberSourcePaymentGateway()

    if test_failure:
        with pytest.raises(Exception):  # noqa: B017, PT011
            response = cybersource_gateway.find_transactions(fake_ids)
    else:
        response = cybersource_gateway.find_transactions(fake_ids)

        assert "mitxonline-test-12345" in response[0]


def create_transaction_detail_record():
    """Returns a faked out detail record in the same format you'd get from CyberSource for a TransactionDetailApi request."""  # noqa: E501, D401

    fake_id = random.randrange(1000000000000000000000, 9999999999999999999999)  # noqa: S311
    fake_recon_id = fuzzy.FuzzyText(length=16)

    data_dict = {
        "application_information": cs_models.TssV2TransactionsGet200ResponseApplicationInformation(  # noqa: E501
            **{
                "applications": [
                    cs_models.TssV2TransactionsGet200ResponseApplicationInformationApplications(
                        **{
                            "name": "ics_auth",
                            "r_code": "1",
                            "r_flag": "SOK",
                            "r_message": "Request was " "processed " "successfully.",
                            "reason_code": "100",
                            "reconciliation_id": fake_recon_id,
                            "return_code": 1010000,
                            "status": None,
                        }
                    ),
                    cs_models.TssV2TransactionsGet200ResponseApplicationInformationApplications(
                        **{
                            "name": "ics_bill",
                            "r_code": "1",
                            "r_flag": "SOK",
                            "r_message": "Request was " "processed " "successfully.",
                            "reason_code": "100",
                            "reconciliation_id": fake_recon_id,
                            "return_code": 1260000,
                            "status": "TRANSMITTED",
                        }
                    ),
                ],
                "r_code": None,
                "r_flag": None,
                "reason_code": "100",
                "status": "TRANSMITTED",
            }
        ),
        "buyer_information": cs_models.TssV2TransactionsGet200ResponseBuyerInformation(
            **{
                "hashed_password": None,
                "merchant_customer_id": "1a2bd577a252342290dae0459b0c92ac",
            }
        ),
        "client_reference_information": cs_models.TssV2TransactionsGet200ResponseClientReferenceInformation(  # noqa: E501
            **{
                "application_name": "Secure Acceptance " "Web/Mobile",
                "application_user": None,
                "application_version": None,
                "code": "mitxonline-dev-4",
                "comments": None,
                "partner": cs_models.TssV2TransactionsGet200ResponseClientReferenceInformationPartner(  # noqa: E501
                    **{"solution_id": None}
                ),
            }
        ),
        "consumer_authentication_information": cs_models.TssV2TransactionsGet200ResponseConsumerAuthenticationInformation(  # noqa: E501
            **{
                "cavv": None,
                "eci_raw": None,
                "strong_authentication": cs_models.TssV2TransactionsGet200ResponseConsumerAuthenticationInformationStrongAuthentication(  # noqa: E501
                    **{
                        "delegated_authentication_exemption_indicator": None,
                        "low_value_exemption_indicator": None,
                        "risk_analysis_exemption_indicator": None,
                        "secure_corporate_payment_indicator": None,
                        "trusted_merchant_exemption_indicator": None,
                    }
                ),
                "transaction_id": None,
                "xid": None,
            }
        ),
        "device_information": cs_models.TssV2TransactionsGet200ResponseDeviceInformation(  # noqa: E501
            **{"cookies_accepted": None, "host_name": None, "ip_address": "172.20.0.9"}
        ),
        "error_information": None,
        "fraud_marking_information": {"reason": None},
        "health_care_information": None,
        "id": fake_id,
        "installment_information": {"identifier": None, "number_of_installments": None},
        "links": cs_models.TssV2TransactionsGet200ResponseLinks(
            **{
                "_self": cs_models.PtsV2PaymentsPost201ResponseLinksSelf(
                    **{
                        "href": "https://apitest.cybersource.com/tss/v2/transactions/fake_id",
                        "method": "GET",
                    }
                ),
                "related_transactions": None,
            }
        ),
        "merchant_defined_information": [
            cs_models.Ptsv2paymentsMerchantDefinedInformation(
                **{"key": "1", "value": "3"}
            )
        ],
        "merchant_id": "fake_test_merchant",
        "merchant_information": cs_models.TssV2TransactionsGet200ResponseMerchantInformation(  # noqa: E501
            **{
                "merchant_descriptor": cs_models.TssV2TransactionsGet200ResponseMerchantInformationMerchantDescriptor(  # noqa: E501
                    **{"name": "fake_test_merchant"}
                )
            }
        ),
        "order_information": cs_models.TssV2TransactionsGet200ResponseOrderInformation(
            **{
                "amount_details": cs_models.TssV2TransactionsGet200ResponseOrderInformationAmountDetails(  # noqa: E501
                    **{
                        "authorized_amount": "750",
                        "currency": "USD",
                        "settlement_amount": None,
                        "settlement_currency": None,
                        "surcharge": None,
                        "tax_amount": "0",
                        "total_amount": "750",
                    }
                ),
                "bill_to": cs_models.TssV2TransactionsGet200ResponseOrderInformationBillTo(  # noqa: E501
                    **{
                        "address1": "123 The Place to Be",
                        "address2": None,
                        "administrative_area": "TN",
                        "company": None,
                        "country": "US",
                        "email": "alearner@mitxonline.odl.local",
                        "first_name": "TEST",
                        "last_name": "USER",
                        "locality": "Memphis",
                        "middle_name": None,
                        "name_suffix": None,
                        "phone_number": "9015551212",
                        "postal_code": "38104",
                        "title": None,
                    }
                ),
                "invoice_details": cs_models.TssV2TransactionsGet200ResponseOrderInformationInvoiceDetails(  # noqa: E501
                    **{"sales_slip_number": None}
                ),
                "line_items": [
                    cs_models.TssV2TransactionsGet200ResponseOrderInformationLineItems(
                        **{
                            "fulfillment_type": "P ",
                            "product_code": "60",
                            "product_name": "course-v1:MITx+14.310x+1T2023",
                            "product_sku": "60-35",
                            "quantity": 1,
                            "tax_amount": "0",
                            "unit_price": "750",
                        }
                    )
                ],
                "ship_to": cs_models.TssV2TransactionsGet200ResponseOrderInformationShipTo(  # noqa: E501
                    **{
                        "address1": None,
                        "address2": None,
                        "administrative_area": None,
                        "company": None,
                        "country": None,
                        "first_name": None,
                        "last_name": None,
                        "locality": None,
                        "phone_number": None,
                        "postal_code": None,
                    }
                ),
                "shipping_details": cs_models.TssV2TransactionsGet200ResponseOrderInformationShippingDetails(  # noqa: E501
                    **{"gift_wrap": None, "shipping_method": None}
                ),
            }
        ),
        "payment_information": cs_models.TssV2TransactionsGet200ResponsePaymentInformation(  # noqa: E501
            **{
                "account_features": cs_models.TssV2TransactionsGet200ResponsePaymentInformationAccountFeatures(  # noqa: E501
                    **{
                        "balance_amount": None,
                        "currency": None,
                        "previous_balance_amount": None,
                    }
                ),
                "bank": None,
                "card": cs_models.TssV2TransactionsGet200ResponsePaymentInformationCard(
                    **{
                        "account_encoder_id": None,
                        "expiration_month": "02",
                        "expiration_year": "2025",
                        "issue_number": None,
                        "prefix": "411111",
                        "start_month": None,
                        "start_year": None,
                        "suffix": "1111",
                        "type": "001",
                        "use_as": None,
                    }
                ),
                "customer": cs_models.TssV2TransactionsGet200ResponsePaymentInformationCustomer(  # noqa: E501
                    **{"customer_id": None, "id": None}
                ),
                "instrument_identifier": cs_models.TssV2TransactionsGet200ResponsePaymentInformationInstrumentIdentifier(  # noqa: E501
                    **{"id": None}
                ),
                "invoice": cs_models.TssV2TransactionsGet200ResponsePaymentInformationInvoice(  # noqa: E501
                    **{"barcode_number": None, "expiration_date": None, "number": None}
                ),
                "payment_instrument": cs_models.PtsV2PaymentsPost201ResponseTokenInformationPaymentInstrument(  # noqa: E501
                    **{"id": None}
                ),
                "payment_type": cs_models.TssV2TransactionsGet200ResponsePaymentInformationPaymentType(  # noqa: E501
                    **{"method": "VI", "name": "smartpay", "type": "credit card"}
                ),
                "shipping_address": cs_models.PtsV2PaymentsPost201ResponseTokenInformationShippingAddress(  # noqa: E501
                    **{"id": None}
                ),
            }
        ),
        "payment_insights_information": cs_models.PtsV2PaymentsPost201ResponsePaymentInsightsInformation(  # noqa: E501
            **{
                "response_insights": cs_models.PtsV2PaymentsPost201ResponsePaymentInsightsInformationResponseInsights(  # noqa: E501
                    **{"category": None, "category_code": None}
                )
            }
        ),
        "point_of_sale_information": cs_models.TssV2TransactionsGet200ResponsePointOfSaleInformation(  # noqa: E501
            **{
                "emv": None,
                "entry_mode": None,
                "terminal_capability": None,
                "terminal_id": "111111",
            }
        ),
        "processing_information": cs_models.TssV2TransactionsGet200ResponseProcessingInformation(  # noqa: E501
            **{
                "authorization_options": cs_models.TssV2TransactionsGet200ResponseProcessingInformationAuthorizationOptions(  # noqa: E501
                    **{
                        "auth_type": "O",
                        "initiator": cs_models.TssV2TransactionsGet200ResponseProcessingInformationAuthorizationOptionsInitiator(  # noqa: E501
                            **{
                                "credential_stored_on_file": None,
                                "merchant_initiated_transaction": cs_models.Ptsv2paymentsProcessingInformationAuthorizationOptionsInitiatorMerchantInitiatedTransaction(  # noqa: E501
                                    **{
                                        "original_authorized_amount": None,
                                        "previous_transaction_id": None,
                                        "reason": None,
                                    }
                                ),
                                "stored_credential_used": None,
                                "type": None,
                            }
                        ),
                    }
                ),
                "bank_transfer_options": cs_models.TssV2TransactionsGet200ResponseProcessingInformationBankTransferOptions(  # noqa: E501
                    **{"sec_code": None}
                ),
                "business_application_id": None,
                "commerce_indicator": "7",
                "industry_data_type": None,
                "japan_payment_options": cs_models.TssV2TransactionsGet200ResponseProcessingInformationJapanPaymentOptions(  # noqa: E501
                    **{
                        "business_name": None,
                        "business_name_katakana": None,
                        "payment_method": None,
                        "terminal_id": None,
                    }
                ),
                "payment_solution": "Visa",
            }
        ),
        "processor_information": cs_models.TssV2TransactionsGet200ResponseProcessorInformation(  # noqa: E501
            **{
                "ach_verification": cs_models.PtsV2PaymentsPost201ResponseProcessorInformationAchVerification(  # noqa: E501
                    **{"result_code": None, "result_code_raw": "100"}
                ),
                "approval_code": "888888",
                "avs": cs_models.PtsV2PaymentsPost201ResponseProcessorInformationAvs(
                    **{"code": "X", "code_raw": "I1"}
                ),
                "card_verification": cs_models.Riskv1decisionsProcessorInformationCardVerification(  # noqa: E501
                    **{"result_code": None}
                ),
                "electronic_verification_results": cs_models.TssV2TransactionsGet200ResponseProcessorInformationElectronicVerificationResults(  # noqa: E501
                    **{
                        "email": None,
                        "email_raw": None,
                        "name": None,
                        "name_raw": None,
                        "phone_number": None,
                        "phone_number_raw": None,
                        "postal_code": None,
                        "postal_code_raw": None,
                        "street": None,
                        "street_raw": None,
                    }
                ),
                "multi_processor_routing": None,
                "network_transaction_id": "123456789619999",
                "payment_account_reference_number": None,
                "processor": cs_models.TssV2TransactionsGet200ResponseProcessorInformationProcessor(  # noqa: E501
                    **{"name": "smartpay"}
                ),
                "response_code": "100",
                "response_code_source": None,
                "response_id": None,
                "retrieval_reference_number": None,
                "system_trace_audit_number": None,
                "transaction_id": None,
            }
        ),
        "reconciliation_id": fake_recon_id,
        "risk_information": cs_models.TssV2TransactionsGet200ResponseRiskInformation(
            **{
                "local_time": None,
                "passive_profile": None,
                "passive_rules": None,
                "profile": None,
                "rules": None,
                "score": cs_models.TssV2TransactionsGet200ResponseRiskInformationScore(
                    **{"factor_codes": None, "result": None}
                ),
            }
        ),
        "root_id": fake_id,
        "sender_information": cs_models.TssV2TransactionsGet200ResponseSenderInformation(  # noqa: E501
            **{"reference_number": None}
        ),
        "submit_time_utc": "2023-02-03T16:55:49Z",
        "token_information": cs_models.TssV2TransactionsGet200ResponseTokenInformation(
            **{
                "customer": None,
                "instrument_identifier": None,
                "payment_instrument": None,
                "shipping_address": None,
            }
        ),
    }

    return cs_models.TssV2TransactionsGet200Response(**data_dict)


@pytest.mark.parametrize("test_failure", [[True, False]])
def test_get_transaction_details(mocker, test_failure):
    """Tests to make sure the processing in get_transaction_details is working."""
    fake_record = create_transaction_detail_record()
    fake_id = fake_record.id
    cybersource_gateway = CyberSourcePaymentGateway()
    expected_exception = Exception("CyberSource API returned HTTP status 500: Error")

    if test_failure:
        mocker.patch(
            "CyberSource.TransactionDetailsApi.get_transaction",
            side_effect=expected_exception,
        )

        with pytest.raises(Exception):  # noqa: B017, PT011
            cybersource_gateway.get_transaction_details(fake_id)
    else:
        mocker.patch(
            "CyberSource.TransactionDetailsApi.get_transaction",
            return_value=(fake_record, 200, {}),
        )

        (cs_response, fmt_response) = cybersource_gateway.get_transaction_details(
            fake_id
        )

        assert cs_response == fake_record
        assert fmt_response["transaction_id"] == fake_record.id
        assert fmt_response["req_reference_number"] == "mitxonline-dev-4"


@pytest.mark.parametrize("test_failure", [[None, "search", "get"]])
def test_find_and_get_transactions(mocker, test_failure):
    """Tests the combined find_and_get_transaction function."""

    fake_ids = ["mitxonline-dev-2"]
    faked_responses = create_transaction_search_results()
    fake_record = create_transaction_detail_record()
    expected_exception = Exception("CyberSource API returned HTTP status 500: Error")
    cybersource_gateway = CyberSourcePaymentGateway()

    if test_failure:
        if test_failure == "search":
            mocker.patch(
                "CyberSource.SearchTransactionsApi.create_search",
                side_effect=expected_exception,
            )
        else:
            mocker.patch(
                "CyberSource.SearchTransactionsApi.create_search",
                return_value=(faked_responses, 200, {}),
            )

            mocker.patch(
                "CyberSource.TransactionDetailsApi.get_transaction",
                side_effect=expected_exception,
            )

        with pytest.raises(Exception):  # noqa: B017, PT011
            cybersource_gateway.find_and_get_transactions(fake_ids)
    else:
        mocker.patch(
            "CyberSource.SearchTransactionsApi.create_search",
            return_value=(faked_responses, 200, {}),
        )
        mocker.patch(
            "CyberSource.TransactionDetailsApi.get_transaction",
            return_value=(fake_record, 200, {}),
        )

        results = cybersource_gateway.find_and_get_transactions(fake_ids)
        assert len(results) == 1
        assert fake_ids[0] in results
        assert results[0]["req_reference_number"] == fake_ids[0]
