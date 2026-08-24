"""Digital credentials admin app"""

from django.contrib import admin
from mitol.digitalcredentials.models import (
    DigitalCredential,
    DigitalCredentialRequest,
    LearnerDID,
)


@admin.register(DigitalCredentialRequest)
class DigitalCredentialRequestAdmin(admin.ModelAdmin):
    """Admin for DigitalCredentialRequest"""


@admin.register(DigitalCredential)
class DigitalCredentialAdmin(admin.ModelAdmin):
    """Admin for DigitalCredential"""


@admin.register(LearnerDID)
class LearnerDIDAdmin(admin.ModelAdmin):
    """Admin for LearnerDID"""
