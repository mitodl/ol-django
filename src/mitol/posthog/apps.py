import os
from mitol.common.apps import BaseApp
from mitol.posthog.features import configure

class Posthog(BaseApp):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mitol.posthog"
    label = "posthog"
    verbose_name = "PostHog"
    configure()

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))
