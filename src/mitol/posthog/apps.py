import os
from mitol.common.apps import BaseApp


class Posthog(BaseApp):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mitol.posthog"
    label = "posthog"
    verbose_name = "PostHog"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))
