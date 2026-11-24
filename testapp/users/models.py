"""Test app user models"""

from django.contrib.auth.models import AbstractUser
from django.db.models import CASCADE, BooleanField, CharField, OneToOneField
from django_scim.models import AbstractSCIMUserMixin
from mitol.common.models import TimestampedModel, UserGlobalIdMixin


# Create your models here.
class User(AbstractUser, AbstractSCIMUserMixin, TimestampedModel, UserGlobalIdMixin):
    """Custom user"""


class UserProfile(TimestampedModel):
    """Related model for testing the userinfo map's additional_models"""

    user = OneToOneField(User, on_delete=CASCADE, related_name="profile")
    country_code = CharField(max_length=2, blank=True, default="")
    email_optin = BooleanField(default=False)
