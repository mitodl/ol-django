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

Exit codes are part of the contract, not a nicety: the backends run these
commands as subprocesses and treat any non-zero exit as a failure of the step.
``2`` is a configuration problem, ``1`` is everything else that is known to go
wrong, including a comparison whose two arms disagree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
import cloup
from cloup.constraints import RequireExactly
from mitol.benchmark import __version__, scaffold
from mitol.benchmark import config as config_module
from mitol.benchmark.config import ConfigError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Sequence

    from mitol.benchmark.config import BenchmarkConfig

DEFAULT_BENCHMARK_DIR = "benchmarks"

CONTEXT = cloup.Context.settings(
    help_option_names=["-h", "--help"],
    show_default=True,
)


class ConfigurationError(click.ClickException):
    """A benchmark configuration is wrong, as distinct from a run failing."""

    exit_code = 2

    def format_message(self) -> str:
        """Mark the message as being about configuration, not execution."""
        return f"configuration error: {self.message}"


class BenchmarkCLI(cloup.Group):
    """A group that turns the harness's own exceptions into exit codes."""

    def invoke(self, ctx: click.Context) -> Any:
        """
        Run the subcommand, translating known failures into clean exits.

        Every failure mode the harness raises deliberately becomes one line on
        stderr and a non-zero exit, because a backend only ever sees the exit
        code and the captured output. An unexpected exception is left alone so
        its traceback survives.
        """
        try:
            return super().invoke(ctx)
        except (click.ClickException, click.exceptions.Exit, click.Abort):
            # click's own control flow, including ctx.exit() and --help.
            # Both Exit and Abort subclass RuntimeError, so they have to be
            # let through before the catch-all below sees them.
            raise
        except ConfigError as exc:
            raise ConfigurationError(str(exc)) from exc
        except (OSError, RuntimeError, ValueError) as exc:
            msg = f"{type(exc).__name__}: {exc}"
            raise click.ClickException(msg) from exc


def _knob_pairs(values: Sequence[str]) -> dict[str, str]:
    knobs = {}
    for entry in values:
        name, separator, value = entry.partition("=")
        if not separator:
            msg = f"--knob expects name=value, got {entry!r}"
            raise ConfigError(msg)
        knobs[name.strip()] = value
    return knobs


def load_config(
    config: Path,
    project_config: Path | None,
    local_config: Path | None,
    knob: Sequence[str],
) -> BenchmarkConfig:
    """Load the three layers named or discovered for this invocation."""
    return config_module.load(
        config,
        project_path=project_config,
        local_path=local_config,
        knob_overrides=_knob_pairs(knob),
    )


def config_options(func: Callable) -> Callable:
    """
    Declare the benchmark file and the overrides every reading command takes.

    The path is deliberately not ``exists=True``: a missing file has to reach
    the loader so the failure is the domain one, naming the layer that was
    looked for, rather than a generic usage error.
    """
    return cloup.option_group(
        "Configuration layers",
        cloup.option(
            "--project-config",
            type=click.Path(dir_okay=False, path_type=Path),
            help=(
                f"override discovery of {config_module.PROJECT_CONFIG_NAME} "
                f"(searched for at or above the benchmark file)"
            ),
        ),
        cloup.option(
            "--local-config",
            type=click.Path(dir_okay=False, path_type=Path),
            help=f"override discovery of {config_module.LOCAL_CONFIG_NAME}",
        ),
        cloup.option(
            "--knob",
            multiple=True,
            metavar="NAME=VALUE",
            help="override a shape knob; repeatable",
        ),
    )(
        cloup.argument(
            "config",
            type=click.Path(dir_okay=False, path_type=Path),
        )(func)
    )


@cloup.group(cls=BenchmarkCLI, context_settings=CONTEXT)
@cloup.version_option(__version__, prog_name="ol-benchmark")
def cli() -> None:
    """
    A/B a Django endpoint across two git refs.

    Seeds one production-shaped scratch database, runs the same request on
    both refs against identical rows, and attributes the difference query by
    query.
    """


@cli.command()
@cloup.option_group(
    "Which layer to scaffold",
    cloup.option("--project", is_flag=True, help="the committed project-wide layer"),
    cloup.option("--local", is_flag=True, help="the uncommitted per-developer layer"),
    cloup.option("--benchmark", metavar="NAME", help="a new benchmark"),
    constraint=RequireExactly(1),
)
@cloup.option(
    "--path",
    type=click.Path(dir_okay=False, path_type=Path),
    help="write here instead of the default path",
)
@cloup.option(
    "--dir",
    "directory",
    type=click.Path(file_okay=False, path_type=Path),
    default=DEFAULT_BENCHMARK_DIR,
    help="directory for the default path",
)
@cloup.option("--force", is_flag=True, help="overwrite an existing file")
@click.pass_context
def init(  # noqa: PLR0913
    ctx: click.Context,
    *,
    project: bool,
    local: bool,
    benchmark: str | None,
    path: Path | None,
    directory: Path,
    force: bool,
) -> None:
    """Write a commented scaffold for one configuration layer."""
    if project:
        target = path or directory / config_module.PROJECT_CONFIG_NAME
        content = scaffold.PROJECT_TEMPLATE
    elif local:
        target = path or directory / config_module.LOCAL_CONFIG_NAME
        content = scaffold.LOCAL_TEMPLATE
    else:
        target = path or directory / f"{config_module.slugify(benchmark)}.toml"
        content = scaffold.benchmark_template(benchmark)

    if target.exists() and not force:
        click.echo(f"{target} already exists; pass --force to overwrite it", err=True)
        ctx.exit(1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    click.echo(f"wrote {target}")
    if local:
        click.echo(
            f"add this to .gitignore — it holds your machine's connection "
            f"strings:\n    {target}"
        )


@cli.command()
@config_options
def validate(
    *,
    config: Path,
    project_config: Path | None,
    local_config: Path | None,
    knob: Sequence[str],
) -> None:
    """Parse and merge every layer, touching no database."""
    resolved = load_config(config, project_config, local_config, knob)
    click.echo(f"{resolved.name}: configuration is valid")
    click.echo(f"  database      {resolved.database.name}")
    click.echo(f"  settings      {resolved.django.settings_module}")
    click.echo(f"  backend       {resolved.backend.kind}")
    click.echo(f"  seed steps    {len(resolved.seed.steps)}")
    click.echo(f"  knobs         {json.dumps(dict(resolved.knobs))}")


@cli.command()
@config_options
def show(
    *,
    config: Path,
    project_config: Path | None,
    local_config: Path | None,
    knob: Sequence[str],
) -> None:
    """Print the merged configuration and where each section came from."""
    resolved = load_config(config, project_config, local_config, knob)
    click.echo(json.dumps(resolved.redacted_dict(), indent=2, default=str))


@cli.command()
@config_options
@cloup.option("--base-ref", default="main", help="the ref to compare against")
@cloup.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="where to write results  [default: .bench/out/<benchmark>]",
)
@cloup.option(
    "--skip-seed",
    is_flag=True,
    help="reuse the database and seed from the previous run",
)
@click.pass_context
def run(  # noqa: PLR0913
    ctx: click.Context,
    *,
    config: Path,
    project_config: Path | None,
    local_config: Path | None,
    knob: Sequence[str],
    base_ref: str,
    out_dir: Path | None,
    skip_seed: bool,
) -> None:
    """Run both arms and write the comparison."""
    from mitol.benchmark.runner import Runner  # noqa: PLC0415

    resolved = load_config(config, project_config, local_config, knob)
    comparison = Runner(
        resolved, base_ref=base_ref, out_dir=out_dir, skip_seed=skip_seed
    ).run()
    click.echo(json.dumps(comparison["metrics"], indent=2))
    # A void comparison is a failure: something differed between the arms and
    # no delta may be quoted from it.
    if comparison["verdict"] == "void":
        ctx.exit(1)


@cli.command()
@config_options
@cloup.option(
    "--out-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="where the previous run wrote its results",
)
@click.pass_context
def report(  # noqa: PLR0913
    ctx: click.Context,
    *,
    config: Path,
    project_config: Path | None,
    local_config: Path | None,
    knob: Sequence[str],
    out_dir: Path | None,
) -> None:
    """Recompute the comparison from a previous run's JSON."""
    from mitol.benchmark.runner import rebuild_report  # noqa: PLC0415

    resolved = load_config(config, project_config, local_config, knob)
    directory = out_dir or Path(".bench", "out", resolved.slug)
    comparison = rebuild_report(resolved, directory)
    click.echo(json.dumps(comparison, indent=2, default=str))
    if comparison["verdict"] == "void":
        ctx.exit(1)


@cli.command()
@cloup.argument("step", type=click.Choice(["migrate", "seed", "bench", "trace"]))
def step(*, step: str) -> None:
    """Run one in-process step; invoked by 'run', not usually by hand."""
    from mitol.benchmark import steps  # noqa: PLC0415
    from mitol.benchmark.django_env import bootstrap  # noqa: PLC0415

    config = steps.config_from_environment()
    bootstrap(config)
    steps.run(step, config, steps.label_from_environment())


if __name__ == "__main__":  # pragma: no cover
    cli()
