"""Sync users with SCIM to the remote"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Sync users with SCIM to the remote"""

    help = "Sync users with SCIM to the remote"

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--never-synced-only",
            action="store_true",
            default=False,
            help="Only sync users who have never been synced",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Sync users with SCIM to the remote"""
        from mitol.scim import tasks

        never_synced_only = options["never_synced_only"]

        task = tasks.sync_all_users_to_scim_remote.delay(
            never_synced_only=never_synced_only
        )

        task.get()

        self.stdout.write(self.style.SUCCESS("Synced users to remote"))
