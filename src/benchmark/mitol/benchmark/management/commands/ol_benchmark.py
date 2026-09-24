"""
``manage.py ol_benchmark`` — the fallback for a non-standard Django bootstrap.

The console script starts Django itself, which is what lets a step run against
the application's real settings rather than a test harness. Where a project's
bootstrap cannot be reproduced that way — a custom ``manage.py``, an unusual
settings loader — this command gives the same steps an entry point through
Django's own startup instead.

It does *not* re-point the database or re-check the preconditions: Django is
already configured by the time a management command runs. Pass ``--strict`` off
only if you understand what the resulting number does not mean.
"""

from django.core.management.base import BaseCommand, CommandError
from mitol.benchmark import steps


class Command(BaseCommand):
    """Run one in-process benchmark step inside an already-started Django."""

    help = "Run one mitol-django-benchmark step (migrate, seed, bench, trace)"

    def add_arguments(self, parser):
        """Declare the step to run."""
        parser.add_argument("step", choices=["migrate", "seed", "bench", "trace"])

    def handle(self, *args, **options):  # noqa: ARG002
        """Dispatch to the same step handlers the console script uses."""
        try:
            config = steps.config_from_environment()
            steps.run(options["step"], config, steps.label_from_environment())
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
