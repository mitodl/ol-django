"""
The Kubernetes backend, for a local-dev cluster driven by Tilt or similar.

Two things make this different from the other backends, and both exist because
getting them wrong is expensive:

*The context is always explicit, and it is checked.* A developer's current
``kubectl`` context is routinely a deployed environment, and this harness
issues ``DROP DATABASE``. The context is therefore required configuration and
is passed on every command; it is never inherited from whatever ``kubectl
config current-context`` happens to say. On top of that, a context whose name
looks like a deployed cluster is refused outright — being required to name it
does not help if the name you type is ``applications-qa``.

*A source change is asynchronous.* Tilt pushes files into a running pod and may
re-sync dependencies afterwards, so a ``git switch`` on the host is not
immediately true inside the pod. :meth:`wait_settled` gives that a chance to
finish, and the runner separately verifies the switched-to files actually
arrived before it measures anything.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from mitol.benchmark.backends import Backend, BackendError, run_process

if TYPE_CHECKING:  # pragma: no cover
    import subprocess
    from collections.abc import Mapping, Sequence

# Substrings that mark a kubectl context as a deployed cluster rather than a
# local one. Matched case-insensitively against the context name. This is
# defence in depth behind the scratch-database name guard: that one stops the
# wrong *database* being dropped, this one stops the right-looking name being
# dropped in the wrong *cluster*.
DEPLOYED_CONTEXT_MARKERS = ("ci", "qa", "prod", "applications")


class KubernetesBackend(Backend):
    """Run steps with ``kubectl exec`` against a local-dev cluster."""

    name = "k8s"

    def describe(self) -> str:
        """Name the cluster, namespace and database about to be used."""
        return (
            f"kubernetes: context '{self.context}', namespace "
            f"'{self.namespace}', pod matching '{self.selector}', database "
            f"'{self.config.database.name}'"
        )

    @property
    def denylist(self) -> tuple[str, ...]:
        """Substrings that mark a context as a deployed cluster."""
        configured = self.options.get("context_denylist")
        if configured is None:
            return DEPLOYED_CONTEXT_MARKERS
        return tuple(str(marker).lower() for marker in configured)

    @property
    def context(self) -> str:
        """The kubectl context; required, never inherited, never deployed."""
        context = self.options.get("context")
        if not context:
            msg = (
                "[backend].context is required for the k8s backend. This "
                "harness runs DROP DATABASE, so it will not inherit whichever "
                "cluster your kubectl happens to point at."
            )
            raise BackendError(msg)
        context = str(context)
        matched = [marker for marker in self.denylist if marker in context.lower()]
        if matched:
            msg = (
                f"[backend].context = {context!r} contains "
                f"{', '.join(repr(m) for m in matched)}, which marks it as a "
                f"deployed cluster. This harness runs DROP DATABASE and will "
                f"not point it at one. If that name really is a local cluster, "
                f"override the list in your own benchmark.local.toml: "
                f"[backend].context_denylist."
            )
            raise BackendError(msg)
        return context

    @property
    def namespace(self) -> str:
        """The namespace the application runs in."""
        return str(self.options.get("namespace", "default"))

    @property
    def selector(self) -> str:
        """The label selector identifying the application pod."""
        selector = self.options.get("selector")
        if not selector:
            msg = "[backend].selector is required for the k8s backend"
            raise BackendError(msg)
        return str(selector)

    @property
    def container(self) -> str | None:
        """The container within the pod, when the pod has more than one."""
        container = self.options.get("container")
        return str(container) if container else None

    @property
    def settle_seconds(self) -> float:
        """How long to let a push-based sync finish after a source change."""
        return float(self.options.get("settle_seconds", 5))

    def _kubectl(self, *args: str) -> list[str]:
        return [
            "kubectl",
            "--context",
            self.context,
            "--namespace",
            self.namespace,
            *args,
        ]

    def _pod(self, selector: str) -> str:
        completed = run_process(
            self._kubectl(
                "get",
                "pod",
                "--selector",
                selector,
                "--field-selector",
                "status.phase=Running",
                "-o",
                "jsonpath={.items[0].metadata.name}",
            )
        )
        pod = completed.stdout.strip()
        if not pod:
            msg = f"no running pod matches selector {selector!r} in {self.namespace}"
            raise BackendError(msg)
        return pod

    def _exec_argv(self, pod: str, env: Mapping[str, str] | None) -> list[str]:
        argv = self._kubectl("exec", pod)
        if self.container:
            argv += ["-c", self.container]
        argv += ["--", "env"]
        argv += [f"{key}={value}" for key, value in (env or {}).items()]
        return argv

    def exec(
        self,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command in the application pod."""
        pod = self._pod(self.selector)
        return run_process([*self._exec_argv(pod, env), *argv], check=check)

    def admin_sql(self, statements: Sequence[str]) -> None:
        """
        Run administrative SQL from inside the cluster.

        By default that is the application pod, because the scratch database's
        admin URL is usually only routable from within the cluster. A separate
        ``db_selector`` targets a Postgres pod where one is preferred.
        """
        selector = self.options.get("db_selector") or self.selector
        pod = self._pod(str(selector))
        argv = self._kubectl("exec", pod)
        if selector == self.selector and self.container:
            argv += ["-c", self.container]
        argv += [
            "--",
            "psql",
            self.config.database.admin_url,
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
        ]
        for statement in statements:
            argv += ["-c", statement]
        run_process(argv)

    def read_file(self, path: str) -> bytes:
        """Read a file as the application pod sees it."""
        return self.exec(["cat", path]).stdout.encode()

    def wait_settled(self) -> None:
        """Give a push-based file sync time to finish before measuring."""
        time.sleep(self.settle_seconds)
