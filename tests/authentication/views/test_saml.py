"""SAML view tests"""

import sys
from xml.etree import ElementTree as ET

import pytest
from django.urls import reverse

pytestmark = pytest.mark.skipif(
    sys.version_info >= (3, 13), reason="Not supported in python >= 3.13"
)


def test_saml_metadata(settings, client):
    """Test that SAML metadata page renders XML"""
    settings.SOCIAL_AUTH_SAML_SP_ENTITY_ID = "http://mit.edu"
    settings.SOCIAL_AUTH_SAML_SP_PUBLIC_CERT = ""
    settings.SOCIAL_AUTH_SAML_SP_PRIVATE_KEY = ""
    settings.SOCIAL_AUTH_SAML_ORG_INFO = {
        "en-US": {"name": "MIT", "displayname": "MIT", "url": "http://mit.edu"}
    }
    settings.SOCIAL_AUTH_SAML_TECHNICAL_CONTACT = {
        "givenName": "TestName",
        "emailAddress": "test@example.com",
    }
    settings.SOCIAL_AUTH_SAML_SUPPORT_CONTACT = {
        "givenName": "TestName",
        "emailAddress": "test@example.com",
    }
    settings.SOCIAL_AUTH_SAML_SP_EXTRA = {
        "assertionConsumerService": {"url": "http://mit.edu"}
    }
    response = client.get(reverse("saml-metadata"))

    root = ET.fromstring(response.content)  # noqa: S314
    assert root.tag == "{urn:oasis:names:tc:SAML:2.0:metadata}EntityDescriptor"
    assert response.status_code == 200  # noqa: PLR2004
