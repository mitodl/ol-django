"""Admin for hubspot CRM"""
from django.contrib import admin

from mitol.hubspot_api.models import HubspotObject


class HubspotObjectAdmin(admin.ModelAdmin):
    """Admin for HubspotObject"""

    model = HubspotObject
    list_display = ("content_object", "content_type", "object_id", "hubspot_id")
    list_filter = ("content_type",)

    def has_add_permission(self, request):
        return False


admin.site.register(HubspotObject, HubspotObjectAdmin)
