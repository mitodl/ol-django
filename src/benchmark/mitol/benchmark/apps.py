"""Benchmark app AppConfig"""

import os

from django.apps import AppConfig


class BenchmarkApp(AppConfig):
    """
    Default configuration for the benchmark app.

    Registering the app is optional: the harness normally runs as the
    ``ol-benchmark`` console script, which bootstraps Django itself. Add it to
    ``INSTALLED_APPS`` only if you want the ``ol_benchmark`` management command
    as a fallback for a project whose Django bootstrap the console script
    cannot reproduce.
    """

    name = "mitol.benchmark"
    label = "benchmark"
    verbose_name = "Benchmark"

    # necessary because this is a namespaced app
    path = os.path.dirname(os.path.abspath(__file__))  # noqa: PTH100, PTH120
