"""HTTP views for sheets app"""
import logging
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from google.auth.exceptions import GoogleAuthError
from google_auth_oauthlib.flow import Flow

from mitol.google_sheets.constants import REQUIRED_GOOGLE_API_SCOPES
from mitol.google_sheets.models import GoogleApiAuth
from mitol.google_sheets.utils import generate_google_client_config

log = logging.getLogger(__name__)


@staff_member_required(login_url="login")
def sheets_admin_view(request):
    """Admin view that renders a page that allows a user to begin Google OAuth auth"""
    existing_api_auth = GoogleApiAuth.objects.first()
    successful_action = request.GET.get("success")
    return render(
        request,
        "admin.html",
        {
            "existing_api_auth": existing_api_auth,
            "auth_completed": successful_action == "auth",
        },
    )


@staff_member_required(login_url="login")
def request_google_auth(request):
    """Admin view to begin Google OAuth auth"""
    flow = Flow.from_client_config(
        generate_google_client_config(), scopes=REQUIRED_GOOGLE_API_SCOPES
    )
    flow.redirect_uri = urljoin(
        settings.SITE_BASE_URL, reverse("google-sheets:complete-google-auth")
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    request.session["state"] = state
    request.session["code_verifier"] = flow.code_verifier
    return redirect(authorization_url)


@csrf_exempt
def complete_google_auth(request):
    """Admin view that handles the redirect from Google after completing Google auth"""
    state = request.session.get("state")
    if not state:
        raise GoogleAuthError(
            "Could not complete Google auth - 'state' was not found in the session"
        )
    flow = Flow.from_client_config(
        generate_google_client_config(), scopes=REQUIRED_GOOGLE_API_SCOPES, state=state
    )
    flow.redirect_uri = urljoin(
        settings.SITE_BASE_URL, reverse("google-sheets:complete-google-auth")
    )
    flow.code_verifier = request.session["code_verifier"]
    flow.fetch_token(code=request.GET.get("code"))

    # Store credentials
    credentials = flow.credentials
    with transaction.atomic():
        google_api_auth, _ = GoogleApiAuth.objects.select_for_update().get_or_create()
        google_api_auth.requesting_user = request.user
        google_api_auth.access_token = credentials.token
        google_api_auth.refresh_token = credentials.refresh_token
        google_api_auth.save()

    return redirect(
        "{}?success=auth".format(reverse("google-sheets:sheets-admin-view"))
    )
