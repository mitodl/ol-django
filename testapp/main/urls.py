"""testapp URL Configuration"""

import sys

from django.contrib import admin
from django.urls import include, path
from oauth2_provider.urls import base_urlpatterns
from rest_framework import routers

from main.views import DemoCoursewareViewSet

router = routers.SimpleRouter()
router.register(r"democourseware", DemoCoursewareViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/", include("mitol.digitalcredentials.urls")),
    path("api/", include("mitol.google_sheets.urls")),
    path("api/", include("mitol.mail.urls")),
    path("", include("mitol.authentication.urls.djoser_urls")),
    path("", include("social_django.urls", namespace="social")),
    path(
        "oauth2/",
        include((base_urlpatterns, "oauth2_provider"), namespace="oauth2_provider"),
    ),
    path("admin/", admin.site.urls),
    path("api/", include("mitol.transcoding.urls")),
    path("", include("mitol.scim.urls")),
    path("", include("mitol.apigateway.urls")),
]

if sys.version_info < (3, 13):
    urlpatterns += [
        path("", include("mitol.authentication.urls.saml")),
    ]
