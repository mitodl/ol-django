"""URL configurations for mail"""
from django.conf import settings
from django.urls import re_path

from mitol.mail.views import EmailDebuggerView

urlpatterns = []

if getattr(settings, "MITOL_MAIL_ENABLE_EMAIL_DEBUGGER", False):  # pragma: no cover
    urlpatterns += [
        re_path(
            r"^__emaildebugger__/$", EmailDebuggerView.as_view(), name="email-debugger"
        )
    ]
