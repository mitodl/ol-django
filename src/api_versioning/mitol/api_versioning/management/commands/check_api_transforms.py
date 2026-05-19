"""Run the api_versioning system checks with a discoverable name.

Wraps ``./manage.py check --tag api_versioning`` so consuming projects can
add a single, self-explanatory step to CI:

    ./manage.py check_api_transforms

Defaults to ``--fail-level WARNING`` so canonical-path drift (W001) also
fails the command. Pass ``--fail-level ERROR`` to allow warnings.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

_FAIL_LEVELS = ("CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG")


class Command(BaseCommand):
    help = "Validate every registered api_versioning Transform."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-level",
            default="WARNING",
            choices=_FAIL_LEVELS,
            help=("Message level that causes a non-zero exit (default: %(default)s)."),
        )

    def handle(self, *args, **options):  # noqa: ARG002
        call_command(
            "check",
            tags=["api_versioning"],
            fail_level=options["fail_level"],
        )
