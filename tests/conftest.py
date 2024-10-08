from datetime import timedelta  # noqa: INP001
from os import environ
from types import SimpleNamespace

import pytest
from django.test.client import Client
from mitol.common.utils import now_in_utc
from pytest_django.fixtures import _set_suffix_to_test_databases
from pytest_django.lazy_django import skip_if_no_django


@pytest.fixture(scope="session")
def django_db_modify_db_settings_pants_suffix() -> None:  # noqa: PT004
    skip_if_no_django()

    slot_id = environ.get("PANTS_EXECUTION_SLOT", None)

    if slot_id is not None:
        _set_suffix_to_test_databases(suffix=slot_id)


@pytest.fixture(scope="session")
def django_db_modify_db_settings_parallel_suffix(  # noqa: PT004
    django_db_modify_db_settings_pants_suffix,  # noqa: ARG001
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
def learner(db):  # noqa: ARG001
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
        token="1234567890",  # noqa: S106
        application=application,
        expires=now_in_utc() + timedelta(days=1),
        scope="digitalcredentials",
    )
    return SimpleNamespace(
        learner=learner, application=application, access_token=access_token
    )


@pytest.fixture
def staff_user(db):  # noqa: ARG001
    """Staff user fixture"""
    from mitol.common.factories import UserFactory

    return UserFactory.create(is_staff=True)


@pytest.fixture
def user_client(learner):
    """Django test client that is authenticated with the user"""
    client = Client()
    client.force_login(learner)
    return client


@pytest.fixture
def staff_client(staff_user):
    """Django test client that is authenticated with the staff user"""
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def google_sheets_base_settings(settings):
    """Fixture for base google sheets settings"""
    settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID = "1"
    settings.MITOL_GOOGLE_SHEETS_PROCESSOR_APP_NAME = "test app name"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_API_PROJECT_ID = "project-id-1234"
    settings.MITOL_GOOGLE_SHEETS_ENROLLMENT_CHANGE_SHEET_ID = "sheet-id-1234"
    return settings


@pytest.fixture
def google_sheets_service_creds_settings(settings):
    """Fixture for google sheets settings configured for a service account"""
    settings.MITOL_GOOGLE_SHEETS_DRIVE_SERVICE_ACCOUNT_CREDS = '{"credentials": "json"}'
    return settings


@pytest.fixture
def google_sheets_client_creds_settings(settings):
    """Fixture gor google sheets settings configured with OAuth"""
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_ID = "nhijg1i.apps.googleusercontent.com"
    settings.MITOL_GOOGLE_SHEETS_DRIVE_CLIENT_SECRET = "secret"  # noqa: S105
    return settings
