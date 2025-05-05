from django.contrib.auth.models import AbstractUser
from django_scim.models import AbstractSCIMUserMixin
from mitol.common.models import TimestampedModel, UserGlobalIdMixin


# Create your models here.
class User(AbstractUser, AbstractSCIMUserMixin, TimestampedModel, UserGlobalIdMixin):
    """Custom user"""
