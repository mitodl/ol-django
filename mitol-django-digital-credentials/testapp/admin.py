from django.contrib import admin

from testapp.models import DemoCourseware


class DemoCoursewareAdmin(admin.ModelAdmin):
    """Admin for DemoCourseware"""


admin.site.register(DemoCourseware, DemoCoursewareAdmin)
