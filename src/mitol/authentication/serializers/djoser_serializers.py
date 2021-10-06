"""
Custom serializers for overriding default djoser behaviours
"""

from django.contrib.auth import get_user_model
from djoser.conf import settings
from djoser.serializers import SendEmailResetSerializer

User = get_user_model()


class CustomSendEmailResetSerializer(SendEmailResetSerializer):
    def get_user(self, is_active=True):
        # NOTE: This directly copies the implementation of djoser.serializers.UserFunctionsMixin.get_user
        # and only changes the User query. If this method is changed in an updated Djoser
        # release, this method may need to be updated as well.
        try:
            user = User._default_manager.get(
                is_active=is_active,
                **{f"{self.email_field}__iexact": self.data.get(self.email_field, "")},
            )
            if user.has_usable_password():
                return user
        except User.DoesNotExist:
            pass
        if (
            settings.PASSWORD_RESET_SHOW_EMAIL_NOT_FOUND
            or settings.USERNAME_RESET_SHOW_EMAIL_NOT_FOUND
        ):
            self.fail("email_not_found")
