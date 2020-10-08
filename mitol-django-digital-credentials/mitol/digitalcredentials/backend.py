"""Digital credentials proxy to sign-and-verify service"""
import json
from copy import deepcopy
from typing import Dict
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.module_loading import import_string

from mitol.common.utils import now_in_utc
from mitol.digitalcredentials.models import LearnerDID


def build_api_url(path: str) -> str:
    """Build a url for the verify service"""
    base_url = settings.MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL
    if not base_url:
        raise ImproperlyConfigured(
            "MITOL_DIGITAL_CREDENTIALS_VERIFY_SERVICE_BASE_URL is not set"
        )
    return urljoin(base_url, path)


def build_credential(courseware_object: Dict, learner_did: LearnerDID) -> Dict:
    """Build the credential"""
    build_credendial_func_name = (
        settings.MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC
    )
    if not build_credendial_func_name:
        raise ImproperlyConfigured(
            "MITOL_DIGITAL_CREDENTIALS_BUILD_CREDENTIAL_FUNC is not set"
        )

    build_credendial_func = import_string(build_credendial_func_name)

    return build_credendial_func(courseware_object, learner_did)


def issue_credential(credential: Dict) -> Dict:
    """Request signed credential from the sign-and-verify service"""
    response = requests.post(build_api_url("/issue/credentials"), json=credential)
    response.raise_for_status()
    return response.json()
