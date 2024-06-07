"""Digital credentials admin app"""
from django.contrib import admin

from mitol.digitalcredentials.models import (
    DigitalCredential,
    DigitalCredentialRequest,
    LearnerDID,
)


class DigitalCredentialRequestAdmin(admin.ModelAdmin):
    """Admin for DigitalCredentialRequest"""


admin.site.register(DigitalCredentialRequest, DigitalCredentialRequestAdmin)


class DigitalCredentialAdmin(admin.ModelAdmin):
    """Admin for DigitalCredential"""


admin.site.register(DigitalCredential, DigitalCredentialAdmin)


class LearnerDIDAdmin(admin.ModelAdmin):
    """Admin for LearnerDID"""


admin.site.register(LearnerDID, LearnerDIDAdmin)
