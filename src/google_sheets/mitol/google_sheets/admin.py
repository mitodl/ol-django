"""
Admin site bindings for sheets models
"""

from django.contrib import admin
from django.core.exceptions import ValidationError

from mitol.common.admin import SingletonModelAdmin
from mitol.google_sheets import models


class GoogleApiAuthAdmin(SingletonModelAdmin):
    """Admin for GoogleApiAuth"""

    model = models.GoogleApiAuth
    list_display = ("id", "requesting_user")


class GoogleFileWatchAdmin(admin.ModelAdmin):
    """Admin for GoogleFileWatch"""

    model = models.GoogleFileWatch
    list_display = (
        "id",
        "file_id",
        "channel_id",
        "activation_date",
        "expiration_date",
        "last_request_received",
    )
    ordering = ["-expiration_date"]

    def save_form(self, request, form, change):
        if not change:
            file_id = form.cleaned_data["file_id"]
            if self.model.objects.filter(file_id=file_id).exists():
                raise ValidationError(
                    f"Only one GoogleFileWatch object should exist for each unique file_id (file_id provided: {file_id}). "
                    "Update the existing object instead of creating a new one."
                )
        return super().save_form(request, form, change)


class FileWatchRenewalAttemptAdmin(admin.ModelAdmin):
    """Admin for FileWatchRenewalAttempt"""

    model = models.FileWatchRenewalAttempt
    list_display = (
        "id",
        "sheet_type",
        "sheet_file_id",
        "date_attempted",
        "result",
        "result_status_code",
    )
    search_fields = ("sheet_file_id", "result")
    list_filter = ("sheet_type", "result_status_code")
    readonly_fields = ("date_attempted",)
    ordering = ("-date_attempted",)


admin.site.register(models.GoogleApiAuth, GoogleApiAuthAdmin)
admin.site.register(models.GoogleFileWatch, GoogleFileWatchAdmin)
admin.site.register(models.FileWatchRenewalAttempt, FileWatchRenewalAttemptAdmin)
