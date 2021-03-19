"""testapp URL Configuration"""
from django.contrib import admin
from django.urls import include, path
from rest_framework import routers

from testapp.views import DemoCoursewareViewSet


router = routers.SimpleRouter()
router.register(r"democourseware", DemoCoursewareViewSet)

urlpatterns = [
    path("api/", include(router.urls)),
    path("api/", include("mitol.digitalcredentials.urls")),
    path("admin/", admin.site.urls),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]
