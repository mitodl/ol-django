import os

from mitol.common.apps import BaseApp


class OlPosthog(BaseApp):
    default_auto_field = "django.db.models.BigAutoField"
    name = "mitol.olposthog"
    label = "olposthog"
    verbose_name = "OlPosthog"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))
