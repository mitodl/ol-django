"""Admin for hubspot CRM"""

from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.db.models import prefetch_related_objects
from mitol.hubspot_api.models import HubspotObject


class HubspotObjectChangeList(ChangeList):
    """ChangeList that loads each page's content_object in one query per type"""

    def get_results(self, request):
        super().get_results(request)
        # Prefetching a row whose content type's model is gone raises, so skip those
        prefetch_related_objects(
            [obj for obj in self.result_list if obj.content_type.model_class()],
            "content_object",
        )


@admin.register(HubspotObject)
class HubspotObjectAdmin(admin.ModelAdmin):
    """Admin for HubspotObject"""

    model = HubspotObject
    list_display = ("content_object", "content_type", "object_id", "hubspot_id")
    list_filter = ("content_type",)

    def get_changelist(self, request, **kwargs):  # noqa: ARG002
        return HubspotObjectChangeList

    def has_add_permission(self, request):  # noqa: ARG002
        return False
