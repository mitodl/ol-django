"""
Bootstrap Django for a benchmark step, and refuse to measure a rigged process.

Two failure modes make a benchmark worse than no benchmark, and both are
environmental rather than anything the benchmark author does wrong:

*Instrumentation that scales with the thing under test.* An N+1 profiler hooks
every ORM fetch, and coverage traces every line. Both cost more in whichever
arm loads more rows, which inflates the apparent saving of a change that loads
fewer. These are refused outright.

*Debug bookkeeping.* With ``DEBUG`` on, Django records every statement it runs
and that cost grows with statement size. Dev settings modules routinely hardcode
``DEBUG = True``, so refusing would make the harness unusable against the
settings people actually have; it is forced off instead, and the fact that it
was forced is recorded in every result.

Everything this module decides is reported back in a ``preconditions`` block so
the write-up can cite the conditions the number was measured under.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import dj_database_url

if TYPE_CHECKING:  # pragma: no cover
    from mitol.benchmark.config import BenchmarkConfig

# Middleware whose cost scales with the number of objects a request hydrates.
PROFILER_MARKERS = ("zeal", "nplusone", "silk", "debug_toolbar")

# File storage backends that write somewhere other than this machine. Matched
# against the module path of the configured default storage class.
REMOTE_STORAGE_MARKERS = ("s3", "boto", "gcloud", "google", "azure", "dropbox")


class PreconditionError(RuntimeError):
    """The process is not in a state where a measurement would mean anything."""


@dataclass
class Preconditions:
    """What the harness found, and what it changed, before measuring."""

    debug_forced_off: bool = False
    profilers_active: list[str] = field(default_factory=list)
    middleware_stripped: list[str] = field(default_factory=list)
    trace_function: str | None = None
    under_pytest: bool = False
    database: str = ""
    remote_storage: str = ""

    def blockers(self) -> list[str]:
        """Return the reasons this process cannot produce a usable number."""
        reasons = []
        if self.profilers_active:
            reasons.append(
                f"profiler middleware is active ({', '.join(self.profilers_active)}); "
                f"its cost scales with the objects a request hydrates, so it "
                f"inflates whichever arm loads more rows. Strip it with "
                f"[measure].middleware_exclude, or set allow_profilers = true to "
                f"measure anyway and have the result say so."
            )
        if self.trace_function:
            reasons.append(
                f"a trace function is installed ({self.trace_function}); line "
                f"tracing (coverage, a profiler, a debugger) dwarfs the effect "
                f"being measured"
            )
        if self.under_pytest:
            reasons.append(
                "running under pytest; test settings commonly enable profilers "
                "and coverage that scale with the work under test"
            )
        if self.remote_storage:
            reasons.append(
                f"default file storage is remote ({self.remote_storage}); a seed "
                f"that creates image or attachment rows would upload to that "
                f"bucket, and a developer environment usually holds real "
                f"credentials for a real one. Point storage at a local path "
                f"through [django].env, or set allow_remote_storage = true if "
                f"the bucket is genuinely disposable."
            )
        return reasons

    def as_dict(self) -> dict[str, Any]:
        """Return the preconditions as a plain mapping, for the result JSON."""
        return asdict(self)


def parse_database_url(url: str) -> dict[str, Any]:
    """
    Turn a database URL into Django ``DATABASES`` entries.

    ``dj_database_url`` is a declared dependency rather than an optional one:
    every consuming project already carries it, and its edge cases are better
    tested than anything worth writing here.
    """
    return dj_database_url.parse(url)


def _prepare_environment(config: BenchmarkConfig) -> None:
    """Apply chdir, sys.path and the environment the settings module reads."""
    if config.django.chdir:
        os.chdir(config.django.chdir)
    for entry in reversed(config.django.pythonpath):
        resolved = str(Path(entry).resolve())
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
    os.environ["DJANGO_SETTINGS_MODULE"] = config.django.settings_module
    # Set before django.setup(): most settings modules build DATABASES from
    # this, and getting there first avoids a connection to the wrong database
    # if an AppConfig.ready() queries.
    os.environ["DATABASE_URL"] = config.database.url
    for key, value in config.django.env.items():
        os.environ[key] = value


def _point_at_bench_database(config: BenchmarkConfig) -> None:
    """
    Override ``DATABASES['default']`` rather than trusting the settings module.

    A settings module that ignores ``DATABASE_URL`` would otherwise point the
    whole run at a developer's real database — which the next step drops.
    """
    from django.conf import settings  # noqa: PLC0415
    from django.db import connections  # noqa: PLC0415

    settings.DATABASES["default"] = {
        **settings.DATABASES.get("default", {}),
        **parse_database_url(config.database.url),
    }
    # Forget anything opened while the apps were loading, so the next query
    # connects with the settings above. Private access is the only way to drop
    # an already-initialised alias.
    for connection in connections.all(initialized_only=True):
        connection.close()
        delattr(connections._connections, connection.alias)  # noqa: SLF001
    connections.__dict__.pop("settings", None)


def _remote_storage_backend() -> str:
    """
    Return the dotted path of the default file storage if it writes remotely.

    Resolving ``default_storage`` rather than reading a setting covers both the
    ``STORAGES`` dict and the older ``DEFAULT_FILE_STORAGE``, and follows
    whatever a project's own indirection produces. A storage that cannot be
    constructed is not reported as remote: the seed will fail on its own terms,
    with a better message than this one could give.
    """
    try:
        from django.core.files.storage import default_storage  # noqa: PLC0415

        backend = type(default_storage)
        dotted = f"{backend.__module__}.{backend.__name__}"
    except Exception:  # noqa: BLE001 - misconfigured storage is not this check's business
        return ""
    lowered = dotted.lower()
    if any(marker in lowered for marker in REMOTE_STORAGE_MARKERS):
        return dotted
    return ""


def enforce_preconditions(
    config: BenchmarkConfig, *, strict: bool = True
) -> Preconditions:
    """
    Inspect the configured Django process, fix what is safe to fix, and report.

    With ``strict`` set, anything that would make the measurement meaningless
    raises instead of being recorded. The non-strict form is for callers that
    are already running inside someone else's process (a test suite, a
    management command) and only want the state described.
    """
    from django.conf import settings  # noqa: PLC0415

    found = Preconditions(
        trace_function=getattr(sys.gettrace(), "__qualname__", None)
        if sys.gettrace()
        else None,
        under_pytest="pytest" in sys.modules,
        database=settings.DATABASES.get("default", {}).get("NAME", ""),
    )

    if config.measure.middleware_exclude:
        keep, dropped = [], []
        for entry in settings.MIDDLEWARE:
            if any(marker in entry for marker in config.measure.middleware_exclude):
                dropped.append(entry)
            else:
                keep.append(entry)
        settings.MIDDLEWARE = keep
        found.middleware_stripped = dropped

    found.profilers_active = [
        entry
        for entry in settings.MIDDLEWARE
        if any(marker in entry for marker in PROFILER_MARKERS)
    ]
    if config.measure.allow_profilers:
        found.profilers_active = []

    if not config.measure.allow_remote_storage:
        found.remote_storage = _remote_storage_backend()

    if settings.DEBUG:
        settings.DEBUG = False
        found.debug_forced_off = True

    if strict and (reasons := found.blockers()):
        msg = "refusing to measure:\n  - " + "\n  - ".join(reasons)
        raise PreconditionError(msg)
    return found


def bootstrap(config: BenchmarkConfig) -> Preconditions:
    """
    Start Django against the scratch database and enforce the preconditions.

    This is the entry point for every step that runs in-process: it is what
    makes ``ol-benchmark step seed`` and ``ol-benchmark step bench`` run against
    the same Django the application runs, rather than a test harness.
    """
    import django  # noqa: PLC0415

    _prepare_environment(config)
    django.setup()
    _point_at_bench_database(config)
    return enforce_preconditions(config)
