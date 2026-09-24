"""
The local backend: steps run as subprocesses of the harness itself.

This is the right backend whenever the application runs in the same
environment you are typing in — a virtualenv, a uv workspace, a devcontainer
shell. A ``git switch`` is visible to it immediately, so there is nothing to
wait for.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess  # the command is an argv list built by the harness
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from mitol.benchmark.backends import Backend, BackendError, run_process

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping, Sequence


class LocalBackend(Backend):
    """Run every step in a subprocess of this machine's own environment."""

    name = "local"

    def default_python_command(self) -> list[str]:
        """
        Return this interpreter.

        The one running the harness already has ``mitol.benchmark``
        importable, which is the only requirement a step has.
        """
        return [sys.executable]

    def describe(self) -> str:
        """Name the database and working directory about to be used."""
        return (
            f"local subprocesses in {self.cwd}, database '{self.config.database.name}'"
        )

    @property
    def cwd(self) -> str:
        """The working directory steps run in."""
        return str(Path(self.config.django.chdir or ".").resolve())

    def exec(
        self,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in a subprocess, inheriting this environment."""
        return run_process(
            argv, env={**os.environ, **(env or {})}, cwd=self.cwd, check=check
        )

    def admin_sql(self, statements: Sequence[str]) -> None:
        """Run administrative SQL, preferring a driver over the psql binary."""
        url = self.config.database.admin_url
        driver = _import_driver()
        if driver is None:
            self._psql(statements)
            return
        connection = driver.connect(url)
        try:
            connection.autocommit = True  # CREATE/DROP DATABASE cannot be in one
            with connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
        finally:
            connection.close()

    def _psql(self, statements: Sequence[str]) -> None:
        argv = ["psql", self.config.database.admin_url, "-v", "ON_ERROR_STOP=1", "-q"]
        for statement in statements:
            argv += ["-c", statement]
        try:
            run_process(argv)
        except FileNotFoundError as exc:
            msg = (
                "no psycopg, psycopg2 or psql available to run administrative "
                "SQL; install one, or use a backend that runs it inside a "
                "container"
            )
            raise BackendError(msg) from exc

    def read_file(self, path: str) -> bytes:
        """Read a file from the working tree."""
        return Path(self.cwd, path).read_bytes()


def _import_driver():
    """Return the first importable Postgres driver, or None."""
    for module_name in ("psycopg", "psycopg2"):
        if importlib.util.find_spec(module_name) is not None:
            return importlib.import_module(module_name)
    return None
