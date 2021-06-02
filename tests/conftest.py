from datetime import timedelta
from os import environ
from types import SimpleNamespace

import pytest
from pytest_django.fixtures import _set_suffix_to_test_databases
from pytest_django.lazy_django import skip_if_no_django

from mitol.common.utils import now_in_utc


@pytest.fixture(scope="session")
def django_db_modify_db_settings_pants_suffix() -> None:
    skip_if_no_django()

    slot_id = environ.get("PANTS_EXECUTION_SLOT", None)

    if slot_id is not None:
        _set_suffix_to_test_databases(suffix=slot_id)


@pytest.fixture(scope="session")
def django_db_modify_db_settings_parallel_suffix(
    django_db_modify_db_settings_pants_suffix,
) -> None:
    skip_if_no_django()


@pytest.fixture
def learner_drf_client(learner):
    """DRF API test client that is authenticated with the user"""
    # import is here to avoid trying to load django before settings are initialized
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user=learner)
    return client


@pytest.fixture
def learner():
    """Fixture for a default learner"""
    # import is here to avoid trying to load django before settings are initialized
    from mitol.common.factories import UserFactory

    return UserFactory.create()


@pytest.fixture
def learner_and_oauth2(learner):
    """Fixture for a default learner and oauth2 records"""
    # import is here to avoid trying to load django before settings are initialized
    from oauth2_provider.models import AccessToken, get_application_model

    Application = get_application_model()
    application = Application.objects.create(
        name="Test Application",
        redirect_uris="http://localhost",
        user=learner,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
    )
    access_token = AccessToken.objects.create(
        user=learner,
        token="1234567890",
        application=application,
        expires=now_in_utc() + timedelta(days=1),
        scope="digitalcredentials",
    )
    return SimpleNamespace(
        learner=learner, application=application, access_token=access_token
    )
