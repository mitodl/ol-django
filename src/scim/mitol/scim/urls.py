"""URL configurations for SCIM"""

from django.urls import include, path, re_path
from django_scim import views as djs_views
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
        # ahead of the Groups pattern below, which would otherwise match
        # `.search` as a uuid and shadow django_scim's search endpoint
        path(
            "Groups/.search",
            djs_views.GroupSearchView.as_view(),
            name="groups-search",
        ),
        re_path(
            r"^Groups(?:/(?P<uuid>[^/]+))?$",
            views.GroupsView.as_view(),
            name="groups",
        ),
    ],
    "ol-scim",
)

urlpatterns = [
    path("scim/v2/", include(ol_scim_urls)),
    path("scim/v2/", include("django_scim.urls", namespace="scim")),
]
