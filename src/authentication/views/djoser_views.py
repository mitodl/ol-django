"""
Custom views to override default djoser behaviours
"""
from anymail.message import AnymailMessage
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.core import mail as django_mail
from djoser.email import PasswordResetEmail as DjoserPasswordResetEmail
from djoser.utils import ActionViewMixin
from djoser.views import UserViewSet
from rest_framework import status
from rest_framework.decorators import action

from mitol.mail.api import render_email_templates, send_message


class CustomDjoserAPIView(UserViewSet, ActionViewMixin):
    """
    Overrides the post method of a Djoser view to update session after successful password change
    """

    @action(["post"], detail=False)
    def set_password(self, request, *args, **kwargs):
        """
        Overrides CustomDjoserAPIView.set_password to update the session after a successful
        password change. Without this explicit refresh, the user's session would be
        invalid and they would be logged out.
        """
        response = super().set_password(request, *args, **kwargs)
        if response.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT):
            update_session_auth_hash(self.request, self.request.user)
        return response


class CustomPasswordResetEmail(DjoserPasswordResetEmail):
    """Custom class to modify base functionality in Djoser's PasswordResetEmail class"""

    def send(self, to, *args, **kwargs):
        """
        Overrides djoser.email.PasswordResetEmail#send to use our mail API.
        """
        context = self.get_context_data()
        context.update(self.context)
        with django_mail.get_connection(
            settings.NOTIFICATION_EMAIL_BACKEND
        ) as connection:
            subject, text_body, html_body = render_email_templates(
                "password_reset", context
            )
            msg = AnymailMessage(
                subject=subject,
                body=text_body,
                to=to,
                from_email=settings.MITOL_AUTHENTICATION_FROM_EMAIL,
                connection=connection,
                headers={"Reply-To": settings.MITOL_AUTHENTICATION_REPLY_TO_EMAIL},
            )
            msg.attach_alternative(html_body, "text/html")
            send_message(msg)

    def get_context_data(self):
        """Adds base_url to the template context"""
        context = super().get_context_data()
        context["base_url"] = settings.SITE_BASE_URL
        return context
