"""URL conf for BulkView operation dispatch.

Paths here are SCIM-relative (no /scim/v2/ prefix), matching the path format
used in bulk operation payloads. Overrides the Users endpoint with our custom
UsersView so bulk operations go through our transaction wrapping and row locking.
"""

from django.urls import include, re_path
from mitol.scim import views

urlpatterns = [
    re_path(r"^Users(?:/(?P<uuid>[^/]+))?$", views.UsersView.as_view(), name="users"),
    include("django_scim.urls"),
]
