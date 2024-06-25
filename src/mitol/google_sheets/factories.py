"""Factories for sheets app"""

from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from mitol.common.factories import UserFactory
from mitol.google_sheets import models


class GoogleApiAuthFactory(DjangoModelFactory):  # noqa: D101
    requesting_user = SubFactory(UserFactory)
    access_token = Faker("pystr", max_chars=30)
    refresh_token = Faker("pystr", max_chars=30)

    class Meta:  # noqa: D106
        model = models.GoogleApiAuth
