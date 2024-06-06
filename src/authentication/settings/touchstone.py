"""Touchstone configuration settings"""
from urllib.parse import urlparse

from mitol.common.envs import get_bool, get_site_name, get_string
from mitol.common.settings.base import SITE_BASE_URL
from mitol.mail.settings.email import EMAIL_SUPPORT

_SITE_NAME = get_site_name()

# SAML settings
SOCIAL_AUTH_SAML_SP_ENTITY_ID = get_string(
    name="SOCIAL_AUTH_SAML_SP_ENTITY_ID", default=SITE_BASE_URL, description=""
)
SOCIAL_AUTH_SAML_SP_PUBLIC_CERT = get_string(
    name="SOCIAL_AUTH_SAML_SP_PUBLIC_CERT",
    default=None,
    description="The SAML public certificate",
)
SOCIAL_AUTH_SAML_SP_PRIVATE_KEY = get_string(
    name="SOCIAL_AUTH_SAML_SP_PRIVATE_KEY",
    default=None,
    description="The SAML private key",
)
SOCIAL_AUTH_SAML_ORG_DISPLAYNAME = get_string(
    name="SOCIAL_AUTH_SAML_ORG_DISPLAYNAME",
    default=_SITE_NAME,
    description="The SAML Organization display name",
)
SOCIAL_AUTH_SAML_CONTACT_NAME = get_string(
    name="SOCIAL_AUTH_SAML_CONTACT_NAME",
    default=f"{_SITE_NAME} Support",
    description="The SAML contact name for our app",
)
SOCIAL_AUTH_SAML_IDP_ENTITY_ID = get_string(
    name="SOCIAL_AUTH_SAML_IDP_ENTITY_ID",
    default=None,
    description="The SAML IDP entity ID",
)
SOCIAL_AUTH_SAML_IDP_URL = get_string(
    name="SOCIAL_AUTH_SAML_IDP_URL", default=None, description="The SAML IDP URL"
)
SOCIAL_AUTH_SAML_IDP_X509 = get_string(
    name="SOCIAL_AUTH_SAML_IDP_X509",
    default=False,
    description="The SAML IDP x509 certificate",
)
SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_PERM_ID = get_string(
    name="SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_PERM_ID",
    default=None,
    description="The IDP attribute for the user's immutable ID",
)
SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_NAME = get_string(
    name="SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_NAME",
    default=None,
    description="The IDP attribute for the user's name",
)
SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_EMAIL = get_string(
    name="SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_EMAIL",
    default=None,
    description="The IDP attribute for the user's email",
)
SOCIAL_AUTH_SAML_SECURITY_ENCRYPTED = get_bool(
    name="SOCIAL_AUTH_SAML_SECURITY_ENCRYPTED",
    default=False,
    description="If True, SMAL assertions should be encrypted",
)

SOCIAL_AUTH_SAML_ORG_INFO = {
    "en-US": {
        "name": urlparse(SITE_BASE_URL).netloc,
        "displayname": SOCIAL_AUTH_SAML_ORG_DISPLAYNAME,
        "url": SITE_BASE_URL,
    }
}
SOCIAL_AUTH_SAML_TECHNICAL_CONTACT = {
    "givenName": SOCIAL_AUTH_SAML_CONTACT_NAME,
    "emailAddress": EMAIL_SUPPORT,
}
SOCIAL_AUTH_SAML_SUPPORT_CONTACT = SOCIAL_AUTH_SAML_TECHNICAL_CONTACT
SOCIAL_AUTH_DEFAULT_IDP_KEY = "default"
SOCIAL_AUTH_SAML_ENABLED_IDPS = {
    SOCIAL_AUTH_DEFAULT_IDP_KEY: {
        "entity_id": SOCIAL_AUTH_SAML_IDP_ENTITY_ID,
        "url": SOCIAL_AUTH_SAML_IDP_URL,
        "attr_user_permanent_id": SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_PERM_ID,
        "attr_username": SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_PERM_ID,
        "attr_email": SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_EMAIL,
        "attr_full_name": SOCIAL_AUTH_SAML_IDP_ATTRIBUTE_NAME,
        "x509cert": SOCIAL_AUTH_SAML_IDP_X509,
    }
}


SOCIAL_AUTH_SAML_SECURITY_CONFIG = {
    "wantAssertionsEncrypted": SOCIAL_AUTH_SAML_SECURITY_ENCRYPTED,
    "requestedAuthnContext": False,
}
