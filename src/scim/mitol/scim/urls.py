"""URL configurations for SCIM"""

from django.urls import include, re_path

from mitol.scim import views

ol_scim_urls = (
    [
        re_path(r"^Bulk$", views.BulkView.as_view(), name="bulk"),
        re_path(r"^Users/\.search$", views.SearchView.as_view(), name="users-search"),
    ],
    "ol-scim",
)

urlpatterns = [
    re_path(r"^scim/v2/", include(ol_scim_urls)),
    re_path(r"^scim/v2/", include("django_scim.urls", namespace="scim")),
]
