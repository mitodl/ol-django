"""User models for the testapp."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django_scim.models import AbstractSCIMUserMixin
from mitol.common.models import TimestampedModel, UserGlobalIdMixin


# Create your models here.
class User(AbstractUser, AbstractSCIMUserMixin, TimestampedModel, UserGlobalIdMixin):
    """Custom user"""


class UserProfile(TimestampedModel):
    """Profile attached to a user, for exercising gateway user sync."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    name = models.CharField(max_length=255, blank=True, default="")
    email_optin = models.BooleanField(default=False)
