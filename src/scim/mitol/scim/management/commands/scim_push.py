"""Sync users with SCIM to the remote"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Sync users with SCIM to the remote"""

    help = "Sync users with SCIM to the remote"

    def handle(self, *args, **options):  # noqa: ARG002
        """Sync users with SCIM to the remote"""
        from mitol.scim import tasks

        task = tasks.sync_all_users_to_scim_remote.delay()

        task.get()

        self.stdout.write(self.style.SUCCESS("Synced users to remote"))
