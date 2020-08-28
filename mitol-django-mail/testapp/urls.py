"""testapp URL Configuration"""
from django.urls import include, path


urlpatterns = [path("", include("mitol.mail.urls"))]
