"""
Execution backends: the one thing that differs between development setups.

Every step of a benchmark has to run *in the application's Django environment*,
reach Postgres with administrative rights, and notice when a ``git switch``
takes effect. Those three are the only things that change between a local
virtualenv, a ``docker compose`` stack and a Kubernetes local-dev cluster, so
they are the whole backend contract and nothing else in the harness knows which
one is in use.

Choosing a backend is a property of a developer's machine, not of the project
or the benchmark, which is why it is configured in the uncommitted
``benchmark.local.toml`` layer.
"""

from __future__ import annotations

import shlex
import subprocess
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping, Sequence

    from mitol.benchmark.config import BenchmarkConfig

DEFAULT_TIMEOUT = 1800


class BackendError(RuntimeError):
    """A backend command failed, or the backend is misconfigured."""


def run_process(
    argv: Sequence[str],
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command, capturing both streams, and raise on a non-zero exit."""
    completed = subprocess.run(  # noqa: S603  # argv is a list built by the harness
        list(argv),
        env=dict(env) if env is not None else None,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and completed.returncode != 0:
        msg = (
            f"command failed ({completed.returncode}): "
            f"{shlex.join(argv)}\n{completed.stderr.strip()}"
        )
        raise BackendError(msg)
    return completed


class Backend(ABC):
    """What the runner needs from an execution environment."""

    name = "abstract"

    def __init__(self, config: BenchmarkConfig):
        """Bind this backend to one benchmark's configuration."""
        self.config = config
        self.options: Mapping[str, Any] = config.backend.options

    @property
    def python_command(self) -> list[str]:
        """The command that starts a Python able to import ``mitol.benchmark``."""
        configured = self.options.get("python")
        if isinstance(configured, str):
            return shlex.split(configured)
        if configured:
            return list(configured)
        return self.default_python_command()

    def default_python_command(self) -> list[str]:
        """Return the interpreter to use when the local config names none."""
        return ["python"]

    def step_command(self, step: str) -> list[str]:
        """Return the argv that runs one in-process harness step."""
        return [*self.python_command, "-m", "mitol.benchmark", "step", step]

    @abstractmethod
    def describe(self) -> str:
        """One line naming exactly what is about to be written to."""

    @abstractmethod
    def exec(
        self,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command inside the application environment."""

    @abstractmethod
    def admin_sql(self, statements: Sequence[str]) -> None:
        """Run administrative SQL against a database that is not the scratch one."""

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """Read a file *as the application environment sees it*."""

    def wait_settled(self) -> None:
        """
        Block until the environment has reacted to a source change.

        Nothing to do where the application reads the working tree directly;
        overridden by backends that push source into a running container.
        """
        return


def get_backend(config: BenchmarkConfig) -> Backend:
    """Instantiate the backend named by ``[backend].kind``."""
    from mitol.benchmark.backends.compose import ComposeBackend  # noqa: PLC0415
    from mitol.benchmark.backends.k8s import KubernetesBackend  # noqa: PLC0415
    from mitol.benchmark.backends.local import LocalBackend  # noqa: PLC0415

    backends = {
        LocalBackend.name: LocalBackend,
        ComposeBackend.name: ComposeBackend,
        KubernetesBackend.name: KubernetesBackend,
    }
    kind = config.backend.kind
    if kind not in backends:
        known = ", ".join(sorted(backends))
        msg = f"unknown [backend].kind {kind!r} (known: {known})"
        raise BackendError(msg)
    return backends[kind](config)
