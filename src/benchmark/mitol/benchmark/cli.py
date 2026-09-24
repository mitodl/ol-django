"""
Command line entry point for ``ol-benchmark``.

Usage::

    ol-benchmark init --project
    ol-benchmark init --benchmark library-list
    ol-benchmark validate benchmarks/library-list.toml
    ol-benchmark show benchmarks/library-list.toml
    ol-benchmark run benchmarks/library-list.toml --base-ref main
    ol-benchmark report benchmarks/library-list.toml
    ol-benchmark step seed            # what a backend invokes; reads its
                                      # configuration from the environment

``run`` is the one that produces a result. The ``step`` subcommands exist
because the harness drives the application environment from outside it, and
that environment may be a container with no shared filesystem: a step is
handed its configuration as JSON on the environment and answers with one
prefixed JSON line on stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from mitol.benchmark import __version__, scaffold
from mitol.benchmark import config as config_module
from mitol.benchmark.config import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from mitol.benchmark.config import BenchmarkConfig

DEFAULT_BENCHMARK_DIR = "benchmarks"


def out(message: str = "") -> None:
    """Write a line to stdout."""
    sys.stdout.write(f"{message}\n")


def err(message: str) -> None:
    """Write a line to stderr."""
    sys.stderr.write(f"{message}\n")


def _knob_pairs(values: list[str] | None) -> dict[str, str]:
    knobs = {}
    for entry in values or []:
        name, separator, value = entry.partition("=")
        if not separator:
            msg = f"--knob expects name=value, got {entry!r}"
            raise ConfigError(msg)
        knobs[name.strip()] = value
    return knobs


def load_config(args: argparse.Namespace) -> BenchmarkConfig:
    """Load the three layers named or discovered for this invocation."""
    return config_module.load(
        args.config,
        project_path=args.project_config,
        local_path=args.local_config,
        knob_overrides=_knob_pairs(getattr(args, "knob", None)),
    )


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    """Write a commented scaffold for one configuration layer."""
    directory = Path(args.dir)
    if args.project:
        path = Path(args.path or directory / config_module.PROJECT_CONFIG_NAME)
        content = scaffold.PROJECT_TEMPLATE
    elif args.local:
        path = Path(args.path or directory / config_module.LOCAL_CONFIG_NAME)
        content = scaffold.LOCAL_TEMPLATE
    else:
        name = args.benchmark
        path = Path(args.path or directory / f"{config_module.slugify(name)}.toml")
        content = scaffold.benchmark_template(name)

    if path.exists() and not args.force:
        err(f"{path} already exists; pass --force to overwrite it")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    out(f"wrote {path}")
    if args.local:
        out(
            f"add this to .gitignore — it holds your machine's connection "
            f"strings:\n    {path}"
        )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Parse and merge every layer without touching a database."""
    config = load_config(args)
    out(f"{config.name}: configuration is valid")
    out(f"  database      {config.database.name}")
    out(f"  settings      {config.django.settings_module}")
    out(f"  backend       {config.backend.kind}")
    out(f"  seed steps    {len(config.seed.steps)}")
    out(f"  knobs         {json.dumps(dict(config.knobs))}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Print the merged configuration and where each section came from."""
    config = load_config(args)
    out(json.dumps(config.redacted_dict(), indent=2, default=str))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run both arms and write the comparison."""
    from mitol.benchmark.runner import Runner  # noqa: PLC0415

    config = load_config(args)
    runner = Runner(
        config,
        base_ref=args.base_ref,
        out_dir=args.out_dir,
        skip_seed=args.skip_seed,
    )
    comparison = runner.run()
    out(json.dumps(comparison["metrics"], indent=2))
    # A void comparison is a failure: something differed between the arms and
    # no delta may be quoted from it.
    return 1 if comparison["verdict"] == "void" else 0


def cmd_report(args: argparse.Namespace) -> int:
    """Recompute the comparison from a previous run's JSON."""
    from mitol.benchmark.runner import rebuild_report  # noqa: PLC0415

    config = load_config(args)
    out_dir = args.out_dir or Path(".bench", "out", config.slug)
    comparison = rebuild_report(config, out_dir)
    out(json.dumps(comparison, indent=2, default=str))
    return 1 if comparison["verdict"] == "void" else 0


def cmd_step(args: argparse.Namespace) -> int:
    """Run one in-process step against the scratch database."""
    from mitol.benchmark import steps  # noqa: PLC0415
    from mitol.benchmark.django_env import bootstrap  # noqa: PLC0415

    config = steps.config_from_environment()
    bootstrap(config)
    steps.run(args.step, config, steps.label_from_environment())
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def _add_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("config", help="path to the benchmark's TOML file")
    parser.add_argument(
        "--project-config",
        metavar="PATH",
        help=(
            f"override discovery of {config_module.PROJECT_CONFIG_NAME} "
            f"(searched for at or above the benchmark file)"
        ),
    )
    parser.add_argument(
        "--local-config",
        metavar="PATH",
        help=f"override discovery of {config_module.LOCAL_CONFIG_NAME}",
    )
    parser.add_argument(
        "--knob",
        action="append",
        metavar="NAME=VALUE",
        help="override a shape knob; repeatable",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the ``ol-benchmark`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="ol-benchmark",
        description=(
            "A/B a Django endpoint across two git refs against one "
            "production-shaped scratch database."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    initialize = subparsers.add_parser(
        "init", help="write a commented scaffold for one configuration layer"
    )
    layer = initialize.add_mutually_exclusive_group(required=True)
    layer.add_argument(
        "--project", action="store_true", help="the committed project-wide layer"
    )
    layer.add_argument(
        "--local", action="store_true", help="the uncommitted per-developer layer"
    )
    layer.add_argument("--benchmark", metavar="NAME", help="a new benchmark")
    initialize.add_argument("--path", help="write here instead of the default path")
    initialize.add_argument(
        "--dir",
        default=DEFAULT_BENCHMARK_DIR,
        help=f"directory for the default path (default: {DEFAULT_BENCHMARK_DIR})",
    )
    initialize.add_argument("--force", action="store_true", help="overwrite")
    initialize.set_defaults(handler=cmd_init)

    validate = subparsers.add_parser(
        "validate", help="parse and merge every layer, touching no database"
    )
    _add_config_arguments(validate)
    validate.set_defaults(handler=cmd_validate)

    show = subparsers.add_parser(
        "show", help="print the merged configuration and its provenance"
    )
    _add_config_arguments(show)
    show.set_defaults(handler=cmd_show)

    run = subparsers.add_parser("run", help="run both arms and write the comparison")
    _add_config_arguments(run)
    run.add_argument(
        "--base-ref", default="main", help="the ref to compare against (default: main)"
    )
    run.add_argument("--out-dir", help="where to write results")
    run.add_argument(
        "--skip-seed",
        action="store_true",
        help="reuse the database and seed from the previous run",
    )
    run.set_defaults(handler=cmd_run)

    report = subparsers.add_parser(
        "report", help="recompute the comparison from a previous run's JSON"
    )
    _add_config_arguments(report)
    report.add_argument("--out-dir", help="where the previous run wrote its results")
    report.set_defaults(handler=cmd_report)

    step = subparsers.add_parser(
        "step",
        help="run one in-process step; invoked by 'run', not usually by hand",
    )
    step.add_argument("step", choices=["migrate", "seed", "bench", "trace"])
    step.set_defaults(handler=cmd_step)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch, turning known failures into exit codes."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ConfigError as exc:
        err(f"ol-benchmark: configuration error: {exc}")
        return 2
    except (OSError, RuntimeError, ValueError) as exc:
        err(f"ol-benchmark: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
