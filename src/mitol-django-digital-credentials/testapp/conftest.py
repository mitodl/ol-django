from datetime import timedelta
from types import SimpleNamespace

import pytest
from oauth2_provider.models import AccessToken, get_application_model

from mitol.common.factories import UserFactory
from mitol.common.utils import now_in_utc


Application = get_application_model()


@pytest.fixture
def learner_and_oauth2():
    learner = UserFactory.create()
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
        scope="read write digitalcredentials",
    )
    return SimpleNamespace(
        learner=learner, application=application, access_token=access_token
    )
