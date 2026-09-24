"""
The in-process steps, and the protocol by which they report back.

A step runs *inside* the application's Django: it is what actually seeds,
calls the endpoint and captures spans. The harness driving it may be outside a
container with no filesystem in common, so the contract between them is
deliberately narrow:

* the merged configuration arrives as JSON in one environment variable;
* the seed's shape arrives the same way for the steps that need it;
* each step answers with exactly one prefixed JSON line on stdout.

Nothing is written to the source tree. Under a dev server watching it, that
would re-import the application in the middle of a measurement.
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING, Any

from mitol.benchmark import config as config_module

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

    from mitol.benchmark.config import BenchmarkConfig

SEED_PREFIX = "SEED_SHAPE "
BENCH_PREFIX = "BENCH_RESULT "
TRACE_PREFIX = "TRACE_RESULT "
MIGRATE_PREFIX = "MIGRATE_OK "


def emit(prefix: str, payload: Any) -> None:
    """Write one step result to stdout in the harness's line protocol."""
    sys.stdout.write(f"{prefix}{json.dumps(payload, default=str)}\n")
    sys.stdout.flush()


def config_from_environment(
    environ: Mapping[str, str] | None = None,
) -> BenchmarkConfig:
    """Rebuild the merged configuration a step was handed."""
    env = os.environ if environ is None else environ
    raw = env.get(config_module.CONFIG_ENV_VAR)
    if not raw:
        msg = (
            f"{config_module.CONFIG_ENV_VAR} is not set. A step is normally "
            f"invoked by 'ol-benchmark run', which passes the merged "
            f"configuration in that variable."
        )
        raise config_module.ConfigError(msg)
    return config_module.from_dict(json.loads(raw))


def shape_from_environment(
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Return the shape the seed step produced, as handed to this step."""
    env = os.environ if environ is None else environ
    raw = env.get(config_module.IDS_ENV_VAR)
    if not raw:
        msg = (
            f"{config_module.IDS_ENV_VAR} is not set; this step needs the "
            f"shape the seed step produced"
        )
        raise config_module.ConfigError(msg)
    return json.loads(raw)


def label_from_environment(environ: Mapping[str, str] | None = None) -> str:
    """Return the arm label this step is measuring."""
    env = os.environ if environ is None else environ
    return env.get(config_module.LABEL_ENV_VAR, "unknown")


def step_migrate(config: BenchmarkConfig, _label: str = "") -> None:
    """Bring the scratch database up to the current migration state."""
    from django.core.management import call_command  # noqa: PLC0415

    call_command("migrate", no_input=True, verbosity=0)
    emit(MIGRATE_PREFIX, {"database": config.database.name})


def step_seed(config: BenchmarkConfig, _label: str = "") -> None:
    """Build the dataset and report the shape it produced."""
    from mitol.benchmark.seeding import run_seed  # noqa: PLC0415

    emit(SEED_PREFIX, run_seed(config).as_dict())


def step_bench(config: BenchmarkConfig, label: str = "unknown") -> None:
    """Time the endpoint and report the wall-clock result."""
    from mitol.benchmark.measure import run_bench  # noqa: PLC0415

    emit(BENCH_PREFIX, run_bench(config, shape_from_environment(), label))


def step_trace(config: BenchmarkConfig, label: str = "unknown") -> None:
    """Capture traced requests and report the spans with their gaps."""
    from mitol.benchmark.tracing import run_trace  # noqa: PLC0415

    emit(TRACE_PREFIX, run_trace(config, shape_from_environment(), label))


HANDLERS = {
    "migrate": step_migrate,
    "seed": step_seed,
    "bench": step_bench,
    "trace": step_trace,
}


def run(step: str, config: BenchmarkConfig, label: str = "unknown") -> None:
    """Run one named step."""
    if step not in HANDLERS:
        known = ", ".join(sorted(HANDLERS))
        msg = f"unknown step {step!r} (known: {known})"
        raise config_module.ConfigError(msg)
    HANDLERS[step](config, label)
