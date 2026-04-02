"""oauth_toolkit_extensions admin"""

from django.contrib import admin
from mitol.oauth_toolkit_extensions.models import ApplicationAccess
from oauth2_provider.admin import ApplicationAdmin
from oauth2_provider.models import get_application_model


class ApplicationAccessInlineAdmin(admin.StackedInline):
    """Admin for ApplicationAccess"""

    model = ApplicationAccess
    extra = 0


class ApplicationWithAccessAdmin(ApplicationAdmin):
    """Admin for Application"""

    inlines = [ApplicationAccessInlineAdmin]


Application = get_application_model()

admin.site.unregister(Application)
admin.site.register(Application, ApplicationWithAccessAdmin)
