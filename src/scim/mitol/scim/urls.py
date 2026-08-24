"""URL configurations for SCIM"""

from django.urls import include, path, re_path
from mitol.scim import views

ol_scim_urls = (
    [
        path("Bulk", views.BulkView.as_view(), name="bulk"),
        path("Users/.search", views.SearchView.as_view(), name="users-search"),
        re_path(
            r"^Users(?:/(?P<uuid>[^/]+))?$",
            views.UsersView.as_view(),
            name="users",
        ),
    ],
    "ol-scim",
)

urlpatterns = [
    path("scim/v2/", include(ol_scim_urls)),
    path("scim/v2/", include("django_scim.urls", namespace="scim")),
]
