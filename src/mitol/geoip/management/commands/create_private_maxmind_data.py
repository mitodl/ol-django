"""
Creates a set of netblocks for the private IPv4 netblocks, which aren't in the
MaxMind dataset.

The ISO code must match one that we've imported from MaxMind, so if you haven't
imported the geonames data yet, this will not work (since we have to map the
created netblock to a geoname anyway).
"""

import ipaddress
from decimal import Decimal

from django.core.management import BaseCommand, CommandError

from mitol.geoip.models import Geoname, NetBlock


class Command(BaseCommand):
    """
    Creates MaxMind assignments for the private IPv4 netblocks.
    """

    help = "Creates MaxMind assignments for the private IPv4 netblocks."
    MAX_BIGINTEGERFIELD = 9223372036854775807

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "iso",
            type=str,
            help="The ISO 3166 alpha2 code to assign these to.",
        )

        parser.add_argument(
            "--remove",
            action="store_true",
            help="Remove the local address netblocks rather than create them.",
        )

    def handle(self, *args, **kwargs):
        try:
            geoname = Geoname.objects.filter(country_iso_code=kwargs["iso"]).first()
        except Geoname.DoesNotExist:
            raise CommandError(
                f"Could not find a Geoname record for {kwargs['iso']} - have you imported the MaxMind databases?"
            )

        netblocks = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]

        if "remove" in kwargs and kwargs["remove"]:
            removed_count = NetBlock.objects.filter(network__in=netblocks).delete()

            self.stdout.write(
                self.style.SUCCESS(f"{removed_count[0]} netblocks removed!")
            )
        else:
            for netblock in netblocks:
                network = ipaddress.ip_network(netblock)

                (_, created) = NetBlock.objects.update_or_create(
                    network=netblock,
                    defaults={
                        "is_ipv6": False,
                        "decimal_ip_start": Decimal(int(network[0])),
                        "decimal_ip_end": Decimal(int(network[-1])),
                        "ip_start": network[0],
                        "ip_end": network[-1],
                        "geoname_id": geoname.geoname_id,
                    },
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{'Created' if created else 'Updated'} record for {netblock} for ISO {kwargs['iso']}"
                    )
                )
