"""
A/B orchestration: two git refs, one seeded database.

The shape of this is the whole method. Seed **once**, then switch refs around
the seeded database, because reseeding between arms reintroduces data variance
and stops it being an A/B at all. Verify that each arm really is running the
ref you think, rather than trusting that a ``git switch`` reached the process
doing the work. Keep the destructive step pointed at a database whose name says
it is scratch.

Results travel between the host and the application environment as prefixed
JSON lines on stdout, never through a shared filesystem: a container backend
may not have one in common with the machine driving it.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mitol.benchmark import config as config_module
from mitol.benchmark.aggregate import aggregate
from mitol.benchmark.backends import get_backend, run_process
from mitol.benchmark.report import compare, render_markdown
from mitol.benchmark.steps import (
    BENCH_PREFIX,
    MIGRATE_PREFIX,
    SEED_PREFIX,
    TRACE_PREFIX,
)

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Mapping, Sequence

    from mitol.benchmark.backends import Backend
    from mitol.benchmark.config import BenchmarkConfig

DEFAULT_SYNC_TIMEOUT = 300
_MAX_PROBES = 3


class RunnerError(RuntimeError):
    """The A/B run cannot proceed, or produced something unusable."""


def _log(message: str) -> None:
    sys.stderr.write(f"{message}\n")
    sys.stderr.flush()


def git(*args: str, cwd: str | None = None, check: bool = True) -> str:
    """Run a git command in the repository and return its stdout."""
    return run_process(["git", *args], cwd=cwd, check=check).stdout.strip()


@dataclass
class ArmResult:
    """One arm's measurements."""

    label: str
    ref: str
    bench: dict[str, Any]
    trace: dict[str, Any]


class Runner:
    """Drives one benchmark across two git refs."""

    def __init__(
        self,
        config: BenchmarkConfig,
        base_ref: str = "main",
        out_dir: Path | str | None = None,
        *,
        skip_seed: bool = False,
        log: Callable[[str], None] = _log,
    ):
        """Prepare a run; nothing is executed until :meth:`run` is called."""
        self.config = config
        self.base_ref = base_ref
        self.backend: Backend = get_backend(config)
        self.repo_root = git("rev-parse", "--show-toplevel")
        self.out_dir = Path(
            out_dir or Path(self.repo_root, ".bench", "out", config.slug)
        )
        self.skip_seed = skip_seed
        self.log = log

    # -- environment -----------------------------------------------------

    def step_env(
        self, shape: Mapping[str, Any] | None = None, label: str = ""
    ) -> dict[str, str]:
        """Build the environment a step process needs to rebuild the config."""
        env = {
            config_module.CONFIG_ENV_VAR: json.dumps(self.config.as_dict()),
            "DJANGO_SETTINGS_MODULE": self.config.django.settings_module,
            "DATABASE_URL": self.config.database.url,
            "DEBUG": "False",
            **dict(self.config.django.env),
        }
        if shape is not None:
            env[config_module.IDS_ENV_VAR] = json.dumps(shape)
        if label:
            env[config_module.LABEL_ENV_VAR] = label
        return env

    def run_step(
        self,
        step: str,
        prefix: str,
        shape: Mapping[str, Any] | None = None,
        label: str = "",
    ) -> dict[str, Any]:
        """Run one step in the application environment and parse its payload."""
        completed = self.backend.exec(
            self.backend.step_command(step), self.step_env(shape, label)
        )
        for line in completed.stdout.splitlines():
            if line.startswith(prefix):
                return json.loads(line[len(prefix) :])
        msg = (
            f"step {step!r} produced no {prefix.strip()} line.\n"
            f"stdout:\n{completed.stdout[-2000:]}\n"
            f"stderr:\n{completed.stderr[-2000:]}"
        )
        raise RunnerError(msg)

    # -- guards ----------------------------------------------------------

    def check_working_tree(self) -> None:
        """Refuse to benchmark a dirty tree: the arms would not be two refs."""
        if git("status", "--porcelain", cwd=self.repo_root):
            msg = (
                "the working tree has uncommitted changes; commit or stash "
                "them, or the two arms are not the two refs you think"
            )
            raise RunnerError(msg)

    def check_local_config_untracked(self) -> None:
        """Refuse if the developer-specific layer has been committed."""
        layers = self.config.raw.get("_layers") or {}
        local = layers.get("local")
        if not local:
            return
        tracked = git(
            "ls-files", "--error-unmatch", local, cwd=self.repo_root, check=False
        )
        if tracked:
            msg = (
                f"{local} is tracked by git. It holds one developer's backend "
                f"and connection strings; add it to .gitignore and remove it "
                f"from the index."
            )
            raise RunnerError(msg)

    # -- ref handling ----------------------------------------------------

    @property
    def current_ref(self) -> str:
        """The ref currently checked out, by name where it has one."""
        branch = git("rev-parse", "--abbrev-ref", "HEAD", cwd=self.repo_root)
        return (
            git("rev-parse", "HEAD", cwd=self.repo_root) if branch == "HEAD" else branch
        )

    def short_ref(self) -> str:
        """Return the current commit, abbreviated, for the report."""
        return git("rev-parse", "--short", "HEAD", cwd=self.repo_root)

    def probe_files(self, left: str, right: str) -> list[str]:
        """Pick files the two refs genuinely differ on, to verify a switch."""
        diff = git("diff", "--name-only", left, right, "--", "*.py", cwd=self.repo_root)
        candidates = [name for name in diff.splitlines() if name.strip()]
        return [
            name
            for name in candidates[:_MAX_PROBES]
            if Path(self.repo_root, name).is_file()
        ]

    def sync_ref(self, want: str, probes: Sequence[str]) -> None:
        """
        Block until the application environment is running ``want``.

        Immediate under a bind mount, a real wait under a push-based sync. If
        the two refs differ in no Python file there is nothing to compare, and
        that is said out loud rather than silently passing.
        """
        if not probes:
            self.log(
                f"!! no .py file differs between the refs; cannot verify the "
                f"arm ran {want}"
            )
            return
        deadline = time.monotonic() + float(
            os.environ.get("OL_BENCHMARK_SYNC_TIMEOUT", DEFAULT_SYNC_TIMEOUT)
        )
        for name in probes:
            expected = Path(self.repo_root, name).read_bytes()
            while self.backend.read_file(name).strip() != expected.strip():
                if time.monotonic() >= deadline:
                    msg = (
                        f"timed out waiting for {name} to reach the "
                        f"application environment at {want}"
                    )
                    raise RunnerError(msg)
                time.sleep(2)
        self.backend.wait_settled()

    # -- phases ----------------------------------------------------------

    def recreate_database(self) -> None:
        """Drop and recreate the scratch database."""
        name = self.config.database.name
        self.log(f"==> recreating {name}")
        self.backend.admin_sql(
            [f'DROP DATABASE IF EXISTS "{name}"', f'CREATE DATABASE "{name}"']
        )

    def migrate(self) -> None:
        """Bring the scratch database up to the current migration state."""
        self.log("==> migrating")
        self.run_step("migrate", MIGRATE_PREFIX)

    def seed(self) -> dict[str, Any]:
        """Build the dataset once, for both arms to share."""
        self.log("==> seeding")
        shape = self.run_step("seed", SEED_PREFIX)
        self.log(f"    {json.dumps(shape.get('counts', {}))}")
        for warning in shape.get("warnings", []):
            self.log(f"    !! {warning}")
        return shape

    def run_arm(self, label: str, shape: Mapping[str, Any]) -> ArmResult:
        """Measure one arm: the timed pass, then the traced pass."""
        ref = self.short_ref()
        self.log(f"==> measuring {label} ({ref})")
        bench = self.run_step("bench", BENCH_PREFIX, shape, label)
        bench["ref"] = ref
        self.log(
            f"    min {bench['total_ms_min']} ms, median "
            f"{bench['total_ms_median']} ms, {bench['queries']} queries"
        )
        trace = self.run_step("trace", TRACE_PREFIX, shape, label)
        trace["ref"] = ref
        return ArmResult(label=label, ref=ref, bench=bench, trace=trace)

    # -- outputs ---------------------------------------------------------

    def write(self, name: str, payload: Any) -> Path:
        """Write one output file and return its path."""
        self.out_dir.mkdir(parents=True, exist_ok=True)
        path = self.out_dir / name
        if isinstance(payload, str):
            path.write_text(payload)
        else:
            path.write_text(json.dumps(payload, indent=2, default=str))
        return path

    def write_outputs(
        self, shape: Mapping[str, Any], arms: Mapping[str, ArmResult]
    ) -> dict[str, Any]:
        """Write every artifact and return the comparison payload."""
        self.write("config.resolved.json", self.config.redacted_dict())
        self.write("seed.json", shape)
        traces = {}
        for label, arm in arms.items():
            self.write(f"{label}.json", arm.bench)
            self.write(f"trace-{label}.json", arm.trace)
            self.write(
                f"agg-{label}.json", aggregate(arm.trace, self.config.trace.classify)
            )
            traces[label] = arm.trace
        comparison = compare(
            self.config,
            arms["base"].bench,
            arms["branch"].bench,
            traces=traces,
            shape=shape,
        )
        self.write("comparison.json", comparison)
        self.write("report.md", render_markdown(comparison))
        return comparison

    # -- driving ---------------------------------------------------------

    def run(self) -> dict[str, Any]:
        """Run both arms against one seeded database and report the result."""
        self.check_working_tree()
        self.check_local_config_untracked()
        self.log(f"==> target: {self.backend.describe()}")

        original_ref = self.current_ref
        probes = self.probe_files(self.base_ref, original_ref)

        if self.skip_seed:
            shape = json.loads((self.out_dir / "seed.json").read_text())
            self.log("==> reusing the existing seed")
        else:
            self.recreate_database()
            self.migrate()
            shape = self.seed()

        self.sync_ref(original_ref, probes)
        arms = {"branch": self.run_arm("branch", shape)}
        try:
            self.log(f"==> switching to {self.base_ref}")
            git("checkout", "--quiet", self.base_ref, cwd=self.repo_root)
            self.sync_ref(self.base_ref, probes)
            arms["base"] = self.run_arm("base", shape)
        finally:
            git("checkout", "--quiet", original_ref, cwd=self.repo_root)
            self.log(f"==> back on {original_ref}")

        if arms["base"].ref == arms["branch"].ref:
            self.log(
                "!! both arms ran the same commit; any delta here is "
                "measurement noise, which is exactly what makes this a useful "
                "check of the harness itself"
            )
        comparison = self.write_outputs(shape, arms)
        self.log(f"==> {comparison['verdict']}: {comparison['reason']}")
        self.log(f"==> wrote {self.out_dir}")
        return comparison


def rebuild_report(config: BenchmarkConfig, out_dir: Path | str) -> dict[str, Any]:
    """Recompute the comparison from the JSON a previous run left behind."""
    directory = Path(out_dir)

    def read(name: str) -> dict[str, Any]:
        path = directory / name
        if not path.is_file():
            msg = f"{path}: missing; run the benchmark before reporting on it"
            raise RunnerError(msg)
        return json.loads(path.read_text())

    comparison = compare(
        config,
        read("base.json"),
        read("branch.json"),
        traces={
            "base": read("trace-base.json"),
            "branch": read("trace-branch.json"),
        },
        shape=read("seed.json"),
    )
    (directory / "comparison.json").write_text(
        json.dumps(comparison, indent=2, default=str)
    )
    (directory / "report.md").write_text(render_markdown(comparison))
    return comparison
