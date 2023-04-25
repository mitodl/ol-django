"""
Parses deferral request row(s), reverses orders/enrollments, and updates the spreadsheet
to reflect the processed request(s).
"""
from django.core.management import BaseCommand

from mitol.google_sheets_deferrals.api import DeferralRequestHandler


class Command(BaseCommand):
    """
    Parses refund request row(s), reverses orders/enrollments, and updates the spreadsheet
    to reflect the processed request(s).
    """

    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "-r", "--row", type=int, help="Row number in the deferral request Sheet"
        )

    def handle(self, *args, **options):
        deferral_request_handler = DeferralRequestHandler()
        self.stdout.write("Handling refunds and updating spreadsheet...")
        results = deferral_request_handler.process_sheet(
            limit_row_index=options.get("row", None)
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Deferral sheet successfully processed.\n{}".format(results)
            )
        )
