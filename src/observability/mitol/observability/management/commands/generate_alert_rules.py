"""Management command to generate alert rule YAML files for grafana-alerts."""

import os
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand

from mitol.observability.alerting import get_all_rule_groups
from mitol.observability.alerts.baseline import BaselineAlerts


class Command(BaseCommand):
    """Generate Loki and Cortex/Prometheus alert rule YAML files for grafana-alerts."""

    help = "Generate Loki and Cortex/Prometheus alert rule YAML files"

    def add_arguments(self, parser):
        """Register CLI arguments."""
        parser.add_argument(
            "--format",
            choices=["loki", "cortex", "both"],
            default="both",
        )
        parser.add_argument(
            "--output-dir",
            default=".",
            help="Directory to write output YAML files",
        )
        parser.add_argument(
            "--service",
            help="Override service name (default: OTEL_SERVICE_NAME env var)",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Execute the command — generate YAML alert rule files."""
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        fmt = options["format"]

        # Collect all rules: application-defined + baseline
        all_groups = get_all_rule_groups()
        loki_rules = []
        prometheus_rules = []

        for group in all_groups:
            # Skip BaselineAlerts — handled separately below to avoid double-counting
            if group is BaselineAlerts:
                continue
            loki_rules.extend(group.get_loki_rules())
            prometheus_rules.extend(group.get_prometheus_rules())

        # Always include baseline
        loki_rules.extend(BaselineAlerts.get_loki_rules())
        prometheus_rules.extend(BaselineAlerts.get_prometheus_rules())

        svc = options.get("service") or os.environ.get("OTEL_SERVICE_NAME", "unknown")

        if fmt in ("loki", "both") and loki_rules:
            loki_doc = {
                "namespace": f"{svc}-alerts",
                "groups": [
                    {
                        "name": svc,
                        "interval": "1m",
                        "rules": [r.to_cortex_dict() for r in loki_rules],
                    }
                ],
            }
            out_path = output_dir / f"{svc}-loki.yaml"
            out_path.write_text(
                yaml.dump(loki_doc, default_flow_style=False, sort_keys=False)
            )
            self.stdout.write(f"Written: {out_path}")

        if fmt in ("cortex", "both") and prometheus_rules:
            cortex_doc = {
                "namespace": f"{svc}-alerts",
                "groups": [
                    {
                        "name": svc,
                        "interval": "1m",
                        "rules": [r.to_cortex_dict() for r in prometheus_rules],
                    }
                ],
            }
            out_path = output_dir / f"{svc}-cortex.yaml"
            out_path.write_text(
                yaml.dump(cortex_doc, default_flow_style=False, sort_keys=False)
            )
            self.stdout.write(f"Written: {out_path}")
