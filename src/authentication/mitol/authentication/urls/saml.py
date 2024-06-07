"""URL configurations for authentication"""

from django.urls import path

from mitol.authentication.views.saml import saml_metadata

urlpatterns = [
    path("saml/metadata/", saml_metadata, name="saml-metadata"),
]
