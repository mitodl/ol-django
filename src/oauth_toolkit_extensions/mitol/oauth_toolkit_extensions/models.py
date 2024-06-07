"""OAuth toolkit extensions model classes"""
from typing import List

from django.db import models
from oauth2_provider.settings import oauth2_settings

from mitol.common.models import TimestampedModel

APPLICATION_MODEL = oauth2_settings.APPLICATION_MODEL


class ApplicationAccess(TimestampedModel):
    """Data model for managing application-specific OAuth2 scopes"""

    application = models.OneToOneField(
        APPLICATION_MODEL, on_delete=models.CASCADE, related_name="access"
    )

    scopes = models.CharField(max_length=512)

    @property
    def scopes_list(self) -> List[str]:
        """Return a list of scopes this application is permitted"""
        return [scope.strip() for scope in self.scopes.split(",")]
