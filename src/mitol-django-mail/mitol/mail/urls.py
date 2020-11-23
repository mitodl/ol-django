"""URL configurations for mail"""
from django.conf import settings
from django.conf.urls import url

from mitol.mail.views import EmailDebuggerView


urlpatterns = []

if getattr(settings, "MITOL_MAIL_ENABLE_EMAIL_DEBUGGER", False):  # pragma: no cover
    urlpatterns += [
        url(r"^__emaildebugger__/$", EmailDebuggerView.as_view(), name="email-debugger")
    ]
