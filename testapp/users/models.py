from django.contrib.auth.models import AbstractUser
from django_scim.models import AbstractSCIMUserMixin
from mitol.common.models import TimestampedModel
from django.db import models


# Create your models here.
class User(AbstractUser, AbstractSCIMUserMixin, TimestampedModel):
    """Custom user"""

    USERNAME_FIELD = "global_id"

    global_id = models.CharField(max_length=255, blank=True, default="")
