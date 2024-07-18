"""Admin for geoip models"""

from django.contrib import admin

from mitol.geoip import models


class NetBlockAdmin(admin.ModelAdmin):
    """Admin for netblock"""

    list_display = ["network", "ip_start", "ip_end", "is_ipv6"]  # noqa: RUF012
    list_filter = ["is_ipv6"]  # noqa: RUF012
    search_fields = ["ip_start", "ip_end", "network"]  # noqa: RUF012


admin.site.register(models.Geoname)
admin.site.register(models.NetBlock, NetBlockAdmin)
