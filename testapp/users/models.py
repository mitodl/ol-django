from django.contrib.auth.models import AbstractUser
from django.db import models
from django_scim.models import AbstractSCIMUserMixin
from mitol.common.models import TimestampedModel


# Create your models here.
class User(AbstractUser, AbstractSCIMUserMixin, TimestampedModel):
    """Custom user"""

    global_id = models.CharField(max_length=255, blank=True, default="")
