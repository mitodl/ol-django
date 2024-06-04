"""Generates app.json based on settings configuration"""

import json

from django.core.management.base import BaseCommand

from mitol.common import envs


class Command(BaseCommand):
    """Generates app.json based on settings configuration"""

    help = "Generates app.json based on settings configuration"

    def handle(self, *args, **options):  # noqa: ARG002
        """Generates app.json based on settings configuration"""  # noqa: D401
        config = envs.generate_app_json()

        with open("app.json", "w") as app_json:  # noqa: PTH123
            app_json.write(json.dumps(config, sort_keys=True, indent=2))
        self.stdout.write(self.style.SUCCESS("Updated app.json"))
