"""testapp URL Configuration"""
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("api/", include("mitol.digitalcredentials.urls")),
    path("admin/", admin.site.urls),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]
