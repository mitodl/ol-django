"""Endpoint URLs for sheets app"""
from django.urls import re_path

from mitol.google_sheets import views

app_name = "google-sheets"

urlpatterns = [
    re_path(r"^sheets/admin/", views.sheets_admin_view, name="sheets-admin-view"),
    re_path(r"^sheets/auth/", views.request_google_auth, name="request-google-auth"),
    re_path(
        r"^sheets/auth-complete/",
        views.complete_google_auth,
        name="complete-google-auth",
    ),
]
