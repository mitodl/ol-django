"""Tests for the payment gateway models"""

import pytest
from django.core.exceptions import ValidationError
from mitol.payment_gateway import constants
from mitol.payment_gateway.factories import StripePaymentMethodTypeFactory
from mitol.payment_gateway.models import PaymentMethodType, StripePaymentMethodType

pytestmark = [pytest.mark.django_db]


def test_stripe_payment_method_type_decodes_gateway_data():
    """Test that the Stripe proxy model decodes the gateway data."""

    method = StripePaymentMethodTypeFactory.create(
        gateway_data={"type": "custom", "id": "cpmt_123"}
    )

    method = StripePaymentMethodType.objects.get(pk=method.pk)
    assert method.stripe_type == constants.STRIPE_PAYMENT_METHOD_TYPE_CUSTOM
    assert method.stripe_id == "cpmt_123"
    assert method.is_custom

    method.stripe_type = constants.STRIPE_PAYMENT_METHOD_TYPE_BUILTIN
    method.stripe_id = "card"
    method.save()
    method.refresh_from_db()

    assert method.gateway_data == {"type": "builtin", "id": "card"}
    assert not method.is_custom


def test_stripe_payment_method_type_forces_gateway():
    """Test that the Stripe proxy model always saves with the Stripe gateway."""

    method = StripePaymentMethodType(
        name="PayPal",
        gateway=constants.MITOL_PAYMENT_GATEWAY_CYBERSOURCE,
        gateway_data={"type": "custom", "id": "cpmt_123"},
    )
    method.save()

    assert method.gateway == constants.MITOL_PAYMENT_GATEWAY_STRIPE
    assert PaymentMethodType.objects.get(pk=method.pk).gateway == (
        constants.MITOL_PAYMENT_GATEWAY_STRIPE
    )


def test_stripe_payment_method_type_manager():
    """Test that the Stripe proxy manager only returns Stripe payment methods."""

    stripe_method = StripePaymentMethodTypeFactory.create()
    PaymentMethodType.objects.create(
        name="other", gateway=constants.MITOL_PAYMENT_GATEWAY_CYBERSOURCE
    )

    assert list(StripePaymentMethodType.objects.all()) == [stripe_method]
    assert PaymentMethodType.objects.count() == 2  # noqa: PLR2004


def test_stripe_payment_method_type_manager_update_bumps_timestamp():
    """Test that .update() on the Stripe manager still sets updated_on."""

    method = StripePaymentMethodTypeFactory.create()
    original_updated_on = method.updated_on

    StripePaymentMethodType.objects.filter(pk=method.pk).update(is_default=False)
    method.refresh_from_db()

    assert method.updated_on > original_updated_on


@pytest.mark.parametrize(
    ("gateway_data", "is_valid"),
    [
        ({"type": "custom", "id": "cpmt_123"}, True),
        ({"type": "builtin", "id": "card"}, True),
        ({"type": "custom", "id": "card"}, False),
        ({"type": "builtin", "id": ""}, False),
        ({"type": "builtin"}, False),
        ({"type": "other", "id": "card"}, False),
        ({"id": "cpmt_123"}, False),
        ({}, False),
        ({"type": "custom", "id": 123}, False),
        ("cpmt_123", False),
        (["cpmt_123"], False),
    ],
)
def test_stripe_payment_method_type_clean(gateway_data, is_valid):
    """Test validation of the Stripe gateway data."""

    method = StripePaymentMethodType(name="test", gateway_data=gateway_data)

    if is_valid:
        method.full_clean(exclude=["gateway"])
    else:
        with pytest.raises(ValidationError) as exc:
            method.full_clean(exclude=["gateway"])
        assert "gateway_data" in exc.value.message_dict
