""" testapp admin """
from django.contrib import admin
from testapp.models import DemoCourseware


@admin.register(DemoCourseware)
class DemoCoursewareAdmin(admin.ModelAdmin):
    """Admin for DemoCourseware"""


