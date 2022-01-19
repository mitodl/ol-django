"""Test factories"""
import faker
from factory import Factory, SubFactory, fuzzy
from factory.django import DjangoModelFactory
from testapp.models import DemoCourseware

from mitol.common.factories import UserFactory
from mitol.digitalcredentials.factories import (
    DigitalCredentialFactory,
    DigitalCredentialRequestFactory,
)
from mitol.payment_gateway.api import CartItem, Order

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
