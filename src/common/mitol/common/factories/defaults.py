"""Common default factories"""

from django.contrib.auth import get_user_model
from factory import Faker, SelfAttribute, Trait
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyText


class UserFactory(DjangoModelFactory):
    """
    User factory for default django model

    This expects the user model to be django.contrib.auth.models.User or a subclass of it
    """  # noqa: E501

    username = SelfAttribute("email")
    email = FuzzyText(length=20, suffix="@example.com")
    first_name = Faker("first_name")
    last_name = Faker("first_name")

    class Meta:
        model = get_user_model()

    class Params:
        with_scim = Trait(
            scim_external_id=Faker("uuid4"), scim_username=SelfAttribute("email")
        )
