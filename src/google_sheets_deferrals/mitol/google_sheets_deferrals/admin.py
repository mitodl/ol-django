"""Admin for DeferralRequest"""
from django.contrib import admin

from mitol.google_sheets_deferrals.models import DeferralRequest


class DeferralRequestAdmin(admin.ModelAdmin):
    """Admin for DeferralRequest"""

    model = DeferralRequest
    list_display = ("form_response_id", "date_completed", "raw_data")


admin.site.register(DeferralRequest, DeferralRequestAdmin)
