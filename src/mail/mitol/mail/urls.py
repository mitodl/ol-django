"""URL configurations for mail"""

from django.conf import settings
from django.urls import path
from mitol.mail.views import EmailDebuggerView

urlpatterns = []

if getattr(settings, "MITOL_MAIL_ENABLE_EMAIL_DEBUGGER", False):  # pragma: no cover
    urlpatterns += [
        path("__emaildebugger__/", EmailDebuggerView.as_view(), name="email-debugger")
    ]
