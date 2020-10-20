"""Common default factories"""

from django.contrib.auth import get_user_model
from factory import Faker, Sequence
from factory.django import DjangoModelFactory


class UserFactory(DjangoModelFactory):
    """
    User factory for default django model

    This expects the user model to be django.contrib.auth.models.User or a subclass of it
    """

    username = Sequence(lambda n: f"user-{n}")
    email = Sequence(lambda n: f"user-{n}@example.com")
    first_name = Faker("first_name")
    last_name = Faker("first_name")

    class Meta:
        model = get_user_model()
