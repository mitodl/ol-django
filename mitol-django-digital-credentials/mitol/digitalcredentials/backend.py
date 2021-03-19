"""Digital credentials proxy to sign-and-verify service"""
from typing import Dict
from urllib.parse import urlencode, urljoin

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from django.utils.module_loading import import_string

from mitol.common.utils import now_in_utc
from mitol.digitalcredentials.models import DigitalCredentialRequest, LearnerDID
from mitol.digitalcredentials.requests_utils import (
    prepare_request_digest,
    prepare_request_hmac_signature,
)


def build_api_url(path: str) -> str:
    """Build a url for the verify service"""
    base_url = settings.MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL
    if not base_url:
        raise ImproperlyConfigured(
            "MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL is not set"
        )
    return urljoin(base_url, path)


def _extract_verification_method(presentation: Dict) -> str:
    """Extract the verification method from the presentation"""
    proof = presentation.get("proof", {})

    for key, value in proof.items():
        if key.endswith("verificationMethod"):
            if isinstance(value, str):
                return value
            elif isinstance(value, dict):
                return value.get("id", "")

    # fail-safe value
    return ""


def verify_presentations(
    credential_request: DigitalCredentialRequest, presentation: Dict
) -> requests.Response:
    """Verifies the learner's presentation against the backend service"""
    return requests.post(
        build_api_url("/verify/presentations"),
        json={
            "verifiablePresentation": presentation,
            "options": {
                "verificationMethod": _extract_verification_method(presentation),
                "challenge": str(credential_request.uuid),
            },
        },
    )


def build_credential(credentialed_object: Dict, learner_did: LearnerDID) -> Dict:
    """Build the credential"""
    build_credendial_func_name = (
        settings.MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC
    )
    if not build_credendial_func_name:
        raise ImproperlyConfigured(
            "MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC is not set"
        )

    build_credendial_func = import_string(build_credendial_func_name)

    return build_credendial_func(credentialed_object, learner_did)


def issue_credential(credential: Dict) -> Dict:
    """Request signed credential from the sign-and-verify service"""
    request = requests.Request(
        "POST",
        build_api_url("/issue/credentials"),
        json=credential,
        headers={"Date": now_in_utc().strftime("%a, %d %b %Y %H:%M:%S GMT")},
    ).prepare()
    # compute the digest after the request is prepared because we need the JSON body serialized
    request = prepare_request_digest(request)
    if settings.MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET:
        request = prepare_request_hmac_signature(
            request, settings.MITOL_DIGITAL_CREDENTIALS_HMAC_SECRET
        )

    with requests.Session() as session:
        response = session.send(request)
    response.raise_for_status()
    return response.json()


def create_deep_link_url(credential_request: DigitalCredentialRequest) -> str:
    """Creates and returns a deep link credential url"""
    auth_type = settings.MITOL_DIGITAL_CREDENTIALS_AUTH_TYPE
    deep_link_url = settings.MITOL_DIGITAL_CREDENTIALS_DEEP_LINK_URL

    if not auth_type:
        raise ImproperlyConfigured(
            "MITOL_DIGITAL_CREDENTIALS_AUTH_TYPE is required to create deep links"
        )
    if not deep_link_url:
        raise ImproperlyConfigured(
            "MITOL_DIGITAL_CREDENTIALS_DEEP_LINK_URL is required to create deep links"
        )

    params = {
        "auth_type": auth_type,
        "issuer": settings.SITE_BASE_URL,
        "vc_request_url": urljoin(
            settings.SITE_BASE_URL,
            reverse(
                "digital-credentials:credentials-issue",
                kwargs={"uuid": credential_request.uuid},
            ),
        ),
        "challenge": credential_request.uuid,
    }

    return f"{deep_link_url}?{urlencode(params)}"
