"""
The ``docker compose`` backend.

Each step gets a fresh throwaway container with nothing else running in it,
which makes this the cleanest measurement environment of the three. It assumes
the stack is already up: every command uses ``--no-deps`` and nothing here
starts or stops a service for you.

Source is bind-mounted in the normal compose setup, so a ``git switch`` on the
host is visible to the container immediately and there is nothing to wait for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mitol.benchmark.backends import Backend, psql_argv, run_process

if TYPE_CHECKING:  # pragma: no cover
    import subprocess
    from collections.abc import Mapping, Sequence


class ComposeBackend(Backend):
    """Run steps with ``docker compose run`` against an already-up stack."""

    name = "compose"

    @property
    def service(self) -> str:
        """The compose service whose image has the application in it."""
        return self.options.get("service", "web")

    @property
    def db_service(self) -> str:
        """The compose service running Postgres."""
        return self.options.get("db_service", "db")

    @property
    def compose_command(self) -> list[str]:
        """The compose entry point, so ``docker-compose`` still works."""
        configured = self.options.get("compose_command")
        if isinstance(configured, str):
            return configured.split()
        return list(configured) if configured else ["docker", "compose"]

    def describe(self) -> str:
        """Name the service and database about to be used."""
        return (
            f"docker compose: service '{self.service}', database "
            f"'{self.config.database.name}' on service '{self.db_service}'"
        )

    def _env_flags(self, env: Mapping[str, str] | None) -> list[str]:
        flags = []
        for key, value in (env or {}).items():
            flags += ["-e", f"{key}={value}"]
        return flags

    def exec(
        self,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in a fresh container of the application service."""
        command = [
            *self.compose_command,
            "run",
            "--rm",
            "--no-deps",
            # -T: no TTY, so output is captured cleanly and stdin is not a
            # terminal the step might try to interact with.
            "-T",
            *self._env_flags(env),
            self.service,
            *argv,
        ]
        return run_process(command, check=check)

    def admin_sql(self, statements: Sequence[str]) -> None:
        """Run administrative SQL with psql inside the database service."""
        run_process(
            [
                *self.compose_command,
                "exec",
                "-T",
                self.db_service,
                *psql_argv(self.config.database.admin_url, statements),
            ]
        )
