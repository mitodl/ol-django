"""Test factories"""

import string

import faker
from factory import Factory, SubFactory, fuzzy
from factory.django import DjangoModelFactory
from mitol.common.factories import UserFactory
from mitol.digitalcredentials.factories import (
    DigitalCredentialFactory,
    DigitalCredentialRequestFactory,
)
from mitol.payment_gateway.api import CartItem, Order, Refund

from testapp.models import DemoCourseware

FAKE = faker.Factory.create()


class DemoCoursewareFactory(DjangoModelFactory):
    """Factory for DemoCourseware"""

    learner = SubFactory(UserFactory)

    class Meta:
        model = DemoCourseware


class DemoCoursewareDigitalCredentialFactory(DigitalCredentialFactory):
    """Factory for a DigitalCredential of DemoCourseware"""

    credentialed_object = SubFactory(DemoCoursewareFactory)


class DemoCoursewareDigitalCredentialRequestFactory(DigitalCredentialRequestFactory):
    """Factory for a DigitalCredentialRequest of DemoCourseware"""

    credentialed_object = SubFactory(DemoCoursewareFactory)


class CartItemFactory(Factory):
    class Meta:
        model = CartItem

    sku = fuzzy.FuzzyText()
    code = fuzzy.FuzzyText(length=6)
    quantity = fuzzy.FuzzyInteger(1, 5, 1)
    name = FAKE.sentence(nb_words=3)
    taxable = 0
    unitprice = fuzzy.FuzzyDecimal(1, 300, precision=2)


class OrderFactory(Factory):
    class Meta:
        model = Order

    ip_address = FAKE.ipv4()
    reference = fuzzy.FuzzyText(length=6)
    username = FAKE.safe_email()
    items = []


class RefundFactory(Factory):
    """Factory for creating Refund data object for CyberSource API calls"""

    class Meta:
        model = Refund

    transaction_id = fuzzy.FuzzyText(length=22, chars=string.digits)
    refund_amount = fuzzy.FuzzyFloat(
        1.00, 100.00
    )  # Just a random amount with some min/max constraints
    refund_currency = "USD"
