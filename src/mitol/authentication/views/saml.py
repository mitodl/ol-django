"""SAML-specific auth views"""
from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from social_django.utils import load_backend, load_strategy


def saml_metadata(request: HttpRequest):
    """Display SAML configuration metadata as XML"""
    complete_url = reverse("social:complete", args=("saml",))
    saml_backend = load_backend(
        load_strategy(request), "saml", redirect_uri=complete_url
    )
    metadata, _ = saml_backend.generate_metadata_xml()
    return HttpResponse(content=metadata, content_type="text/xml")
