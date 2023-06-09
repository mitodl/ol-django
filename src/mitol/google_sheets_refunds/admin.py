"""Admin for RefundRequest"""
from django.contrib import admin

from mitol.google_sheets_refunds.models import RefundRequest


class RefundRequestAdmin(admin.ModelAdmin):
    """Admin for RefundRequest"""

    model = RefundRequest
    list_display = ("form_response_id", "date_completed", "raw_data")


admin.site.register(RefundRequest, RefundRequestAdmin)
