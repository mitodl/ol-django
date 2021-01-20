from django.contrib import admin
from oauth2_provider.admin import ApplicationAdmin
from oauth2_provider.models import get_application_model

from mitol.oauth_toolkit_extensions.models import ApplicationAccess


class ApplicationAccessInlineAdmin(admin.StackedInline):
    model = ApplicationAccess
    extra = 0


class ApplicationWithAccessAdmin(ApplicationAdmin):
    inlines = [ApplicationAccessInlineAdmin]


Application = get_application_model()

admin.site.unregister(Application)
admin.site.register(Application, ApplicationWithAccessAdmin)
