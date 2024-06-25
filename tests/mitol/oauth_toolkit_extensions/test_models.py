"""Admin interfaces"""

import pytest
from mitol.oauth_toolkit_extensions.factories import ApplicationAccessFactory

pytestmark = pytest.mark.django_db


def test_application_access_scopes_list():
    """Verify that scopes_list correctly parses scoeps into a list"""
    access = ApplicationAccessFactory.create(scopes="one,two, three , four")

    assert access.scopes_list == [
        "one",
        "two",
        "three",
        "four",
    ]
