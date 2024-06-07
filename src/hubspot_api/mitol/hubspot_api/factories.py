"""Factory for Hubspot API models"""
import string

import pytest
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from factory import Factory, Faker, LazyAttribute, Sequence, SubFactory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyInteger, FuzzyText
from hubspot.crm.objects import SimplePublicObject

from mitol.hubspot_api.models import HubspotObject

pytestmark = pytest.mark.django_db


class GroupFactory(DjangoModelFactory):
    """Factory for default Group model"""

    name = FuzzyText()

    class Meta:
        model = Group


class HubspotObjectFactory(DjangoModelFactory):
    """Factory for HubspotObjects"""

    content_object = SubFactory(GroupFactory)
    content_type = LazyAttribute(
        lambda o: ContentType.objects.get_for_model(o.content_object)
    )
    object_id = FuzzyInteger(1, 999999999)
    hubspot_id = FuzzyText(chars=string.digits)

    class Meta:
        model = HubspotObject


class SimplePublicObjectFactory(Factory):
    """Factory for SimplePublicObject"""

    id = Sequence(lambda number: "111000{}".format(number))
    properties = Faker("pydict")

    class Meta:
        model = SimplePublicObject
