from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user"""

    USERNAME_FIELD = "global_id"

    global_id = models.CharField(max_length=255, blank=True, default="")
